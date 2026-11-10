"""Step 8: train the Q-learning pump dispatcher on historical flood days.

Response zones are rebuilt for every archived day with a meaningful heavy-rain risk;
2001-2020 days train the agent, 2021-2024 days evaluate it against simple rules.

Usage:  python scripts/train_dispatch.py
Outputs: models/dispatch_qtable.json, reports/dispatch/*
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from monsoon_sentinel import dispatch as dp  # noqa: E402
from monsoon_sentinel.service import Sentinel  # noqa: E402


def build_events(s: Sentinel) -> pd.DataFrame:
    cache = s.cfg.path("processed") / "dispatch_events.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    probs = s._predict(s.archive.copy())
    probs["p_eff"] = probs.p_heavy
    city = {tuple(c) for c in s.cfg["grid"]["city_cells"]}
    pc = probs[[(a, b) in city for a, b in zip(probs.lat, probs.lon)]].groupby("date").p_eff.max()
    days = pc[pc >= 0.25].index
    rows = []
    for i, d in enumerate(days):
        ds = str(pd.Timestamp(d).date())
        for z in s.actions("replay", ds, max_items=40, use_rl=False):
            rows.append({"date": ds, "score": z["priority_score"], "p_flood": z["p_flood"]})
        if i % 50 == 0:
            print(f"  {i}/{len(days)} days", flush=True)
        s._road_alerts_cached.cache_clear()
    ev = pd.DataFrame(rows)
    ev.to_parquet(cache, index=False)
    return ev


def main():
    s = Sentinel()
    out = s.cfg.path("reports") / "dispatch"
    out.mkdir(exist_ok=True)
    ev = build_events(s)
    ev["year"] = pd.to_datetime(ev.date).dt.year
    to_days = lambda d: [[dp.Zone(r.score, r.p_flood) for r in g.itertuples()]  # noqa: E731
                         for _, g in d.groupby("date") if len(g) >= 2]
    train, test = to_days(ev[ev.year <= 2020]), to_days(ev[ev.year > 2020])
    print(f"events: {len(train)} train days, {len(test)} test days; "
          f"zones/day median {ev.groupby('date').size().median():.0f}")

    agent = dp.QAgent(alpha=0.01)
    rng = np.random.default_rng(0)
    curve = []
    episodes = 120000
    for ep in range(episodes):
        eps = max(0.05, 1 - ep / (0.6 * episodes))
        r = agent.run_episode(train[rng.integers(len(train))], eps=eps, learn=True)
        curve.append(r)

    def q_eval(days, reps=30):
        agent.rng = np.random.default_rng(1)
        return float(np.mean([agent.run_episode(z, 0.0, False) for z in days for _ in range(reps)]))

    results = {
        "Q-learning (learned policy)": q_eval(test),
        "Rule: deploy to every zone until pumps run out": dp.evaluate_rule(test, lambda z, p, f: True),
        "Rule: deploy only to zones with >= 50 red segments": dp.evaluate_rule(test, lambda z, p, f: z.score >= 100),
        "Rule: deploy if zone is above median severity": dp.evaluate_rule(
            test, lambda z, p, f: z.score >= np.median([zz.score for d in train for zz in d])),
        "Never deploy": 0.0,
        "Oracle (knows outcomes in advance; upper bound)": dp.evaluate_oracle(test),
    }
    res = pd.Series(results).rename("avg_reward_per_event").sort_values(ascending=False)
    res.to_csv(out / "dispatch_benchmark.csv")
    print(res.round(3).to_string())

    (s.cfg.path("models") / "dispatch_qtable.json").write_text(json.dumps(agent.to_json()))
    policy = {f"severity {sev}, pumps {p}": ["hold", "deploy"][int(np.argmax(agent.Q[sev, p, 1]))]
              for sev in range(4) for p in range(1, dp.K_PUMPS + 1)}
    (out / "policy_mid_event.json").write_text(json.dumps(policy, indent=2))
    (out / "summary.json").write_text(json.dumps({
        "train_days": len(train), "test_days": len(test), "pumps": dp.K_PUMPS,
        "episodes": episodes, "test_results": res.round(4).to_dict(),
        "q_vs_best_rule_pct": round(100 * (results["Q-learning (learned policy)"] /
                                           max(v for k, v in results.items() if k.startswith("Rule")) - 1), 1),
    }, indent=2))

    w = 500
    sm = np.convolve(curve, np.ones(w) / w, mode="valid")
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(sm)
    ax.set(xlabel="Training episode", ylabel=f"Reward ({w}-episode mean)", title="Q-learning dispatcher: learning curve")
    fig.tight_layout()
    fig.savefig(out / "learning_curve.png", dpi=140)


if __name__ == "__main__":
    main()
