"""Shared fixtures. The API tests run on the same committed artifacts the server ships
(deploy/artifacts), copied into place exactly as the Dockerfile does."""

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _ensure_artifacts():
    art = ROOT / "deploy" / "artifacts"
    for sub in ["models", "data/processed", "data/labels", "data/raw/nwp"]:
        src, dst = art / sub, ROOT / sub
        if not src.exists():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.iterdir():
            if not (dst / f.name).exists():
                shutil.copy2(f, dst / f.name)


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    _ensure_artifacts()
    os.environ["MS_DB"] = str(tmp_path_factory.mktemp("db") / "test.sqlite")
    os.environ.pop("DATABASE_URL", None)
    os.environ["MS_ALERTS_DRY_RUN"] = "1"
    os.environ["MS_ADMIN_TOKEN"] = "test-token"
    os.environ["TELEGRAM_BOT_TOKEN"] = "123:test-only-not-a-real-token"  # dry run: never called
    os.environ["TELEGRAM_BOT_USERNAME"] = "ms_test_bot"
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c
