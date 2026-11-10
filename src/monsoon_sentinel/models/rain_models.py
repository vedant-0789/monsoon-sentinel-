"""Candidate classifiers for the 24 h heavy-rain forecast (syllabus Units III-V)."""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import xgboost as xgb
from sklearn.ensemble import BaggingClassifier, RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier


def _scaled(model):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), model)


def _imputed(model):
    return make_pipeline(SimpleImputer(strategy="median"), model)


def candidates(seed: int = 42) -> dict:
    """name -> (estimator, max training rows or None)."""
    return {
        "Logistic Regression": (_scaled(LogisticRegression(C=0.3, max_iter=2000)), None),
        "Gaussian Naive Bayes": (_scaled(GaussianNB()), None),
        "KNN (k=50)": (_scaled(KNeighborsClassifier(n_neighbors=50, weights="distance")), None),
        "SVM (RBF)": (_scaled(SVC(C=1.0, gamma="scale", probability=True, random_state=seed)), 12000),
        "Decision Tree": (_imputed(DecisionTreeClassifier(max_depth=6, min_samples_leaf=50,
                                                          random_state=seed)), None),
        "Random Forest": (_imputed(RandomForestClassifier(n_estimators=500, min_samples_leaf=5,
                                                          max_features="sqrt", n_jobs=-1,
                                                          random_state=seed)), None),
        "Bagging (Decision Trees)": (_imputed(BaggingClassifier(
            DecisionTreeClassifier(max_depth=8, min_samples_leaf=20), n_estimators=200,
            max_samples=0.7, n_jobs=-1, random_state=seed)), None),
        "Neural Network (MLP)": (_scaled(MLPClassifier(
            hidden_layer_sizes=(64, 32), alpha=1e-3, learning_rate_init=1e-3, batch_size=256,
            max_iter=200, early_stopping=True, validation_fraction=0.15, n_iter_no_change=10,
            random_state=seed)), None),
    }


# The deployed model must give exact per-forecast explanations (TreeSHAP), so only
# gradient-boosted trees are deployable; every model is still benchmarked.
DEPLOYABLE = {"XGBoost", "LightGBM"}


def fit_lightgbm(X, y, Xv, yv, seed: int = 42) -> lgb.LGBMClassifier:
    m = lgb.LGBMClassifier(
        n_estimators=3000, learning_rate=0.02, num_leaves=31, min_child_samples=40,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0,
        random_state=seed, verbose=-1,
    )
    m.fit(X, y, eval_set=[(Xv, yv)], eval_metric="binary_logloss",
          callbacks=[lgb.early_stopping(150, verbose=False)])
    return m


def fit_xgboost(X, y, Xv, yv, seed: int = 42) -> xgb.XGBClassifier:
    m = xgb.XGBClassifier(
        n_estimators=3000, learning_rate=0.02, max_depth=5, min_child_weight=5,
        subsample=0.8, colsample_bytree=0.7, reg_lambda=1.0, eval_metric="logloss",
        early_stopping_rounds=150, random_state=seed, n_jobs=-1,
    )
    m.fit(X, y, eval_set=[(Xv, yv)], verbose=False)
    return m


class EnsembleModel:
    """Mean probability of several fitted classifiers (picklable for deployment)."""

    def __init__(self, members):
        self.members = members

    def predict_proba(self, X):
        p = np.mean([m.predict_proba(X)[:, 1] for m in self.members], axis=0)
        return np.column_stack([1 - p, p])


def subsample(X, y, n: int | None, seed: int = 42):
    if n is None or len(y) <= n:
        return X, y
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    k_pos = min(len(pos), int(n * len(pos) / len(y)) + 1)
    idx = np.concatenate([rng.choice(pos, k_pos, replace=False),
                          rng.choice(neg, n - k_pos, replace=False)])
    return X.iloc[idx], y[idx]
