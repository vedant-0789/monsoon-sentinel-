"""Reinforcement-learning dispatcher for dewatering pumps (tabular Q-learning).

Problem (online allocation). During a flood event, response zones are confirmed one at
a time as the evening unfolds. The city has K mobile pumps. For each zone the operator
must decide now: DEPLOY a pump (it is committed for the night) or HOLD it for a zone
that may be worse. This is a finite-horizon MDP:

  state  s = (zone severity level 0-3, pumps left 0..K, share of zones still to come 0-2)
  action a = 0 hold / 1 deploy
  reward r = damage averted if the zone actually floods - fixed deployment cost
  update   Q(s,a) <- Q(s,a) + alpha * [ r + gamma * max_a' Q(s',a') - Q(s,a) ]   (Bellman)

Flooding is simulated from each zone's own risk: P(flood) = heavy-rain probability of
its rain cell, scaled by how much of the zone is red. This is a planning model built on
the forecast, not an observed-outcome dataset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

K_PUMPS = 5
DEPLOY_COST = 0.15
EFFECTIVENESS = 0.7
SEV_EDGES = [40, 90, 160]          # zone priority-score bins -> levels 0..3


def severity_level(score: float) -> int:
    return int(np.digitize(score, SEV_EDGES))


def damage(score: float) -> float:
    """Damage units if a zone floods unattended (diminishing with size)."""
    return float(np.log1p(score) / np.log1p(300))


@dataclass
class Zone:
    score: float        # 2 x red segments + orange segments nearby
    p_flood: float      # chance the zone floods tonight


def _state(z: Zone, pumps: int, frac_left: float) -> tuple[int, int, int]:
    return severity_level(z.score), pumps, int(np.digitize(frac_left, [0.34, 0.67]))


def _reward(z: Zone, deploy: bool, flooded: bool) -> float:
    if not deploy:
        return 0.0
    return (EFFECTIVENESS * damage(z.score) if flooded else 0.0) - DEPLOY_COST


class QAgent:
    def __init__(self, k: int = K_PUMPS, alpha: float = 0.05, gamma: float = 1.0, seed: int = 0):
        self.k, self.alpha, self.gamma = k, alpha, gamma
        self.Q = np.zeros((4, k + 1, 3, 2))
        self.N = np.zeros_like(self.Q)          # visit counts -> decaying step size
        self.rng = np.random.default_rng(seed)

    def act(self, s, eps: float = 0.0) -> int:
        sev, pumps, _ = s
        if pumps == 0:
            return 0
        if self.rng.random() < eps:
            return int(self.rng.integers(2))
        return int(np.argmax(self.Q[s]))

    def run_episode(self, zones: list[Zone], eps: float, learn: bool) -> float:
        order = self.rng.permutation(len(zones))
        pumps, total = self.k, 0.0
        for t, i in enumerate(order):
            z = zones[i]
            s = _state(z, pumps, 1 - t / len(zones))
            a = self.act(s, eps)
            flooded = self.rng.random() < z.p_flood
            r = _reward(z, a == 1, flooded)
            if learn:  # learn from the expected reward (P(flood) x damage): far lower variance
                r_learn = (EFFECTIVENESS * damage(z.score) * z.p_flood - DEPLOY_COST) if a == 1 else 0.0
            pumps -= a
            total += r
            if learn:
                done = t == len(order) - 1
                if done:
                    target = r_learn
                else:
                    s2 = _state(zones[order[t + 1]], pumps, 1 - (t + 1) / len(zones))
                    q2 = self.Q[s2] if s2[1] > 0 else self.Q[s2][:1]   # no pumps -> only "hold"
                    target = r_learn + self.gamma * np.max(q2)
                self.N[s][a] += 1
                step = max(self.alpha, 1.0 / np.sqrt(self.N[s][a]))
                self.Q[s][a] += step * (target - self.Q[s][a])
        return total

    def to_json(self) -> dict:
        return {"k": self.k, "Q": self.Q.round(5).tolist(), "sev_edges": SEV_EDGES,
                "deploy_cost": DEPLOY_COST, "effectiveness": EFFECTIVENESS}


def evaluate_rule(days: list[list[Zone]], rule, k: int = K_PUMPS, reps: int = 30, seed: int = 1) -> float:
    """Average reward per event of a hand-written rule(zone, pumps_left, frac_left) -> 0/1."""
    rng = np.random.default_rng(seed)
    tot, n = 0.0, 0
    for zones in days:
        for _ in range(reps):
            pumps, r = k, 0.0
            order = rng.permutation(len(zones))
            for t, i in enumerate(order):
                z = zones[i]
                a = 1 if pumps and rule(z, pumps, 1 - t / len(zones)) else 0
                r += _reward(z, a == 1, rng.random() < z.p_flood)
                pumps -= a
            tot += r
            n += 1
    return tot / n


def evaluate_oracle(days: list[list[Zone]], k: int = K_PUMPS, reps: int = 30, seed: int = 1) -> float:
    """Upper bound: sees every zone and its true flood outcome before deciding."""
    rng = np.random.default_rng(seed)
    tot, n = 0.0, 0
    for zones in days:
        for _ in range(reps):
            gains = sorted((_reward(z, True, rng.random() < z.p_flood) for z in zones), reverse=True)
            tot += sum(g for g in gains[:k] if g > 0)
            n += 1
    return tot / n


def plan(qtable: dict, zones: list[dict]) -> list[dict]:
    """Apply the learned policy to today's ranked zones (in the order they are listed)."""
    Q = np.asarray(qtable["Q"])
    k = qtable["k"]
    pumps = k
    out = []
    for t, z in enumerate(zones):
        s = _state(Zone(z["priority_score"], z.get("p_flood", 0.5)), pumps, 1 - t / max(len(zones), 1))
        a = int(np.argmax(Q[s])) if pumps else 0
        pumps -= a
        out.append({**z, "rl_deploy_pump": bool(a), "pumps_left_after": pumps})
    return out


def load_qtable(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None
