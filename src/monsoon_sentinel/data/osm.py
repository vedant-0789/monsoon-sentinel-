"""OpenStreetMap layers via the Overpass API: road network and mapped waterways."""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from monsoon_sentinel.config import Config

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "monsoon-sentinel/0.1 (academic flood-risk research)"}

QUERIES = {
    "roads": """way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|
               motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"]({bbox});""",
    "waterways": """way["waterway"~"^(river|stream|canal|drain|ditch)$"]({bbox});""",
}


def _bbox(cfg: Config) -> str:
    b = cfg["urban"]["bbox"]
    return f"{b['lat_min']},{b['lon_min']},{b['lat_max']},{b['lon_max']}"


def download(cfg: Config) -> dict[str, Path]:
    d = cfg.path("raw") / "osm"
    d.mkdir(exist_ok=True)
    out = {}
    for name, q in QUERIES.items():
        f = d / f"{name}.json"
        out[name] = f
        if f.exists():
            continue
        query = f"[out:json][timeout:300];({q.format(bbox=_bbox(cfg))});out geom tags;"
        for attempt in range(6):
            try:
                r = requests.post(OVERPASS, data={"data": query}, headers=UA, timeout=400)
                if r.status_code == 200:
                    f.write_text(r.text, encoding="utf-8")
                    break
                print(f"  overpass {name}: HTTP {r.status_code}, retrying", flush=True)
            except requests.RequestException as e:
                print(f"  overpass {name}: {e}, retrying", flush=True)
            time.sleep(30 * (attempt + 1))
        else:
            raise RuntimeError(f"Overpass download failed for {name}")
    return out


def load_lines(path: Path):
    """Return a GeoDataFrame (EPSG:4326) of OSM ways with their main tags."""
    import geopandas as gpd
    from shapely.geometry import LineString

    js = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for el in js["elements"]:
        if el.get("type") != "way" or "geometry" not in el or len(el["geometry"]) < 2:
            continue
        t = el.get("tags", {})
        rows.append({
            "osm_id": el["id"],
            "highway": t.get("highway"),
            "waterway": t.get("waterway"),
            "name": t.get("name"),
            "geometry": LineString([(p["lon"], p["lat"]) for p in el["geometry"]]),
        })
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
