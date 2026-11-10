"""Scheduled pipeline step: snapshot the latest Open-Meteo inputs for live forecasting.

Runs every 3 hours in GitHub Actions (.github/workflows/live-data.yml) and is published
to the `live-data` branch. The API reads this snapshot instead of calling Open-Meteo from
shared cloud IPs (which are often rate-limited).

Usage:  python scripts/fetch_live.py OUT_DIR
"""

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from monsoon_sentinel.config import load_config  # noqa: E402
from monsoon_sentinel.data import live  # noqa: E402

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "live-snapshot")
    out.mkdir(parents=True, exist_ok=True)
    hourly = live.fetch(load_config())
    hourly.to_parquet(out / "openmeteo_hourly.parquet", index=False)
    meta = {"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "rows": len(hourly), "source": "Open-Meteo forecast API (best-match NWP)",
            "first": str(hourly.time.min()), "last": str(hourly.time.max())}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta))
