# Real Data Lab

This subfolder calibrates RMBS scenarios with public data while keeping the model explainable.

## Scope

- Geographic focus: U.S.
- Data tier: public macro and house-price data.
- Not institutional production. See `docs/limitations_non_production.md`.

## Folder Structure

- `config/`: calibration rules, templates, and generated scenario config.
- `data/raw/`: downloaded FRED and FHFA source files.
- `data/processed/`: merged monthly macro panel and summary.
- `scripts/`: ingestion and calibration scripts.
- `runs/`: local generated sandbox runs. This folder is ignored by Git.
- `docs/`: method, dictionary, and limitations.

## End-To-End Commands

Run from the repo root:

```bash
python3 real_data_lab/scripts/01_pull_fred.py
python3 real_data_lab/scripts/02_pull_fhfa.py
python3 real_data_lab/scripts/03_prepare_panel.py
python3 real_data_lab/scripts/04_calibrate_assumptions.py
python3 run_sandbox_validation.py \
  --skip-latex \
  --scenario-config real_data_lab/config/scenarios_calibrated.yaml \
  --output-root real_data_lab/runs
```

## Expected Key Outputs

- `config/scenarios_calibrated.yaml`
- `data/processed/macro_panel_monthly.csv`
- `runs/LATEST_RUN_PATH`
- `runs/<run_id>/logs/excellence_scorecard.md`

## Source URLs

- FRED mortgage rate: https://fred.stlouisfed.org/series/MORTGAGE30US
- FRED unemployment rate: https://fred.stlouisfed.org/series/UNRATE
- FHFA HPI datasets: https://www.fhfa.gov/house-price-index
