# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A notebook-first course project (SUTD 42.510 Statistical Learning, catalogue topic 1.2): do satellite fire detections and local weather improve short-horizon prediction of high-PM2.5 periods in Singapore, beyond persistence and seasonality? Linear regression (the PM2.5 level) and logistic regression (a high-PM2.5 event) are the methods so far. Course materials (project rules/rubric, catalogue, lecture PDFs), the draft feature plan (`column_dictionary.xlsx`) and the professor's `WinePrediction(1) (1).Rmd` (the template `linear_regression.ipynb` follows) live in the parent folder `..`, outside this repo.

Rubric points that constrain the analysis: validate with a time-based split (hold out later periods or whole haze seasons, never random rows), compare against a persistence/seasonal baseline, do all preprocessing and feature selection on training data only, keep the final test set untouched until the end, and log AI help in `AI_USE.md`.

## Commands

The `.venv` uses Python 3.14 (created with uv). Run commands with `.venv\Scripts\python.exe`, or activate it first.

```
pip install -r requirements.txt     # pandas, numpy, requests, matplotlib, ipykernel, statsmodels, nbconvert
python load_data.py                 # loads every cached file under data/raw and prints row counts and time spans (no API calls)
python features.py                  # builds the modelling table and prints non-missing counts per column
jupyter nbconvert --to notebook --execute --inplace <notebook>.ipynb   # run a notebook headless
```

Run the notebooks in order: `data.ipynb` (only to crawl) → `data_transform.ipynb` (writes `data/processed/model_table.csv`) → `linear_regression.ipynb` and `logistic_regression.ipynb` (both read that CSV and save figures to `figures/`). There are no tests or linters. scikit-learn is not installed yet.

`.env` (gitignored, template in `.env.example`) holds `FIRMS_MAP_KEY` and the optional `DATAGOV_API_KEY` (raises the data.gov.sg rate limit). Only `data.ipynb` needs them.

## Architecture

There are three stages, connected only through files under `data/` (gitignored):

