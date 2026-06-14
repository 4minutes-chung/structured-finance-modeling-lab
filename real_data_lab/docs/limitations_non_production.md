# Non-Production Limitations

This lab intentionally stops short of institutional production scope.

## What Is Included
- Real public macro and HPI data ingestion.
- Explainable scenario calibration with explicit rules.
- v1/v2 model runs and governance scorecard in isolated run folders.

## What Is Not Included
- Deal-level legal waterfall covenant parsing.
- Full model risk governance workflow (formal validation committee, signoff process).
- Loan-level calibration against full agency historical panels by default.
- Containerized runtime and enterprise CI/CD controls.
- Regulatory reporting packs and immutable audit archive controls.

## Practical Meaning
- Suitable for transparent prototype demonstrations and model-method discussion.
- Not suitable for institutional credit decisions without further hardening.

## Optional Next Data Upgrade
When access is available, add loan-level performance data into:
- `data/external/agency_optional/`

Suggested sources:
- Freddie Mac loan-level dataset: https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset
- Fannie Mae loan performance data: https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data
