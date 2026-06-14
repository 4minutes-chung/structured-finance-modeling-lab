# Model Assumptions

Date: 2026-02-12  

Scope: simplified RMBS prototype assumptions for the v1 deterministic model.
The v2 engine extends this with delinquency and trigger parameters defined in
`model/scenario_config.py` and optional calibrated scenario YAML files.

## 1) Pool Setup

| Assumption | Value | Rationale | Notes |
|---|---:|---|---|
| Number of loans | 1,000 | Large enough for pool behavior | Cohort-level simplification |
| Original balance per loan | 300,000 | Round value for traceability | Currency assumed CAD |
| Initial pool balance | 300,000,000 | Derived | `loan_count * balance_per_loan` |
| Weighted average coupon (WAC) | 5.75% | Plausible base rate level | Fixed-rate simplification |
| Remaining term | 300 months | Typical long-dated mortgage profile | No ARM reset logic |

## 2) Performance Assumptions

| Assumption | Base | Mild Stress | Severe Stress | Notes |
|---|---:|---:|---:|---|
| CPR (annual) | 8.0% | 5.0% | 3.0% | Converted to SMM monthly |
| CDR (annual) | 1.5% | 3.0% | 5.0% | Converted to MDR monthly |
| Severity | 25.0% | 35.0% | 45.0% | Loss on defaulted balance |

Conversion formulas:
- `SMM = 1 - (1 - CPR)^(1/12)`
- `MDR = 1 - (1 - CDR)^(1/12)`

## 3) Fees and Expenses

| Assumption | Value | Notes |
|---|---:|---|
| Servicing + admin fee | 0.50% annual | Applied to beginning performing balance |

## 4) Capital Structure (Waterfall)

| Tranche | Share of initial collateral | Type |
|---|---:|---|
| Class A | 80.0% | Senior |
| Class B | 15.0% | Mezzanine |
| Equity | 5.0% | First-loss |

Rules:
- Sequential principal: A -> B -> Equity.
- Interest priority: A -> B (Equity gets residual).
- Loss allocation (simple): Equity -> B -> A by remaining balance.

## 5) Validation Checks

- Every model input must live on `Inputs` or `Scenarios` tab.
- No hardcoded rates inside monthly cashflow formulas.
- Checks tab must include:
  - cash conservation,
  - non-negative balances,
  - scenario monotonicity (Severe >= Mild >= Base losses),
  - end-balance floor at zero.

## 6) Known Simplifications

- Single representative mortgage cohort, not loan-level heterogeneity.
- No delinquency roll-rate state machine.
- No cure/redefault process.
- No trigger mechanics (OC/IC tests) in v1.
- No legal/tax nuances in trust structure.
