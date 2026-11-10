"""Step 1: download IMD gridded rainfall and ERA5 hourly reanalysis for Pune.

Usage:  python scripts/download_data.py
Re-running is safe: finished files are skipped.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from monsoon_sentinel.config import load_config  # noqa: E402
from monsoon_sentinel.data import era5, imd  # noqa: E402

if __name__ == "__main__":
    cfg = load_config()
    print("Downloading IMD gridded rainfall ...", flush=True)
    imd.download(cfg)
    print("Downloading ERA5 hourly (Open-Meteo) ...", flush=True)
    era5.download(cfg)
    print("Done.")
