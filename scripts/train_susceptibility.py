"""Step 5: street-level waterlogging susceptibility for Pune.

Positive-unlabelled (PU) learning: known hotspots are positives, road locations
are unlabelled (most are dry, a few are unreported hotspots). Evaluated with
spatial block cross-validation so the model is always scored on unseen areas.

Usage:  python scripts/train_susceptibility.py
Outputs: reports/urban/*, models/susceptibility.joblib, data/processed/road_susceptibility.parquet
"""

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import geopandas as gpd  # noqa: E402
import joblib  # noqa: E402
import lightgbm as lgb  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.naive_bayes import GaussianNB  # noqa: E402
from sklearn.neighbors import KNeighborsClassifier  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402

from monsoon_sentinel.config import load_config  # noqa: E402
from monsoon_sentinel.data import osm  # noqa: E402
from monsoon_sentinel.features import urban_features as uf  # noqa: E402

warnings.filterwarnings("ignore")
SEED = 42


# Compact, physically motivated feature set (with only ~30 positives, fewer features generalise
# better). Monotone direction: +1 = more of it -> more risk, -1 = less of it -> more risk.
PHYS = {"log_dist_river": -1, "log_dist_nala": -1, "sink_depth_smooth": 1,
        "hand_smooth": -1, "road_density_500m": 1, "tpi_300m": -1}
PHYS_F = list(PHYS)


def models():
    """name -> (estimator, feature list)."""
    s = lambda m: make_pipeline(StandardScaler(), m)  # noqa: E731
    all_f = uf.FEATURES
    return {
        "Logistic Regression (all 15)": (s(LogisticRegression(C=0.3, class_weight="balanced", max_iter=3000)), all_f),
        "Gaussian Naive Bayes (all 15)": (s(GaussianNB()), all_f),
        "KNN k=25 (all 15)": (s(KNeighborsClassifier(25, weights="distance")), all_f),
        "SVM RBF (all 15)": (s(SVC(C=1.0, class_weight="balanced", probability=True, random_state=SEED)), all_f),
        "Random Forest (all 15)": (RandomForestClassifier(500, min_samples_leaf=3, class_weight="balanced_subsample",
                                                          max_features="sqrt", n_jobs=-1, random_state=SEED), all_f),
        "LightGBM (all 15)": (lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=8,
                                                 min_child_samples=5, subsample=0.8, subsample_freq=1,
                                                 colsample_bytree=0.8, class_weight="balanced",
                                                 random_state=SEED, verbose=-1), all_f),
        "Logistic Regression (physics 6)": (s(LogisticRegression(C=0.1, class_weight="balanced", max_iter=3000)),
                                            PHYS_F),
        "Random Forest (physics 6)": (RandomForestClassifier(500, min_samples_leaf=5, class_weight="balanced_subsample",
                                                             max_features=2, n_jobs=-1, random_state=SEED), PHYS_F),
        "Monotone LightGBM (physics 6)": (lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.03, num_leaves=4, min_child_samples=10,
            monotone_constraints=[PHYS[f] for f in PHYS_F], class_weight="balanced",
            subsample=0.8, subsample_freq=1, random_state=SEED, verbose=-1), PHYS_F),
    }


def fit(model, X, y, w):
    """Fit with sample weights where the (final) estimator supports them."""
    import inspect

    from sklearn.pipeline import Pipeline
    est = model.steps[-1][1] if isinstance(model, Pipeline) else model
    if "sample_weight" not in inspect.signature(est.fit).parameters:
        return model.fit(X, y)
    if isinstance(model, Pipeline):
        return model.fit(X, y, **{f"{model.steps[-1][0]}__sample_weight": w})
    return model.fit(X, y, sample_weight=w)


def capture_at(scores_pos, scores_unl, frac):
    """Share of hotspots ranked within the top `frac` of road locations (ties get average rank)."""
    from scipy.stats import rankdata
    allv = np.concatenate([scores_pos, scores_unl])
    r = rankdata(allv) / len(allv)
    return float(np.mean(r[: len(scores_pos)] > 1 - frac))


