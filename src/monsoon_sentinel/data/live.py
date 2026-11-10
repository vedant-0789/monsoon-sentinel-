"""Live inputs from the Open-Meteo forecast API (latest model analysis + 2-day forecast).

The rain model was trained on IMD gauge rainfall and ERA5. In live mode the same
features are rebuilt from Open-Meteo's best-match NWP analysis:
  * hourly state variables  -> ERA5-equivalent features
  * hourly precipitation    -> IMD-style 08:30-to-08:30 IST daily totals (antecedent rain)
  * next-24 h forecast rain -> shown to users and used to raise alert likelihood
This is a documented approximation: NWP rainfall is smoother than gauge rainfall.
"""

from __future__ import annotations

import pandas as pd
import requests

from monsoon_sentinel.config import Config

API = "https://api.open-meteo.com/v1/forecast"
VARS = ["precipitation", "pressure_msl", "relative_humidity_2m", "dew_point_2m", "cloud_cover",
        "wind_speed_10m", "wind_direction_10m", "total_column_integrated_water_vapour",
        "soil_moisture_0_to_1cm", "soil_moisture_1_to_3cm", "boundary_layer_height"]


def fetch(cfg: Config, past_days: int = 40) -> pd.DataFrame:
    cells = cfg.cells
    params = {
        "latitude": ",".join(str(c[0]) for c in cells),
        "longitude": ",".join(str(c[1]) for c in cells),
        "hourly": ",".join(VARS), "past_days": past_days, "forecast_days": 2, "timezone": "GMT",
    }
    r = requests.get(API, params=params, timeout=25)
    r.raise_for_status()
    js = r.json()
    js = js if isinstance(js, list) else [js]
    frames = []
    for (lat, lon), loc in zip(cells, js):
        h = pd.DataFrame(loc["hourly"])
        h["time"] = pd.to_datetime(h["time"])
        h["soil_moisture_0_to_7cm"] = h[["soil_moisture_0_to_1cm", "soil_moisture_1_to_3cm"]].mean(axis=1)
        h = h.drop(columns=["soil_moisture_0_to_1cm", "soil_moisture_1_to_3cm"])
        h["lat"], h["lon"], h["elevation"] = lat, lon, loc.get("elevation")
        frames.append(h)
    return pd.concat(frames, ignore_index=True)


SNAPSHOT_URL = ("https://raw.githubusercontent.com/vedant-0789/monsoon-sentinel-/live-data/"
                "openmeteo_hourly.parquet")


def load_snapshot(url: str, max_age_hours: float = 7) -> pd.DataFrame | None:
    """Hourly inputs published by the scheduled pipeline, or None if missing / stale."""
    import io
    import json

    try:
        meta = requests.get(url.rsplit("/", 1)[0] + "/meta.json", timeout=8).json()
        age = pd.Timestamp.now(tz="UTC") - pd.Timestamp(meta["fetched_at"])
        if age > pd.Timedelta(hours=max_age_hours):
            return None
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        df = pd.read_parquet(io.BytesIO(r.content))
        df["time"] = pd.to_datetime(df["time"])
        return df
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError):
        return None


def get_hourly(cfg: Config) -> tuple[pd.DataFrame, str]:
    """Prefer the published snapshot; fall back to calling Open-Meteo directly."""
    import os

    url = os.environ.get("MS_LIVE_SNAPSHOT_URL", SNAPSHOT_URL)
    snap = load_snapshot(url) if url else None
    if snap is not None:
        return snap, "snapshot"
    return fetch(cfg), "direct"


NWP_SNAPSHOT_URL = SNAPSHOT_URL.replace("openmeteo_hourly.parquet", "nwp_live.parquet")


def get_nwp_hourly(cfg: Config) -> tuple[pd.DataFrame, str]:
    """5-model hourly forecast: published snapshot if fresh, else a direct request."""
    import os

    from monsoon_sentinel.data import nwp

    url = os.environ.get("MS_NWP_SNAPSHOT_URL", NWP_SNAPSHOT_URL)
    snap = load_snapshot(url, max_age_hours=7) if url else None
    if snap is not None:
        return snap, "snapshot"
    return nwp.fetch_live(cfg), "direct"


def daily_rain_imd_style(hourly: pd.DataFrame, issue_hour: int = 3) -> pd.DataFrame:
    """Sum hourly rain over 03 UTC (D) -> 03 UTC (D+1) windows, labelled D (IMD convention)."""
    h = hourly[["time", "lat", "lon", "precipitation"]].copy()
    # Open-Meteo hourly precipitation at time t is the total for (t-1h, t]. Window D covers
    # (03 UTC D, 03 UTC D+1] -> timestamps 04:00 D ... 03:00 D+1 -> shift by issue_hour + 1.
    h["date"] = (h["time"] - pd.Timedelta(hours=issue_hour + 1)).dt.normalize()
    d = h.groupby(["date", "lat", "lon"], as_index=False)["precipitation"].sum()
    return d.rename(columns={"precipitation": "rain_mm"})
