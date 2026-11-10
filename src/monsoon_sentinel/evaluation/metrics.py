"""Forecast-verification metrics for rare binary events (WMO / IMD practice)."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def contingency(y: np.ndarray, yhat: np.ndarray) -> dict:
    y, yhat = np.asarray(y).astype(bool), np.asarray(yhat).astype(bool)
    hits = int(np.sum(y & yhat))
    misses = int(np.sum(y & ~yhat))
    fa = int(np.sum(~y & yhat))
    cn = int(np.sum(~y & ~yhat))
    n = hits + misses + fa + cn
    pod = hits / (hits + misses) if hits + misses else np.nan        # = recall
    far = fa / (hits + fa) if hits + fa else np.nan                   # = 1 - precision
    csi = hits / (hits + misses + fa) if hits + misses + fa else np.nan
    exp = ((hits + misses) * (hits + fa) + (cn + misses) * (cn + fa)) / n
    hss = (hits + cn - exp) / (n - exp) if n != exp else np.nan
    precision = hits / (hits + fa) if hits + fa else np.nan
    f1 = 2 * precision * pod / (precision + pod) if precision and pod else 0.0
    return dict(hits=hits, misses=misses, false_alarms=fa, correct_neg=cn,
                POD=pod, FAR=far, CSI=csi, HSS=hss, precision=precision, F1=f1)


def best_threshold(y: np.ndarray, p: np.ndarray, metric: str = "CSI") -> float:
    grid = np.unique(np.quantile(p, np.linspace(0.5, 0.999, 300)))
    scores = [contingency(y, p >= t)[metric] for t in grid]
    return float(grid[int(np.nanargmax(scores))])


def evaluate(y: np.ndarray, p: np.ndarray, threshold: float, p_clim: np.ndarray) -> dict:
    out = {
        "ROC_AUC": roc_auc_score(y, p) if len(np.unique(p)) > 1 else 0.5,
        "PR_AUC": average_precision_score(y, p),
        "Brier": brier_score_loss(y, p),
    }
    bs_ref = brier_score_loss(y, p_clim)
    out["BSS_vs_clim"] = 1 - out["Brier"] / bs_ref
    out["threshold"] = threshold
    out.update(contingency(y, p >= threshold))
    return out
