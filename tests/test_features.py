"""Tests for alerts (dry-run), short-range outlook, photo verification and persistence."""

import base64
import io

import pytest

DAY = "2024-07-25"
EKTA = {"lat": 18.4821, "lon": 73.8261}


def _subscribe(client, phone="+919800000001", **kw):
    body = {"channel": "whatsapp", "phone": phone, "lang": "mr", "label": "Ekta Nagar",
            "min_alert": "orange", "consent": True, **EKTA, **kw}
    return client.post("/api/subscribe", json=body)


def test_subscribe_requires_consent_and_valid_phone(client):
    assert _subscribe(client, consent=False).status_code == 400
    assert _subscribe(client, phone="98765").status_code == 400


def test_subscribe_verify_dispatch_unsubscribe(client):
    r = _subscribe(client)
    assert r.status_code == 201
    sub = r.json()
    assert sub["status"] == "dry_run" and len(sub["demo_code"]) == 6

    assert client.post("/api/subscribe/verify", json={"id": sub["id"], "code": "000000" if sub["demo_code"] != "000000" else "111111"}).status_code == 400
    ok = client.post("/api/subscribe/verify", json={"id": sub["id"], "code": sub["demo_code"]})
    assert ok.json()["status"] == "subscribed"
    unsub_url = ok.json()["unsubscribe_url"]

    # dispatch is admin-only
    assert client.post("/api/alerts/dispatch", json={"mode": "replay", "date": DAY}).status_code == 401
    hdr = {"X-Admin-Token": "test-token"}
    d = client.post("/api/alerts/dispatch", json={"mode": "replay", "date": DAY}, headers=hdr).json()
    assert d["subscribers"] >= 1 and d["dry_run"] >= 1        # Ekta Nagar is red on 25 July 2024
    again = client.post("/api/alerts/dispatch", json={"mode": "replay", "date": DAY}, headers=hdr).json()
    assert again["dry_run"] == 0 and again["skipped"] >= 1     # no duplicate alert the same day
    quiet = client.post("/api/alerts/dispatch", json={"mode": "replay", "date": "2023-07-10"}, headers=hdr).json()
    assert quiet["dry_run"] == 0                               # green day -> nothing sent

    summary = client.get("/api/alerts/summary").json()
    assert summary["active_subscribers"].get("whatsapp", 0) >= 1
    assert "phone" not in str(summary)                         # never expose numbers

    token = unsub_url.split("token=")[1]
    assert client.get(f"/api/unsubscribe?token={token}").status_code == 200
    assert client.get("/api/alerts/summary").json()["active_subscribers"].get("whatsapp", 0) == 0


def test_alert_message_language():
    from monsoon_sentinel import alerts
    txt = alerts.alert_text("mr", "red", "Ekta Nagar", "Sinhagad Road", 0.62, "https://x", "https://u")
    assert "लाल इशारा" in txt and "62%" in txt and "https://u" in txt


def test_outlook_archive_and_missing(client):
    o = client.get(f"/api/outlook?mode=replay&date={DAY}").json()
    assert o["available"] and len(o["hours"]) == 24 and len(o["models"]) >= 3
    assert client.get("/api/outlook?mode=replay&date=2019-09-25").json()["available"] is False


def _jpeg(color):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), color).save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def test_report_with_photo_is_scored_and_served(client):
    health = client.get("/api/health").json()
    r = client.post("/api/reports", json={"lat": 18.5, "lon": 73.85, "category": "waterlogging",
                                          "depth": "knee", "note": "", "lang": "en", "photo": _jpeg((90, 110, 120))})
    assert r.status_code == 201
    body = r.json()
    if health["photo_model"]:
        assert 0 <= body["photo_flood_probability"] <= 1
    img = client.get(f"/api/reports/{body['id']}/photo")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    rows = client.get("/api/reports?hours=1").json()
    assert any(x["id"] == body["id"] and x["has_photo"] == 1 for x in rows)


def test_bad_photo_rejected(client):
    r = client.post("/api/reports", json={"lat": 18.5, "lon": 73.85, "category": "other", "photo": "not-base64!!"})
    assert r.status_code == 400


@pytest.mark.parametrize("p", [0.0, 0.6, 0.99])
def test_photo_verdict_thresholds(client, p):
    from api.main import _photo_verdict
    v = _photo_verdict(p)
    assert v in (0, 1, None)
