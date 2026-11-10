"""Step 4: download DEM + OSM for Pune and derive terrain/drainage layers.

Usage:  python scripts/build_urban_layers.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from monsoon_sentinel.config import load_config  # noqa: E402
from monsoon_sentinel.data import osm, terrain  # noqa: E402

if __name__ == "__main__":
    cfg = load_config()
    print("DEM ...", flush=True)
    tile = terrain.download_dem(cfg)
    dem = terrain.clip_dem(cfg, tile)
    print("Hydrology layers ...", flush=True)
    out = terrain.derive_layers(cfg, dem)
    print("  ->", out)
    print("OpenStreetMap roads & waterways ...", flush=True)
    for k, v in osm.download(cfg).items():
        print(f"  {k}: {v} ({v.stat().st_size / 1e6:.1f} MB)")
    print("Done.")
