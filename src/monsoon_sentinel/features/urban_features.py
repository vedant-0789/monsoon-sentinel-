"""Point features for waterlogging susceptibility (road locations + hotspots)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from monsoon_sentinel.config import Config
from monsoon_sentinel.data import osm, terrain

UTM = "EPSG:32643"  # metric CRS for Pune


def road_candidates(cfg: Config, roads: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Points every `sample_spacing_m` along roads, thinned to one per grid cell."""
    sp = cfg["urban"]["sample_spacing_m"]
    r = roads.to_crs(UTM)
    pts = []
    for geom, hw in zip(r.geometry, r.highway):
        n = max(1, int(geom.length // sp))
        for d in np.linspace(0, geom.length, n + 1):
            p = geom.interpolate(d)
            pts.append((p.x, p.y, hw))
    df = pd.DataFrame(pts, columns=["x", "y", "highway"])
    df["cell"] = (df.x // sp).astype(int).astype(str) + "_" + (df.y // sp).astype(int).astype(str)
    df = df.drop_duplicates("cell")
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.x, df.y), crs=UTM)
    return g.drop(columns=["cell"])


def hotspot_points(cfg: Config, hotspots: pd.DataFrame) -> gpd.GeoDataFrame:
    h = hotspots.dropna(subset=["lat"]).copy()
    h = h[~h.name.isin(cfg["urban"]["exclude_hotspots"])]
    h["weight"] = np.where(h.precision == "point", 1.0, 0.5)
    g = gpd.GeoDataFrame(h, geometry=gpd.points_from_xy(h.lon, h.lat), crs="EPSG:4326").to_crs(UTM)
    # merge duplicates that geocoded within 100 m of each other
    g["k"] = (g.geometry.x // 100).astype(int).astype(str) + "_" + (g.geometry.y // 100).astype(int).astype(str)
    g = g.sort_values("weight", ascending=False).drop_duplicates("k").drop(columns="k")
    return g.reset_index(drop=True)


def _density(points: gpd.GeoDataFrame, lines: gpd.GeoDataFrame, radius: float) -> np.ndarray:
    """Line length (km) within `radius` metres of each point, per km^2."""
    buf = points.geometry.buffer(radius)
    lines = lines[["geometry"]].reset_index(drop=True)
    sidx = lines.sindex
    out = np.zeros(len(points))
    for i, b in enumerate(buf):
        idx = list(sidx.query(b, predicate="intersects"))
        if idx:
            out[i] = lines.geometry.iloc[idx].intersection(b).length.sum() / 1000
    return out / (np.pi * (radius / 1000) ** 2)


def build(cfg: Config, points: gpd.GeoDataFrame, roads: gpd.GeoDataFrame,
          waterways: gpd.GeoDataFrame) -> pd.DataFrame:
    """Terrain + drainage + urban-form features at each point (points in UTM)."""
    ll = points.to_crs("EPSG:4326")
    lay = terrain.sample(cfg.path("interim") / "terrain_layers.tif",
                         ll.geometry.y.values, ll.geometry.x.values, window_px=1)
    f = pd.DataFrame(lay, index=points.index)
    # neighbourhood minimum HAND / maximum sink within ~90 m: tolerates geocoding error
    lay3 = terrain.sample(cfg.path("interim") / "terrain_layers.tif",
                          ll.geometry.y.values, ll.geometry.x.values, window_px=3)
    f["hand_smooth"] = lay3["hand"]
    f["sink_depth_smooth"] = lay3["sink_depth"]

    ww = waterways.to_crs(UTM)
    rivers = ww[ww.waterway.isin(["river", "canal"])]
    small = ww[ww.waterway.isin(["stream", "drain", "ditch"])]
    f["dist_river_m"] = points.geometry.apply(lambda p: rivers.distance(p).min()).values
    f["dist_nala_m"] = points.geometry.apply(lambda p: small.distance(p).min()).values if len(small) else 5000
    f["log_dist_river"] = np.log1p(f.dist_river_m)
    f["log_dist_nala"] = np.log1p(f.dist_nala_m)
    r = roads.to_crs(UTM)
    f["road_density_500m"] = _density(points, r, 500)   # urbanisation / imperviousness proxy
    major = r[r.highway.isin(["motorway", "trunk", "primary", "secondary"])]
    f["major_road_density_500m"] = _density(points, major, 500)
    return f


FEATURES = ["elevation", "slope", "tpi_300m", "tpi_1km", "sink_depth", "sink_depth_smooth",
            "log_flow_acc", "twi", "hand", "hand_smooth", "dist_stream_m", "log_dist_river",
            "log_dist_nala", "road_density_500m", "major_road_density_500m"]
