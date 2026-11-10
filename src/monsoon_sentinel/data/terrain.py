"""Terrain & drainage layers for urban waterlogging susceptibility.

Source: Copernicus GLO-30 DEM (30 m, public AWS bucket). Derived layers:
elevation, slope, topographic position (TPI), depression (sink) depth,
flow accumulation, topographic wetness index (TWI) and height above
nearest drainage (HAND), all on the same 30 m grid.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.windows import from_bounds
from scipy import ndimage

from monsoon_sentinel.config import Config

DEM_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N18_00_E073_00_DEM/"
           "Copernicus_DSM_COG_10_N18_00_E073_00_DEM.tif")


def download_dem(cfg: Config) -> Path:
    d = cfg.path("raw") / "dem"
    d.mkdir(exist_ok=True)
    tile = d / "cop30_N18_E073.tif"
    if not tile.exists():
        with requests.get(DEM_URL, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(tile, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    return tile


def clip_dem(cfg: Config, tile: Path) -> Path:
    b = cfg["urban"]["bbox"]
    out = cfg.path("interim") / "dem_pune.tif"
    with rasterio.open(tile) as src:
        win = from_bounds(b["lon_min"], b["lat_min"], b["lon_max"], b["lat_max"], src.transform)
        data = src.read(1, window=win)
        prof = src.profile.copy()
        prof.update(height=data.shape[0], width=data.shape[1],
                    transform=src.window_transform(win), compress="deflate", tiled=False)
        prof.pop("blockxsize", None); prof.pop("blockysize", None)
    with rasterio.open(out, "w", **prof) as dst:
        dst.write(data, 1)
    return out


def _cell_size_m(transform, lat: float) -> tuple[float, float]:
    dx = abs(transform.a) * 111_320 * np.cos(np.deg2rad(lat))
    dy = abs(transform.e) * 110_574
    return dx, dy


def derive_layers(cfg: Config, dem_path: Path) -> Path:
    """Compute hydrological layers with pysheds; returns path of a multi-band GeoTIFF."""
    if not hasattr(np, "in1d"):  # pysheds 0.4 still calls np.in1d (removed in NumPy 2.x)
        np.in1d = lambda a, b, **kw: np.isin(np.ravel(a), b, **kw)
    from pysheds.grid import Grid

    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))
    pits = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pits)
    inflated = grid.resolve_flats(flooded)
    fdir = grid.flowdir(inflated)
    acc = grid.accumulation(fdir)

    with rasterio.open(dem_path) as src:
        prof = src.profile.copy()
        transform = src.transform
        lat0 = src.bounds.bottom + (src.bounds.top - src.bounds.bottom) / 2
    dx, dy = _cell_size_m(transform, lat0)
    cell_area = dx * dy

    z = np.asarray(dem, dtype="float32")
    gy, gx = np.gradient(z, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")

    sink_depth = (np.asarray(flooded) - z).astype("float32")  # where water ponds before draining
    acc_a = np.asarray(acc, dtype="float64")
    sca = (acc_a + 1) * cell_area / dx  # specific catchment area (m)
    twi = np.log(sca / np.tan(np.deg2rad(np.maximum(slope, 0.1)))).astype("float32")

    stream_thr = cfg["urban"]["stream_threshold_cells"]
    hand = grid.compute_hand(fdir, inflated, acc > stream_thr)
    hand = np.asarray(hand, dtype="float32")
    streams = acc_a > stream_thr
    dist_stream = (ndimage.distance_transform_edt(~streams) * (dx + dy) / 2).astype("float32")

    def tpi(radius_m):
        k = max(1, int(round(radius_m / dx)))
        mean = ndimage.uniform_filter(z, size=2 * k + 1, mode="nearest")
        return (z - mean).astype("float32")

    layers = {
        "elevation": z, "slope": slope, "tpi_300m": tpi(300), "tpi_1km": tpi(1000),
        "sink_depth": sink_depth, "log_flow_acc": np.log1p(acc_a).astype("float32"),
        "twi": twi, "hand": hand, "dist_stream_m": dist_stream,
    }
    out = cfg.path("interim") / "terrain_layers.tif"
    prof.update(count=len(layers), dtype="float32", compress="deflate", nodata=None)
    with rasterio.open(out, "w", **prof) as dst:
        for i, (name, arr) in enumerate(layers.items(), start=1):
            dst.write(arr, i)
            dst.set_band_description(i, name)
    return out


def sample(layers_path: Path, lats, lons, window_px: int = 1) -> dict[str, np.ndarray]:
    """Sample every band at points, averaging a (2w+1)^2 window to absorb geocode error."""
    with rasterio.open(layers_path) as src:
        names = list(src.descriptions)
        stack = src.read()
        rows, cols = rasterio.transform.rowcol(src.transform, lons, lats)
    rows, cols = np.asarray(rows), np.asarray(cols)
    out = {}
    H, W = stack.shape[1:]
    for b, name in enumerate(names):
        band = stack[b].astype("float64")
        if window_px > 0:  # NaN-aware moving mean (HAND is undefined on a few edge cells)
            valid = np.isfinite(band)
            size = 2 * window_px + 1
            num = ndimage.uniform_filter(np.where(valid, band, 0.0), size=size, mode="nearest")
            den = ndimage.uniform_filter(valid.astype("float64"), size=size, mode="nearest")
            band = np.where(den > 0, num / np.maximum(den, 1e-9), np.nan)
        r = np.clip(rows, 0, H - 1)
        c = np.clip(cols, 0, W - 1)
        out[name] = band[r, c]
    return out
