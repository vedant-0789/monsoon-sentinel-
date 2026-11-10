"""Load project configuration and resolve paths relative to the repo root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    raw: dict

    def __getitem__(self, key):
        return self.raw[key]

    def path(self, name: str) -> Path:
        p = ROOT / self.raw["paths"][name]
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cells(self) -> list[tuple[float, float]]:
        g = self.raw["grid"]
        return [(lat, lon) for lat in g["lats"] for lon in g["lons"]]

    @property
    def years(self) -> range:
        y = self.raw["years"]
        return range(y["start"], y["end"] + 1)


def load_config(name: str = "pune") -> Config:
    with open(ROOT / "configs" / f"{name}.yaml", encoding="utf-8") as f:
        return Config(yaml.safe_load(f))
