"""Monsoon Sentinel REST API.

Run:  uvicorn api.main:app --reload --port 8077
Docs: http://localhost:8077/docs

Environment
  DATABASE_URL        Postgres URL (e.g. Neon). Without it a local SQLite file is used.
  MS_ADMIN_TOKEN      secret required by the alert-dispatch endpoint
  MS_WEB_URL          public web app URL used in alert links
  MS_API_URL          public API URL used in unsubscribe links
  MS_ALERTS_DRY_RUN   "1" = log alerts instead of sending
  Provider keys       see monsoon_sentinel/alerts.py
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import os
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from monsoon_sentinel import alerts  # noqa: E402
from monsoon_sentinel.db import DB, new_token  # noqa: E402
from monsoon_sentinel.photo import PhotoVerifier, downscale_jpeg  # noqa: E402
from monsoon_sentinel.service import Sentinel  # noqa: E402

STATE: dict = {}
WEB_URL = os.environ.get("MS_WEB_URL", "https://monsoon-sentinel-zeta.vercel.app").rstrip("/")
API_URL = os.environ.get("MS_API_URL", "https://monsoon-sentinel-api.onrender.com").rstrip("/")
MAX_PHOTO_BYTES = 4_000_000


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    STATE["s"] = Sentinel()
    STATE["db"] = DB()
    STATE["photo"] = PhotoVerifier(ROOT / "models" / "photo_verifier.onnx")
    yield


app = FastAPI(title="Monsoon Sentinel API", version="1.0.0", lifespan=lifespan,
              description="Explainable heavy-rain and street-level waterlogging alerts for Pune.")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("MS_CORS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])

Mode = Literal["live", "replay"]
AlertLevel = Literal["yellow", "orange", "red"]


def _guard(mode: str, date: str | None):
    if mode == "replay" and not date:
        raise HTTPException(400, "replay mode needs ?date=YYYY-MM-DD")


@app.exception_handler(Exception)
async def upstream_error(request: Request, exc: Exception):
    """Live mode depends on Open-Meteo; report upstream failures clearly instead of a bare 500."""
    live = request.query_params.get("mode", "live") == "live"
    msg = f"{type(exc).__name__}: {str(exc)[:300]}"
    if live and request.url.path in ("/api/bulletin", "/api/roads", "/api/point", "/api/actions", "/api/history"):
        return JSONResponse({"detail": f"Live weather data is unavailable right now ({msg}). "
                                       "Try again shortly, or use Replay."}, status_code=503)
    return JSONResponse({"detail": msg}, status_code=500)


# ------------------------------------------------------------------ forecast
@app.get("/api/health")
def health():
    return {"status": "ok", "time": now_iso(), "database": STATE["db"].kind,
            "photo_model": STATE["photo"].available}


@app.get("/api/bulletin")
def bulletin(mode: Mode = "live", date: str | None = None):
    """City-wide bulletin: headline alert, heavy-rain probability with reasons, impact, streets to watch."""
    _guard(mode, date)
    try:
        return STATE["s"].bulletin(mode, date)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/roads")
def roads(mode: Mode = "live", date: str | None = None,
          min_alert: Literal["green", "yellow", "orange", "red"] = "green"):
    """GeoJSON points (~every 150 m of road) with alert colour a, susceptibility s, road name n."""
    _guard(mode, date)
    try:
        return Response(STATE["s"].roads_geojson(mode, date, min_alert), media_type="application/json")
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/point")
def point(lat: float = Query(..., ge=18.0, le=19.0), lon: float = Query(..., ge=73.0, le=74.5),
          mode: Mode = "live", date: str | None = None):
    """Alert and advice for the road nearest to a location (e.g. the user's GPS position)."""
    _guard(mode, date)
    return STATE["s"].point(lat, lon, mode, date)


@app.get("/api/actions")
def actions(mode: Mode = "live", date: str | None = None, limit: int = Query(10, ge=1, le=30)):
    """Ranked response zones with the Q-learning pump plan and nearest fire-station depot."""
    _guard(mode, date)
    try:
        return STATE["s"].actions(mode, date, limit)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/history")
def history(mode: Mode = "live", date: str | None = None, days: int = Query(14, ge=3, le=30)):
    _guard(mode, date)
    return STATE["s"].history(mode, date, days)


@app.get("/api/outlook")
def outlook(mode: Mode = "live", date: str | None = None):
    """Hour-by-hour rain for the next 24 h over the city from 5 NWP models, with an intense-rain watch."""
    _guard(mode, date)
    return STATE["s"].outlook(mode, date)


@app.get("/api/model-card")
def model_card():
    return STATE["s"].model_card()


@app.get("/api/replay-days")
def replay_days():
    return STATE["s"].replay_days()


# --------------------------------------------------------- citizen reports
class ClassifyIn(BaseModel):
    text: str = Field(..., max_length=500)


@app.post("/api/classify")
def classify(body: ClassifyIn):
    """Naive Bayes suggestion of report category and urgency from free text (EN / MR / HI / Hinglish)."""
    return STATE["s"].classify_report(body.text) or {}


class Report(BaseModel):
    lat: float = Field(..., ge=18.0, le=19.0)
    lon: float = Field(..., ge=73.0, le=74.5)
    category: Literal["waterlogging", "blocked_drain", "tree_fall", "road_closed", "other"]
    depth: Literal["ankle", "knee", "waist", "unknown"] = "unknown"
    note: str = Field("", max_length=500)
    lang: Literal["en", "mr", "hi"] = "en"
    photo: str | None = Field(None, description="JPEG/PNG as base64 or data URL (<= 4 MB)")


def _decode_photo(s: str) -> bytes:
    if s.startswith("data:") and "," in s[:100]:
        s = s.split(",", 1)[1]
    try:
        raw = base64.b64decode(s, validate=True)
    except Exception:
        raise HTTPException(400, "photo must be base64")
    if len(raw) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "photo too large (max 4 MB)")
    return raw


