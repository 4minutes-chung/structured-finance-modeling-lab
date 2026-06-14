# Production Gap

This project shows the mechanics of an RMBS cash-flow model and the checks
around it. It is useful for explaining how the model is built and tested. It is
not a model for rating, investment, or regulatory use.

## Current Strengths

- Reproducible workbook generation from Python.
- Independent Python v1 validation of cash-flow identities.
- v2 delinquency migration and trigger mechanics.
- Public-data scenario calibration using FRED and FHFA inputs.
- Local sandbox runner with scorecards and isolated run outputs.
- Clear non-production limitations and data-source documentation.

## Main Production Gaps

| Area | Current State | Production Gap |
|---|---|---|
| Collateral data | Representative pool and public macro/HPI calibration | Loan-level historical performance data and servicer tapes |
| Deal structure | Simplified tranche waterfall | Deal-document covenant parsing and transaction-specific waterfalls |
| Calibration | Rule-based public-data stress calibration | Back-tested transition/default/prepayment models |
| Validation | Accounting identity checks and scenario monotonicity | Formal independent model validation and challenger models |
| Reconciliation | Excel/Python compare available when exports are produced | Automated CI gate with complete reconciliation artifacts |
| Runtime | Local Python scripts and macOS Excel automation option | Locked environment, reproducible container, CI/CD pipeline |
| Governance | Local scorecard and documentation | Versioned model inventory, approvals, audit archive, signoff workflow |
| Reporting | Local reports and CSV outputs | Standardized model risk and regulatory reporting packs |

## How To Describe It

A plain description is:

> An RMBS cash-flow model with tranche waterfalls, stress scenarios, validation
> checks, and public-data scenario calibration.

Do not describe it as a rating model, pricing model, or production credit engine.

## Highest-Value Next Steps

1. Automate Excel/Python reconciliation with `--automate-excel` and retain the
   generated scorecard as local evidence.
2. Add loan-level Freddie Mac or Fannie Mae performance data as an optional
   calibration input.
3. Add CI tests for workbook schema, scenario monotonicity, and edge cases.
4. Add model version metadata and input/output checksums to each run folder.
