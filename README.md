# Monsoon Sentinel

**Explainable AI early-warning platform for heavy rain and street-level waterlogging in Indian cities — Pune pilot.**

Monsoon Sentinel answers three questions every monsoon morning:

1. **Will it rain heavily?** — probability of IMD "heavy rain" (≥ 64.5 mm / 24 h) for each grid cell over Pune and its Western Ghats catchment, with a plain-language explanation of *why*.
2. **Which streets will flood?** — waterlogging risk for known hotspots and road segments *(in progress)*.
3. **What should we do?** — where to pre-position pumps and response crews, and who to alert *(planned)*.

---

## Status

| Module | Status |
|---|---|
| ① Rain module — 24 h heavy-rain forecast + SHAP explanations | ✅ v0.1 |
| ② Waterlogging module — hotspot risk with weak labels + uncertainty | ⏳ next |
| ③ Impact module — roads, population, critical facilities | 🗓 planned |
| ④ Decision module — RL pump / crew allocation | 🗓 planned |
| ⑤ Citizen signals — report classifier + photo verification | 🗓 planned |
| API + dashboard + citizen app | 🗓 planned |

---

## Rain module (v0.1)

**Forecast set-up.** Issued daily at 08:30 IST for the next 24 h, matching IMD's rain-gauge day.
Target = IMD 0.25° gridded rainfall ≥ 64.5 mm. 15 grid cells (18.25–18.75 °N, 73.25–74.25 °E) cover Pune city and the dam catchments upstream.

**Data (all public).**
- IMD 0.25° gridded daily rainfall (rain-gauge based), 2001–2024 — via [`imdlib`](https://pypi.org/project/imdlib/)
- ERA5 hourly reanalysis (water vapour, pressure, winds, humidity, soil moisture, boundary layer) — via the [Open-Meteo archive API](https://open-meteo.com/en/docs/historical-weather-api)

**Validation.** Strictly chronological: train 2001–2016, validate 2017–2020, test 2021–2024 (never seen during training or model selection). Metrics follow forecast-verification practice for rare events: POD, FAR, CSI, HSS, ROC-AUC, PR-AUC, Brier skill vs climatology.

**Models benchmarked.** Climatology and persistence baselines, Logistic Regression, Gaussian Naive Bayes, KNN, SVM (RBF), Decision Tree, Random Forest, LightGBM, XGBoost and an ensemble.

### Results on the unseen test years (2021–2024)

Selected model: **XGBoost** (chosen on validation years only: best PR-AUC, ties broken by calibration).

| | ROC-AUC | PR-AUC | Brier skill vs climatology | POD | FAR | CSI | HSS |
|---|---|---|---|---|---|---|---|
| Climatology baseline | 0.887 | 0.266 | 0.000 | 0.62 | 0.77 | 0.21 | 0.31 |
| Persistence baseline | 0.762 | 0.309 | −0.088 | 0.54 | 0.46 | 0.37 | 0.52 |
| **XGBoost (deployed)** | **0.961** | **0.655** | **+0.28** | **0.77** | **0.53** | **0.41** | **0.56** |

PR-AUC is **2.5×** the climatology baseline. Full table of 9 models + 2 baselines: [`reports/rain/benchmark.md`](reports/rain/benchmark.md).

**Hindcast — Pune flood, 25 July 2024** ([figure](reports/rain/case_pune_jul2024.png)): the city-cell probability rose above the alert threshold on 24–26 July, bracketing the 114 mm day, and stayed low on the quiet days before and after.

**Why the model says what it says** ([SHAP](reports/rain/shap_summary.png)): yesterday's rain, last-24 h rain over the Ghats, 30-day antecedent wetness, domain-wide westerly wind and column water vapour — the physical drivers of orographic monsoon rain.

**Known limitation.** The 0.25° city cells see heavy rain far less often than the Ghats cells (11 vs 236 test-period days), and many city events are short convective storms. City-cell skill is therefore lower (ROC-AUC 0.81, POD 0.22 on only 9 test events). Live NWP forecast inputs and the waterlogging module (which uses lower, impact-relevant rain thresholds) are the planned fixes.

### Syllabus analyses ([`reports/rain/analysis/`](reports/rain/analysis))

| Technique | Finding |
|---|---|
| PCA | 15 of 50 components keep 90 % of variance; a PCA-15 logistic model loses ~9 % PR-AUC (0.658 → 0.602) |
| Sequential forward / backward selection | Both keep yesterday's rain, 30-day rain, humidity and domain moisture/rain signals |
| K-means (k chosen by silhouette) + hierarchical | Two synoptic regimes: heavy-rain rate **1 %** vs **27 %** |
| DBSCAN (anomaly mode) | 75 "unusual" synoptic days, **80 %** of them had heavy rain somewhere (vs 17 % otherwise) |
| HMM (3 hidden states) | Dry / break / active monsoon phases; heavy rain on **41 %** of active-phase days vs **2 %** of break days |
| Apriori | e.g. *cloudy + strong westerly moisture flux + heavy rain yesterday → heavy rain* (confidence 0.81, lift 15.9) |
| Regression (rain amount) | Random Forest: MAE 6.3 mm, R² 0.64; Linear Regression: R² 0.18 |

---

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

python scripts/download_data.py   # IMD + ERA5 (~700 MB, resumable)
python scripts/train_rain.py      # features, benchmark, SHAP, case study
python scripts/analyze_rain.py    # PCA, feature selection, clustering, HMM, Apriori, regression
```

## Project layout

```
configs/pune.yaml              study area, thresholds, data split
src/monsoon_sentinel/
  data/        imd.py, era5.py          data download & loading
  features/    rain_features.py         leakage-safe feature engineering
  models/      rain_models.py           candidate classifiers
  evaluation/  metrics.py               POD / FAR / CSI / HSS / BSS
scripts/       download_data.py, train_rain.py, analyze_rain.py
reports/       generated benchmark tables and figures
```

## Data notes

- ERA5 is reanalysis. In live operation the same features come from the latest model analysis (e.g. GFS / ECMWF via Open-Meteo forecast API).
- Open-Meteo's free API is for non-commercial use; commercial deployment needs their paid plan or ECMWF open data.