def _photo_verdict(prob: float | None) -> int | None:
    if prob is None:
        return None
    t = STATE["s"].photo_thresholds()
    return 1 if prob >= t["threshold_verified"] else (0 if prob < t["threshold_possible"] else None)


@app.post("/api/reports", status_code=201)
def add_report(r: Report):
    s = STATE["s"]
    auto = s.classify_report(r.note) if r.note else None
    urgent = bool(auto and auto["urgent"]) or r.depth == "waist"
    photo, prob = None, None
    if r.photo:
        raw = _decode_photo(r.photo)
        try:
            photo = downscale_jpeg(raw)
        except Exception:
            raise HTTPException(400, "photo could not be read as an image")
        if STATE["photo"].available:
            prob = round(STATE["photo"].score(photo), 3)
    verdict = _photo_verdict(prob)
    rid = STATE["db"].execute(
        "INSERT INTO reports (created_at, lat, lon, category, depth, note, lang, auto_category, urgent, "
        "photo, photo_flood_prob, photo_verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (now_iso(), r.lat, r.lon, r.category, r.depth, r.note, r.lang, auto["category"] if auto else None,
         int(urgent), photo, prob, verdict))
    return {"id": rid, "status": "received", "urgent": urgent, "auto": auto,
            "photo_flood_probability": prob,
            "photo_verdict": None if photo is None else
            {1: "flooding confirmed", 0: "no flooding visible", None: "uncertain"}[verdict]}


@app.get("/api/reports")
def list_reports(hours: int = Query(48, ge=1, le=24 * 30)):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).isoformat()
    return STATE["db"].query(
        "SELECT id, created_at, lat, lon, category, depth, note, lang, auto_category, urgent, "
        "photo_flood_prob, photo_verified, CASE WHEN photo IS NULL THEN 0 ELSE 1 END AS has_photo "
        "FROM reports WHERE created_at >= ? ORDER BY urgent DESC, created_at DESC LIMIT 500", (since,))


