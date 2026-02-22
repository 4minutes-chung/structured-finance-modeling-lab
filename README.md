# RMBS Modelling vA_1

Simple RMBS modelling baseline for portfolio use.

## What is included
- `build_rmbs_workbook.py`: creates `rmbs_interview_model.xlsx`
- `rmbs_python_validation.py`: v1 RMBS cashflow and waterfall validation
- `rmbs_v2_engine.py`: v2 delinquency-state and trigger model
- `rmbs_excel_python_compare.py`: compares Excel export with Python monthly output
- `scenario_config.py`: shared scenario config loader
- `real_data_scripts/`: public-data pull and calibration scripts
- `config/`: calibration and scenario YAML files
- `data/processed/`: sample processed macro panel
- `rmbs_interview_model.xlsx`: workbook snapshot

## Quick run
```bash
python3 build_rmbs_workbook.py
python3 rmbs_python_validation.py
python3 rmbs_v2_engine.py
```

## Real-data calibration run
```bash
python3 real_data_scripts/04_calibrate_assumptions.py \
  --panel-csv data/processed/macro_panel_monthly.csv \
  --rules-yaml config/calibration_rules.yaml \
  --template-yaml config/scenario_template.yaml \
  --out-yaml config/scenarios_calibrated.yaml
```

## Notes
- This is a learning and interview baseline, not a production model.
