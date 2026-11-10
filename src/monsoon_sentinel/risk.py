"""Daily street-level waterlogging alert = rain likelihood x location impact.

Follows the impact-based-forecasting risk matrix used by IMD / WMO:
likelihood (from the rain module) and impact (from street susceptibility)
are each binned to 4 levels and combined into a colour-coded alert.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LIKELIHOOD_BINS = [0.0, 0.10, 0.30, 0.55, 1.01]           # heavy-rain probability
LIKELIHOOD = ["very low", "low", "medium", "high"]
IMPACT = ["low", "moderate", "high", "very high"]          # susceptibility class
ALERTS = ["green", "yellow", "orange", "red"]

# rows = likelihood, cols = impact  (IMD impact-based warning matrix)
MATRIX = np.array([
    [0, 0, 0, 1],
    [0, 1, 1, 2],
    [1, 1, 2, 3],
    [1, 2, 3, 3],
])

ALERT_TEXT = {
    "green": "No action needed.",
    "yellow": "Be aware: water may collect on this road during heavy showers.",
    "orange": "Be prepared: waterlogging likely; avoid low-lying stretches, keep drains clear.",
    "red": "Take action: severe waterlogging expected; avoid travel here, pre-position pumps.",
}


def likelihood_level(p_heavy: np.ndarray, antecedent_3d_mm: np.ndarray | None = None) -> np.ndarray:
    """Bin heavy-rain probability; saturated ground (>=100 mm in 3 days) raises it one level."""
    lvl = np.digitize(np.asarray(p_heavy), LIKELIHOOD_BINS[1:-1])
    if antecedent_3d_mm is not None:
        lvl = np.minimum(lvl + (np.asarray(antecedent_3d_mm) >= 100), 3)
    return lvl


def impact_level(risk_class: pd.Series) -> np.ndarray:
    return risk_class.astype(str).map({c: i for i, c in enumerate(IMPACT)}).to_numpy()


def alerts(p_heavy, risk_class, antecedent_3d_mm=None) -> pd.Series:
    li = likelihood_level(p_heavy, antecedent_3d_mm)
    im = impact_level(risk_class)
    return pd.Series(np.array(ALERTS)[MATRIX[li, im]], index=getattr(risk_class, "index", None))


def nearest_cell(lat: np.ndarray, lon: np.ndarray, cells: list[tuple[float, float]]) -> list[tuple[float, float]]:
    c = np.array(cells)
    d = (lat[:, None] - c[None, :, 0]) ** 2 + (lon[:, None] - c[None, :, 1]) ** 2
    return [tuple(c[i]) for i in d.argmin(1)]
