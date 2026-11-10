"""IMD 0.25 deg gridded daily rainfall (Pai et al. 2014) for the study cells.

The value for date D is the 24 h accumulation from 08:30 IST on D to 08:30 IST
on D+1 (03 UTC to 03 UTC), observed by IMD's rain-gauge network.
"""

from __future__ import annotations

import time

import imdlib as imd
import pandas as pd

from monsoon_sentinel.config import Config


def download(cfg: Config) -> None:
    raw = cfg.path("raw") / "imd"
    raw.mkdir(exist_ok=True)
    for year in cfg.years:
        f = raw / "rain" / f"{year}.grd"
        days = 366 if pd.Timestamp(year, 12, 31).dayofyear == 366 else 365
        expected = 135 * 129 * days * 4  # float32 grid x days
        if f.exists() and f.stat().st_size == expected:
            continue
        for attempt in range(6):
            try:
                imd.get_data("rain", year, year, fn_format="yearwise", file_dir=str(raw))
                if f.stat().st_size == expected:
                    break
                print(f"  {year}: incomplete file, retrying", flush=True)
            except Exception as e:  # flaky IMD server connections
                print(f"  {year}: {e!r}; retry {attempt + 1}", flush=True)
            time.sleep(10)
        else:
            raise RuntimeError(f"IMD download failed for {year}")


def load_cells(cfg: Config) -> pd.DataFrame:
    """Return long table: date, lat, lon, rain_mm for every study cell."""
    raw = cfg.path("raw") / "imd"
    g = cfg["grid"]
    frames = []
    for year in cfg.years:
        ds = imd.open_data("rain", year, year, "yearwise", str(raw)).get_xarray()
        sub = ds.rain.sel(lat=g["lats"], lon=g["lons"])
        df = sub.to_dataframe().reset_index().rename(columns={"time": "date", "rain": "rain_mm"})
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out.loc[out["rain_mm"] < 0, "rain_mm"] = float("nan")  # IMD missing flag (-999)
    return out.sort_values(["lat", "lon", "date"]).reset_index(drop=True)
