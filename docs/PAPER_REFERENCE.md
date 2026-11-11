# Monsoon Sentinel — Paper Reference Notes

> Working notes for writing the research paper. Everything here comes from the
> code and evaluation outputs in this repository (`reports/`, `models/model_card.json`).
> Numbers are from the final runs; re-run the scripts and update if anything is retrained.
> This file holds facts, results and structure. It is not the paper text.

---

## 0. Quick facts sheet

| Item | Value |
|---|---|
| Study area | Pune (PMC/PCMC) + upstream Western Ghats catchment, 18.25–18.75 °N × 73.25–74.25 °E |
| Rain grid | 15 IMD 0.25° cells (2 "city" cells: 18.5 °N 73.75/74.0 °E) |
| Rain data | IMD gridded gauge rainfall + ERA5 hourly (Open-Meteo), Jun–Oct 2001–2024 → 55,080 cell-days |
| Target | IMD "heavy rain" ≥ 64.5 mm / 24 h (08:30–08:30 IST); base rate 5.1 % train, 3.6 % test |
| Split | Train 2001–2016 · Validate 2017–2020 · Test 2021–2024 (chronological) |
| Features | 50 (antecedent gauge rain, ERA5 state & 24 h stats, domain/Ghats synoptic context, calendar, climatology) |
| Street points | 21,458 road locations (+433 near-hotspot) ≈ every 150 m of OSM road network |
| Hotspot labels | 38 curated public locations → 32 usable after geocoding/de-duplication |
| Terrain | Copernicus GLO-30 DEM → slope, TPI, sink depth, flow accumulation, TWI, HAND |
| Facilities | 1,763 OSM hospitals, clinics, schools, colleges, police, fire stations linked to streets |
| Deployed rain model | XGBoost (exact TreeSHAP explanations) |
| Deployed susceptibility model | Monotone-constrained LightGBM on 6 physics features |
| Live system | FastAPI (Render) + Next.js (Vercel), EN/मराठी/हिंदी, live + replay modes, WhatsApp/SMS alerts, photo verification, 5-model hourly outlook |
| Live demo | https://monsoon-sentinel-zeta.vercel.app · API docs https://monsoon-sentinel-api.onrender.com/docs |

---

## 1. Title options

1. *Monsoon Sentinel: An Explainable, Impact-Based Street-Level Waterlogging Early-Warning System for Data-Scarce Indian Cities*
2. *From Forecast to Footpath: Explainable Heavy-Rain Prediction and Street-Level Waterlogging Alerts for Pune*
3. *Coupling Explainable Heavy-Rain Forecasting with Physics-Guided Waterlogging Susceptibility and Reinforcement-Learning Response Planning*

## 2. Problem statement and motivation

