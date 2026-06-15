# RMBS Cash-Flow Prototype

This repository contains a residential mortgage-backed securities (RMBS)
cash-flow model built to show the mechanics: pool cash flows, tranche
waterfalls, stress scenarios, validation checks, and a simple public-data
calibration workflow.

It is intentionally simplified. It is not trying to be a rating-agency model or
a production credit engine.

## What It Does

- Builds an RMBS workbook with inputs, pool cash flows, tranche waterfall,
  integrity checks, and a compare export sheet.
- Runs an independent Python v1 model for cash-flow and allocation validation.
- Runs a v2 model with delinquency states and simplified trigger behavior.
- Calibrates stress scenarios from public FRED mortgage/unemployment data and
  FHFA HPI data.
- Produces local run folders with scorecards and validation artifacts.

## Repository Layout

```text
.
├── model/
│   ├── build_workbook.py           # workbook builder
│   ├── validate_cashflows.py       # v1 cash-flow validator
│   ├── delinquency_trigger_model.py
│   ├── compare_excel_python.py
│   ├── run_validation.py           # one-command local runner
│   └── scenario_config.py
├── docs/
│   ├── ASSUMPTIONS.md
│   └── LIMITATIONS.md
├── outputs/
│   └── rmbs_model_20260615.xlsx    # sample generated workbook
├── data_calibration/
│   ├── config/
│   ├── data/
│   ├── docs/
│   └── scripts/
└── tests/
```

Generated run outputs are intentionally ignored by Git:

- `.sandbox_runs/`
- `data_calibration/runs/`

The repo includes one sample workbook at `outputs/rmbs_model_20260615.xlsx` so
the model output can be inspected without running the scripts first.

## Quick Run

```bash
python3 model/run_validation.py --skip-latex --run-id quick_check
```

Run with the calibrated public-data scenario config:

```bash
python3 model/run_validation.py \
  --skip-latex \
  --scenario-config data_calibration/config/scenarios_calibrated.yaml \
  --output-root data_calibration/runs \
  --run-id quick_realdata
```

Run smoke tests:

```bash
python3 -m unittest discover -s tests
```

## Excel Reconciliation

The no-Excel run validates model identities and stress behavior but does not
complete workbook reconciliation. To compare Excel workbook outputs against
Python outputs on macOS with Microsoft Excel installed:

```bash
python3 model/run_validation.py \
  --automate-excel \
  --skip-latex \
  --run-id excel_compare_check
```

For calibrated scenarios:

```bash
python3 model/run_validation.py \
  --automate-excel \
  --skip-latex \
  --scenario-config data_calibration/config/scenarios_calibrated.yaml \
  --output-root data_calibration/runs \
  --run-id excel_compare_realdata
```

## Scope

This repo is best read as a transparent modeling exercise. The missing pieces
for real institutional use are documented in
[docs/LIMITATIONS.md](docs/LIMITATIONS.md).
