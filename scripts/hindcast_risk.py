"""Step 6: hindcast daily street-level alerts on recorded Pune flood days.

For each day: rain-module probability (per IMD cell) x street susceptibility
-> green/yellow/orange/red alert for every road location. Checks whether known
hotspots were flagged on flood days and how quiet the map is on dry days.

Usage:  python scripts/hindcast_risk.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import geopandas as gpd  # noqa: E402
import joblib  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from monsoon_sentinel import risk  # noqa: E402
from monsoon_sentinel.config import load_config  # noqa: E402
from monsoon_sentinel.features import rain_features as rf  # noqa: E402

EVENTS = {  # IMD rain-day dates (08:30 IST -> 08:30 IST next day)
    "2019-09-25": "Ambil Odha flash flood (Sahakar Nagar, Aranyeshwar, Katraj)",
    "2024-07-24": "Night before the Khadakwasla-release flood",
    "2024-07-25": "Sinhagad Road / Ekta Nagar flood",
}
QUIET = ["2023-07-10", "2022-08-20", "2024-08-15"]  # ordinary monsoon days for contrast
COLORS = {"green": "#2ca25f", "yellow": "#fed976", "orange": "#fd8d3c", "red": "#d7301f"}


def main():
    cfg = load_config()
    out = cfg.path("reports") / "urban"
    rm = joblib.load(cfg.path("models") / "rain_model.joblib")
    feats = pd.read_parquet(cfg.path("processed") / "rain_features.parquet")
    clim = rm["climatology"].rename("clim_heavy_freq")
    feats = feats.drop(columns=["clim_heavy_freq"], errors="ignore").merge(
        clim, on=["lat", "lon", "month"], how="left")
    feats["p_heavy"] = rm["model"].predict_proba(feats[rm["features"]])[:, 1]
    feats["antecedent_3d"] = feats["rain_sum3"]

    roads = gpd.read_parquet(cfg.path("processed") / "road_susceptibility.parquet")
    cells = risk.nearest_cell(roads.geometry.y.values, roads.geometry.x.values, cfg.cells)
    roads["cell_lat"] = [c[0] for c in cells]
    roads["cell_lon"] = [c[1] for c in cells]

    city = pd.MultiIndex.from_tuples([tuple(c) for c in cfg["grid"]["city_cells"]])
    days = list(EVENTS) + QUIET
    summary = {}
    fig, axs = plt.subplots(2, 3, figsize=(16, 11))
    for ax, day in zip(axs.ravel(), days):
        f = feats[feats.date == pd.Timestamp(day)][["lat", "lon", "p_heavy", "antecedent_3d", "rain_mm"]]
        d = roads.merge(f, left_on=["cell_lat", "cell_lon"], right_on=["lat", "lon"], how="left")
        d["alert"] = risk.alerts(d.p_heavy.fillna(0).values, d.risk_class, d.antecedent_3d.fillna(0).values).values
        share = d[d.label == 0].alert.value_counts(normalize=True).reindex(risk.ALERTS, fill_value=0)
        hs = d[d.label == 1]
        summary[day] = {
            "event": EVENTS.get(day, "ordinary monsoon day"),
            "observed_rain_city_cells_mm": round(float(f.set_index(["lat", "lon"]).loc[lambda x: x.index.isin(city)].rain_mm.max()), 1) if len(f) else None,
            "max_p_heavy_city": round(float(f.set_index(["lat", "lon"]).loc[lambda x: x.index.isin(city)].p_heavy.max()), 2) if len(f) else None,
            "road_share_by_alert": share.round(3).to_dict(),
            "hotspots_orange_or_red": f"{int(hs.alert.isin(['orange', 'red']).sum())}/{len(hs)}",
        }
        for a in risk.ALERTS:
            s = d[(d.label == 0) & (d.alert == a)]
            ax.scatter(s.geometry.x, s.geometry.y, s=1.5, c=COLORS[a])
        ax.scatter(hs.geometry.x, hs.geometry.y, s=40, facecolor="none", edgecolor="k")
        ax.set_title(f"{day}: {summary[day]['event'][:38]}\nrain {summary[day]['observed_rain_city_cells_mm']} mm, "
                     f"P(heavy) {summary[day]['max_p_heavy_city']}, hotspots alerted {summary[day]['hotspots_orange_or_red']}",
                     fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Monsoon Sentinel hindcast: street-level alerts (green / yellow / orange / red)", fontsize=13)
    fig.tight_layout()
    fig.savefig(out / "hindcast_alerts.png", dpi=110)
    (out / "hindcast_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
