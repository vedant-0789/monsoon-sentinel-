"""Step 10: short-range (0-24 h) rainfall forecast from 5 NWP models, verified against IMD.

Compares, on 2022-2024 monsoons with leave-one-season-out cross-validation:
  A. morning ML model alone (XGBoost, issued 08:30 IST from observations)
  B. raw NWP ensemble (share of models forecasting >= 64.5 mm)
  C. NWP-only logistic model
  D. blended model: ML probability + NWP ensemble features (stacked logistic regression)
Also hindcasts single events and fits the deployed blend on all three seasons.

Usage:  python scripts/build_nowcast.py
Outputs: models/nowcast_blend.joblib, reports/nowcast/*
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import joblib  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from monsoon_sentinel.data import nwp  # noqa: E402
from monsoon_sentinel.evaluation.metrics import best_threshold, contingency  # noqa: E402
from monsoon_sentinel.service import Sentinel  # noqa: E402

YEARS = [2022, 2023, 2024]
TH = 64.5


def main():
    s = Sentinel()
    out = s.cfg.path("reports") / "nowcast"
    out.mkdir(exist_ok=True)

    feats = []
    for y in YEARS:
        print(f"NWP {y} ...", flush=True)
        feats.append(nwp.daily_features(nwp.fetch_history(s.cfg, y), s.cfg["issue_hour_utc"]))
    nf = pd.concat(feats, ignore_index=True)

    arch = s.archive[s.archive.year.isin(YEARS)].copy()
    ml = s._predict(arch)[["date", "lat", "lon", "p_heavy", "rain_mm"]]
    df = ml.merge(nf, on=["date", "lat", "lon"], how="inner").dropna(subset=["rain_mm"])
    df["y"] = (df.rain_mm >= TH).astype(int)
    df["year"] = df.date.dt.year
    city = {tuple(c) for c in s.cfg["grid"]["city_cells"]}
    df["is_city"] = [(a, b) in city for a, b in zip(df.lat, df.lon)]
    df["logit_ml"] = np.log(np.clip(df.p_heavy, 1e-4, 1 - 1e-4) / (1 - np.clip(df.p_heavy, 1e-4, 1 - 1e-4)))
    for c in ["nwp_mean", "nwp_max", "nwp_median", "nwp_neigh_max", "nwp_peak3h_max", "nwp_peak3h_mean", "nwp_std"]:
        df[f"log_{c}"] = np.log1p(df[c])
    NWP_X = [f"log_{c}" for c in ["nwp_mean", "nwp_max", "nwp_median", "nwp_neigh_max", "nwp_peak3h_max",
                                   "nwp_peak3h_mean", "nwp_std"]] + ["nwp_frac_heavy", "nwp_frac_35"]
    BLEND_X = ["logit_ml"] + NWP_X
    print(f"rows {len(df)}, heavy days {int(df.y.sum())} (city {int(df[df.is_city].y.sum())})", flush=True)

    make = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.5, class_weight=None, max_iter=3000))  # noqa: E731
    preds = {"A. Morning ML model (XGBoost)": df.p_heavy.values,
             "B. Raw NWP ensemble (share of models >= 64.5 mm)": df.nwp_frac_heavy.values}
    for name, X in [("C. NWP-only logistic model", NWP_X), ("D. Blend: ML + NWP ensemble (stacked)", BLEND_X)]:
        p = np.zeros(len(df))
        for y in YEARS:  # leave one monsoon season out
            tr, te = df.year != y, df.year == y
            p[te] = make().fit(df.loc[tr, X], df.y[tr]).predict_proba(df.loc[te, X])[:, 1]
        preds[name] = p

    # raise-only combinations: keep the ML probability, let strong NWP rain push it up
    rule = np.where(df.nwp_mean >= 64.5, 0.60, np.where(df.nwp_mean >= 35, 0.35, 0.0))
    preds["E. ML, raised by NWP rule (>=35 / >=64.5 mm)"] = np.maximum(df.p_heavy.values, rule)
    preds["F. max(ML, NWP-only logistic)"] = np.maximum(df.p_heavy.values, preds["C. NWP-only logistic model"])

    rows = []
    for name, p in preds.items():
        thr = best_threshold(df.y.values, p) if len(np.unique(p)) > 2 else 0.5
        r = {"model": name, "ROC_AUC": roc_auc_score(df.y, p), "PR_AUC": average_precision_score(df.y, p)}
        r.update({k: v for k, v in contingency(df.y, p >= thr).items() if k in ("POD", "FAR", "CSI", "HSS")})
        c = df.is_city.values
        r["city_PR_AUC"] = average_precision_score(df.y[c], p[c])
        r["city_ROC_AUC"] = roc_auc_score(df.y[c], p[c])
        cc = contingency(df.y[c], p[c] >= thr)
        r["city_POD"], r["city_CSI"] = cc["POD"], cc["CSI"]
        r["threshold"] = thr
        rows.append(r)
    bench = pd.DataFrame(rows)
    bench.to_csv(out / "nowcast_benchmark.csv", index=False)
    (out / "nowcast_benchmark.md").write_text(bench.round(3).to_markdown(index=False), encoding="utf-8")
    print(bench.round(3).to_string(index=False), flush=True)

    # per-model skill (each model's own 24 h total as the score)
    per = {}
    for m in nwp.MODELS:  # each model judged only on seasons it is archived for
        if m not in df:
            continue
        v = df[m].notna()
        if v.sum() and df.y[v].nunique() == 2:
            per[nwp.MODEL_NAMES[m]] = {"seasons": sorted(df.year[v].unique().tolist()), "n_days": int(v.sum()),
                                       "ROC_AUC": roc_auc_score(df.y[v], df[m][v]),
                                       "PR_AUC": average_precision_score(df.y[v], df[m][v])}
    # fair same-sample comparison on 2024, when all five models are archived
    s24 = df.year == 2024
    per["_2024_ML_model"] = {"ROC_AUC": roc_auc_score(df.y[s24], df.p_heavy[s24]),
                             "PR_AUC": average_precision_score(df.y[s24], df.p_heavy[s24])}
    per["_2024_ensemble_mean"] = {"ROC_AUC": roc_auc_score(df.y[s24], df.nwp_mean[s24]),
                                  "PR_AUC": average_precision_score(df.y[s24], df.nwp_mean[s24])}
    pd.DataFrame(per).T.to_csv(out / "per_model_skill.csv")
    print(pd.DataFrame(per).T.to_string())

    # event hindcasts (out-of-season predictions)
    df["p_blend"] = preds["D. Blend: ML + NWP ensemble (stacked)"]
    events = {}
    for day in ["2024-07-24", "2024-07-25", "2024-09-25", "2023-07-27", "2022-10-17"]:
        e = df[(df.date == pd.Timestamp(day)) & df.is_city]
        if len(e):
            events[day] = {"city_rain_mm": round(float(e.rain_mm.max()), 1),
                           "p_ml": round(float(e.p_heavy.max()), 2), "p_blend": round(float(e.p_blend.max()), 2),
                           "nwp_mean_mm": round(float(e.nwp_mean.max()), 1),
                           "nwp_max_mm": round(float(e.nwp_max.max()), 1)}
    (out / "event_hindcasts.json").write_text(json.dumps(events, indent=2))
    print(json.dumps(events, indent=2))

    # deployed blend: fit on all three seasons
    final = make().fit(df[BLEND_X], df.y)
    nwp_only = make().fit(df[NWP_X], df.y)
    best = bench.set_index("model")
    joblib.dump({"blend": final, "nwp_only": nwp_only, "blend_features": BLEND_X, "nwp_features": NWP_X,
                 "threshold": float(best.loc["D. Blend: ML + NWP ensemble (stacked)", "threshold"]),
                 "models": nwp.MODELS}, s.cfg.path("models") / "nowcast_blend.joblib")
    coefs = pd.Series(final[-1].coef_[0], index=BLEND_X).sort_values(key=abs, ascending=False)
    coefs.to_csv(out / "blend_coefficients.csv", header=["coef_std"])
    (out / "summary.json").write_text(json.dumps({
        "seasons": YEARS, "rows": len(df), "heavy_days": int(df.y.sum()),
        "city_heavy_days": int(df[df.is_city].y.sum()),
        "models": [nwp.MODEL_NAMES[m] for m in nwp.MODELS], "cv": "leave-one-season-out",
        "benchmark": bench.round(4).to_dict("records"), "per_model": per, "events": events,
        "blend_coefficients": coefs.round(3).to_dict(),
    }, indent=2, default=float))

    fig, ax = plt.subplots(figsize=(7, 4))
    for name, p in preds.items():
        from sklearn.metrics import precision_recall_curve
        pr, rc, _ = precision_recall_curve(df.y, p)
        ax.plot(rc, pr, label=f"{name.split('(')[0].strip()} (AP {average_precision_score(df.y, p):.2f})")
    ax.set(xlabel="Recall (POD)", ylabel="Precision (1 - FAR)", title="Heavy rain 2022-2024: morning ML vs NWP vs blend")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "pr_curves.png", dpi=140)


if __name__ == "__main__":
    main()
