"use client";

import { useEffect, useState } from "react";
import { Bars } from "@/components/charts";
import { Card, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
type CardData = Record<string, any>;

const PIPELINE = [
  { t: "Data", d: "IMD rain gauges · ERA5 / Open-Meteo weather · Copernicus 30 m terrain · OpenStreetMap roads, drains, facilities · public flood reports" },
  { t: "1 · Heavy rain", d: "XGBoost predicts the chance of ≥ 64.5 mm in 24 h for 15 areas; TreeSHAP explains each forecast" },
  { t: "2 · Street risk", d: "Physics-guided monotone model scores ~21,900 street points for waterlogging susceptibility" },
  { t: "3 · Alert", d: "IMD-style risk matrix: likelihood × street impact → green / yellow / orange / red" },
  { t: "4 · Impact", d: "Road-km and critical facilities (hospitals, fire stations, schools) whose access road is on alert" },
  { t: "5 · Action", d: "DBSCAN groups red streets into response zones; a Q-learning agent decides where the limited pumps go" },
  { t: "6 · People", d: "Citizen reports in English, मराठी, हिंदी; Naive Bayes flags category and urgency" },
];

const SYLLABUS: [string, string][] = [
  ["Linear & logistic regression", "Rain amount regression; heavy-rain and susceptibility baselines"],
  ["KNN", "Heavy-rain classifier; analogue-day lookup idea"],
  ["Naive Bayes (Gaussian, Multinomial)", "Rain benchmark; citizen-report text classifier"],
  ["SVM / SVR", "Rain benchmark (RBF SVM); rain-amount Linear SVR"],
  ["Decision tree, bagging, random forest, boosting", "Rain benchmark; deployed XGBoost; monotone LightGBM for streets"],
  ["Neural network", "MLP in the rain benchmark"],
  ["Feature selection (filter, wrapper, embedded)", "Mutual information, forward/backward selection, L1"],
  ["PCA", "Components, variance and std-dev; PCA-compressed model"],
  ["K-means, hierarchical, DBSCAN", "Weather regimes; anomaly days; response zones"],
  ["Homogeneity & completeness", "Regime clusters vs. observed rain classes"],
  ["Apriori (market-basket rules)", "Readable rules for heavy rain with support / confidence / lift"],
  ["Hidden Markov model", "Dry / break / active monsoon phases"],
  ["MDP, Q-learning, Bellman equation", "Pump dispatch under a limited fleet"],
  ["Error analysis, precision / recall, CV", "POD, FAR, CSI, HSS, Brier skill; chronological and spatial CV"],
];

const fmt = (v: unknown, d = 3) => (typeof v === "number" ? v.toFixed(d) : "—");

export default function About() {
  const [card, setCard] = useState<CardData | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    api.modelCard().then(setCard).catch(() => setErr(true));
  }, []);

  const rain = card?.rain;
  const rainRows = (rain?.benchmark ?? []).filter((r: any) => !String(r.model).includes("baseline"));
  const base = (rain?.benchmark ?? []).filter((r: any) => String(r.model).includes("baseline"));
  const sus = card?.susceptibility;
  const disp = card?.dispatch;
  const cit = card?.citizen_reports;
  const an = card?.analysis;
  const hind = card?.hindcast ?? {};

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
        <header className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">How Monsoon Sentinel works</h1>
          <p className="max-w-3xl text-zinc-600 dark:text-zinc-400">
            An explainable early-warning system that turns a heavy-rain forecast into street-level waterlogging alerts and a concrete
            response plan for Pune. Every number on this page comes from evaluation on data the models never saw.
          </p>
        </header>

        <section aria-labelledby="pipe">
          <h2 id="pipe" className="mb-3 text-lg font-semibold">Pipeline</h2>
          <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {PIPELINE.map((p) => (
              <li key={p.t} className="rounded-2xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
                <div className="text-sm font-semibold">{p.t}</div>
                <div className="mt-1 text-xs leading-snug text-zinc-600 dark:text-zinc-400">{p.d}</div>
              </li>
            ))}
          </ol>
        </section>

        {!card && !err && <div className="flex items-center gap-2 text-sm text-zinc-500"><Spinner /> Loading model card…</div>}
        {err && <p className="text-sm text-red-600">Could not load the model card from the API.</p>}

        {rain && (
          <section aria-labelledby="rain" className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h2 id="rain" className="text-lg font-semibold">1 · Heavy-rain forecast</h2>
              <p className="mt-1 text-xs text-zinc-500">{rain.task}. {rain.split}.</p>
              <h3 className="mt-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">PR-AUC on 2021–2024 (higher is better)</h3>
              <div className="mt-2">
                <Bars rows={[...rainRows, ...base].map((r: any) => ({ label: r.model, value: r.PR_AUC }))}
                  max={0.75} highlight={rain.deployed} />
              </div>
            </Card>
            <Card>
              <h3 className="text-sm font-semibold">Deployed: {rain.deployed}</h3>
              {(() => {
                const d = (rain.benchmark ?? []).find((r: any) => r.model === rain.deployed) ?? {};
                const c = base.find((r: any) => String(r.model).startsWith("Climatology")) ?? {};
                return (
                  <table className="mt-2 w-full text-sm">
                    <thead><tr className="text-left text-xs text-zinc-500"><th className="py-1">Metric</th><th>Model</th><th>Climatology</th></tr></thead>
                    <tbody className="tabular-nums">
                      {[["ROC-AUC", "ROC_AUC"], ["PR-AUC", "PR_AUC"], ["Probability of detection", "POD"], ["False-alarm ratio", "FAR"],
                        ["Critical success index", "CSI"], ["Heidke skill", "HSS"], ["Brier skill vs climatology", "BSS_vs_clim"]].map(([n, k]) => (
                        <tr key={k} className="border-t border-zinc-100 dark:border-zinc-800"><td className="py-1">{n}</td><td>{fmt(d[k])}</td><td>{fmt(c[k])}</td></tr>
                      ))}
                    </tbody>
                  </table>
                );
              })()}
              <h3 className="mt-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">What drives the forecast (mean |SHAP|)</h3>
              <div className="mt-2">
                <Bars rows={(rain.top_drivers ?? []).map((r: any) => ({ label: r.feature, value: r.mean_abs_shap }))}
                  max={Math.max(...(rain.top_drivers ?? [{ mean_abs_shap: 1 }]).map((r: any) => r.mean_abs_shap))} format={(v) => v.toFixed(4)} />
              </div>
            </Card>
          </section>
        )}

        {sus && (
          <section className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h2 className="text-lg font-semibold">2 · Street waterlogging susceptibility</h2>
              <p className="mt-1 text-xs text-zinc-500">{sus.labels}. {sus.validation}.</p>
              <h3 className="mt-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">Known hotspots in the riskiest 20 % of roads</h3>
              <div className="mt-2">
                <Bars rows={(sus.benchmark ?? []).slice(0, 9).map((r: any) => ({ label: r.model, value: r.capture_top20pct }))}
                  max={1} format={(v) => `${Math.round(v * 100)}%`} highlight={sus.summary?.best_model} />
              </div>
            </Card>
            <Card>
              <h2 className="text-lg font-semibold">3 · Alerts on real flood days</h2>
              <table className="mt-2 w-full text-sm">
                <thead><tr className="text-left text-xs text-zinc-500"><th className="py-1">Day</th><th>City rain</th><th>P(heavy)</th><th>Hotspots alerted</th></tr></thead>
                <tbody className="tabular-nums">
                  {Object.entries(hind).map(([day, v]: [string, any]) => (
                    <tr key={day} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="py-1"><a className="text-blue-600 hover:underline" href={`/?date=${day}`}>{day}</a><div className="text-[10px] text-zinc-500">{v.event}</div></td>
                      <td>{v.observed_rain_city_cells_mm} mm</td><td>{v.max_p_heavy_city}</td><td>{v.hotspots_orange_or_red}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-zinc-500">The 2019 Ambil Odha event was a sudden local cloudburst with no large-scale signal in the morning data — a known limitation.</p>
            </Card>
          </section>
        )}

        {disp?.test_results && (
          <section className="grid gap-4 lg:grid-cols-2">
            <Card>
              <h2 className="text-lg font-semibold">5 · Pump dispatch (Q-learning)</h2>
              <p className="mt-1 text-xs text-zinc-500">
                {disp.pumps} pumps, zones arrive one by one; trained on {disp.train_days} flood days (2001–2020), tested on {disp.test_days} (2021–2024).
                Average reward per event (damage averted − deployment cost):
              </p>
              <div className="mt-2">
                <Bars rows={Object.entries(disp.test_results).map(([k, v]) => ({ label: k, value: v as number }))}
                  max={Math.max(...Object.values(disp.test_results as Record<string, number>))} format={(v) => v.toFixed(2)}
                  highlight="Q-learning (learned policy)" />
              </div>
            </Card>
            <Card>
              <h2 className="text-lg font-semibold">6 · Citizen reports (Naive Bayes)</h2>
              <p className="mt-1 text-xs text-zinc-500">
                {cit?.summary?.examples} seed reports in English, Hinglish, मराठी and हिंदी; tested on incident phrasings never seen in training
                ({cit?.summary?.cv}). The model suggests a category and flags urgency; the citizen always confirms.
              </p>
              <div className="mt-2">
                <Bars rows={(cit?.benchmark ?? []).map((r: any) => ({ label: `${r.model} · category`, value: r.category_macro_F1 }))}
                  max={1} highlight="Multinomial Naive Bayes · category" />
              </div>
              <p className="mt-2 text-xs text-zinc-500">Urgency F1 (Naive Bayes): {fmt(cit?.summary?.metrics?.urgent_F1, 2)}</p>
            </Card>
          </section>
        )}

        {an && (
          <section>
            <Card>
              <h2 className="text-lg font-semibold">Supporting analyses</h2>
              <ul className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
                <li><strong>PCA:</strong> {an.pca_components_90pct} of 50 components keep 90 % of variance; PR-AUC {fmt(an.pca_pr_auc?.[0])} → {fmt(an.pca_pr_auc?.[1])} when compressed.</li>
                <li><strong>Feature selection (10 features, test PR-AUC):</strong> {an.feature_selection && Object.entries(an.feature_selection).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(" · ")}</li>
                <li><strong>HMM monsoon phases:</strong> heavy rain on {an.hmm ? `${Math.round(an.hmm.active * 100)} %` : "—"} of active days vs {an.hmm ? `${Math.round(an.hmm.break * 100)} %` : "—"} of break days.</li>
                <li><strong>DBSCAN anomalies:</strong> {an.dbscan?.anomalous_days} unusual days, {an.dbscan ? Math.round(an.dbscan.heavy_rain_rate_anomalous_days * 100) : "—"} % of them with heavy rain.</li>
                {(an.apriori ?? []).slice(0, 2).map((r: any) => (
                  <li key={r.antecedents}><strong>Apriori rule:</strong> {r.antecedents} → heavy rain (confidence {fmt(r.confidence, 2)}, lift {fmt(r.lift, 1)})</li>
                ))}
                {an.regression && <li><strong>Rain amount:</strong> Random Forest MAE {fmt(an.regression["Random Forest Regressor"]?.MAE_mm, 1)} mm, R² {fmt(an.regression["Random Forest Regressor"]?.R2, 2)}.</li>}
              </ul>
            </Card>
          </section>
        )}

        <section>
          <Card>
            <h2 className="text-lg font-semibold">Course coverage</h2>
            <table className="mt-2 w-full text-sm">
              <tbody>
                {SYLLABUS.map(([a, b]) => (
                  <tr key={a} className="border-t border-zinc-100 align-top first:border-0 dark:border-zinc-800">
                    <td className="py-1.5 pr-3 font-medium">{a}</td><td className="py-1.5 text-zinc-600 dark:text-zinc-400">{b}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card>
            <h2 className="text-lg font-semibold">Data sources</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
              <li>IMD 0.25° gridded daily rainfall (rain-gauge based), 2001–2024</li>
              <li>ERA5 reanalysis and Open-Meteo forecasts (non-commercial terms)</li>
              <li>Copernicus GLO-30 digital elevation model</li>
              <li>© OpenStreetMap contributors (roads, waterways, facilities)</li>
              <li>Pune Traffic Police / PMC hotspot lists and news reports (with links in the dataset)</li>
            </ul>
          </Card>
          <Card>
            <h2 className="text-lg font-semibold">Limitations</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
              <li>Sudden local cloudbursts (e.g. Sept 2019) are hard to foresee from morning data.</li>
              <li>Only ~30 public hotspot locations exist for training; the official 120-spot list would help most.</li>
              <li>Live mode uses model-analysis rain, which is smoother than gauge rain.</li>
              <li>The dispatcher and report classifier are trained on simulated outcomes / seed text, and need real data to mature.</li>
              <li>Advisory only — always follow official PMC / IMD instructions.</li>
            </ul>
          </Card>
        </section>
      </div>
    </div>
  );
}