def main():
    cfg = load_config()
    out = cfg.path("reports") / "urban"
    out.mkdir(exist_ok=True)
    cache = cfg.path("processed") / "urban_points.parquet"

    roads = osm.load_lines(cfg.path("raw") / "osm" / "roads.json")
    ww = osm.load_lines(cfg.path("raw") / "osm" / "waterways.json")
    if cache.exists():
        pts = gpd.read_parquet(cache)
    else:
        print("Building candidate road points + features ...", flush=True)
        cand = uf.road_candidates(cfg, roads)
        hot = uf.hotspot_points(cfg, pd.read_csv(cfg.path("raw").parent / "labels" / "pune_hotspots.csv"))
        # unlabelled points within 300 m of a hotspot are ambiguous -> drop them
        near = cand.geometry.apply(lambda p: hot.distance(p).min() < 300)
        cand = cand[~near].assign(label=0, weight=1.0, name=None, hazard_type=None)
        hot = hot.assign(label=1, highway=None)[["geometry", "label", "weight", "name", "hazard_type", "highway"]]
        pts = pd.concat([hot, cand[["geometry", "label", "weight", "name", "hazard_type", "highway"]]],
                        ignore_index=True)
        pts = gpd.GeoDataFrame(pts, geometry="geometry", crs=uf.UTM)
        feats = uf.build(cfg, pts, roads, ww)
        pts = pd.concat([pts, feats], axis=1)
        pts.to_parquet(cache)
    print(f"points: {int(pts.label.sum())} hotspots, {int((pts.label == 0).sum())} road locations", flush=True)

    X = pts[uf.FEATURES].astype(float).fillna(pts[uf.FEATURES].median())
    y = pts.label.values
    w = pts.weight.values
    blk = cfg["urban"]["spatial_block_km"] * 1000
    groups = (pts.geometry.x // blk).astype(int).astype(str) + "_" + (pts.geometry.y // blk).astype(int).astype(str)

    # spatial CV: whole blocks held out; folds balanced by hotspot count
    pos_blocks = groups[y == 1].value_counts()
    rng = np.random.default_rng(SEED)
    blocks = groups.unique()
    order = list(pos_blocks.index) + [b for b in rng.permutation(blocks) if b not in pos_blocks.index]
    K = 5
    fold_of = {b: i % K for i, b in enumerate(order)}
    folds = groups.map(fold_of).values

    # ---------------------------------------- baselines: single physical indices
    oof = {
        "Baseline: low HAND": -X.hand_smooth.values,
        "Baseline: high TWI": X.twi.values,
        "Baseline: flow accumulation": X.log_flow_acc.values,
        "Baseline: near river/nala": -np.minimum(X.log_dist_river, X.log_dist_nala).values,
    }
    oof["Baseline: near nala"] = -X.log_dist_nala.values
    for name, (m, F) in models().items():
        p = np.zeros(len(y))
        for k in range(K):
            tr, te = folds != k, folds == k
            fit(m, X.loc[tr, F], y[tr], w[tr])
            p[te] = m.predict_proba(X.loc[te, F])[:, 1]
        oof[name] = p
        print(f"  {name} done", flush=True)

    rows = []
    for name, s in oof.items():
        sp, su = s[y == 1], s[y == 0]
        fold_auc = [roc_auc_score(y[folds == k], s[folds == k]) for k in range(K)
                    if y[folds == k].sum() > 0]
        rows.append({"model": name, "ROC_AUC": roc_auc_score(y, s),
                     "AUC_fold_mean": np.mean(fold_auc), "AUC_fold_std": np.std(fold_auc),
                     "capture_top5pct": capture_at(sp, su, 0.05),
                     "capture_top10pct": capture_at(sp, su, 0.10),
                     "capture_top20pct": capture_at(sp, su, 0.20)})
    bench = pd.DataFrame(rows).sort_values("ROC_AUC", ascending=False)
    bench.to_csv(out / "susceptibility_benchmark.csv", index=False)
    (out / "susceptibility_benchmark.md").write_text(bench.round(3).to_markdown(index=False), encoding="utf-8")
    print("\n" + bench.round(3).to_string(index=False), flush=True)

    # --------------------------- final model = best ML model, refit on all data
    best = next(m for m in bench.model if not m.startswith("Baseline"))
    est, F = models()[best]
    final = fit(est, X[F], y, w)
    # bootstrap ensemble -> uncertainty of each location's score
    boots = []
    for b in range(30):
        idx = rng.choice(len(y), len(y), replace=True)
        mb = fit(models()[best][0], X[F].iloc[idx], y[idx], w[idx])
        boots.append(mb.predict_proba(X[F])[:, 1])
    boots = np.array(boots)
    score = final.predict_proba(X[F])[:, 1]
    pct = pd.Series(score).rank(pct=True).values  # percentile among all road locations
    res = pts[["geometry", "label", "name", "highway"]].copy()
    res["susceptibility"] = score
    res["percentile"] = pct
    res["p10"] = np.quantile(boots, 0.1, axis=0)
    res["p90"] = np.quantile(boots, 0.9, axis=0)
    res["risk_class"] = pd.cut(pct, [0, 0.6, 0.85, 0.95, 1.0], labels=["low", "moderate", "high", "very high"],
                               include_lowest=True)
    res = res.to_crs("EPSG:4326")
    res.to_parquet(cfg.path("processed") / "road_susceptibility.parquet")
    joblib.dump({"model": final, "features": F, "name": best,
                 "median": pts[F].median()}, cfg.path("models") / "susceptibility.joblib")

    # explainability: permutation importance (AUC drop when a feature is shuffled), averaged
    imp = {}
    base_auc = roc_auc_score(y, final.predict_proba(X[F])[:, 1])
    for f in F:
        drops = []
        for _ in range(10):
            Xp = X[F].copy()
            Xp[f] = rng.permutation(Xp[f].values)
            drops.append(base_auc - roc_auc_score(y, final.predict_proba(Xp)[:, 1]))
        imp[f] = float(np.mean(drops))
    imp = pd.Series(imp).sort_values(ascending=False)
    imp.to_csv(out / "feature_importance.csv", header=["auc_drop"])

    summary = {"best_model": best, "n_hotspots": int(y.sum()), "n_road_locations": int((y == 0).sum()),
               "spatial_folds": K, "block_km": cfg["urban"]["spatial_block_km"],
               "metrics": bench.set_index("model").loc[best].to_dict(),
               "top_features": imp.head(6).round(4).to_dict(),
               "risk_class_counts": res.risk_class.value_counts().to_dict()}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=float))

    # ------------------------------------------------------------- map
    fig, ax = plt.subplots(figsize=(9, 9))
    u = res[res.label == 0]
    order_ = np.argsort(u.percentile.values)
    sc = ax.scatter(u.geometry.x.values[order_], u.geometry.y.values[order_], c=u.percentile.values[order_],
                    s=2, cmap="RdYlBu_r", vmin=0.3, vmax=1)
    hs = res[res.label == 1]
    ax.scatter(hs.geometry.x, hs.geometry.y, facecolor="none", edgecolor="k", s=60, lw=1.2,
               label="known hotspots")
    ww.plot(ax=ax, color="#2b8cbe", lw=0.6, alpha=0.7)
    b = cfg["urban"]["bbox"]
    ax.set(xlim=(b["lon_min"], b["lon_max"]), ylim=(b["lat_min"], b["lat_max"]),
           title=f"Pune street-level waterlogging susceptibility ({best})")
    plt.colorbar(sc, ax=ax, shrink=0.7, label="percentile among road locations")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "susceptibility_map.png", dpi=130)
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
