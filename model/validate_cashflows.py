#!/usr/bin/env python3
"""
Independent RMBS simulation and validation report generator.

This script does not depend on Excel recalculation. It reproduces model logic
from the documented assumptions and writes:
- a scenario summary CSV
- a markdown validation report
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from .scenario_config import load_scenario_bundle
except ImportError:  # pragma: no cover - direct script execution
    from scenario_config import load_scenario_bundle


@dataclass(frozen=True)
class ModelParams:
    loan_count: int = 1000
    balance_per_loan: float = 300_000.0
    wac_annual: float = 0.0575
    term_months: int = 300
    fee_annual: float = 0.005
    class_a_share: float = 0.80
    class_b_share: float = 0.15
    equity_share: float = 0.05
    horizon_months: int = 360

    @property
    def initial_pool_balance(self) -> float:
        return self.loan_count * self.balance_per_loan

    @property
    def class_a_initial(self) -> float:
        return self.initial_pool_balance * self.class_a_share

    @property
    def class_b_initial(self) -> float:
        return self.initial_pool_balance * self.class_b_share

    @property
    def equity_initial(self) -> float:
        return self.initial_pool_balance * self.equity_share


@dataclass(frozen=True)
class Scenario:
    name: str
    cpr_annual: float
    cdr_annual: float
    severity: float


def annual_to_monthly(annual_rate: float) -> float:
    return 1.0 - (1.0 - annual_rate) ** (1.0 / 12.0)


def pmt(monthly_rate: float, n_periods: int, present_value: float) -> float:
    if n_periods <= 0 or present_value <= 0:
        return 0.0
    if abs(monthly_rate) < 1e-12:
        return present_value / n_periods
    return present_value * monthly_rate / (1.0 - (1.0 + monthly_rate) ** (-n_periods))


def run_scenario(params: ModelParams, scenario: Scenario) -> dict:
    smm = annual_to_monthly(scenario.cpr_annual)
    mdr = annual_to_monthly(scenario.cdr_annual)
    monthly_rate = params.wac_annual / 12.0

    pool_begin = params.initial_pool_balance
    a_begin = params.class_a_initial
    b_begin = params.class_b_initial
    e_begin = params.equity_initial

    rows: list[dict] = []
    cum_loss = 0.0
    cum_default = 0.0
    principal_diff_max = 0.0
    interest_diff_max = 0.0
    loss_diff_max = 0.0
    min_balance_seen = min(pool_begin, a_begin, b_begin, e_begin)
    first_a_zero_month: int | None = None

    a_principal_weights = 0.0
    b_principal_weights = 0.0
    e_principal_weights = 0.0

    for month in range(1, params.horizon_months + 1):
        if month <= params.term_months and pool_begin > 0:
            sched_payment = pmt(monthly_rate, params.term_months - month + 1, pool_begin)
            interest = pool_begin * monthly_rate
            sched_principal = max(sched_payment - interest, 0.0)
        else:
            sched_payment = 0.0
            interest = 0.0
            sched_principal = 0.0

        prepay = max((pool_begin - sched_principal) * smm, 0.0)
        default = max((pool_begin - sched_principal - prepay) * mdr, 0.0)
        loss = default * scenario.severity
        total_principal_outflow = min(pool_begin, sched_principal + prepay + default)
        pool_end = max(pool_begin - total_principal_outflow, 0.0)
        fee = pool_begin * params.fee_annual / 12.0
        interest_available = max(interest - fee, 0.0)
        principal_available = max(total_principal_outflow - loss, 0.0)

        loss_to_e = min(loss, e_begin)
        loss_to_b = min(max(loss - loss_to_e, 0.0), b_begin)
        loss_to_a = min(max(loss - loss_to_e - loss_to_b, 0.0), a_begin)
        a_after_loss = max(a_begin - loss_to_a, 0.0)
        b_after_loss = max(b_begin - loss_to_b, 0.0)
        e_after_loss = max(e_begin - loss_to_e, 0.0)

        a_int_due = a_after_loss * monthly_rate
        a_int_paid = min(interest_available, a_int_due)
        b_int_due = b_after_loss * monthly_rate
        b_int_paid = min(max(interest_available - a_int_paid, 0.0), b_int_due)
        e_resid_int = max(interest_available - a_int_paid - b_int_paid, 0.0)

        a_principal_paid = min(principal_available, a_after_loss)
        b_principal_paid = min(max(principal_available - a_principal_paid, 0.0), b_after_loss)
        e_principal_paid = min(
            max(principal_available - a_principal_paid - b_principal_paid, 0.0),
            e_after_loss,
        )

        a_end = max(a_after_loss - a_principal_paid, 0.0)
        b_end = max(b_after_loss - b_principal_paid, 0.0)
        e_end = max(e_after_loss - e_principal_paid, 0.0)

        principal_diff = principal_available - (a_principal_paid + b_principal_paid + e_principal_paid)
        interest_diff = interest_available - (a_int_paid + b_int_paid + e_resid_int)
        loss_diff = loss - (loss_to_e + loss_to_b + loss_to_a)

        principal_diff_max = max(principal_diff_max, abs(principal_diff))
        interest_diff_max = max(interest_diff_max, abs(interest_diff))
        loss_diff_max = max(loss_diff_max, abs(loss_diff))
        min_balance_seen = min(min_balance_seen, pool_end, a_end, b_end, e_end)
        cum_loss += loss
        cum_default += default

        if first_a_zero_month is None and a_end <= 0.01:
            first_a_zero_month = month

        a_principal_weights += month * a_principal_paid
        b_principal_weights += month * b_principal_paid
        e_principal_weights += month * e_principal_paid

        rows.append(
            {
                "scenario": scenario.name,
                "month": month,
                "pool_begin": pool_begin,
                "pool_end": pool_end,
                "interest_available": interest_available,
                "principal_available": principal_available,
                "loss": loss,
                "a_end": a_end,
                "b_end": b_end,
                "e_end": e_end,
                "principal_diff": principal_diff,
                "interest_diff": interest_diff,
                "loss_diff": loss_diff,
            }
        )

        pool_begin = pool_end
        a_begin = a_end
        b_begin = b_end
        e_begin = e_end

    def wal_years(weighted_sum: float, initial_balance: float) -> float:
        if initial_balance <= 0:
            return 0.0
        return (weighted_sum / initial_balance) / 12.0

    return {
        "scenario": scenario.name,
        "rows": rows,
        "metrics": {
            "cum_loss": cum_loss,
            "cum_default": cum_default,
            "final_pool_balance": pool_begin,
            "final_a_balance": a_begin,
            "final_b_balance": b_begin,
            "final_e_balance": e_begin,
            "first_a_zero_month": first_a_zero_month if first_a_zero_month is not None else -1,
            "wal_a_years": wal_years(a_principal_weights, params.class_a_initial),
            "wal_b_years": wal_years(b_principal_weights, params.class_b_initial),
            "wal_e_years": wal_years(e_principal_weights, params.equity_initial),
            "principal_diff_max": principal_diff_max,
            "interest_diff_max": interest_diff_max,
            "loss_diff_max": loss_diff_max,
            "min_balance_seen": min_balance_seen,
        },
    }


def write_summary_csv(results: list[dict], output_csv: Path) -> None:
    fieldnames = [
        "scenario",
        "cum_loss",
        "cum_default",
        "final_pool_balance",
        "final_a_balance",
        "final_b_balance",
        "final_e_balance",
        "first_a_zero_month",
        "wal_a_years",
        "wal_b_years",
        "wal_e_years",
        "principal_diff_max",
        "interest_diff_max",
        "loss_diff_max",
        "min_balance_seen",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            row = {"scenario": result["scenario"]}
            row.update(result["metrics"])
            writer.writerow(row)


def write_monthly_csv(results: list[dict], output_csv: Path) -> None:
    fieldnames = [
        "scenario",
        "month",
        "pool_begin",
        "pool_end",
        "interest_available",
        "principal_available",
        "loss",
        "a_end",
        "b_end",
        "e_end",
        "principal_diff",
        "interest_diff",
        "loss_diff",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for row in result["rows"]:
                writer.writerow(row)


def scenario_monotonicity(results: list[dict]) -> bool:
    metrics = {r["scenario"]: r["metrics"] for r in results}
    required = ["Base", "Mild_Stress", "Severe_Stress"]
    if any(name not in metrics for name in required):
        return False
    return (
        metrics["Severe_Stress"]["cum_loss"] >= metrics["Mild_Stress"]["cum_loss"] >= metrics["Base"]["cum_loss"]
        and metrics["Severe_Stress"]["final_a_balance"] >= metrics["Mild_Stress"]["final_a_balance"] >= metrics["Base"]["final_a_balance"]
        and metrics["Severe_Stress"]["final_b_balance"] >= metrics["Mild_Stress"]["final_b_balance"] >= metrics["Base"]["final_b_balance"]
    )


def write_markdown_report(
    params: ModelParams,
    results: list[dict],
    report_path: Path,
    tolerance: float,
) -> None:
    mono_ok = scenario_monotonicity(results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = []
    lines.append("# RMBS Validation Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Run Configuration")
    lines.append("")
    lines.append(f"- Initial pool balance: {params.initial_pool_balance:,.2f}")
    lines.append(f"- WAC annual: {params.wac_annual:.4%}")
    lines.append(f"- Term months: {params.term_months}")
    lines.append(f"- Validation tolerance: {tolerance}")
    lines.append("")
    lines.append("## Scenario Summary")
    lines.append("")
    lines.append("| Scenario | Cum Loss | Final A | Final B | Final Equity | A Payoff Month | WAL A (yrs) | WAL B (yrs) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        m = result["metrics"]
        payoff = m["first_a_zero_month"] if m["first_a_zero_month"] != -1 else "Not Paid"
        lines.append(
            f"| {result['scenario']} | {m['cum_loss']:,.2f} | {m['final_a_balance']:,.2f} | "
            f"{m['final_b_balance']:,.2f} | {m['final_e_balance']:,.2f} | {payoff} | "
            f"{m['wal_a_years']:.2f} | {m['wal_b_years']:.2f} |"
        )

    lines.append("")
    lines.append("## Integrity Checks")
    lines.append("")
    lines.append("| Check | Status | Detail |")
    lines.append("|---|---|---|")
    for result in results:
        m = result["metrics"]
        p_ok = m["principal_diff_max"] <= tolerance
        i_ok = m["interest_diff_max"] <= tolerance
        l_ok = m["loss_diff_max"] <= tolerance
        n_ok = m["min_balance_seen"] >= -tolerance
        lines.append(
            f"| {result['scenario']} principal allocation | {'PASS' if p_ok else 'FAIL'} | "
            f"max abs diff = {m['principal_diff_max']:.6f} |"
        )
        lines.append(
            f"| {result['scenario']} interest allocation | {'PASS' if i_ok else 'FAIL'} | "
            f"max abs diff = {m['interest_diff_max']:.6f} |"
        )
        lines.append(
            f"| {result['scenario']} loss allocation | {'PASS' if l_ok else 'FAIL'} | "
            f"max abs diff = {m['loss_diff_max']:.6f} |"
        )
        lines.append(
            f"| {result['scenario']} non-negative balances | {'PASS' if n_ok else 'FAIL'} | "
            f"min balance = {m['min_balance_seen']:.6f} |"
        )
    lines.append(
        f"| Scenario monotonicity (Severe >= Mild >= Base losses and remaining senior/mezz balances) | "
        f"{'PASS' if mono_ok else 'FAIL'} | Ordered stress impact check |"
    )

    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- This report validates accounting identities and stress ordering under the prototype model.")
    lines.append("- It does not validate external calibration quality or legal transaction nuances.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run independent RMBS validation.")
    parser.add_argument(
        "--out-report",
        default="rmbs_validation_report.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--out-summary-csv",
        default="rmbs_validation_summary.csv",
        help="Output scenario summary CSV path.",
    )
    parser.add_argument(
        "--out-monthly-csv",
        default="rmbs_validation_monthly.csv",
        help="Output monthly detail CSV path.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Absolute tolerance for identity checks.",
    )
    parser.add_argument(
        "--scenario-config",
        default="",
        help="Optional YAML path with v1_scenarios/v2_scenarios. If omitted, built-in defaults are used.",
    )
    args = parser.parse_args()

    params = ModelParams()
    scenario_bundle = load_scenario_bundle(args.scenario_config or None)
    scenarios = [
        Scenario(
            str(item["name"]),
            float(item["cpr_annual"]),
            float(item["cdr_annual"]),
            float(item["severity"]),
        )
        for item in scenario_bundle["v1_scenarios"]
    ]

    results = [run_scenario(params, scenario) for scenario in scenarios]
    out_report = Path(args.out_report)
    out_summary = Path(args.out_summary_csv)
    out_monthly = Path(args.out_monthly_csv)

    write_summary_csv(results, out_summary)
    write_monthly_csv(results, out_monthly)
    write_markdown_report(params, results, out_report, args.tolerance)

    print(f"Wrote {out_report.resolve()}")
    print(f"Wrote {out_summary.resolve()}")
    print(f"Wrote {out_monthly.resolve()}")


if __name__ == "__main__":
    main()
