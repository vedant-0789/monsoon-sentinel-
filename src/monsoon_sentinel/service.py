"""Monsoon Sentinel service: one object that produces bulletins, maps and point look-ups.

Two modes:
  * live   - today's 08:30 IST forecast from Open-Meteo NWP inputs
  * replay - any historical monsoon day (2001-2024) from the IMD + ERA5 training archive,
             run through exactly the same alert logic (used for demos and hindcasts)
"""

from __future__ import annotations

import datetime as dt
import json
import threading
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from monsoon_sentinel import risk
from monsoon_sentinel.config import load_config
from monsoon_sentinel.data import live
from monsoon_sentinel.features import rain_features as rf

FRIENDLY = {
    "rain_lag1": "rain in the last 24 hours", "rain_lag2": "rain 2 days ago", "rain_lag3": "rain 3 days ago",
    "rain_sum3": "rain over the last 3 days", "rain_sum7": "rain over the last week",
    "rain_sum15": "rain over the last 2 weeks", "rain_sum30": "how wet the last month was",
    "heavy_days7": "heavy-rain days this week", "tcwv_now": "moisture in the air now",
    "tcwv_mean24": "moisture in the air (24 h)", "tcwv_max24": "peak air moisture (24 h)",
    "rh_now": "humidity now", "rh_mean24": "humidity (24 h)", "cc_mean24": "cloud cover (24 h)",
    "u_now": "westerly monsoon wind", "u_mean24": "westerly monsoon wind (24 h)",
    "dom_u": "monsoon wind across the region", "dom_tcwv": "moisture across the region",
    "ghats_pr24": "rain over the Western Ghats", "ghats_u": "wind over the Ghats",
    "ghats_tcwv": "moisture over the Ghats", "dom_pr24": "rain across the region (24 h)",
    "pr_24h": "rain in the last 24 hours", "pr_6h": "rain in the last 6 hours",
    "mslp_tend24": "falling air pressure", "moist_flux_u": "moisture carried in from the Arabian Sea",
    "dom_rain_lag1_max": "heaviest rain anywhere in the region yesterday",
    "dom_rain_lag1_mean": "average rain across the region yesterday",
    "doy_sin": "time of the monsoon season", "doy_cos": "time of the monsoon season",
    "clim_heavy_freq": "how often this area normally gets heavy rain", "sm_now": "soil wetness",
    "elevation": "terrain height",
}
LIKELIHOOD_WORDS = ["very unlikely", "unlikely", "possible", "likely"]
_LAT0 = np.deg2rad(18.52)  # equirectangular metres: < 0.1 % error across Pune


def _xy(lat, lon):
    return np.asarray(lon) * 111_320 * np.cos(_LAT0), np.asarray(lat) * 110_574


def _lat_lon(x, y):
    return y / 110_574, x / (111_320 * np.cos(_LAT0))


