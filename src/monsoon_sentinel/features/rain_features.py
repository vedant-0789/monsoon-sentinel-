"""Feature table for the 24 h heavy-rain forecast.

One row = one grid cell x one forecast day D. The forecast is issued at
03 UTC (08:30 IST) on D and targets the IMD rainfall for day D (03 UTC D to
03 UTC D+1). Every feature uses only information available at issue time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from monsoon_sentinel.config import Config

ERA5_COLS = {
    "precipitation": "pr",
    "pressure_msl": "mslp",
    "relative_humidity_2m": "rh",
    "dew_point_2m": "td",
    "cloud_cover": "cc",
    "wind_speed_10m": "ws",
    "wind_direction_10m": "wd",
    "total_column_integrated_water_vapour": "tcwv",
    "soil_moisture_0_to_7cm": "sm",
    "boundary_layer_height": "blh",
}


def _era5_cell_features(h: pd.DataFrame, issue_hour: int) -> pd.DataFrame:
    """Hourly ERA5 for one cell -> one row per issue time."""
    h = h.rename(columns=ERA5_COLS).set_index("time").sort_index()
    rad = np.deg2rad(h["wd"])
    h["u"] = -h["ws"] * np.sin(rad)  # +ve = westerly (from the Arabian Sea)
    h["v"] = -h["ws"] * np.cos(rad)

    r24 = h.rolling("24h")
    r6 = h.rolling("6h")
    f = pd.DataFrame(index=h.index)
    for c in ["tcwv", "mslp", "rh", "td", "cc", "sm", "blh", "u", "v"]:
        f[f"{c}_now"] = h[c]
    f["pr_6h"] = r6["pr"].sum()
    f["pr_24h"] = r24["pr"].sum()
    f["pr_max1h_24h"] = r24["pr"].max()
    for c in ["tcwv", "rh", "cc", "u", "v"]:
        f[f"{c}_mean24"] = r24[c].mean()
    f["tcwv_max24"] = r24["tcwv"].max()
    f["mslp_tend24"] = h["mslp"] - h["mslp"].shift(freq="24h").reindex(h.index)
    f["tcwv_tend24"] = h["tcwv"] - h["tcwv"].shift(freq="24h").reindex(h.index)
    f["u_tend24"] = h["u"] - h["u"].shift(freq="24h").reindex(h.index)
    f["moist_flux_u"] = h["tcwv"] * h["u"]  # westerly moisture transport proxy

    f = f[f.index.hour == issue_hour].copy()
    f["date"] = f.index.normalize()
    return f.reset_index(drop=True)


def build(cfg: Config, imd_df: pd.DataFrame, era5_df: pd.DataFrame,
          training: bool = True) -> pd.DataFrame:
    """training=False keeps rows without an observed target (live forecasting, any month)."""
    issue_hour = cfg["issue_hour_utc"]
    th = cfg["thresholds"]["heavy"]

    # ---- ERA5 per-cell features -------------------------------------------
    parts = []
    elev = {}
    for (lat, lon), h in era5_df.groupby(["lat", "lon"]):
        elev[(lat, lon)] = float(h["elevation"].iloc[0])
        f = _era5_cell_features(h.drop(columns=["lat", "lon", "elevation"]), issue_hour)
        f["lat"], f["lon"] = lat, lon
        parts.append(f)
    era = pd.concat(parts, ignore_index=True)

    # domain-wide synoptic context at issue time
    dom = era.groupby("date").agg(
        dom_tcwv=("tcwv_now", "mean"),
        dom_u=("u_now", "mean"),
        dom_mslp=("mslp_now", "mean"),
        dom_pr24=("pr_24h", "mean"),
    )
    ghats = era[era["lon"] == era["lon"].min()].groupby("date").agg(
        ghats_u=("u_now", "mean"), ghats_tcwv=("tcwv_now", "mean"), ghats_pr24=("pr_24h", "mean")
    )

    # ---- IMD antecedent rainfall (observed, known at issue time) ------------
    imd = imd_df.sort_values(["lat", "lon", "date"]).copy()
    g = imd.groupby(["lat", "lon"])["rain_mm"]
    for k in range(1, 8):
        imd[f"rain_lag{k}"] = g.shift(k)
    imd["rain_sum3"] = imd[["rain_lag1", "rain_lag2", "rain_lag3"]].sum(axis=1, min_count=1)
    imd["rain_sum7"] = imd[[f"rain_lag{k}" for k in range(1, 8)]].sum(axis=1, min_count=1)
    imd["rain_sum15"] = g.transform(lambda s: s.shift(1).rolling(15, min_periods=10).sum())
    imd["rain_sum30"] = g.transform(lambda s: s.shift(1).rolling(30, min_periods=20).sum())
    imd["heavy_days7"] = imd[[f"rain_lag{k}" for k in range(1, 8)]].ge(th).sum(axis=1)

    lag1 = imd.pivot_table(index="date", columns=["lat", "lon"], values="rain_lag1")
    dom_imd = pd.DataFrame({
        "dom_rain_lag1_mean": lag1.mean(axis=1),
        "dom_rain_lag1_max": lag1.max(axis=1),
        "dom_heavy_cells_lag1": lag1.ge(th).sum(axis=1),
    })

    df = imd.merge(era, on=["date", "lat", "lon"], how="inner")
    df = df.merge(dom, on="date", how="left").merge(ghats, on="date", how="left")
    df = df.merge(dom_imd, on="date", how="left")

    # ---- calendar & static ------------------------------------------------
    doy = df["date"].dt.dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["month"] = df["date"].dt.month
    df["year"] = df["date"].dt.year
    df["elevation"] = [elev[(a, b)] for a, b in zip(df["lat"], df["lon"])]

    # ---- target -----------------------------------------------------------
    if training:
        df = df[df["month"].isin(cfg["target_months"])]
        df = df.dropna(subset=["rain_mm"])
    df["y_heavy"] = (df["rain_mm"] >= th).astype(int)
    return df.reset_index(drop=True)


def add_climatology(df: pd.DataFrame, train_mask: pd.Series) -> pd.DataFrame:
    """Cell x month heavy-rain frequency, learned from training years only."""
    clim = (
        df[train_mask].groupby(["lat", "lon", "month"])["y_heavy"].mean().rename("clim_heavy_freq")
    )
    return df.drop(columns=["clim_heavy_freq"], errors="ignore").merge(
        clim, on=["lat", "lon", "month"], how="left"
    )


NON_FEATURES = {"date", "rain_mm", "y_heavy", "year", "month"}


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in NON_FEATURES]
