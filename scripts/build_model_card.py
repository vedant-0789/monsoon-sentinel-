"""Collect every evaluation result into one model card (served by /api/model-card and
shown on the app's "How it works" page).

Usage:  python scripts/build_model_card.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports"


def jload(p):
    p = R / p
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def table(p, cols, n=None):
    p = R / p
    if not p.exists():
        return []
    df = pd.read_csv(p)
    df = df[[c for c in cols if c in df.columns]]
    if n:
        df = df.head(n)
    return json.loads(df.round(3).to_json(orient="records"))


if __name__ == "__main__":
    rain_best = jload("rain/best_model.json")
    analysis = jload("rain/analysis/summary.json")
    card = {
        "rain": {
            "task": "P(IMD heavy rain >= 64.5 mm in the next 24 h), issued 08:30 IST, 15 grid cells",
            "data": "IMD 0.25 deg gauge rainfall + ERA5 hourly reanalysis, Jun-Oct 2001-2024",
            "split": "train 2001-2016 / validate 2017-2020 / test 2021-2024 (chronological)",
            "deployed": rain_best.get("best_model"),
            "benchmark": table("rain/benchmark.csv", ["model", "ROC_AUC", "PR_AUC", "BSS_vs_clim", "POD", "FAR",
                                                      "CSI", "HSS", "city_ROC_AUC"]),
            "top_drivers": table("rain/shap_importance.csv", ["feature", "mean_abs_shap"], 8),
        },
        "analysis": {
            "pca_components_90pct": analysis.get("pca_components_for_90pct_variance"),
            "pca_pr_auc": [analysis.get("logreg_PR_AUC_all_features"), analysis.get("logreg_PR_AUC_pca_90pct")],
            "feature_selection": analysis.get("feature_subset_test_PR_AUC"),
            "hmm": analysis.get("hmm", {}).get("heavy_rain_rate_by_phase"),
            "regimes": analysis.get("weather_regimes", {}).get("heavy_rain_rate_by_kmeans_regime"),
            "dbscan": analysis.get("weather_regimes", {}).get("dbscan"),
            "apriori": (analysis.get("apriori_top_rules") or [])[:3],
            "regression": analysis.get("regression"),
        },
        "susceptibility": {
            "task": "Street-level waterlogging susceptibility, ~21,900 road locations",
            "labels": "32 geocoded hotspots from public sources (traffic police, PMC, 2019/2024 floods)",
            "validation": "spatial block cross-validation (2 km blocks, 5 folds)",
            "benchmark": table("urban/susceptibility_benchmark.csv", ["model", "ROC_AUC", "capture_top10pct",
                                                                      "capture_top20pct"]),
            "summary": jload("urban/summary.json"),
        },
        "hindcast": jload("urban/hindcast_summary.json"),
        "dispatch": jload("dispatch/summary.json"),
        "nowcast": jload("nowcast/summary.json"),
        "photo": jload("photo/summary.json"),
        "citizen_reports": {
            "summary": jload("citizen/summary.json"),
            "benchmark": table("citizen/classifier_benchmark.csv", ["model", "category_macro_F1", "urgent_F1"]),
        },
    }
    out = ROOT / "models" / "model_card.json"
    out.write_text(json.dumps(card, indent=1, default=str), encoding="utf-8")
    print(f"model card -> {out} ({out.stat().st_size / 1e3:.1f} kB)")
