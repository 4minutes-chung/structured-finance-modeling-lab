# Real Data Method

## Source URLs
- FRED API docs: https://fred.stlouisfed.org/docs/api/fred
- FRED mortgage series page: https://fred.stlouisfed.org/series/MORTGAGE30US
- FRED unemployment series page: https://fred.stlouisfed.org/series/UNRATE
- FHFA HPI datasets page: https://www.fhfa.gov/house-price-index
- FHFA monthly HPI CSV: https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv

## Pull Timestamp
The exact pull timestamp is recorded in:
- `data/raw/fred/fred_pull_metadata.json`
- `data/raw/fhfa/fhfa_pull_metadata.json`

## Transformation Steps
1. FRED pull (`01_pull_fred.py`)
- Download raw CSV for:
  - `MORTGAGE30US`
  - `UNRATE`

2. FHFA pull (`02_pull_fhfa.py`)
- Download raw CSV:
  - `hpi_master.csv`

3. Panel prep (`03_prepare_panel.py`)
- Mortgage rate: weekly values aggregated to monthly mean.
- Unemployment rate: monthly mean (already monthly, aggregation still applied defensively).
- HPI filter criteria:
  - `hpi_type = traditional`
  - `hpi_flavor = purchase-only`
  - `frequency = monthly`
  - `place_name = United States`
- HPI year-over-year formula:
  - `hpi_yoy = hpi_index_t / hpi_index_(t-12) - 1`
- Output contract columns:
  - `date, mortgage_rate, unemployment_rate, hpi_index, hpi_yoy, source_timestamp`

4. Calibration (`04_calibrate_assumptions.py`)
- Use trailing window (`window_months` in `config/calibration_rules.yaml`).
- Compute scenario macro anchors via percentile targets.
- Convert macro deltas to model assumptions using linear sensitivities and hard bounds.
- Enforce monotonic stress ordering using `config/scenario_template.yaml`.

## Calibration Formula Form
For each parameter:

`param = clamp(base_param + sum_i(beta_i * feature_i), lower_bound, upper_bound)`

Feature definitions:
- `mortgage_rate_pp = mortgage_rate_scenario - mortgage_rate_base`
- `unemployment_rate_pp = unemployment_rate_scenario - unemployment_rate_base`
- `hpi_yoy_pp = (hpi_yoy_scenario - hpi_yoy_base) * 100`

## What This Gives You
- Real-data anchored scenario values.
- Same explainable v1/v2 model mechanics.
- Reproducible run outputs under `real_data_lab/runs/`.
