"""Copy the trained artifacts the API needs into deploy/artifacts/ (committed, ~11 MB).

Run after retraining:  python scripts/export_artifacts.py
The GitHub Action then ships them to the Hugging Face Space.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from monsoon_sentinel.service import Sentinel  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "models/rain_model.joblib",
    "data/processed/rain_features.parquet",
    "data/processed/road_points_light.parquet",
    "data/labels/pune_hotspots.csv",
    "data/processed/facilities.parquet",
    "models/dispatch_qtable.json",
    "models/report_classifier.joblib",
    "models/model_card.json",
    "models/photo_verifier.onnx",
    "models/photo_verifier.json",
    "data/raw/nwp/nwp_hourly_2022.parquet",
    "data/raw/nwp/nwp_hourly_2023.parquet",
    "data/raw/nwp/nwp_hourly_2024.parquet",
]

if __name__ == "__main__":
    Sentinel()  # makes sure road_points_light.parquet exists
    out = ROOT / "deploy" / "artifacts"
    shutil.rmtree(out / "data" / "processed", ignore_errors=True)
    for f in FILES:
        if not (ROOT / f).exists():
            print(f"{f:45s} MISSING - skipped")
            continue
        dst = out / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dst)
        print(f"{f:45s} {dst.stat().st_size / 1e6:6.2f} MB")
