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
├── build_rmbs_workbook.py          # workbook builder
├── rmbs_python_validation.py       # v1 cash-flow validator
├── rmbs_v2_engine.py               # delinquency + trigger engine
├── rmbs_excel_python_compare.py    # workbook export vs Python reconciliation
├── run_sandbox_validation.py       # one-command local runner
├── scenario_config.py              # scenario config loader
├── docs/
│   ├── ASSUMPTIONS.md
│   └── PRODUCTION_GAP.md
├── real_data_lab/
│   ├── config/
│   ├── data/
│   ├── docs/
│   └── scripts/
└── tests/
```

Generated run outputs are intentionally ignored by Git:

- `.sandbox_runs/`
- `real_data_lab/runs/`

## Quick Run

```bash
python3 run_sandbox_validation.py --skip-latex --run-id quick_check
```

Run with the calibrated public-data scenario config:

```bash
python3 run_sandbox_validation.py \
  --skip-latex \
  --scenario-config real_data_lab/config/scenarios_calibrated.yaml \
  --output-root real_data_lab/runs \
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
python3 run_sandbox_validation.py \
  --automate-excel \
  --skip-latex \
  --run-id excel_compare_check
```

For calibrated scenarios:

```bash
python3 run_sandbox_validation.py \
  --automate-excel \
  --skip-latex \
  --scenario-config real_data_lab/config/scenarios_calibrated.yaml \
  --output-root real_data_lab/runs \
  --run-id excel_compare_realdata
```

## Scope

This repo is best read as a transparent modeling exercise. The missing pieces
for real institutional use are documented in
[docs/PRODUCTION_GAP.md](docs/PRODUCTION_GAP.md).
