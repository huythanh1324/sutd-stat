# AI use log

Required by the project brief (§5). Add a row each time an AI tool contributes material code, text or figures.

| Date | Tool | Purpose | Representative prompt | What was generated | How it was checked |
|---|---|---|---|---|---|
| 2026-10-05 | Claude Code (Anthropic) | Choose columns for topic 1.2 and draft a feature dictionary | "From data.ipynb, which columns should I use for this project? I need a dictionary of columns and the reason for each." | `../column_dictionary.xlsx`: columns to keep/drop and formulas for derived features | Team review against the NEA/FIRMS documentation in `data.ipynb`; to be confirmed with the TA |
| 2026-10-06 | Claude Code (Anthropic) | Extend the weather crawl window; build the hourly feature table | "Perform a linear regression prediction that does not violate the project rules, following the flow of the wine prediction example." | `features.py`, new cells in `data_transform.ipynb`, the `WEATHER_START/END` change in `data.ipynb` | Built-in asserts (target alignment, no input after t); manual spot checks of sector assignment and hourly aggregation; the team must be able to explain every line |
| 2026-10-06 | Claude Code (Anthropic) | Linear regression analysis notebook | Same as above | `linear_regression.ipynb` (models, diagnostics, rolling-origin validation, final test) | Notebook runs end to end; manual R² equals statsmodels; persistence RMSE recomputed by hand; the team must verify each statistical claim before it goes into the report |
| 2026-11-08 | Claude Code (Anthropic) | Logistic regression notebook for high-PM2.5 hours; date window for the loaders | "Add a logistic regression notebook for high-PM2.5 periods" | `logistic_regression.ipynb`; `start/end` arguments in `load_data.py`; the window setting in `data_transform.ipynb` | Notebook runs end to end; manual log-likelihood, McFadden R² and AIC equal statsmodels; persistence Brier recomputed by hand; GLM and Logit coefficients asserted equal; the rebuilt table reproduces the earlier maximum of 54.4 µg/m³. The team must verify each claim before it goes into the report |
| 2026-11-08 | Claude Code (Anthropic) | Variable-level subset selection in both regression notebooks, with the method list and the reasoning for the chosen approach | "Put these into the ipynb as the reasoning of why we follow the recommended way" (variable level, highlight the data source of each variable) | New subsection at the end of the validation section of `linear_regression.ipynb` and `logistic_regression.ipynb` | In-notebook asserts: full-size subset equals the full model, size 0 equals 'Season only', stepwise paths share both ends, lasso with α = 0 equals OLS. The team must verify each claim before it goes into the report |

Notes:
- No confidential or personal data was shared. All sources are public (data.gov.sg, NASA FIRMS).
- Results in the report must come from running the notebooks, not from AI-written text.