@app.get("/api/reports/{rid}/photo")
def report_photo(rid: int):
    rows = STATE["db"].query("SELECT photo FROM reports WHERE id = ?", (rid,))
    if not rows or rows[0]["photo"] is None:
        raise HTTPException(404, "no photo")
    return Response(bytes(rows[0]["photo"]), media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


class PhotoIn(BaseModel):
    photo: str


@app.post("/api/verify-photo")
def verify_photo(body: PhotoIn):
    """Score a photo without saving it (the browser also does this on-device)."""
    if not STATE["photo"].available:
        raise HTTPException(503, "photo model not available")
    prob = STATE["photo"].score(downscale_jpeg(_decode_photo(body.photo)))
    return {"photo_flood_probability": round(prob, 3), **STATE["s"].photo_thresholds()}


# ------------------------------------------------------------------ alerts
def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class SubscribeIn(BaseModel):
    channel: Literal["sms", "whatsapp"]
    phone: str = Field(..., max_length=20, description="E.164, e.g. +9198XXXXXXXX")
    lang: Literal["en", "mr", "hi"] = "en"
    lat: float = Field(..., ge=18.0, le=19.0)
    lon: float = Field(..., ge=73.0, le=74.5)
    label: str = Field("My street", max_length=60)
    min_alert: AlertLevel = "orange"
    consent: bool


@app.post("/api/subscribe", status_code=201)
def subscribe(body: SubscribeIn):
    """Start an alert subscription: a 6-digit code is sent to the phone to prove ownership."""
    if not body.consent:
        raise HTTPException(400, "consent is required")
    phone = body.phone.replace(" ", "").replace("-", "")
    if not alerts.PHONE_RE.match(phone):
        raise HTTPException(400, "phone must be in international format, e.g. +9198XXXXXXXX")
    db = STATE["db"]
    hour_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
    recent = db.query("SELECT COUNT(*) AS n FROM subscribers WHERE phone = ? AND created_at >= ?", (phone, hour_ago))
    if recent[0]["n"] >= 3:
        raise HTTPException(429, "too many attempts for this number; try again in an hour")
    code = f"{secrets.randbelow(10**6):06d}"
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)).isoformat()
    sid = db.execute(
        "INSERT INTO subscribers (created_at, channel, phone, lang, lat, lon, label, min_alert, active, token, "
        "verified, code_hash, code_expires, attempts) VALUES (?,?,?,?,?,?,?,?,0,?,0,?,?,0)",
        (now_iso(), body.channel, phone, body.lang, body.lat, body.lon, body.label, body.min_alert,
         new_token(), _hash(code), expires))
    # template variables fit Twilio's pre-approved "Your {{1}} code is {{2}}" verification template
    res = alerts.send(body.channel, phone, alerts.code_text(body.lang, code),
                      template_params=["Monsoon Sentinel", code], kind="code")
    if res.status == "failed":
        raise HTTPException(502, f"could not send the code ({res.provider}): {res.detail}")
    out = {"id": sid, "status": "code_sent" if res.status == "sent" else res.status, "channel": body.channel}
    if res.status == "dry_run":  # demo / testing without a provider: show the code on screen
        out["demo_code"] = code
    return out


class VerifyIn(BaseModel):
    id: int
    code: str = Field(..., min_length=6, max_length=6)


@app.post("/api/subscribe/verify")
def verify(body: VerifyIn):
    db = STATE["db"]
    rows = db.query("SELECT * FROM subscribers WHERE id = ?", (body.id,))
    if not rows:
        raise HTTPException(404, "subscription not found")
    sub = rows[0]
    if sub["verified"]:
        return {"status": "already_verified"}
    if (sub["attempts"] or 0) >= 5 or (sub["code_expires"] or "") < now_iso():
        raise HTTPException(410, "code expired; please subscribe again")
    if not hmac.compare_digest(sub["code_hash"] or "", _hash(body.code)):
        db.execute("UPDATE subscribers SET attempts = attempts + 1 WHERE id = ?", (body.id,))
        raise HTTPException(400, "wrong code")
    db.execute("UPDATE subscribers SET verified = 1, active = 1, code_hash = NULL WHERE id = ?", (body.id,))
    db.execute("UPDATE subscribers SET active = 0 WHERE phone = ? AND id <> ? AND label = ?",
               (sub["phone"], body.id, sub["label"]))  # one active subscription per phone + place
    w = alerts.WORDS.get(sub["lang"], alerts.WORDS["en"])
    unsub = f"{API_URL}/api/unsubscribe?token={sub['token']}"
    alerts.send(sub["channel"], sub["phone"], f"{w['welcome']} {sub['label']}. {w['stop']}: {unsub}")
    return {"status": "subscribed", "unsubscribe_url": unsub}