1. **`data.ipynb`: crawl and document.** It calls the APIs, flattens the JSON into long, tidy tables, writes the cache, and holds the data dictionary for each source. Every `crawl_*` function returns the cached file if it exists, so delete a file to force a re-crawl. The shared helpers are in cell 4: `get_json` (back-off on 429/5xx; a 404 returns `{}`), `get_all_pages` (follows `paginationToken`), `to_sgt` and `profile`. Each source section follows the same order: crawl → `profile` → markdown dictionary → sanity plots. The `START/END`, `WEATHER_START/END` and `BBOX` settings are in cell 3.
2. **`load_data.py` + `features.py` → `data_transform.ipynb`: modelling table.** `load_all(start, end)` reads the cache only, never the APIs. The optional dates (inclusive) filter PM2.5 by `date`, weather by per-day file and FIRMS by UTC `acq_date`. `data_transform.ipynb` sets `START, END = "2023-09-15", "2023-10-31"`, because 6 years of 1-minute weather do not fit in memory. `features.build_model_table(d, h=24)` returns one row per hour-ending forecast time t with target `y` = island-mean PM2.5 at t + h, and asserts the alignment. Every input must use only data time-stamped ≤ t; keep that rule when adding features. Fires use `VIIRS_SNPP_SP` only, `type == 0`, confidence ≠ `l`, grouped into four 90° bearing sectors (N/E/S/W) from Singapore. The notebook saves `data/processed/model_table.csv` with a data dictionary.
3. **`linear_regression.ipynb`: analysis.** Generated to mirror the wine notebook's sections. The split is by forecast time: train ≤ 14 Oct, 15 Oct embargoed, final test 16–30 Oct. Model choice uses rolling-origin validation over 1–14 Oct. Sectors are chosen on training data only (≥ 5% of fire radiative power, which keeps S and E). Weather models switch on automatically once `temp` covers > 90% of hours. Test R² uses the test mean; skill vs persistence is the headline metric. The end of the validation section has a variable-level subset-selection subsection (best subset with the size chosen by rolling-origin CV, forward/backward stepwise, lasso standardised within folds, stability counts over the rolling-origin folds), with every candidate tagged by data source; its `Best subset (CV)` model is added to `formulas`/`predictors` so the final test scores it once.
4. **`logistic_regression.ipynb`: event analysis.** Same split, sectors, formula ladder and rolling-origin validation as the linear notebook. Target `high` = `y ≥ 25` µg/m³ (WHO interim target 4 applied hourly; it equals the training 75th percentile). It covers likelihood-ratio tests, HAC Wald test of the fire terms, odds ratios, logistic diagnostics (binned residuals, calibration, Hosmer–Lemeshow, Cook's distance, residual ACF), Brier skill vs persistence (headline), AUC, and a warning cut-off chosen on validation by the Peirce skill score. The test period has only 12 high hours, so test metrics are noisy. The end of the validation section has a variable-level subset-selection subsection (best subset with the size chosen by rolling-origin CV, forward/backward stepwise, lasso standardised within folds, stability counts over the rolling-origin folds), with every candidate tagged by data source; its `Best subset (CV)` model is added to `formulas`/`predictors` so the final test scores it once.

`load_data.py` behaves differently from `data.ipynb` in a few ways:
   - `load_pm25` concatenates **every** `pm25_*_*.csv` and removes duplicates, so crawling an extra date range just adds another file. It drops `updatedTimestamp` unless `keep_updated=True`.
   - `weather_stations` has one row per (station, variable), not one row per station as in the notebook.
   - `firms` is a dict keyed by source (e.g. `VIIRS_SNPP_SP`), because MODIS and VIIRS have different columns. Empty sources are skipped. Each table gets `acq_datetime_utc` and `acq_datetime_sgt`.

Cache layout: `data/raw/pm25_{start}_{end}.csv` + `pm25_regions.csv`; `data/raw/weather/<endpoint>/<date>.csv.gz` + `<date>_stations.csv` (one file per variable per day, so an interrupted crawl resumes); `data/raw/firms/<SOURCE>_{start}_{end}.csv` (fetched in 5-day chunks).

## Current data coverage

- The cache (`data/raw`) now holds 2020-01-01 → 2025-12-31 for PM2.5, FIRMS and weather (`data.ipynb` `START/END`). The analysis still uses 2023-09-15 → 2023-10-31 (set in `data_transform.ipynb`). Only the `*_SP` FIRMS sources have rows; all `*_NRT` sources are empty. FIRMS detections run to 2023-11-01 in SGT, because the last UTC day crosses midnight in Singapore.
- Weather: `WEATHER_START/END` now equal `START/END` (full window). Crawling is slow (~2 min per variable per day anonymously; set `DATAGOV_API_KEY` to speed it up) and resumes from the per-day cache.
- The island-mean PM2.5 never reaches NEA Band II (≥ 56 µg/m³; max 54.4), and most of 8 Oct (inside the haze peak) is missing. An exceedance model will need a different threshold or the regional maximum.

## Data semantics that are easy to get wrong

- **PM2.5** is hourly and **hour-ending** (14:00 = mean over 13:00–14:00), for 5 regions only, in long form. It is not the 15-minute data the catalogue mentions, and it is not PSI. Some hours are missing, so reindex to a full hourly grid before computing lags. `updatedTimestamp` is a back-fill date and must never be used as a feature.
- **Weather** is 1-minute data (rainfall: 5-minute totals, so aggregate with a sum). Wind speed is in **knots**. Wind direction is the direction the wind blows *from*: aggregate it as u/v vectors, never with an arithmetic mean. Only 12 stations report all 5 variables; the rest are rain gauges. `to_hourly` in `data.ipynb` section 4 is the reference aggregation (`ceil("h")` hour-ending labels, per-station mean or sum, then the island mean).
- **FIRMS** `acq_date`/`acq_time` (HHMM integer) are **UTC**. MODIS and VIIRS differ in columns (`brightness` vs `bright_ti4`) and in `confidence` scales (0–100 vs `l`/`n`/`h`). Filter `type == 0` for vegetation fires. Use one product consistently (NRT vs SP) and say which one was used.
