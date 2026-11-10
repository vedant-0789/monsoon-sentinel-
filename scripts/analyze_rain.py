"""Step 3: unsupervised + statistical analyses on the rain feature table.

Covers: PCA, sequential feature selection, K-means / hierarchical / DBSCAN
weather regimes (with homogeneity & completeness), HMM monsoon active/break
phases, Apriori rules for heavy rain, and rain-amount regression.

Usage:  python scripts/analyze_rain.py      (run after train_rain.py)
"""

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from hmmlearn.hmm import GaussianHMM  # noqa: E402
from mlxtend.frequent_patterns import apriori, association_rules  # noqa: E402
from scipy.cluster.hierarchy import fcluster, linkage  # noqa: E402
from sklearn.cluster import DBSCAN, KMeans  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.feature_selection import SequentialFeatureSelector  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LinearRegression, LogisticRegression  # noqa: E402
from sklearn.metrics import (completeness_score, homogeneity_score,  # noqa: E402
                             mean_absolute_error, r2_score, root_mean_squared_error,
                             silhouette_score)
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import LinearSVR  # noqa: E402

from monsoon_sentinel.config import load_config  # noqa: E402
from monsoon_sentinel.features import rain_features as rf  # noqa: E402

warnings.filterwarnings("ignore")


def main():
    cfg = load_config()
    out = cfg.path("reports") / "rain" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(cfg.path("processed") / "rain_features.parquet")
    s = cfg["split"]
    train = df[df.year.between(*s["train"])]
    test = df[df.year.between(*s["test"])]
    feats = [c for c in rf.feature_columns(df) if c != "clim_heavy_freq"]
    summary = {}

    prep = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
    Ztr = prep.fit_transform(train[feats])
    Zte = prep.transform(test[feats])

    # ------------------------------------------------------------- PCA
    pca = PCA().fit(Ztr)
    evr = pca.explained_variance_ratio_
    k90 = int(np.searchsorted(np.cumsum(evr), 0.90) + 1)
    pcs = pca.transform(Ztr)
    pca_tab = pd.DataFrame({
        "PC": [f"PC{i+1}" for i in range(10)],
        "variance": pca.explained_variance_[:10],
        "std_dev": np.sqrt(pca.explained_variance_[:10]),
        "explained_ratio": evr[:10],
        "cumulative": np.cumsum(evr)[:10],
        "top_loadings": [", ".join(pd.Series(pca.components_[i], index=feats)
                                   .abs().nlargest(4).index) for i in range(10)],
    })
    pca_tab.to_csv(out / "pca_components.csv", index=False)
    summary["pca_components_for_90pct_variance"] = k90
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(range(1, 21), evr[:20])
    ax.plot(range(1, 21), np.cumsum(evr)[:20], "r-o", ms=3)
    ax.set(xlabel="Principal component", ylabel="Explained variance ratio", title="PCA scree plot")
    fig.tight_layout(); fig.savefig(out / "pca_scree.png", dpi=150); plt.close(fig)

    # does a PCA-compressed model lose skill?
    from sklearn.metrics import average_precision_score
    lr = LogisticRegression(C=0.3, max_iter=2000)
    ap_full = average_precision_score(test.y_heavy, lr.fit(Ztr, train.y_heavy).predict_proba(Zte)[:, 1])
    pk = PCA(n_components=k90).fit(Ztr)
    ap_pca = average_precision_score(
        test.y_heavy, lr.fit(pk.transform(Ztr), train.y_heavy).predict_proba(pk.transform(Zte))[:, 1])
    summary["logreg_PR_AUC_all_features"] = ap_full
    summary["logreg_PR_AUC_pca_90pct"] = ap_pca

    # ------------------------------------- sequential feature selection
    sub = train.sample(min(8000, len(train)), random_state=0)
    Zs = prep.transform(sub[feats])
    sel = {}
    for direction in ["forward", "backward"]:
        if direction == "backward":  # SBS from the 20 most variable features to keep runtime sane
            pool = pd.Series(np.abs(LogisticRegression(C=0.3, max_iter=2000)
                                    .fit(Zs, sub.y_heavy).coef_[0]), index=feats).nlargest(20).index
            idx = [feats.index(f) for f in pool]
        else:
            idx = list(range(len(feats)))
        sfs = SequentialFeatureSelector(LogisticRegression(C=0.3, max_iter=2000), n_features_to_select=10,
                                        direction=direction, scoring="average_precision", cv=3, n_jobs=-1)
        sfs.fit(Zs[:, idx], sub.y_heavy)
        sel[direction] = [feats[idx[i]] for i in np.flatnonzero(sfs.get_support())]
    # filter method: mutual information with the target (model-free)
    from sklearn.feature_selection import mutual_info_classif
    mi = pd.Series(mutual_info_classif(Zs, sub.y_heavy, random_state=0), index=feats)
    sel["filter_mutual_info"] = mi.nlargest(10).index.tolist()
    # embedded method: L1-regularised logistic regression keeps a sparse subset
    l1 = LogisticRegression(penalty="l1", solver="liblinear", C=0.02, class_weight="balanced").fit(Zs, sub.y_heavy)
    coef = pd.Series(np.abs(l1.coef_[0]), index=feats)
    sel["embedded_L1"] = coef[coef > 0].sort_values(ascending=False).head(10).index.tolist()
    sel["embedded_L1_kept"] = int((coef > 0).sum())
    # how well does each 10-feature subset do on the unseen test years?
    sub_scores = {}
    for name in ["forward", "backward", "filter_mutual_info", "embedded_L1"]:
        cols = [feats.index(f) for f in sel[name]]
        m = LogisticRegression(C=0.3, max_iter=2000).fit(Ztr[:, cols], train.y_heavy)
        sub_scores[name] = average_precision_score(test.y_heavy, m.predict_proba(Zte[:, cols])[:, 1])
    sel["test_PR_AUC_logreg_10_features"] = {k: round(v, 3) for k, v in sub_scores.items()}
    (out / "feature_selection.json").write_text(json.dumps(sel, indent=2))
    summary["SFS_top10"] = sel["forward"]
    summary["SBS_top10"] = sel["backward"]
    summary["filter_MI_top10"] = sel["filter_mutual_info"]
    summary["embedded_L1_top10"] = sel["embedded_L1"]
    summary["feature_subset_test_PR_AUC"] = sel["test_PR_AUC_logreg_10_features"]

    # ----------------------------------- weather regimes (clustering)
    syn_cols = ["dom_tcwv", "dom_u", "dom_mslp", "dom_pr24", "ghats_u", "ghats_tcwv", "dom_rain_lag1_mean"]
    daily = df.groupby("date").agg({**{c: "first" for c in syn_cols}, "y_heavy": "max", "rain_mm": "mean"})
    daily = daily.dropna()
    Zd = StandardScaler().fit_transform(daily[syn_cols])
    sil = {k: silhouette_score(Zd, KMeans(k, n_init=10, random_state=0).fit_predict(Zd),
                               sample_size=3000, random_state=0) for k in range(2, 9)}
    inertia = {k: KMeans(k, n_init=10, random_state=0).fit(Zd).inertia_ for k in range(1, 9)}
    k_best = max(sil, key=sil.get)
    km = KMeans(k_best, n_init=10, random_state=0).fit(Zd)
    daily["regime_kmeans"] = km.labels_
    hc = fcluster(linkage(Zd, method="ward"), t=k_best, criterion="maxclust")
    daily["regime_hier"] = hc
    # DBSCAN as an anomaly detector: days outside the dense core = unusual synoptic states
    from sklearn.neighbors import NearestNeighbors
    kdist = np.sort(NearestNeighbors(n_neighbors=15).fit(Zd).kneighbors(Zd)[0][:, -1])
    eps = float(np.quantile(kdist, 0.95))
    db = DBSCAN(eps=eps, min_samples=15).fit(Zd)
    daily["regime_dbscan"] = db.labels_
    rain_class = pd.cut(daily.rain_mm, [-1, 2.5, 15.5, 64.5, 1e9], labels=["dry", "light", "moderate", "heavy"])
    regimes = {
        "k_by_silhouette": k_best,
        "silhouette": {int(k): round(v, 3) for k, v in sil.items()},
        "kmeans": {"homogeneity": homogeneity_score(rain_class, km.labels_),
                   "completeness": completeness_score(rain_class, km.labels_)},
        "hierarchical": {"homogeneity": homogeneity_score(rain_class, hc),
                         "completeness": completeness_score(rain_class, hc)},
        "dbscan": {"eps": eps,
                   "clusters": int(len(set(db.labels_)) - (1 if -1 in db.labels_ else 0)),
                   "anomalous_days": int((db.labels_ == -1).sum()),
                   "heavy_rain_rate_anomalous_days": float(daily.y_heavy[db.labels_ == -1].mean()),
                   "heavy_rain_rate_normal_days": float(daily.y_heavy[db.labels_ != -1].mean())},
        "heavy_rain_rate_by_kmeans_regime": daily.groupby("regime_kmeans").y_heavy.mean().round(3).to_dict(),
    }
    (out / "weather_regimes.json").write_text(json.dumps(regimes, indent=2, default=float))
    summary["weather_regimes"] = regimes
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    axs[0].plot(list(inertia), list(inertia.values()), "o-")
    axs[0].set(title="Elbow (K-means inertia)", xlabel="k")
    p2 = PCA(2).fit_transform(Zd)
    sc = axs[1].scatter(p2[:, 0], p2[:, 1], c=km.labels_, s=4, cmap="tab10")
    axs[1].set(title=f"K-means weather regimes (k={k_best}) on PC1-PC2")
    fig.tight_layout(); fig.savefig(out / "weather_regimes.png", dpi=150); plt.close(fig)

    # ------------------------------------ HMM: monsoon active / break
    dom_rain = df.groupby("date").rain_mm.mean()
    phases = []
    lengths, seqs = [], []
    for y, sgrp in dom_rain.groupby(dom_rain.index.year):
        seqs.append(np.log1p(sgrp.values).reshape(-1, 1))
        lengths.append(len(sgrp))
    X = np.vstack(seqs)
    # Explicit "sticky" initialisation: monsoon phases persist for days. hmmlearn's default
    # initialisation converges to a meaningless 0-1-2 cycle on this series.
    hmm = GaussianHMM(n_components=3, covariance_type="diag", n_iter=500, tol=1e-4,
                      random_state=0, init_params="", params="stmc")
    hmm.startprob_ = np.array([0.4, 0.4, 0.2])
    hmm.transmat_ = np.full((3, 3), 0.05) + np.eye(3) * 0.85
    hmm.means_ = np.quantile(X, [0.2, 0.55, 0.9]).reshape(-1, 1)
    hmm.covars_ = np.full((3, 1), X.var() / 3)
    hmm.fit(X, lengths)
    states = hmm.predict(X, lengths)
    order = np.argsort(hmm.means_.ravel())
    names = {order[0]: "dry", order[1]: "break", order[2]: "active"}
    ph = pd.DataFrame({"date": dom_rain.index, "domain_rain": dom_rain.values,
                       "phase": [names[s] for s in states]})
    ph.to_csv(out / "hmm_monsoon_phases.csv", index=False)
    heavy_by_phase = ph.merge(daily[["y_heavy"]], left_on="date", right_index=True).groupby("phase").y_heavy.mean()
    summary["hmm"] = {
        "state_mean_rain_mm": {names[i]: float(np.expm1(hmm.means_[i, 0])) for i in range(3)},
        "transition_matrix": pd.DataFrame(hmm.transmat_, index=[names[i] for i in range(3)],
                                          columns=[names[i] for i in range(3)]).round(3).to_dict("index"),
        "share_of_days": ph.phase.value_counts(normalize=True).round(3).to_dict(),
        "heavy_rain_rate_by_phase": heavy_by_phase.round(3).to_dict(),
    }
    yr = ph[ph.date.dt.year == 2024]
    fig, ax = plt.subplots(figsize=(10, 3))
    cmap = {"dry": "#f0ad4e", "break": "#5bc0de", "active": "#d9534f"}
    ax.bar(yr.date, yr.domain_rain, color=[cmap[p] for p in yr.phase])
    ax.set(title="HMM monsoon phases, 2024 (orange=dry, blue=break/weak, red=active)", ylabel="Domain mean rain (mm)")
    fig.tight_layout(); fig.savefig(out / "hmm_phases_2024.png", dpi=150); plt.close(fig)

    # ------------------------------------------- Apriori association rules
    tr = train.copy()
    q = lambda c: tr[c] >= tr[c].quantile(0.8)  # noqa: E731
    basket = pd.DataFrame({
        "tcwv_high": q("tcwv_now"),
        "westerly_strong": q("u_now"),
        "moist_flux_high": q("moist_flux_u"),
        "pressure_falling": tr["mslp_tend24"] <= tr["mslp_tend24"].quantile(0.2),
        "rain_yesterday_heavy": tr["rain_lag1"] >= cfg["thresholds"]["heavy"],
        "wet_week": q("rain_sum7"),
        "ghats_cell": tr["lon"] <= 73.5,
        "cloudy": q("cc_mean24"),
        "HEAVY_RAIN": tr["y_heavy"] == 1,
    })
    fi = apriori(basket, min_support=0.01, use_colnames=True, max_len=4)
    rules = association_rules(fi, metric="confidence", min_threshold=0.2)
    rules = rules[rules.consequents.apply(lambda s: s == frozenset({"HEAVY_RAIN"}))]
    rules = rules.sort_values(["lift", "confidence"], ascending=False).head(15)
    rules = rules.assign(antecedents=rules.antecedents.apply(lambda s: " + ".join(sorted(s))))
    rules[["antecedents", "support", "confidence", "lift"]].to_csv(out / "apriori_rules.csv", index=False)
    summary["apriori_top_rules"] = rules[["antecedents", "support", "confidence", "lift"]].head(5).round(3).to_dict("records")
    summary["base_rate_heavy"] = float(basket.HEAVY_RAIN.mean())

    # ---------------------------------------- rain-amount regression
    reg = {}
    ytr, yte = np.log1p(train.rain_mm), test.rain_mm
    for name, m in {"Linear Regression": LinearRegression(),
                    "Linear SVR": LinearSVR(C=0.1, max_iter=20000, random_state=0),
                    "Random Forest Regressor": RandomForestRegressor(300, min_samples_leaf=5, n_jobs=-1,
                                                                     random_state=0)}.items():
        m.fit(Ztr, ytr)
        # predict in log space, clip to the observed training range, then back-transform
        p = np.expm1(np.clip(m.predict(Zte), 0, ytr.max()))
        reg[name] = {"MAE_mm": mean_absolute_error(yte, p), "RMSE_mm": root_mean_squared_error(yte, p),
                     "R2": r2_score(yte, p),
                     "MAE_on_heavy_days_mm": mean_absolute_error(yte[test.y_heavy == 1], p[test.y_heavy == 1])}
    summary["regression"] = reg

    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