class Sentinel:
    def __init__(self):
        self.cfg = load_config()
        self.rain = joblib.load(self.cfg.path("models") / "rain_model.joblib")
        self.archive = pd.read_parquet(self.cfg.path("processed") / "rain_features.parquet")
        self.archive["date"] = pd.to_datetime(self.archive["date"])
        f64 = self.archive.select_dtypes("float64").columns.difference(["lat", "lon"])
        self.archive[f64] = self.archive[f64].astype("float32")
        self.roads = self._load_roads()
        hs = pd.read_csv(self.cfg.path("raw").parent / "labels" / "pune_hotspots.csv").dropna(subset=["lat"])
        self.hotspots = hs[~hs.name.isin(self.cfg["urban"]["exclude_hotspots"])].reset_index(drop=True)
        self._live_cache: tuple[dt.datetime, pd.DataFrame] | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ roads
    def _load_roads(self) -> pd.DataFrame:
        """Plain table (no geometry library at runtime): plat, plon, road_name, risk_class, ..."""
        light = self.cfg.path("processed") / "road_points_light.parquet"
        if light.exists():
            return pd.read_parquet(light)
        g = self._build_named_roads()
        df = pd.DataFrame({
            "plat": g.geometry.y.values, "plon": g.geometry.x.values, "road_name": g.road_name.values,
            "risk_class": g.risk_class.astype(str).values, "percentile": g.percentile.values,
            "p10": g.p10.values, "p90": g.p90.values, "cell_lat": g.cell_lat.values, "cell_lon": g.cell_lon.values,
        })
        df.to_parquet(light, index=False)
        return df

    def _build_named_roads(self):
        import geopandas as gpd

        from monsoon_sentinel.data import osm

        f = self.cfg.path("processed") / "road_points_named.parquet"
        if f.exists():
            return gpd.read_parquet(f)
        pts = gpd.read_parquet(self.cfg.path("processed") / "road_susceptibility.parquet")
        pts = pts[pts.label == 0].drop(columns=["name"]).reset_index(drop=True)
        roads = osm.load_lines(self.cfg.path("raw") / "osm" / "roads.json")
        named = roads[roads.name.notna()].to_crs("EPSG:32643")[["name", "geometry"]]
        j = gpd.sjoin_nearest(pts.to_crs("EPSG:32643"), named, how="left", max_distance=80,
                              distance_col="d").drop_duplicates(subset="geometry")
        pts["road_name"] = j["name"].values[: len(pts)]
        cells = risk.nearest_cell(pts.geometry.y.values, pts.geometry.x.values, self.cfg.cells)
        pts["cell_lat"] = [c[0] for c in cells]
        pts["cell_lon"] = [c[1] for c in cells]
        pts.to_parquet(f)
        return pts

    # ------------------------------------------------------------- rain layer
    def _predict(self, feats: pd.DataFrame) -> pd.DataFrame:
        clim = self.rain["climatology"].rename("clim_heavy_freq")
        feats = feats.drop(columns=["clim_heavy_freq"], errors="ignore").merge(
            clim, on=["lat", "lon", "month"], how="left")
        X = feats[self.rain["features"]]
        model = self.rain["model"]
        feats["p_heavy"] = model.predict_proba(X)[:, 1]
        if isinstance(model, xgb.XGBClassifier):  # exact TreeSHAP contributions (log-odds)
            contrib = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)[:, :-1]
            feats["drivers"] = [self._drivers(row) for row in contrib]
        else:
            feats["drivers"] = [[] for _ in range(len(feats))]
        return feats

    def _drivers(self, row: np.ndarray, k: int = 4) -> list[dict]:
        """Plain-language top factors, leading with those that agree with the verdict."""
        names = self.rain["features"]
        out, seen = [], set()
        verdict_up = row.sum() > 0
        agree = (row > 0) == verdict_up
        order = sorted(range(len(row)), key=lambda i: (not agree[i], -abs(row[i])))
        for i in order:
            label = FRIENDLY.get(names[i])
            if not label or label in seen or abs(row[i]) < 0.05:
                continue
            seen.add(label)
            out.append({"factor": label, "effect": "raises" if row[i] > 0 else "lowers",
                        "strength": round(float(abs(row[i])), 2)})
            if len(out) == k:
                break
        return out

    def rain_replay(self, date: str) -> pd.DataFrame:
        d = self.archive[self.archive.date == pd.Timestamp(date)]
        if d.empty:
            raise KeyError(f"No archived data for {date} (replay covers Jun-Oct 2001-2024).")
        out = self._predict(d.copy())
        out["nwp_rain_24h"] = np.nan
        out["observed_rain_mm"] = out["rain_mm"]
        return out

    def rain_live(self) -> pd.DataFrame:
        with self._lock:
            now = dt.datetime.now(dt.timezone.utc)
            if self._live_cache and (now - self._live_cache[0]).total_seconds() < 1800:
                return self._live_cache[1]
            hourly = live.fetch(self.cfg)
            daily = live.daily_rain_imd_style(hourly, self.cfg["issue_hour_utc"])
            issue = now if now.hour >= self.cfg["issue_hour_utc"] else now - dt.timedelta(days=1)
            day = pd.Timestamp(issue.date())
            fc = daily[daily.date == day][["lat", "lon", "rain_mm"]].rename(columns={"rain_mm": "nwp_rain_24h"})
            daily.loc[daily.date >= day, "rain_mm"] = np.nan          # the future is unknown
            feats = rf.build(self.cfg, daily, hourly.drop(columns=[]), training=False)
            feats = feats[feats.date == day].copy()
            out = self._predict(feats).merge(fc, on=["lat", "lon"], how="left")
            out["observed_rain_mm"] = np.nan
            self._live_cache = (now, out)
            return out

    # --------------------------------------------------------------- alerts
    def _effective_probability(self, r: pd.DataFrame) -> np.ndarray:
        """ML probability, raised when the NWP forecast itself shows heavy rain (live mode)."""
        p = r.p_heavy.to_numpy(copy=True)
        fc = r.nwp_rain_24h.fillna(0).to_numpy()
        p = np.maximum(p, np.where(fc >= 64.5, 0.60, np.where(fc >= 35, 0.35, 0.0)))
        return p

    @lru_cache(maxsize=8)
    def _road_alerts_cached(self, mode: str, date: str) -> pd.DataFrame:
        r = self.rain_live() if mode == "live" else self.rain_replay(date)
        r = r.assign(p_eff=self._effective_probability(r))
        d = self.roads.merge(r[["lat", "lon", "p_eff", "rain_sum3"]], left_on=["cell_lat", "cell_lon"],
                             right_on=["lat", "lon"], how="left").drop(columns=["lat", "lon"])
        d["alert"] = risk.alerts(d.p_eff.fillna(0).values, d.risk_class, d.rain_sum3.fillna(0).values).values
        return d

    def road_alerts(self, mode: str, date: str | None) -> pd.DataFrame:
        if mode == "live":  # live cache refreshes every 30 min
            key = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H") + str(dt.datetime.now().minute // 30)
            return self._road_alerts_cached("live", key)
        return self._road_alerts_cached("replay", date)

    # -------------------------------------------------------------- outputs
    def bulletin(self, mode: str = "live", date: str | None = None) -> dict:
        r = self.rain_live() if mode == "live" else self.rain_replay(date)
        r = r.assign(p_eff=self._effective_probability(r))
        roads = self.road_alerts(mode, date)
        city = {tuple(c) for c in self.cfg["grid"]["city_cells"]}
        rc = r[[(a, b) in city for a, b in zip(r.lat, r.lon)]]
        main = rc.loc[rc.p_eff.idxmax()]
        lvl = int(risk.likelihood_level([main.p_eff], [main.rain_sum3 or 0])[0])
        counts = roads.alert.value_counts().reindex(risk.ALERTS, fill_value=0)
        headline = ("red" if counts["red"] else "orange" if counts["orange"] else
                    "yellow" if counts["yellow"] > 0.2 * len(roads) else "green")
        issue_date = pd.Timestamp(r.date.iloc[0]).date()

        hs = self.hotspots.copy()
        rx, ry = _xy(roads.plat.values, roads.plon.values)
        hx, hy = _xy(hs.lat.values, hs.lon.values)
        nearest = [int(np.argmin((rx - a) ** 2 + (ry - b) ** 2)) for a, b in zip(hx, hy)]
        hs["alert"] = roads.alert.values[nearest]
        top = (roads[roads.alert.isin(["red", "orange"])].sort_values("percentile", ascending=False)
               .dropna(subset=["road_name"]).drop_duplicates("road_name").head(15))

        return {
            "mode": mode,
            "date": str(issue_date),
            "issued_at": "08:30 IST" if mode == "replay" else dt.datetime.now(
                dt.timezone(dt.timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %H:%M IST"),
            "in_season": issue_date.month in self.cfg["target_months"],
            "headline_alert": headline,
            "headline_text": risk.ALERT_TEXT[headline],
            "heavy_rain": {
                "probability": round(float(main.p_eff), 2),
                "model_probability": round(float(main.p_heavy), 2),
                "likelihood": LIKELIHOOD_WORDS[lvl],
                "nwp_rain_24h_mm": None if pd.isna(main.nwp_rain_24h) else round(float(main.nwp_rain_24h), 1),
                "observed_rain_mm": None if pd.isna(main.observed_rain_mm) else round(float(main.observed_rain_mm), 1),
                "rain_last_3_days_mm": None if pd.isna(main.rain_sum3) else round(float(main.rain_sum3), 1),
                "drivers": main.drivers,
            },
            "cells": [{"lat": float(a.lat), "lon": float(a.lon), "probability": round(float(a.p_eff), 3),
                       "observed_rain_mm": None if pd.isna(a.observed_rain_mm) else round(float(a.observed_rain_mm), 1),
                       "nwp_rain_24h_mm": None if pd.isna(a.nwp_rain_24h) else round(float(a.nwp_rain_24h), 1)}
                      for a in r.itertuples()],
            "road_alert_counts": {k: int(v) for k, v in counts.items()},
            "streets_to_watch": [{"road": t.road_name, "alert": t.alert, "lat": round(float(t.plat), 5),
                                  "lon": round(float(t.plon), 5)} for t in top.itertuples()],
            "hotspots": [{"name": h.name, "type": h.hazard_type, "alert": h.alert, "lat": h.lat, "lon": h.lon,
                          "source": h.source_url} for h in hs.itertuples()],
        }

    def roads_geojson(self, mode: str, date: str | None, min_alert: str = "green") -> str:
        """GeoJSON as compact JSON text (cached as text: far smaller in memory than dicts)."""
        key = (mode, date if mode == "replay" else dt.datetime.now().strftime("%Y%m%d%H"), min_alert)
        cache = self.__dict__.setdefault("_geo_cache", {})
        if key not in cache:
            if len(cache) >= 8:
                cache.pop(next(iter(cache)))
            cache[key] = json.dumps(self._roads_geojson(mode, date, min_alert), separators=(",", ":"))
        return cache[key]

    def _roads_geojson(self, mode: str, date: str | None, min_alert: str) -> dict:
        d = self.road_alerts(mode, date)
        keep = risk.ALERTS[risk.ALERTS.index(min_alert):]
        d = d[d.alert.isin(keep)]
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(x, 5), round(y, 5)]},
                  "properties": {"a": a, "s": round(float(s), 3), "n": n if isinstance(n, str) else None}}
                 for x, y, a, s, n in zip(d.plon, d.plat, d.alert, d.percentile, d.road_name)]
        return {"type": "FeatureCollection", "features": feats}

    def point(self, lat: float, lon: float, mode: str, date: str | None) -> dict:
        d = self.road_alerts(mode, date)
        dist = (d.plat - lat) ** 2 + ((d.plon - lon) * np.cos(np.deg2rad(lat))) ** 2
        i = int(np.argmin(dist.values))
        row = d.iloc[i]
        meters = float(np.sqrt(dist.iloc[i])) * 111_000
        name = row.road_name if isinstance(row.road_name, str) else None
        if name is None:  # fall back to the closest named road within ~400 m
            named = d.road_name.notna().values
            if named.any():
                j = int(np.argmin(np.where(named, dist.values, np.inf)))
                if np.sqrt(dist.values[j]) * 111_000 < 400:
                    name = f"Near {d.road_name.iloc[j]}"
        return {
            "nearest_road": name or "Unnamed road",
            "distance_m": round(meters),
            "alert": row.alert, "advice": risk.ALERT_TEXT[row.alert],
            "street_susceptibility": str(row.risk_class),
            "susceptibility_percentile": round(float(row.percentile) * 100),
            "uncertainty_band": [round(float(row.p10), 3), round(float(row.p90), 3)],
            "heavy_rain_probability": round(float(row.p_eff), 2) if pd.notna(row.p_eff) else None,
            "covered": meters < 1500,
        }

    def actions(self, mode: str, date: str | None, max_items: int = 10) -> list[dict]:
        """Group red/orange street segments with DBSCAN (400 m) into response zones, ranked."""
        from sklearn.cluster import DBSCAN, KMeans

        d = self.road_alerts(mode, date)
        focus = d[d.alert == "red"]
        if len(focus) < 6:
            focus = d[d.alert.isin(["red", "orange"])]
        if focus.empty:
            return []
        fx, fy = _xy(focus.plat.values, focus.plon.values)
        xy = np.c_[fx, fy]
        lab = DBSCAN(eps=250, min_samples=5).fit_predict(xy)
        # split clusters larger than a crew can cover (~120 segments = ~1.5 km^2) with K-means
        next_id = lab.max() + 1
        for z in np.unique(lab[lab >= 0]):
            idx = np.flatnonzero(lab == z)
            if len(idx) > 120:
                k = int(np.ceil(len(idx) / 120))
                sub = KMeans(k, n_init=5, random_state=0).fit_predict(xy[idx])
                lab[idx] = next_id + sub
                next_id += k
        u = focus.assign(zone=lab, x=fx, y=fy)
        named = self.roads[self.roads.road_name.notna()]
        nx, ny = _xy(named.plat.values, named.plon.values)
        orange_all = d[d.alert == "orange"]
        ox, oy = _xy(orange_all.plat.values, orange_all.plon.values)
        zones = []
        for z, g in u[u.zone >= 0].groupby("zone"):
            cx, cy = g.x.mean(), g.y.mean()
            n_red = int((g.alert == "red").sum())
            n_or = int((((ox - cx) ** 2 + (oy - cy) ** 2) < 600 ** 2).sum())
            score = n_red * 2 + n_or
            label = named.road_name.iloc[int(np.argmin((nx - cx) ** 2 + (ny - cy) ** 2))]
            clat, clon = _lat_lon(cx, cy)
            zones.append({
                "zone": int(z), "lat": round(float(clat), 5),
                "lon": round(float(clon), 5), "area_label": label,
                "red_segments": n_red, "orange_segments": n_or,
                "priority_score": score,
                "action": "pump" if n_red >= 10 else "crew" if n_red else "inspect",
                "recommended": ("Pre-position a dewatering pump and a response crew" if n_red >= 10
                                else "Station a drain-clearing crew; keep a pump on standby" if n_red
                                else "Inspect and clear drains before evening"),
            })
        zones.sort(key=lambda z: -z["priority_score"])
        for i, z in enumerate(zones[:max_items], start=1):
            z["rank"] = i
        return zones[:max_items]

    def replay_days(self) -> list[dict]:
        """Notable archived days for the demo picker."""
        city = {tuple(c) for c in self.cfg["grid"]["city_cells"]}
        a = self.archive[[(x, y) in city for x, y in zip(self.archive.lat, self.archive.lon)]]
        top = a.groupby("date").rain_mm.max().sort_values(ascending=False)
        named = {"2024-07-25": "Sinhagad Road / Ekta Nagar flood", "2024-07-24": "Eve of the 2024 flood",
                 "2019-09-25": "Ambil Odha flash flood (missed - cloudburst)",
                 "2023-07-10": "Ordinary monsoon day"}
        days = [{"date": k, "label": v} for k, v in named.items()]
        for d, mm in top.head(8).items():
            k = str(pd.Timestamp(d).date())
            if k not in named:
                days.append({"date": k, "label": f"Heavy rain day ({mm:.0f} mm in the city)"})
        return days
