"""Step 7: impact layer - critical facilities and the street that serves each of them.

Downloads hospitals, clinics, schools, colleges, fire and police stations from
OpenStreetMap and links each to its nearest scored road location (<= 250 m).
On any day the API then reports which facilities have their access road on
orange/red alert.

Usage:  python scripts/build_impact.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from monsoon_sentinel.config import load_config  # noqa: E402
from monsoon_sentinel.data import osm  # noqa: E402
from monsoon_sentinel.service import Sentinel, _xy  # noqa: E402

if __name__ == "__main__":
    cfg = load_config()
    fac = osm.load_facilities(osm.download_facilities(cfg))
    roads = Sentinel().roads
    rx, ry = _xy(roads.plat.values, roads.plon.values)
    fx, fy = _xy(fac.lat.values, fac.lon.values)
    idx, dist = [], []
    for a, b in zip(fx, fy):
        d2 = (rx - a) ** 2 + (ry - b) ** 2
        i = int(np.argmin(d2))
        idx.append(i)
        dist.append(float(np.sqrt(d2[i])))
    fac["road_idx"] = idx
    fac["dist_m"] = np.round(dist).astype(int)
    fac = fac[fac.dist_m <= 250].reset_index(drop=True)
    fac["name"] = fac["name"].fillna(fac["kind"].str.replace("_", " ").str.title())
    out = cfg.path("processed") / "facilities.parquet"
    fac.to_parquet(out, index=False)
    print(fac.kind.value_counts().to_string())
    print(f"{len(fac)} facilities linked to a street -> {out}")
    pd.Series(fac.kind.value_counts()).to_csv(cfg.path("reports") / "urban" / "facilities_by_kind.csv")
