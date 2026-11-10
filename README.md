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
| ② Waterlogging module — street susceptibility + daily alerts | ✅ v0.1 |
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

## Waterlogging module (v0.1)

**1. Hotspot catalogue** — [`data/labels/pune_hotspots_raw.csv`](data/labels/pune_hotspots_raw.csv): 38 waterlogging / flood locations from public sources (Pune Traffic Police 2026 list, PMC disaster-cell reports 2025, July 2024 Khadakwasla-release flood, Sept 2019 Ambil Odha flash flood), each with its source URL, geocoded with OpenStreetMap Nominatim → 32 usable after de-duplication and manual checks. PMC's full list of 120 spots is not published in machine-readable form; obtaining it (e.g. via an RTI request) is the single biggest accuracy upgrade available.

**2. Terrain & drainage** — Copernicus 30 m DEM → slope, topographic position, depression depth, flow accumulation, topographic wetness index, height above nearest drainage (HAND); OpenStreetMap rivers, canals, nalas and road network (urbanisation proxy).

**3. Street susceptibility** — every ~150 m of Pune's road network (21,458 locations) scored by positive-unlabelled learning, evaluated with **spatial block cross-validation** (2 km blocks, 5 folds — the model is always scored on neighbourhoods it never saw).

| Model (spatial CV) | ROC-AUC | Hotspots in riskiest 10 % / 20 % of roads |
|---|---|---|
| Baseline: high TWI | 0.50 | 13 % / 13 % |
| Baseline: low HAND | 0.57 | 22 % / 28 % |
| LightGBM, all 15 features | 0.70 | 19 % / 38 % |
| Baseline: distance to nearest nala | 0.77 | 38 % / 50 % |
| **Monotone LightGBM, 6 physics features (deployed)** | **0.76** (fold mean 0.78) | **34 % / 56 %** |

Lesson: with ~30 labelled hotspots, an unconstrained 15-feature model overfits; a small model with physically enforced monotonic effects (closer to a nala / lower HAND / deeper depression ⇒ never less risk) generalises better and stays explainable. It is statistically on par with the strong "distance to nala" rule while also using depressions, terrain and urban density. Most important drivers: distance to nala, distance to river, road density, local topographic position. Full table: [`reports/urban/susceptibility_benchmark.md`](reports/urban/susceptibility_benchmark.md); map: [`reports/urban/susceptibility_map.png`](reports/urban/susceptibility_map.png). Each location also carries a bootstrap 10–90 % uncertainty band.

**4. Daily alert** — impact-based risk matrix (as used by IMD): rain-module heavy-rain probability (likelihood, raised one level when the previous 3 days had ≥ 100 mm) × street susceptibility (impact) → green / yellow / orange / red per road location, with plain-language advice.

**Hindcast** ([figure](reports/urban/hindcast_alerts.png)):

| Day | City rain (IMD) | P(heavy) | Known hotspots on orange/red |
|---|---|---|---|
| 24 Jul 2024 (night before flood) | 40 mm | 0.34 | 17 / 32 |
| **25 Jul 2024 — Sinhagad Road / Ekta Nagar flood** | 114 mm | 0.62 | **31 / 32** |
| 25 Sep 2019 — Ambil Odha flash flood | 78 mm | 0.04 | **0 / 32 (missed)** |
| Three ordinary monsoon days | 0–1 mm | 0.00 | 0 / 32 |

The 2019 miss is a sudden local cloudburst with no large-scale precursor in the morning data — the same city-cell limitation as in the rain module. Fix planned: ingest live NWP / nowcast rainfall so short convective events can trigger alerts.

---

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

python scripts/download_data.py   # IMD + ERA5 (~700 MB, resumable)
python scripts/train_rain.py      # features, benchmark, SHAP, case study
python scripts/analyze_rain.py    # PCA, feature selection, clustering, HMM, Apriori, regression

python scripts/geocode_hotspots.py      # hotspot catalogue -> coordinates (Nominatim)
python scripts/build_urban_layers.py    # DEM hydrology + OpenStreetMap roads/waterways
python scripts/train_susceptibility.py  # street susceptibility, spatial CV, map
python scripts/hindcast_risk.py         # daily alerts on 2019 / 2024 flood days
```

## Project layout

```
configs/pune.yaml              study area, thresholds, data split
src/monsoon_sentinel/
  data/        imd.py, era5.py, terrain.py, osm.py   data download & GIS layers
  features/    rain_features.py, urban_features.py  leakage-safe feature engineering
  models/      rain_models.py                       candidate classifiers
  evaluation/  metrics.py                           POD / FAR / CSI / HSS / BSS
  risk.py                                           likelihood x impact alert matrix
data/labels/   curated hotspot catalogue (with sources)
scripts/       pipeline steps (see Quick start)
reports/       generated benchmark tables and figures
```

## Data notes

- ERA5 is reanalysis. In live operation the same features come from the latest model analysis (e.g. GFS / ECMWF via Open-Meteo forecast API).
- Open-Meteo's free API is for non-commercial use; commercial deployment needs their paid plan or ECMWF open data.
