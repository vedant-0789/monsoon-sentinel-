"""Geocode the curated Pune hotspot catalogue with OpenStreetMap Nominatim.

Respects the Nominatim usage policy (1 request / second, identifying User-Agent).
Results outside the Pune study box are flagged for manual review.

Usage:  python scripts/geocode_hotspots.py
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "labels" / "pune_hotspots_raw.csv"
OUT = ROOT / "data" / "labels" / "pune_hotspots.csv"
BBOX = dict(lat_min=18.40, lat_max=18.66, lon_min=73.70, lon_max=74.05)
UA = {"User-Agent": "monsoon-sentinel/0.1 (academic flood-risk research)"}


def geocode(q: str):
    for attempt in range(5):
        try:
            return _geocode(q)
        except requests.RequestException as e:
            print(f"  retry {attempt + 1} for {q!r}: {e}", flush=True)
            time.sleep(5 * (attempt + 1))
    return None


def _geocode(q: str):
    r = requests.get("https://nominatim.openstreetmap.org/search",
                     params={"q": q, "format": "jsonv2", "limit": 1, "countrycodes": "in",
                             "viewbox": f"{BBOX['lon_min']},{BBOX['lat_max']},{BBOX['lon_max']},{BBOX['lat_min']}",
                             "bounded": 1},
                     headers=UA, timeout=30)
    r.raise_for_status()
    js = r.json()
    if not js:
        return None
    return float(js[0]["lat"]), float(js[0]["lon"]), js[0].get("display_name", "")


def main():
    df = pd.read_csv(RAW)
    old = pd.read_csv(OUT) if OUT.exists() else None
    rows = []
    for _, row in df.iterrows():
        cached = None
        if old is not None and "manual_lat" in old:
            m = old[old.name == row["name"]]
            if len(m) and pd.notna(m.iloc[0].get("manual_lat")):
                cached = m.iloc[0]
        res = geocode(row["geocode_query"])
        time.sleep(1.1)
        if res is None:  # fall back to a shorter query (drop the qualifier before the first comma)
            parts = row["geocode_query"].split(",")
            if len(parts) > 2:
                res = geocode(",".join(parts[1:]).strip())
                time.sleep(1.1)
        lat, lon, disp = res if res else (None, None, "")
        out = {**row.to_dict(), "lat": lat, "lon": lon, "osm_match": disp,
               "status": "ok" if res else "not_found"}
        if cached is not None:
            out.update(manual_lat=cached.manual_lat, manual_lon=cached.manual_lon)
        rows.append(out)
        print(f"{row['name'][:40]:40s} -> {lat}, {lon}  {disp[:70]}", flush=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\nSaved {OUT}  (found {sum(r['status'] == 'ok' for r in rows)}/{len(rows)})")


if __name__ == "__main__":
    sys.exit(main())
