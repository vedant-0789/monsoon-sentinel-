"""Short-range rainfall from five operational NWP models (via Open-Meteo).

* Historical: the Historical Forecast API stitches each model's latest short-lead
  forecast into a continuous hourly series (archived from 2022), so we can verify
  short-range forecasts against IMD gauge rainfall.
* Live: the forecast API gives the next 48 h hourly from the same models.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from monsoon_sentinel.config import Config

MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "gem_seamless", "jma_seamless"]
MODEL_NAMES = {"ecmwf_ifs025": "ECMWF", "gfs_seamless": "GFS", "icon_seamless": "ICON",
               "gem_seamless": "GEM", "jma_seamless": "JMA"}
HIST_API = "https://historical-forecast-api.open-meteo.com/v1/forecast"
LIVE_API = "https://api.open-meteo.com/v1/forecast"


def _get(url: str, params: dict, attempts: int = 8, timeout: int = 120) -> list[dict]:
    """Batch jobs retry patiently; interactive callers pass attempts=2 so users never wait minutes."""
    for attempt in range(attempts):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                js = r.json()
                return js if isinstance(js, list) else [js]
            if r.status_code in (429, 500, 502, 503):
                if attempt + 1 < attempts:
                    time.sleep(20 * (attempt + 1) if attempts > 2 else 2)
                continue
            r.raise_for_status()
        except requests.RequestException:
            if attempt + 1 < attempts:
                time.sleep(10 * (attempt + 1) if attempts > 2 else 2)
    raise RuntimeError(f"Open-Meteo request failed: {url}")


def _to_long(cells, payload: list[dict]) -> pd.DataFrame:
    frames = []
    for (lat, lon), loc in zip(cells, payload):
        h = pd.DataFrame(loc["hourly"])
        h["time"] = pd.to_datetime(h["time"])
        h = h.rename(columns={f"precipitation_{m}": m for m in MODELS})
        h["lat"], h["lon"] = lat, lon
        frames.append(h[["time", "lat", "lon"] + [m for m in MODELS if m in h]])
    return pd.concat(frames, ignore_index=True)


def fetch_history(cfg: Config, year: int) -> pd.DataFrame:
    """Hourly precipitation (mm) for every study cell and model, May-Oct of `year` (cached)."""
    d = cfg.path("raw") / "nwp"
    d.mkdir(exist_ok=True)
    f = d / f"nwp_hourly_{year}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    cells = cfg.cells
    params = {"latitude": ",".join(str(c[0]) for c in cells),
              "longitude": ",".join(str(c[1]) for c in cells),
              "start_date": f"{year}-05-25", "end_date": f"{year}-11-01",
              "hourly": "precipitation", "models": ",".join(MODELS), "timezone": "GMT"}
    df = _to_long(cells, _get(HIST_API, params))
    df.to_parquet(f, index=False)
    return df


def fetch_live(cfg: Config, hours: int = 48) -> pd.DataFrame:
    cells = cfg.cells
    params = {"latitude": ",".join(str(c[0]) for c in cells),
              "longitude": ",".join(str(c[1]) for c in cells),
              "hourly": "precipitation", "models": ",".join(MODELS), "timezone": "GMT",
              "past_days": 1, "forecast_days": 3}
    return _to_long(cells, _get(LIVE_API, params, attempts=2, timeout=20))


def daily_features(hourly: pd.DataFrame, issue_hour: int = 3) -> pd.DataFrame:
    """Per cell and IMD day (03->03 UTC): per-model 24 h total and 3 h peak, plus ensemble stats.

    Hourly values are totals for the preceding hour, so the window for day D is
    04:00 D .. 03:00 D+1 (same convention as live.daily_rain_imd_style).
    """
    h = hourly.copy()
    h["date"] = (h["time"] - pd.Timedelta(hours=issue_hour + 1)).dt.normalize()
    models = [m for m in MODELS if m in h]
    h[models] = h[models].apply(pd.to_numeric, errors="coerce").astype(float)  # missing hours -> NaN
    h = h.sort_values(["lat", "lon", "time"])
    roll3 = h.groupby(["lat", "lon"])[models].transform(lambda s: s.rolling(3, min_periods=1).sum())
    roll3.columns = [f"{m}_3h" for m in models]
    h = pd.concat([h, roll3], axis=1)
    g = h.groupby(["lat", "lon", "date"])
    d = pd.concat([g[models].sum(min_count=12),             # >= half the day present, else NaN
                   g[[f"{m}_3h" for m in models]].max()], axis=1).reset_index()
    tot = d[models].to_numpy(dtype=float)
    pk = d[[f"{m}_3h" for m in models]].to_numpy(dtype=float)
    d["nwp_mean"] = np.nanmean(tot, axis=1)
    d["nwp_max"] = np.nanmax(tot, axis=1)
    d["nwp_median"] = np.nanmedian(tot, axis=1)
    d["nwp_std"] = np.nanstd(tot, axis=1)
    valid = ~np.isnan(tot)  # models absent from the archive must not count as "no rain"
    d["nwp_n_models"] = valid.sum(axis=1)
    d["nwp_frac_heavy"] = np.nanmean(np.where(valid, tot >= 64.5, np.nan), axis=1)
    d["nwp_frac_35"] = np.nanmean(np.where(valid, tot >= 35, np.nan), axis=1)
    d["nwp_peak3h_max"] = np.nanmax(pk, axis=1)
    d["nwp_peak3h_mean"] = np.nanmean(pk, axis=1)
    # neighbourhood (3x3 cells) maximum of the ensemble mean: tolerates small position errors
    piv = d.pivot_table(index="date", columns=["lat", "lon"], values="nwp_mean")
    lats = sorted({c[0] for c in piv.columns})
    lons = sorted({c[1] for c in piv.columns})
    nb = {}
    for la in lats:
        for lo in lons:
            cols = [(a, b) for a in lats for b in lons if abs(a - la) <= 0.26 and abs(b - lo) <= 0.26
                    and (a, b) in piv.columns]
            nb[(la, lo)] = piv[cols].max(axis=1)
    nbdf = pd.DataFrame(nb).stack([0, 1], future_stack=True).rename("nwp_neigh_max").reset_index()
    nbdf.columns = ["date", "lat", "lon", "nwp_neigh_max"]
    return d.merge(nbdf, on=["date", "lat", "lon"], how="left")


NWP_FEATURES = ["nwp_mean", "nwp_max", "nwp_median", "nwp_std", "nwp_frac_heavy", "nwp_frac_35",
                "nwp_peak3h_max", "nwp_peak3h_mean", "nwp_neigh_max"]
