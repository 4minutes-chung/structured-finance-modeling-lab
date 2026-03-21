# RMBS Waterfall Modeling Lab

Excel + Python structured-finance modeling project focused on RMBS cash-flow waterfalls, tranche behavior, scenario stress testing, and independent output validation.

This is a research / interview-style modeling project, not a production securitization engine. The goal is to demonstrate transparent waterfall logic, validation discipline, and structured-credit analysis.

## What is included
- `build_waterfall_workbook.py`: creates `rmbs_waterfall_model.xlsx`
- `rmbs_validation_engine.py`: v1 RMBS cash-flow and waterfall validation
- `rmbs_v2_engine.py`: v2 delinquency-state and trigger model
- `rmbs_excel_python_compare.py`: compares Excel export with Python monthly output
- `scenario_runner.py`: sandbox runner for workbook generation, scenario runs, and validation outputs
- `scenario_config.py`: shared scenario config loader
- `real_data_scripts/`: public-data pull and calibration scripts
- `config/`: calibration and scenario YAML files
- `data/processed/`: sample processed macro panel
- `rmbs_waterfall_model.xlsx`: workbook snapshot

## Quick run
```bash
python3 build_waterfall_workbook.py
python3 rmbs_validation_engine.py
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


