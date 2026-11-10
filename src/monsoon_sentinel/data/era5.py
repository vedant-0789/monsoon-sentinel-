"""ERA5 hourly reanalysis for each study cell via the Open-Meteo archive API.

Downloads are cached per cell and year (May-Oct) so the job can resume after
rate limits. Open-Meteo's free tier is for non-commercial use.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

from monsoon_sentinel.config import Config

API = "https://archive-api.open-meteo.com/v1/archive"


def _cache_file(cfg: Config, lat: float, lon: float, year: int) -> Path:
    d = cfg.path("raw") / "era5"
    d.mkdir(exist_ok=True)
    return d / f"era5_{lat:.2f}_{lon:.2f}_{year}.parquet"


def _fetch(lat: float, lon: float, start: str, end: str, variables: list[str]) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(variables),
        "models": "era5",
        "timezone": "GMT",
    }
    # Free tier allows ~5000 weighted calls/hour; on 429 wait it out (up to ~90 min).
    for attempt in range(90):
        try:
            r = requests.get(API, params=params, timeout=120)
        except requests.RequestException as e:
            print(f"  network error: {e}; retrying in 30s")
            time.sleep(30)
            continue
        if r.status_code == 200:
            js = r.json()
            df = pd.DataFrame(js["hourly"])
            df["time"] = pd.to_datetime(df["time"])
            df["elevation"] = js.get("elevation")
            return df
        if r.status_code == 429 or r.status_code >= 500:
            print(f"  HTTP {r.status_code} (attempt {attempt + 1}); sleeping 60s", flush=True)
            time.sleep(60)
            continue
        r.raise_for_status()
    raise RuntimeError("Open-Meteo request kept failing")


def download(cfg: Config) -> None:
    months = cfg["season_months"]
    for lat, lon in cfg.cells:
        for year in cfg.years:
            f = _cache_file(cfg, lat, lon, year)
            if f.exists():
                continue
            start = f"{year}-{min(months):02d}-01"
            # one extra day so the last issue time has its 24 h look-back
            end = (pd.Timestamp(year, max(months), 1) + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
            df = _fetch(lat, lon, start, end, cfg["era5_hourly_vars"])
            df["lat"], df["lon"] = lat, lon
            df.to_parquet(f, index=False)
            print(f"  era5 {lat} {lon} {year}: {len(df)} rows")
            time.sleep(1.0)


def load_all(cfg: Config) -> pd.DataFrame:
    files = sorted((cfg.path("raw") / "era5").glob("era5_*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
