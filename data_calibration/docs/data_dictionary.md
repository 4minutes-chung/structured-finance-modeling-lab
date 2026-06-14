# Data Dictionary

## `data/processed/macro_panel_monthly.csv`
- `date`: Month start date in `YYYY-MM-DD`.
- `mortgage_rate`: Monthly average 30-year mortgage rate from FRED (`MORTGAGE30US`), percent level.
- `unemployment_rate`: Monthly unemployment rate from FRED (`UNRATE`), percent level.
- `hpi_index`: FHFA U.S. monthly purchase-only index (seasonally adjusted when available).
- `hpi_yoy`: Year-over-year index growth (`decimal`, e.g. `0.045` = 4.5%).
- `source_timestamp`: UTC timestamp when the panel was generated.

## `config/scenarios_calibrated.yaml`
Top-level keys:
- `meta`
  - `as_of_date`
  - `generated_at_utc`
  - `calibration_version`
  - `data_sources`
  - `window_months_used`
- `v1_scenarios[]`
  - `name`
  - `cpr_annual`
  - `cdr_annual`
  - `severity`
- `v2_scenarios[]`
  - `name`
  - `cpr_annual`
  - `severity`
  - `roll_to_30_annual`
  - `default_from_60_annual`
  - `cure_30_monthly`
  - `roll_30_to_60_monthly`
  - `cure_60_monthly`
