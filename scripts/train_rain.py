"""Step 2: build features, benchmark all classifiers, explain the best one.

Usage:  python scripts/train_rain.py
Outputs: reports/rain/*.csv|md|png, models/rain_model.joblib
"""

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import joblib  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402

from monsoon_sentinel.config import load_config  # noqa: E402
from monsoon_sentinel.data import era5, imd  # noqa: E402
from monsoon_sentinel.evaluation.metrics import best_threshold, evaluate  # noqa: E402
from monsoon_sentinel.features import rain_features as rf  # noqa: E402
from monsoon_sentinel.models import rain_models as rm  # noqa: E402

warnings.filterwarnings("ignore")


EnsembleModel = rm.EnsembleModel


def main():
    cfg = load_config()
    reports = cfg.path("reports") / "rain"
    reports.mkdir(exist_ok=True)
    models_dir = cfg.path("models")

    # ---------------------------------------------------------------- data
    feat_file = cfg.path("processed") / "rain_features.parquet"
    if feat_file.exists():
        df = pd.read_parquet(feat_file)
    else:
        print("Building features ...", flush=True)
        df = rf.build(cfg, imd.load_cells(cfg), era5.load_all(cfg))
        df.to_parquet(feat_file, index=False)

    s = cfg["split"]
    part = np.select(
        [df.year.between(*s["train"]), df.year.between(*s["val"]), df.year.between(*s["test"])],
        ["train", "val", "test"], default="none",
    )
    df = rf.add_climatology(df, pd.Series(part == "train", index=df.index))
    df["part"] = part
    feats = rf.feature_columns(df.drop(columns=["part"]))
    city = set(map(tuple, cfg["grid"]["city_cells"]))
    df["is_city"] = [(a, b) in city for a, b in zip(df.lat, df.lon)]

    tr, va, te = (df[df.part == p] for p in ["train", "val", "test"])
    Xtr, Xva, Xte = tr[feats], va[feats], te[feats]
    ytr, yva, yte = tr.y_heavy.values, va.y_heavy.values, te.y_heavy.values
    print(f"rows train/val/test = {len(tr)}/{len(va)}/{len(te)}; "
          f"heavy-rain rate = {ytr.mean():.3f}/{yva.mean():.3f}/{yte.mean():.3f}; "
          f"features = {len(feats)}", flush=True)

    clim_va = va.clim_heavy_freq.fillna(ytr.mean()).values
    clim_te = te.clim_heavy_freq.fillna(ytr.mean()).values

    # --------------------------------------------------------- predictions
    preds = {
        "Climatology (baseline)": (clim_va, clim_te),
        "Persistence (baseline)": ((va.rain_lag1 >= cfg["thresholds"]["heavy"]).astype(float).values,
                                   (te.rain_lag1 >= cfg["thresholds"]["heavy"]).astype(float).values),
    }
    fitted = {}
    for name, (est, nmax) in rm.candidates().items():
        print(f"  training {name} ...", flush=True)
        Xs, ys = rm.subsample(Xtr, ytr, nmax)
        est.fit(Xs, ys)
        preds[name] = (est.predict_proba(Xva)[:, 1], est.predict_proba(Xte)[:, 1])
        fitted[name] = est

    print("  training LightGBM ...", flush=True)
    imp = Xtr.median()
    lgbm = rm.fit_lightgbm(Xtr, ytr, Xva, yva)
    preds["LightGBM"] = (lgbm.predict_proba(Xva)[:, 1], lgbm.predict_proba(Xte)[:, 1])
    fitted["LightGBM"] = lgbm
    print("  training XGBoost ...", flush=True)
    xgbm = rm.fit_xgboost(Xtr, ytr, Xva, yva)
    preds["XGBoost"] = (xgbm.predict_proba(Xva)[:, 1], xgbm.predict_proba(Xte)[:, 1])
    fitted["XGBoost"] = xgbm

    ens = ["LightGBM", "XGBoost", "Random Forest"]
    preds["Ensemble (LGBM+XGB+RF)"] = tuple(np.mean([preds[m][i] for m in ens], axis=0) for i in (0, 1))

    # ---------------------------------------------------------- evaluation
    rows = []
    city_te, city_va = te.is_city.values, va.is_city.values
    for name, (pv, pt) in preds.items():
        binary = len(np.unique(pv)) <= 2
        thr = 0.5 if binary else best_threshold(yva, pv)
        # A separate city threshold was tried but overfits: val has only ~25 city heavy-rain
        # days. One region-wide threshold is used; city scores are reported separately.
        thr_city = thr
        r_val = evaluate(yva, pv, thr, clim_va)
        r_val_city = evaluate(yva[city_va], pv[city_va], thr_city, clim_va[city_va])
        r_all = evaluate(yte, pt, thr, clim_te)
        r_city = evaluate(yte[city_te], pt[city_te], thr_city, clim_te[city_te])
        rows.append({"model": name, "val_PR_AUC": r_val["PR_AUC"], "val_city_PR_AUC": r_val_city["PR_AUC"],
                     "val_Brier": r_val["Brier"],
                     **{k: r_all[k] for k in ["ROC_AUC", "PR_AUC", "Brier", "BSS_vs_clim",
                                              "POD", "FAR", "CSI", "HSS", "F1", "threshold"]},
                     "city_ROC_AUC": r_city["ROC_AUC"], "city_PR_AUC": r_city["PR_AUC"],
                     "city_POD": r_city["POD"], "city_FAR": r_city["FAR"],
                     "city_CSI": r_city["CSI"], "city_threshold": thr_city})
    # Model selection uses validation years only (test years never touched):
    # best val PR-AUC; models within 0.01 of it are a statistical tie, broken by val Brier.
    bench = pd.DataFrame(rows).sort_values("val_PR_AUC", ascending=False)
    top = bench.val_PR_AUC.max()
    bench["tied_best"] = bench.val_PR_AUC >= top - 0.01
    bench.to_csv(reports / "benchmark.csv", index=False)
    (reports / "benchmark.md").write_text(bench.round(3).to_markdown(index=False), encoding="utf-8")
    print("\n" + bench.round(3).to_string(index=False), flush=True)

    # deployable model = best non-baseline entry by validation selection score
    fitted["Ensemble (LGBM+XGB+RF)"] = EnsembleModel([fitted[m] for m in ens])
    # deployable = exact explanations (see rain_models.DEPLOYABLE); best val PR-AUC among them,
    # near-ties (0.01) broken by validation Brier score
    dep = bench[bench.model.isin(rm.DEPLOYABLE)]
    dep = dep[dep.val_PR_AUC >= dep.val_PR_AUC.max() - 0.01]
    best = dep.sort_values("val_Brier").model.iloc[0]
    b = bench.set_index("model").loc[best]
    best_thr, best_thr_city = float(b["threshold"]), float(b["city_threshold"])
    joblib.dump({"model": fitted[best], "features": feats, "threshold": best_thr,
                 "city_threshold": best_thr_city, "city_cells": cfg["grid"]["city_cells"],
                 "name": best, "train_median": imp,
                 "climatology": df[df.part == "train"].groupby(["lat", "lon", "month"]).y_heavy.mean()},
                models_dir / "rain_model.joblib")
    (reports / "best_model.json").write_text(json.dumps(
        {"best_model": best, "threshold": best_thr, "city_threshold": best_thr_city,
         "test_metrics": b.to_dict()}, indent=2, default=float))
    print(f"\nSelected model (validation score): {best}", flush=True)

    # ----------------------------------------------------- explainability
    print("Computing SHAP ...", flush=True)
    sample = Xte.sample(400, random_state=0)
    background = shap.sample(Xtr.fillna(imp), 100, random_state=0)
    explainer = shap.Explainer(lambda X: fitted[best].predict_proba(
        pd.DataFrame(X, columns=feats))[:, 1], background, algorithm="permutation")
    sv = explainer(sample.fillna(imp), max_evals=2 * len(feats) + 1).values
    pd.DataFrame({"feature": feats, "mean_abs_shap": np.abs(sv).mean(0)}) \
        .sort_values("mean_abs_shap", ascending=False) \
        .to_csv(reports / "shap_importance.csv", index=False)
    plt.figure()
    shap.summary_plot(sv, sample, max_display=20, show=False)
    plt.tight_layout()
    plt.savefig(reports / "shap_summary.png", dpi=150)
    plt.close("all")

    # ------------------------------------------------------- reliability
    fig, ax = plt.subplots(figsize=(5, 5))
    for name in [best, "Ensemble (LGBM+XGB+RF)", "Logistic Regression"]:
        fp, mp = calibration_curve(yte, preds[name][1], n_bins=10, strategy="quantile")
        ax.plot(mp, fp, marker="o", label=name)
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set(xlabel="Forecast probability", ylabel="Observed frequency",
           title="Reliability (test 2021-2024)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(reports / "reliability.png", dpi=150)

    # ------------------------------------- case study: Pune, July 2024
    te = te.assign(p=preds[best][1])
    case = te[te.is_city & (te.date.between("2024-07-15", "2024-08-05"))]
    case = case.groupby("date").agg(p=("p", "max"), rain=("rain_mm", "max")).reset_index()
    case.to_csv(reports / "case_pune_jul2024.csv", index=False)
    fig, ax1 = plt.subplots(figsize=(9, 4))
    ax1.bar(case.date, case.rain, color="#4a90d9", label="Observed rain (IMD, mm)")
    ax1.axhline(cfg["thresholds"]["heavy"], color="#4a90d9", ls=":", lw=1)
    ax1.set_ylabel("Rain (mm / 24 h)")
    ax2 = ax1.twinx()
    ax2.plot(case.date, case.p, color="#d9534f", marker="o", label="Heavy-rain probability")
    ax2.axhline(best_thr_city, color="#d9534f", ls="--", lw=1)
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("Forecast probability")
    ax1.set_title("Pune city cells, 15 Jul - 5 Aug 2024 (unseen test period)")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(reports / "case_pune_jul2024.png", dpi=150)
    print("Done. Reports in", reports)


if __name__ == "__main__":
    main()
