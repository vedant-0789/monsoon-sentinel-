"""Monsoon Sentinel REST API.

Run:  uvicorn api.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import datetime as dt
import os
import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from monsoon_sentinel.service import Sentinel  # noqa: E402

DB = Path(os.environ.get("MS_DB", ROOT / "data" / "reports.sqlite"))
STATE: dict = {}


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, lat REAL, lon REAL,
        category TEXT, depth TEXT, note TEXT, lang TEXT)""")
    return con


@asynccontextmanager
async def lifespan(app: FastAPI):
    STATE["s"] = Sentinel()
    db().close()
    yield


app = FastAPI(title="Monsoon Sentinel API", version="0.1.0", lifespan=lifespan,
              description="Explainable heavy-rain and street-level waterlogging alerts for Pune.")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("MS_CORS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])

Mode = Literal["live", "replay"]


def _guard(mode: str, date: str | None):
    if mode == "replay" and not date:
        raise HTTPException(400, "replay mode needs ?date=YYYY-MM-DD")


@app.get("/api/health")
def health():
    return {"status": "ok", "time": dt.datetime.now(dt.timezone.utc).isoformat()}


@app.get("/api/bulletin")
def bulletin(mode: Mode = "live", date: str | None = None):
    """City-wide bulletin: headline alert, heavy-rain probability with reasons, streets to watch."""
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
        return STATE["s"].roads_geojson(mode, date, min_alert)
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
    """Ranked response zones (DBSCAN clusters of red/orange streets) with a recommended action."""
    _guard(mode, date)
    try:
        return STATE["s"].actions(mode, date, limit)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/replay-days")
def replay_days():
    return STATE["s"].replay_days()


class Report(BaseModel):
    lat: float = Field(..., ge=18.0, le=19.0)
    lon: float = Field(..., ge=73.0, le=74.5)
    category: Literal["waterlogging", "blocked_drain", "tree_fall", "road_closed", "other"]
    depth: Literal["ankle", "knee", "waist", "unknown"] = "unknown"
    note: str = Field("", max_length=500)
    lang: Literal["en", "mr", "hi"] = "en"


@app.post("/api/reports", status_code=201)
def add_report(r: Report):
    con = db()
    with con:
        cur = con.execute(
            "INSERT INTO reports (created_at, lat, lon, category, depth, note, lang) VALUES (?,?,?,?,?,?,?)",
            (dt.datetime.now(dt.timezone.utc).isoformat(), r.lat, r.lon, r.category, r.depth, r.note, r.lang))
    con.close()
    return {"id": cur.lastrowid, "status": "received"}


@app.get("/api/reports")
def list_reports(hours: int = Query(48, ge=1, le=24 * 30)):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).isoformat()
    con = db()
    rows = con.execute("SELECT id, created_at, lat, lon, category, depth, note, lang FROM reports "
                       "WHERE created_at >= ? ORDER BY created_at DESC LIMIT 500", (since,)).fetchall()
    con.close()
    keys = ["id", "created_at", "lat", "lon", "category", "depth", "note", "lang"]
    return [dict(zip(keys, r)) for r in rows]