- Pune's waterlogging hotspots keep growing. PMC reported 73 new spots in June 2025 and 120 waterlogging-prone locations in May 2026, and the traffic police graded 26 hotspots from 2025 emergency calls ([Bridge Chronicle](https://www.thebridgechronicle.com/pune/punepune-identifies-73-new-flood-prone-spots-pmc-disaster-cell-shelters-monsoon), [Bridge Chronicle 2026](https://www.thebridgechronicle.com/pune/pune-flood-prone-spots-monsoon-pmc-preparedness-agn97), [Punekar News](https://www.punekarnews.in/?p=238846)).
- Recent events: the Sept 2019 Ambil Odha flash flood and the 25 July 2024 Khadakwasla-release flood (Sinhagad Road / Ekta Nagar).
- Existing operational systems (iFLOWS-Mumbai, Chennai) are physics-based and city-specific, and need heavy computation ([PIB](https://pib.gov.in/PressReleasePage.aspx?PRID=1630928)). **No published ML waterlogging system exists for Pune.**
- This is the SIH theme raised by ISRO: *explainable AI for heavy, high-impact rain events*.

## 3. Research gaps (cite these)

| Gap | Evidence |
|---|---|
| G1: Rain → flood → impact → action are studied separately | Impact-based flood warning review ([ResearchGate](https://www.researchgate.net/publication/415518711_Artificial_Intelligence_for_Urban_Flood_Early_Warning_A_Review_of_Recent_Advances)); road-flood ensemble ([PMC12546731](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12546731/)) |
| G2: XAI rainfall work is mostly monthly/daily totals, not heavy-rain events | Chhattisgarh XAI ([Springer](https://link.springer.com/article/10.1007/s00704-025-05645-2)); Bengaluru multi-scale ([Springer](https://link.springer.com/article/10.1007/s00477-026-03245-8)); four-city ConvLSTM, where extreme-rain error is about 2× overall ([arXiv 2511.11152](https://arxiv.org/pdf/2511.11152)) |
| G3: AI weather models under-predict Indian extremes | GraphCast/GenCast/AIFS vs 458 IMD stations ([arXiv 2509.01879](https://arxiv.org/html/2509.01879v1)); GraphCast monsoon biases ([arXiv 2607.11905](https://arxiv.org/pdf/2607.11905)) |
| G4: Urban flood labels are scarce; SAR struggles in dense cities | Weak labels / social media ([JSTARS 2026]); UrbanSARFloods; crowdsourcing Mumbai ([arXiv 2306.09770](https://arxiv.org/pdf/2306.09770), [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2210670725006699)) |
| G5: Pump control and crew dispatch are studied separately; not for Indian cities | Hierarchical RL pumps ([Loughborough](https://repository.lboro.ac.uk/articles/journal_contribution/A_coupled_human_and_natural_systems_CHANS_framework_integrated_with_reinforcement_learning_for_urban_flood_mitigation/27961617)); DRL pump stations ([MDPI Water 2024](https://mdpi.com/2073-4441/16/23/3398)); LLM multi-agent ([arXiv 2508.14654](https://arxiv.org/pdf/2508.14654)) |
| G6: Mumbai has ML waterlogging studies; Pune has none | Mumbai ML + GIS ([Springer 2022](https://link.springer.com/article/10.1007/s10708-022-10731-3)) |

## 4. Contributions (claimable)

1. **An end-to-end, impact-based pipeline:** heavy-rain probability → street susceptibility → IMD-style risk matrix → impact on roads and critical facilities → response plan, deployed as a public bilingual app.
2. **An explainable heavy-rain forecaster** on 24 years of gauge data, with a 13-way benchmark (11 models + 2 baselines) and forecast-verification metrics. Every forecast comes with exact TreeSHAP reasons in plain language (EN/MR/HI).
3. **Physics-guided susceptibility from ~30 labels:** monotone constraints beat unconstrained ML under spatial cross-validation (0.70 → 0.76 AUC; 38 % → 56 % hotspot capture in the top 20 %).
4. **A curated, source-linked Pune hotspot dataset** (first public one, as far as we found), plus 21,891 scored street points.
5. **Q-learning online pump dispatch** under a limited fleet. It learns an interpretable threshold policy without hand-tuning, doubles the naive rule's reward, and comes within 4 % of the best hand-tuned rule.
6. **A multilingual citizen-report triage model** (Multinomial NB, char + word n-grams, place-name masking), evaluated on held-out phrasings, plus **two-tier CNN photo verification** (95.3 % accuracy, the same ONNX model on the phone and the server).
7. **A rigorous test of operational short-range NWP:** five models, six ways of combining them, leave-one-season-out. None adds daily heavy-rain skill over the morning ML model, which shapes how NWP is used (timing, not likelihood).
8. **End-to-end delivery:** verified, consented, multilingual WhatsApp/SMS alerts targeted to each subscriber's own street.
9. **An honest negative result** for the 2019 convective cloudburst, which identifies where NWP/radar nowcasting must come in.

---

## 5. Data

| Dataset | Source / access | Use |
|---|---|---|
| IMD 0.25° gridded daily rainfall (Pai et al. 2014) | `imdlib`, IMD Pune | Target + antecedent rain |
| ERA5 hourly reanalysis (10 vars) | Open-Meteo archive API | Atmospheric predictors |
| Open-Meteo forecast API | Snapshot every 3 h by GitHub Actions | Live-mode predictors + NWP rain |
| Copernicus GLO-30 DEM | AWS open data | Terrain / hydrology |
| OpenStreetMap | Overpass API | Roads, waterways, facilities |
| Hotspot catalogue | Traffic police 2026, PMC 2025, news on the 2019/2024 floods (URLs per row) | Susceptibility labels |
| Citizen report seed set | Generated compositionally (968 sentences, 92 incident phrasings, 4 languages) | NB classifier |

**Label conventions:**
- The IMD day D covers 08:30 IST D → 08:30 IST D+1, i.e. 03 UTC → 03 UTC.
- Forecasts are issued at 03 UTC on day D. All features use only information available at issue time, so there is no leakage.

## 6. Methods

### 6.1 Heavy-rain module
- **Features (50):**
  - IMD lags 1–7, sums over 3/7/15/30 days, heavy days in the past 7
  - ERA5 at issue time: TCWV, MSLP, RH, Td, cloud, soil moisture, BLH, u/v
  - 24 h ERA5 statistics: precipitation sum/max, TCWV mean/max, tendencies of MSLP/TCWV/u
  - Westerly moisture flux (TCWV × u)
  - Domain and Ghats means
  - Day-of-year sin/cos, elevation
  - Cell × month heavy-rain climatology, computed from training years only
- **Models:**
  - Baselines: climatology, persistence
  - LR, Gaussian NB, KNN (k=50), SVM-RBF, Decision Tree, Random Forest, Bagging, MLP (64-32), LightGBM, XGBoost (early stopping on validation), and a mean ensemble
- **Model selection:** validation years only. Best validation PR-AUC among models with exact explanations (XGBoost, LightGBM); near-ties within 0.01 broken by validation Brier score.
- **Alert threshold:** maximises validation CSI.
- **Explanations:** TreeSHAP `pred_contribs`, mapped to plain-language factors and listed agreeing-direction first.
- **Analyses:**
  - PCA
  - Feature selection: SFS, SBS, mutual information, L1
  - K-means (k by silhouette), Ward hierarchical, DBSCAN (eps = 95th percentile of the k-distance)
  - Gaussian HMM with 3 states on log domain rain, sticky initialisation
  - Apriori on 8 binary weather conditions
  - Regression in log space: Linear, LinearSVR, Random Forest

### 6.2 Street susceptibility module
- **Candidates:** OSM road network sampled every 150 m and thinned on a 150 m grid.
- **Positives:** geocoded hotspots, weighted 1.0 for points and 0.5 for areas. Road points within 300 m of a hotspot are excluded from training to avoid ambiguity, but scored afterwards.
- **Features (15):**
  - Terrain: elevation, slope, TPI 300 m / 1 km, sink depth (raw and smoothed), log flow accumulation, TWI, HAND (raw and smoothed), DEM drainage distance
  - Mapped drainage: log distance to OSM river/canal and to stream/drain
  - Urban form: road density and major-road density within 500 m
- **Learning setup:** positive-unlabelled, with class weighting.
- **Spatial CV:** 2 km blocks in 5 folds, balanced by hotspot count.
- **Physics-guided model:** 6 features with monotone constraints:

  | Feature | Direction |
  |---|---|
  | Distance to river | − |
  | Distance to nala | − |
  | Sink depth | + |
  | HAND | − |
  | Road density | + |
  | TPI 300 m | − |

- **Uncertainty:** 30-model bootstrap gives 10–90 % bands.

### 6.3 Alert (risk matrix)
- **Likelihood:** heavy-rain probability binned at 0.10 / 0.30 / 0.55. It's raised one level when the previous 3 days had ≥ 100 mm (saturated ground). In live mode, an NWP forecast of ≥ 35 mm or ≥ 64.5 mm sets a minimum probability of 0.35 or 0.60.
- **Impact:** street susceptibility class from the percentile among roads (low < 60, moderate < 85, high < 95, very high).
- **Matrix:** 4 × 4 → green / yellow / orange / red, as in IMD impact-based warnings.

### 6.4 Impact module
- **Road length on alert:** count × 0.15 km.
- **Facilities:** 1,763 OSM facilities, each linked to the nearest street point (≤ 250 m). A facility is "at risk" when its access street is orange or red.

### 6.5 Response zones and RL dispatch
- **Zones:** DBSCAN (eps 250 m, min 5) on red street points. Clusters with more than 120 points are split by K-means. Each zone is labelled with the nearest named road and gets the nearest fire station as its depot.
- **Priority:** 2 × red points + orange points within 600 m.
- **Flood probability:** p_flood = mean P(heavy) × (0.5 + 0.5 × red share).
- **MDP:**
  - State: (severity level 0–3, pumps left 0–5, share of zones remaining 0–2)
  - Actions: hold / deploy
  - Reward: 0.7 × damage(score) if the zone floods, minus a 0.15 cost; damage = log(1 + score) / log(301)
- **Q-learning:**
  - Learns from the *expected* reward (P(flood) × damage) to reduce variance
  - Step size 1/√N(s,a), with a floor of 0.01
  - ε-greedy with linear decay to 0.05
  - 120,000 episodes, zones shuffled each episode
- **Data:** 127 flood-risk days, where the city's P(heavy) ≥ 0.25. 118 days for training (2001–2020), 9 for testing (2021–2024).
- **Evaluation:** stochastic flood outcomes, 30 repetitions per day.

### 6.6 Citizen reports
- **Seed corpus:** compositional, built from an incident phrase (sets the category), an optional urgency phrase and a place. Languages: EN, Hinglish, MR, HI.
- **Preprocessing:** Pune place names are masked with a PLACE token.
- **Features:** char_wb 2–5 + word 1–2 TF-IDF.
- **Models compared:** Multinomial NB (deployed), Complement NB, LR, Linear SVM.
- **CV:** GroupKFold(5) by incident phrasing.
- **In the product:** the model suggests a category and flags urgency. Urgent reports, including any "waist-deep" one, are listed first in the control room.

---

## 7. Results (tables ready to adapt)

### 7.1 Heavy-rain forecast — test 2021–2024 (9,180 cell-days)

| Model | ROC-AUC | PR-AUC | BSS | POD | FAR | CSI | HSS |
|---|---|---|---|---|---|---|---|
| Climatology | 0.887 | 0.266 | 0.000 | 0.624 | 0.765 | 0.206 | 0.305 |
| Persistence | 0.762 | 0.309 | −0.088 | 0.541 | 0.459 | 0.371 | 0.524 |
| Gaussian NB | 0.931 | 0.357 | −3.213 | 0.706 | 0.588 | 0.352 | 0.498 |
| Decision Tree | 0.950 | 0.566 | 0.215 | 0.771 | 0.568 | 0.382 | 0.532 |
| SVM (RBF) | 0.925 | 0.622 | 0.330 | 0.648 | 0.391 | 0.458 | 0.614 |
| Bagging (DT) | 0.960 | 0.625 | 0.315 | 0.731 | 0.499 | 0.423 | 0.577 |
| Random Forest | 0.962 | 0.633 | 0.294 | 0.777 | 0.542 | 0.405 | 0.557 |
| KNN (k=50) | 0.952 | 0.645 | 0.369 | 0.746 | 0.526 | 0.408 | 0.560 |
| MLP | 0.962 | 0.646 | 0.323 | 0.765 | 0.575 | 0.376 | 0.525 |
| LightGBM | 0.960 | 0.655 | 0.313 | 0.694 | 0.475 | 0.427 | 0.581 |
| Ensemble (LGBM+XGB+RF) | 0.964 | 0.655 | 0.311 | 0.768 | 0.530 | 0.411 | 0.564 |
| **XGBoost (deployed)** | **0.961** | **0.655** | **0.279** | **0.771** | **0.534** | **0.409** | **0.561** |
| Logistic Regression | 0.950 | 0.658 | 0.310 | 0.731 | 0.548 | 0.387 | 0.538 |

**Talking points:**
- **Skill over baseline:** PR-AUC is about 2.5× climatology for all strong models.
- **The top models are statistically tied** (0.645 vs 0.640 on validation). Selection used validation only.
- **City cells are much harder:** ROC-AUC 0.81 and POD 0.22 on only 9 heavy-rain days in the test period. City heavy rain is rare and often convective.
- **Top TreeSHAP drivers:** rain in the last 24 h, Ghats rain over 24 h, 30-day wetness, domain westerly wind, ERA5 24 h precipitation, domain moisture.

### 7.2 Supporting analyses
- **PCA:**
  - 15 of 50 components keep 90 % of the variance.
  - PC1 explains 36.2 % (moisture/humidity loadings), PC2 13.9 % (antecedent rain).
  - A logistic model on 15 PCs drops from 0.658 to 0.602 PR-AUC.
- **Feature selection,** test PR-AUC of logistic regression on 10 features:

  | Method | PR-AUC |
  |---|---|
  | Forward (SFS) | 0.654 |
  | Backward (SBS) | 0.655 |
  | Filter, mutual information | 0.663 |
  | **Embedded L1** | **0.672** |
  | All 50 features (for comparison) | 0.658 |

  A sparse 10-feature L1 subset beats the full 50-feature model.
- **Weather regimes:**
  - K-means picks k = 2 by silhouette (0.359). Heavy-rain rate is 1 % in one regime and 27 % in the other.
  - Homogeneity/completeness: 0.14/0.27 for K-means, 0.13/0.32 for hierarchical.
  - DBSCAN flags 75 anomalous days; 80 % of them had heavy rain, against 17 % of normal days.
- **HMM:**

  | Phase | Mean rain/day | Self-transition | Share of days | Heavy-rain rate |
  |---|---|---|---|---|
  | Dry | 0 mm | 0.76 | 14 % | 0 % |
  | Break | 2.7 mm | 0.83 | 42 % | 1.9 % |
  | Active | 18.2 mm | 0.91 | 43 % | 41 % |

- **Apriori** (base rate 5.1 %). Top rules for heavy rain:

  | Rule | Confidence | Lift |
  |---|---|---|
  | cloudy + high moisture flux + heavy rain yesterday | 0.81 | 15.9 |
  | high moisture flux + heavy rain yesterday + wet week | 0.75 | 14.7 |

- **Rain amount regression** (test):

  | Model | MAE | R² | Heavy-day MAE |
  |---|---|---|---|
  | Random Forest | 6.3 mm | 0.64 | 43 mm |
  | Linear Regression | 7.6 mm | 0.18 | — |
  | Linear SVR | 8.3 mm | −0.22 | — |

### 7.3 Street susceptibility — spatial CV (32 hotspots, 21,458 road locations)

| Model | ROC-AUC | Fold mean ± sd | Top-10 % capture | Top-20 % capture |
|---|---|---|---|---|
| Baseline: high TWI | 0.504 | 0.518 ± 0.053 | 13 % | 13 % |
| Baseline: low HAND | 0.566 | 0.556 ± 0.066 | 22 % | 28 % |
| KNN (all 15) | 0.516 | 0.519 ± 0.044 | 6 % | 6 % |
| SVM RBF (all 15) | 0.594 | 0.626 ± 0.172 | 25 % | 38 % |
| LightGBM (all 15) | 0.696 | 0.726 ± 0.078 | 19 % | 38 % |
| Logistic Regression (physics 6) | 0.733 | 0.755 ± 0.119 | 41 % | 50 % |
| Random Forest (physics 6) | 0.737 | 0.751 ± 0.121 | 38 % | 56 % |
| Baseline: near nala | 0.770 | 0.775 ± 0.069 | 38 % | 50 % |
| **Monotone LightGBM (physics 6, deployed)** | **0.761** | **0.778 ± 0.113** | **34 %** | **56 %** |

**Talking points:**
- **Overfitting with few labels:** unconstrained models on 15 features overfit 30 labels.
- **Monotone physics constraints:** +0.065 AUC and +18 points of top-20 % capture.
- **Ranked against the strong "distance to nala" rule,** the deployed model is statistically tied but uses more evidence.
- **Feature importance** (AUC drop when permuted): distance to nala 0.126, distance to river 0.047, road density 0.047, TPI 0.034, HAND 0.025, sink depth 0.018.
- **Weaknesses:**
  - reporting bias (hotspots are reported only in built-up areas)
  - a 30 m DSM includes buildings
  - southern Katraj flash-flood points score low

### 7.4 Alert hindcast

| Day | City rain (IMD) | P(heavy) city | Hotspots orange/red |
|---|---|---|---|
| 2019-09-25 Ambil Odha flash flood | 78.1 mm | 0.04 | 0 / 32 (miss) |
| 2024-07-24 eve of flood | 40.2 mm | 0.34 | 17 / 32 |
| **2024-07-25 Sinhagad Rd / Ekta Nagar** | 113.9 mm | 0.62 | **31 / 32** |
| 2022-08-20, 2023-07-10, 2024-08-15 (ordinary) | 0–0.6 mm | 0.00 | 0 / 32 |

**On 25 July 2024 (replay):**
- 2,672 red, 4,160 orange and 14,934 yellow road locations.
- About 401 km of road on red.
- Facilities whose access road is on alert include Sassoon Hospital.
- Response zones led by Uttamchand Mukunddas Gandhi Path (Kothrud fire-station depot, 1.0 km).

### 7.5 RL dispatch — test 2021–2024 (9 days, 30 stochastic repetitions)

| Policy | Avg reward / event |
|---|---|
| Oracle (knows outcomes; upper bound) | 2.333 |
| Rule: deploy only to zones with ≥ 50 red segments (hand-tuned) | 0.913 |
| **Q-learning (learned)** | **0.874** |
| Rule: deploy if above median severity | 0.867 |
| Rule: deploy until pumps run out (naive) | 0.428 |
| Never deploy | 0.000 |

**Learned policy:**
- Always deploy to severity-3 zones.
- Deploy to severity-2 zones while at least 2 pumps are left.
- Deploy to severity-1 zones only while 4 or more are left.
- Deploy to severity-0 zones only with all 5 left.

This is an interpretable, monotone threshold policy, learned from data alone. Its score is 2.0× the naive rule and −4.3 % vs the best hand rule. The 9-day test set is small.

### 7.6 Citizen-report classifier — GroupKFold over 92 unseen incident phrasings (968 sentences)

| Model | Category macro-F1 | Urgency F1 | EN | Hinglish | MR | HI |
|---|---|---|---|---|---|---|
| Logistic Regression | 0.511 | 0.995 | 0.676 | 0.451 | 0.468 | 0.407 |
| Linear SVM | 0.503 | 0.995 | 0.671 | 0.532 | 0.424 | 0.356 |
| Complement NB | 0.502 | 0.926 | 0.642 | 0.482 | 0.485 | 0.377 |
| **Multinomial NB (deployed)** | **0.486** | **0.939** | 0.600 | 0.467 | 0.481 | 0.398 |

**Notes:**
- **The evaluation is deliberately harsh:** it tests on phrasings never seen in training.
- **Urgency generalises well,** because urgency words recur across reports.
- **The seed set is synthetic,** so the product only suggests and the citizen confirms.
- **Engineering choices:**
  - masking place names was essential, because place names appear in every category
  - generating more examples per phrasing raised Marathi from 0.39 to 0.48

### 7.7 Short-range (0–24 h) NWP forecasts — do they add skill? (2022–2024, leave-one-season-out)

**Setup:**
- **Data:** Open-Meteo Historical Forecast API. The hourly archive is a "best available short-lead forecast" from five operational models:

  | Model | Archived from |
  |---|---|
  | GFS | 2022 |
  | JMA | 2022 |
  | ICON | 2023 |
  | GEM | 2023 |
  | ECMWF IFS 0.25° | 2024 |

- **Features** for each IMD day window (03–03 UTC):
  - per-model 24 h total and 3 h peak
  - ensemble mean, median, max and std
  - share of models ≥ 64.5 mm and ≥ 35 mm, ignoring models with no archive
  - 3×3-cell neighbourhood maximum
- **Sample:** 6,885 cell-days, 266 heavy-rain days (8 in the city cells).

| Approach | ROC-AUC | PR-AUC | POD | FAR | CSI | HSS |
|---|---|---|---|---|---|---|
| **A. Morning ML model (XGBoost)** | 0.961 | **0.683** | 0.613 | 0.373 | 0.449 | 0.605 |
| B. Raw ensemble (share of models ≥ 64.5 mm) | 0.644 | 0.167 | 0.316 | 0.713 | 0.177 | 0.271 |
| C. NWP-only logistic model | 0.924 | 0.362 | 0.492 | 0.588 | 0.289 | 0.424 |
| D. Stacked blend (ML logit + NWP features) | 0.962 | 0.680 | 0.624 | 0.362 | 0.461 | 0.617 |
| E. ML raised by NWP rule (≥ 35 / ≥ 64.5 mm) | 0.960 | 0.673 | 0.613 | 0.373 | 0.449 | 0.605 |
| F. max(ML, NWP-only) | 0.962 | 0.629 | 0.620 | 0.417 | 0.430 | 0.585 |

**Per-model daily skill** (each judged only on its archived seasons):

| Model | ROC-AUC | PR-AUC |
|---|---|---|
| ECMWF | 0.90 | 0.30 |
| GFS | 0.92 | 0.30 |
| ICON | 0.93 | 0.33 |
| GEM | 0.88 | 0.17 |
| JMA | 0.88 | 0.30 |

On the same 2024 sample, the morning ML model reaches PR-AUC 0.67 and the ensemble mean 0.35.

**Event check, 25 July 2024 (city cells):**
- Observed: 114 mm.
- The ensemble mean forecast 24 mm (range 4–58 mm), so the NWP models under-forecast the flood.
- The ML model gave 0.62; the stacked blend would have lowered it to 0.20.

**Finding (a publishable negative result):**
- At daily, 0.25° scale, operational NWP short-range rain adds no skill over the observation-driven morning ML model.
- A naive "raise if NWP is wet" rule slightly *reduces* skill, so it was removed from the live system.
- NWP is therefore used for **timing**: an hour-by-hour outlook, plus an intense-rain watch when ≥ 3 models forecast ≥ 30 mm in 3 h.
- **Caveats:** the archive starts in 2022, so the 2019 cloudburst cannot be hindcast, and there is no hourly gauge truth to verify the watch.

### 7.8 Photo verification of citizen reports (CNN, transfer learning)

**Setup:**
- **Data:** Flood10k (Odebode & Bennett Milburn 2025, Mendeley Data, DOI 10.17632/4sgcd7zdsp.1, CC BY-NC 4.0).
  - 10,320 usable photos: 5,093 flooded, 5,227 normal.
  - Flooded photos come from CrisisMMD, the Twitter Flood Dataset and FloodIMG.
  - Normal photos come from Twitter and Google image searches.
- **Split:** 70/10/20, stratified, seed 42.
- **Model:**
  - Backbone: ImageNet MobileNetV3-Small, frozen, giving 576-d pooled features.
  - Heads compared on those features, against a colour-histogram baseline with no deep learning.
  - Deployed head: logistic regression, folded into the network and exported to ONNX (3.7 MB). ONNX and PyTorch outputs differ by at most 7e-8.

| Model (test, 2,064 photos) | Accuracy | F1 | Precision | Recall | ROC-AUC |
|---|---|---|---|---|---|
| Colour histogram + LR (no deep learning) | 0.857 | 0.859 | 0.835 | 0.885 | 0.915 |
| CNN features + KNN (k=15) | 0.929 | 0.931 | 0.890 | 0.976 | 0.980 |
| CNN features + Random Forest | 0.949 | 0.949 | 0.938 | 0.960 | 0.985 |
| CNN features + Linear SVM | 0.952 | 0.951 | 0.955 | 0.948 | 0.987 |
| **CNN features + Logistic Regression (deployed)** | **0.953** | **0.952** | **0.956** | **0.949** | **0.988** |

- **"Verified" threshold:** 0.70, chosen on validation for ≥ 95 % precision. On test it gives precision 0.967 and recall 0.916.
- **Confusion matrix at 0.5:** TN 1000, FP 45, FN 52, TP 967.
- **Two-tier deployment:**
  - The *same* ONNX model runs in the browser (onnxruntime-web, WebAssembly). This gives instant feedback, and the photo never needs to leave the phone just to be checked.
  - It runs again on the server (onnxruntime) for the authoritative score shown in the control room.
- **Privacy:** photos are resized to ≤ 1024 px on the device, and the canvas re-encode strips EXIF/GPS. The server stores ≤ 640 px JPEGs.
- **Limitations:**
  - The "normal" class comes partly from Google searches, so some source bias is possible.
  - Not yet tested on Pune street photos; collect them from the app and re-evaluate.

### 7.9 Alert delivery (WhatsApp / SMS)

- **Opt-in flow:**
  1. The citizen chooses WhatsApp or SMS, a location, a language (EN/MR/HI) and a minimum level (yellow/orange/red), with explicit consent.
  2. A 6-digit code proves phone ownership. It's stored as a hash, expires in 15 min, and allows 5 attempts and at most 3 sign-ups per number per hour.
- **Morning dispatch:** at 08:45 IST, a GitHub Actions cron calls an admin-token-protected endpoint.
  - Each verified subscriber gets an alert only if *their* street reaches their level.
  - No duplicate is sent the same day unless the level rises.
  - Every message carries an unsubscribe link, and every attempt is logged.
- **Providers:** Twilio SMS, Twilio WhatsApp, and Meta WhatsApp Cloud API (business-initiated messages need an approved template). With no provider configured, the system logs a dry run.
- **Tested end to end:**
  - API tests cover consent, phone validation, the code, dispatch on a red day vs a green day, de-duplication, unsubscribe, and never exposing phone numbers.
  - The live web sign-up was tested in dry-run mode.

### 7.10 Engineering quality
- **Tests:** 30 automated pytest tests (units + API integration on the shipped artifacts).
- **CI:** GitHub Actions runs the tests plus web lint, type check and production build on every push.
- **Scheduled jobs:**
  - live-data snapshot every 3 h
  - morning alerts
  - keep-alive ping every 10 min
- **Storage:** Postgres (Neon) through `DATABASE_URL`, with SQLite fallback and lightweight migrations.
- **Live robustness:** live-mode calls give up after 2 quick tries and are cached for 30 min. An earlier retry loop could block a request for about 3 minutes under upstream rate limiting.

---

## 8. System and deployment (for a "System design" section)

```
IMD/ERA5 archive ┐                       ┌─ Citizen app (mobile-first, EN/MR/HI)
Open-Meteo (3 h  ├─► Sentinel service ──► FastAPI (Render, Docker, ~270 MB) ─┤
 GitHub snapshot)│   rain · susceptibility│                                    └─ Control room (zones, RL plan,
DEM / OSM layers ┘   risk · impact · RL   │                                       impact, reports, 14-day timeline)
                     NB report triage     └─ /api/model-card → "How it works" page
```

**Engineering points worth a paragraph:**
- **Memory: 400–500 MB → 220–270 MB,** to fit the free tier.
  - CPU-only XGBoost saved 190 MB (the standard wheel ships CUDA code).
  - No GIS libraries at runtime.
  - Arrow's system allocator.
  - Text-cached GeoJSON.
- **Rate limits:** Open-Meteo rate-limits shared cloud IPs (HTTP 429). The fix is a scheduled GitHub Actions pipeline that publishes a snapshot to a `live-data` branch, which the API reads.
- **Replay mode** runs any archived day through identical logic, for demos and hindcasts.

**Live:** https://monsoon-sentinel-zeta.vercel.app

## 9. Limitations (state honestly)
1. **Convective cloudbursts:** these are not predictable from 08:30 IST reanalysis state, as the 2019 miss shows. Needs NWP/radar nowcasting.
2. **Few, biased labels:** about 30 public hotspots, reported only in built-up areas. The official PMC list of 120 spots is not public.
3. **Live-mode approximation:** the model trained on gauge rain receives model-analysis rain in live mode.
4. **Simulation-based RL:** the dispatcher uses simulated flood outcomes, not observed ones, and the test set is small.
5. **Synthetic text data:** the report classifier is trained on seed text and must be retrained on real reports.
6. **Temporary storage:** citizen reports are lost when the free-tier API restarts.
7. **DSM, not DTM:** the 30 m surface model includes buildings, which adds terrain error in dense areas.

## 10. Future work
- Ingest NWP and nowcast rainfall (GFS/ECMWF hourly, IMD radar) for convective events.
- Obtain the PMC hotspot list via RTI and get event dates from traffic-police call logs → event-level labels.
- Conformal prediction intervals for street risk; transfer to Mumbai/Chennai.
- Deep RL with travel times and the real pump fleet; multi-agent pump + crew dispatch.
- Re-evaluate the photo CNN on Pune photos collected through the app; an active-learning loop from confirmed reports.
- Hourly rain-gauge or radar truth to verify the intense-rain watch; post-processing NWP at sub-daily scale.
- A persistent database plus WhatsApp/SMS alert delivery.

## 11. Figures available (paths)

| Figure | File |
|---|---|
| SHAP summary (deployed XGBoost) | `reports/rain/shap_summary.png` |
| Reliability diagram | `reports/rain/reliability.png` |
| July 2024 hindcast (probability vs rain) | `reports/rain/case_pune_jul2024.png` |
| PCA scree | `reports/rain/analysis/pca_scree.png` |
| Weather regimes (elbow + PC plot) | `reports/rain/analysis/weather_regimes.png` |
| HMM phases 2024 | `reports/rain/analysis/hmm_phases_2024.png` |
| Susceptibility map | `reports/urban/susceptibility_map.png` |
| Alert hindcast on 6 days | `reports/urban/hindcast_alerts.png` |
| Q-learning curve | `reports/dispatch/learning_curve.png` |
| Morning ML vs NWP precision-recall curves | `reports/nowcast/pr_curves.png` |
| Photo verifier benchmark | `reports/photo/photo_benchmark.md` |
| App screenshots | take from the live demo (citizen, control room, "How it works") |

## 12. Reproducibility

```bash
python scripts/download_data.py        # IMD + ERA5
python scripts/train_rain.py           # benchmark + SHAP
python scripts/analyze_rain.py         # PCA, selection, clustering, HMM, Apriori, regression
python scripts/geocode_hotspots.py     # hotspot catalogue
python scripts/build_urban_layers.py   # DEM hydrology + OSM
python scripts/train_susceptibility.py # spatial CV + map
python scripts/hindcast_risk.py        # alert hindcast
python scripts/build_impact.py         # facilities
python scripts/train_dispatch.py       # Q-learning
python scripts/make_report_seed.py && python scripts/train_report_classifier.py
python scripts/build_nowcast.py         # 5-model short-range forecasts vs IMD
python scripts/train_photo_verifier.py # needs data/raw/flood10k/Flood10k.zip (Mendeley, CC BY-NC 4.0)
python scripts/build_model_card.py && python scripts/export_artifacts.py
python -m pytest -q                    # 30 tests
```
Seeds are fixed (42 / 0). Splits are chronological for rain and spatial (2 km blocks) for streets.

## 13. Target venues
- **Conferences:** IEEE INDICON, ICCCNT, IEEE TENCON; Springer LNNS (Indian AI/ML conferences).
- **Journals:** *Natural Hazards*, *Urban Climate*, *Journal of Hydroinformatics*, *Int. J. Disaster Risk Reduction*.
- **Data paper:** *Data in Brief* (Pune hotspot catalogue + scored street network).

## 14. References collected during the project
- iFLOWS-Mumbai — https://pib.gov.in/PressReleasePage.aspx?PRID=1630928 ; NCMRWF verification https://websevak.ncmrwf.gov.in/iFlows_Mumbai_report_modified_v3.pdf
- Mumbai radar U-Net nowcasting — https://arxiv.org/html/2607.16080v1
- CloudMorphGAN — https://link.springer.com/article/10.1007/s12524-025-02143-w
- Physics-informed ConvLSTM Mumbai — https://arxiv.org/pdf/2404.01122
- Four-city ConvLSTM + XAI — https://arxiv.org/pdf/2511.11152
- Event-level extreme rainfall India — https://arxiv.org/pdf/2602.03166
- Deep learning for extreme rainfall review — https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1908848/full
- XAI monthly rainfall Chhattisgarh — https://link.springer.com/article/10.1007/s00704-025-05645-2
- Multi-scale rainfall XAI Bengaluru — https://link.springer.com/article/10.1007/s00477-026-03245-8
- AI weather models vs IMD stations — https://arxiv.org/html/2509.01879v1
- GraphCast monsoon biases — https://arxiv.org/pdf/2607.11905
- Mumbai waterlogging ML + GIS — https://link.springer.com/article/10.1007/s10708-022-10731-3
- Mumbai crowdsourced floods — https://arxiv.org/pdf/2306.09770 ; NLP crowdsourcing — https://www.sciencedirect.com/science/article/abs/pii/S2210670725006699
- AI for urban flood early warning review — https://www.researchgate.net/publication/415518711_Artificial_Intelligence_for_Urban_Flood_Early_Warning_A_Review_of_Recent_Advances
- Physics-enhanced ML short-range flood — https://doi.org/10.2166/hydro.2026.180
- Ensemble ML road flooding — https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12546731/
- Rainfall temporal statistics for urban flood — https://www.sciencedirect.com/science/article/pii/S2590061725000122
- CHANS + hierarchical RL pumps — https://repository.lboro.ac.uk/articles/journal_contribution/A_coupled_human_and_natural_systems_CHANS_framework_integrated_with_reinforcement_learning_for_urban_flood_mitigation/27961617
- DRL pump stations — https://mdpi.com/2073-4441/16/23/3398
- LLM multi-agent flood dispatch — https://arxiv.org/pdf/2508.14654
- Sentinel-1/2 flood mapping — https://arxiv.org/pdf/2606.30511
- Water level from social media images — https://ar5iv.labs.arxiv.org/html/2007.06749
- Pune hotspot sources: https://www.mypunepulse.com/pune-traffic-police-flag-26-waterlogging-hotspots-ahead-of-peak-monsoon-seek-pmcs-urgent-intervention/ ; https://www.thebridgechronicle.com/pune/heavy-rains-waterlogging-90-locations-pune ; https://www.punekarnews.in/?p=182761 ; https://citizenmatters.in/pune-september-flash-floods-causes-and-aftermath-14109
- Data: IMD gridded rainfall (Pai et al., 2014, *Mausam*); ERA5 (Hersbach et al., 2020, *QJRMS*); Copernicus GLO-30; OpenStreetMap.
- Flood10k: Odebode, A.; Bennett Milburn, A. (2025) Flood10k Dataset, Mendeley Data, V1, doi:10.17632/4sgcd7zdsp.1 (+ CrisisMMD: Alam, Ofli & Imran 2018, ICWSM).
- MobileNetV3: Howard et al. 2019 (ICCV); ONNX Runtime.
- Open-Meteo Historical Forecast API (ECMWF IFS, GFS, ICON, GEM, JMA).
- Methods to cite: XGBoost (Chen & Guestrin 2016); LightGBM (Ke et al. 2017); SHAP/TreeSHAP (Lundberg & Lee 2017; Lundberg et al. 2020); DBSCAN (Ester et al. 1996); Q-learning (Watkins & Dayan 1992); HAND (Rennó et al. 2008); TWI (Beven & Kirkby 1979); verification scores (Wilks, *Statistical Methods in the Atmospheric Sciences*).

> Before submitting, check every external citation against the original paper. The entries above come from search results gathered during development.