@app.get("/api/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str = Query(..., min_length=10, max_length=64)):
    STATE["db"].execute("UPDATE subscribers SET active = 0 WHERE token = ?", (token,))
    return HTMLResponse(
        "<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Unsubscribed</title><body style='font-family:system-ui;max-width:28rem;margin:4rem auto;padding:0 1rem'>"
        "<h1>You're unsubscribed</h1><p>You will no longer receive Monsoon Sentinel alerts for this location.</p>"
        "<p>तुम्हाला यापुढे इशारे मिळणार नाहीत. · अब आपको अलर्ट नहीं मिलेंगे।</p>"
        f"<p><a href='{WEB_URL}'>Back to Monsoon Sentinel</a></p></body>")


@app.get("/api/alerts/summary")
def alerts_summary():
    """Anonymous counts for the control room (never phone numbers)."""
    db = STATE["db"]
    n = db.query("SELECT channel, COUNT(*) AS n FROM subscribers WHERE active = 1 GROUP BY channel")
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    sent = db.query("SELECT status, COUNT(*) AS n FROM alert_log WHERE created_at >= ? GROUP BY status", (today,))
    cfg = alerts.configured()
    return {"active_subscribers": {r["channel"]: r["n"] for r in n},
            "sent_today": {r["status"]: r["n"] for r in sent},
            "providers": {k: v for k, v in cfg.items() if k != "dry_run"}, "dry_run": cfg["dry_run"]}


class DispatchIn(BaseModel):
    mode: Mode = "live"
    date: str | None = None


@app.post("/api/alerts/dispatch")
def dispatch_alerts(body: DispatchIn, x_admin_token: str = Header("")):
    """Send today's alerts to verified subscribers whose street reaches their chosen level.
    Called by the scheduled GitHub Action each morning (requires X-Admin-Token)."""
    expected = os.environ.get("MS_ADMIN_TOKEN", "")
    if not expected or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "admin token required")
    _guard(body.mode, body.date)
    s, db = STATE["s"], STATE["db"]
    day = s.bulletin(body.mode, body.date)["date"]
    subs = db.query("SELECT * FROM subscribers WHERE active = 1 AND verified = 1")
    summary = {"date": day, "subscribers": len(subs), "sent": 0, "dry_run": 0, "failed": 0, "skipped": 0}
    for sub in subs:
        pt = s.point(sub["lat"], sub["lon"], body.mode, body.date)
        rank = alerts.ALERT_RANK[pt["alert"]]
        if rank < alerts.ALERT_RANK[sub["min_alert"]]:
            summary["skipped"] += 1
            continue
        prev = db.query("SELECT alert FROM alert_log WHERE subscriber_id = ? AND alert_date = ? "
                        "AND status IN ('sent', 'dry_run')", (sub["id"], day))
        if prev and max(alerts.ALERT_RANK[p["alert"]] for p in prev) >= rank:
            summary["skipped"] += 1
            continue
        link = f"{WEB_URL}/?lat={sub['lat']:.5f}&lon={sub['lon']:.5f}" + (f"&date={day}" if body.mode == "replay" else "")
        unsub = f"{API_URL}/api/unsubscribe?token={sub['token']}"
        text = alerts.alert_text(sub["lang"], pt["alert"], sub["label"], pt["nearest_road"],
                                 pt["heavy_rain_probability"] or 0, link, unsub)
        fields = {"title": alerts.TITLES[sub["lang"]][pt["alert"]], "place": sub["label"],
                  "road": pt["nearest_road"], "chance": f"{round((pt['heavy_rain_probability'] or 0) * 100)}%",
                  "date": day, "link": link, "advice": alerts.ADVICE[sub["lang"]][pt["alert"]]}
        order = [f.strip() for f in os.environ.get("MS_ALERT_TEMPLATE_VARS", "title,place,link").split(",") if f.strip()]
        res = alerts.send(sub["channel"], sub["phone"], text,
                          template_params=[fields.get(f, f) for f in order], kind="alert")
        db.execute("INSERT INTO alert_log (created_at, subscriber_id, alert_date, alert, channel, status, "
                   "provider_id, detail) VALUES (?,?,?,?,?,?,?,?)",
                   (now_iso(), sub["id"], day, pt["alert"], sub["channel"], res.status, res.provider_id, res.detail))
        summary[res.status if res.status in summary else "failed"] += 1
    return summary
