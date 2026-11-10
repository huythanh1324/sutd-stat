# Project status by pipeline stage

Checked on 2026-11-08 by reading the code and notebook headings. **Nothing was re-run for this report.**

| # | Item | Status | Main file |
|---|---|---|---|
| 1 | Data acquisition | Done | `data.ipynb` |
| 2 | Cleaning | Done | `load_data.py`, `features.py` |
| 3 | Data dictionary | Done | `data.ipynb`, `data_transform.ipynb` |
| 4 | Feature building | Done | `features.py`, `data_transform.ipynb` |
| 5 | Exploratory analysis | Done | `data.ipynb`, `linear_regression.ipynb` §2 |
| 6 | Linear regression | Done (no saved outputs) | `linear_regression.ipynb` §3–10 |
| 7 | Logistic regression | **Missing** | none |
| 8 | Diagnostics | Done for linear regression only | `linear_regression.ipynb` §7 |

---

## 1. Data acquisition
- **What exists:** `data.ipynb` downloads three public sources:
  - NEA PM2.5 (`/v2/real-time/api/pm25`): hourly, 5 regions
  - NEA weather, collection 1459: 1-minute readings for air temperature, relative humidity, rainfall, wind speed and wind direction
  - NASA FIRMS active fires: MODIS and VIIRS, area CSV API, fetched in 5-day chunks
- **How it works:** the shared helper `get_json` backs off and retries on 429 and 5xx errors, and `get_all_pages` follows pagination.
- **Caching:** each `crawl_*` function reuses the cached file in `data/raw/` if it exists. Weather is cached per variable per day, so an interrupted crawl resumes where it stopped.
- **Coverage:** PM2.5 and FIRMS cover 2023-09-15 → 2023-10-31. Weather covers the same window.
  - Only the `*_SP` FIRMS products have rows. The `*_NRT` products are empty for 2023.
  - The raw PM2.5 file is now named `pm25_2020-01-01_2025-12-31.csv`, so check that `CLAUDE.md` still describes the coverage correctly.
- **Gaps:** most of 8 Oct, which falls inside the haze peak, is missing.

## 2. Cleaning
- `load_data.py`:
  - joins all PM2.5 files and removes duplicates
  - drops `updatedTimestamp`, so the back-fill date can't leak into the features
  - converts times to SGT
  - adds UTC and SGT timestamps to the FIRMS data
- `features.py`:
  - puts everything on a full hourly grid (`hourly_grid`), so missing hours become explicit NaN rows
  - computes the island mean only for hours where all 5 regions report
  - uses only the weather stations that report all 5 variables, aggregated per station first and then across the island
  - sums rainfall instead of averaging it, and converts wind speed from knots to m/s
  - averages wind direction as u/v vectors, never as raw angles
  - keeps only vegetation fires (`type == 0`) and drops low-confidence detections, using `VIIRS_SNPP_SP` only
- **Missing values:** a table in `linear_regression.ipynb` (§1) reports them, and every model is fitted on the same complete rows.

## 3. Data dictionary
- **Per source:** `data.ipynb` has a markdown dictionary for PM2.5, weather and FIRMS.
  - Each one covers units, sampling interval and time convention (hour-ending SGT, FIRMS in UTC).
  - The notebook ends with a caveats section to carry into modelling.
- **Modelling table:** `data_transform.ipynb` has a dictionary for it, plus a summary table of type, missing %, min and max for each column.
- **Feature plan:** the draft is in `../column_dictionary.xlsx`, outside the repo.

## 4. Feature building
`features.build_model_table(d, h=24)` returns one row per forecast time *t*. The target `y` is island-mean PM2.5 at *t* + 24 h. The features are:
- **Persistence:** `pm25_lag0` and `pm25_lag24`
- **Calendar:** `hour_sin`, `hour_cos` and `is_weekend`
- **Weather:** `temp`, `rh`, `rain_1h`, `rain_24h`, `ws_ms`, `u` and `v`
- **Fire:** log(1 + FRP) in four 90° sectors (N/E/S/W) over the past 24 h and the 24 h before that
- **Transport:** wind blowing from each sector multiplied by that sector's fire activity

Leakage guards:
- Every input uses only data time-stamped ≤ *t*.
- An assert checks that the target is aligned.

The output is `data/processed/model_table.csv`. **It does not exist at the moment**, so re-run `data_transform.ipynb` to create it.

## 5. Exploratory analysis
- **In `data.ipynb`:** profiles and sanity plots for each source, records-per-day checks, a map of weather stations against the PM2.5 regions, and notes on joining the tables in time.
- **In `linear_regression.ipynb` §2 (training data only):**
  - PM2.5 and fire time series (`figures/train_timeseries.png`)
  - each sector's share of fire radiative power, which selects S and E (≥ 5%)
  - a scatter matrix and correlation table
  - skew of PM2.5 against log PM2.5
- **Key finding:** the island mean never reaches NEA Band II (≥ 56 µg/m³). The maximum is 54.4.

## 6. Linear regression
`linear_regression.ipynb` follows the course's wine template:
- **Simple regression:** `y ~ pm25_lag0`, with training R² computed by hand and checked against statsmodels, and confidence intervals for the coefficients
- **Comparisons:** one-predictor models, a two-variable model, perfect collinearity and VIF checks
- **Model ladder:** season only → baseline (persistence + season) → + weather → + fire → + transport
  - Nested models are compared with ANOVA.
  - Standard errors are reported both as OLS and as autocorrelation-robust (HAC), with a robust joint Wald test on the fire terms.
- **Validation:** rolling-origin over 1–14 Oct, with persistence and hourly climatology as baselines
- **Final test:** 16–30 Oct, used once, with 15 Oct held out as a gap between training and test
  - Reports RMSE, MAE, skill vs persistence and R² against both the test mean and the training mean.
  - The improvement over persistence gets a confidence interval from a day-block bootstrap.
  - Also shows confidence vs prediction intervals, a log-target sensitivity check and the largest errors.
- **Status:** the code is complete, but the notebook has **no saved outputs**, so re-run it before quoting any numbers.

## 7. Logistic regression — missing
There is no logistic or classification code anywhere in the project. To add it:
- **Define a "high PM2.5" target.** Band II never occurs on the island mean, so use one of these instead:
  - a threshold set from the training data, e.g. its 75th–90th percentile
  - a fixed cut-off such as 37.5 µg/m³
  - the regional maximum instead of the island mean
- **Use the same setup as the linear model:** the same split and rolling-origin validation, and the same model ladder fitted with `smf.logit`.
- **Metrics:** log-loss, Brier score, ROC-AUC, a confusion matrix at the chosen threshold, and skill vs a persistence classifier ("high now → high tomorrow")
- **Diagnostics:** calibration (reliability) plot, binned residuals, influence measures and the robust Wald test on the fire terms

## 8. Diagnostics
- **What exists (linear regression only, §7):**
  - four-panel plot: residuals vs fitted, normal Q-Q, scale-location, and leverage coloured by Cook's distance (`figures/diagnostics.png`)
  - residuals over time and the residual ACF up to 72 h
  - VIF and HAC standard errors (§6), which deal with collinearity and autocorrelation
- **Missing:** diagnostics for logistic regression, which depend on item 7.

---

## Environment
- `.venv` was broken because it pointed to another user's Python. It was rebuilt with Python 3.14 and the packages from `requirements.txt`.
- The last attempt to re-run `data_transform.ipynb` did not finish, so `model_table.csv` is still missing.
