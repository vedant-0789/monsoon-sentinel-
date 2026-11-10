"""Unit tests for the core logic (no network, no large data)."""

import numpy as np
import pandas as pd
import pytest

from monsoon_sentinel import dispatch, risk
from monsoon_sentinel.data import live
from monsoon_sentinel.evaluation.metrics import best_threshold, contingency, evaluate
from monsoon_sentinel.text import normalise


# ------------------------------------------------------------------ metrics
def test_contingency_scores():
    y = np.array([1, 1, 0, 0, 0, 1])
    yhat = np.array([1, 0, 1, 0, 0, 1])
    c = contingency(y, yhat)
    assert (c["hits"], c["misses"], c["false_alarms"], c["correct_neg"]) == (2, 1, 1, 2)
    assert c["POD"] == pytest.approx(2 / 3)
    assert c["FAR"] == pytest.approx(1 / 3)
    assert c["CSI"] == pytest.approx(2 / 4)


def test_perfect_forecast_has_full_skill():
    y = np.array([0, 0, 1, 1, 0])
    out = evaluate(y, y.astype(float), 0.5, np.full(5, 0.4))
    assert out["POD"] == 1 and out["FAR"] == 0 and out["HSS"] == pytest.approx(1)
    assert out["BSS_vs_clim"] == pytest.approx(1)


def test_best_threshold_separates_classes():
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(500), np.ones(50)]
    p = np.r_[rng.uniform(0, 0.3, 500), rng.uniform(0.6, 1, 50)]
    t = best_threshold(y, p)
    assert 0.3 <= t <= 0.6 + 1e-9


# --------------------------------------------------------------- risk matrix
def test_risk_matrix_extremes():
    cls = pd.Series(["low", "very high", "very high", "low"])
    out = risk.alerts(np.array([0.0, 0.0, 0.9, 0.9]), cls).tolist()
    assert out == ["green", "yellow", "red", "yellow"]


def test_saturated_ground_raises_likelihood():
    lvl_dry = risk.likelihood_level([0.2], [0])[0]
    lvl_wet = risk.likelihood_level([0.2], [150])[0]
    assert lvl_wet == lvl_dry + 1


def test_alert_is_monotone_in_probability():
    cls = pd.Series(["high"] * 5)
    order = [risk.ALERTS.index(a) for a in risk.alerts(np.linspace(0, 1, 5), cls)]
    assert order == sorted(order)


# ------------------------------------------------------- IMD day convention
def test_imd_day_window_is_03_to_03_utc():
    t = pd.date_range("2024-07-24 00:00", "2024-07-26 00:00", freq="h")
    h = pd.DataFrame({"time": t, "lat": 18.5, "lon": 73.75, "precipitation": 1.0})
    d = live.daily_rain_imd_style(h, issue_hour=3).set_index("date").rain_mm
    # hours 04:00 on the 24th .. 03:00 on the 25th (24 values) belong to the 24th
    assert d[pd.Timestamp("2024-07-24")] == 24
    # 00:00..03:00 on the 24th belong to the 23rd
    assert d[pd.Timestamp("2024-07-23")] == 4


# --------------------------------------------------------------- text / NB
def test_place_names_are_masked():
    assert "place" in normalise("Water logging near Sinhagad Road")
    assert "sinhagad" not in normalise("Water logging near Sinhagad Road")
    assert "place" in normalise("कात्रज येथे झाड पडले")


# ----------------------------------------------------------------- dispatch
def test_dispatch_never_exceeds_fleet():
    q = dispatch.QAgent()
    q.Q[..., 1] = 1.0  # a policy that always wants to deploy
    zones = [{"priority_score": 300, "p_flood": 0.9} for _ in range(12)]
    plan = dispatch.plan(q.to_json(), zones)
    assert sum(z["rl_deploy_pump"] for z in plan) == dispatch.K_PUMPS
    assert plan[-1]["pumps_left_after"] == 0


def test_severity_bins():
    assert [dispatch.severity_level(s) for s in [0, 50, 100, 500]] == [0, 1, 2, 3]
