#!/usr/bin/env python3
"""
RMBS v2 simulation:
- delinquency state transitions (Current -> 30DPD -> 60DPD -> Default)
- simple trigger mechanics (loss/delinquency based)

Outputs:
- scenario summary CSV
- monthly detail CSV
- markdown validation report
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
    initial_dq30_share: float = 0.01
    initial_dq60_share: float = 0.005

    @property
    def initial_pool_balance(self) -> float:
        return self.loan_count * self.balance_per_loan

    @property
    def initial_current_balance(self) -> float:
        return self.initial_pool_balance * (1.0 - self.initial_dq30_share - self.initial_dq60_share)

    @property
    def initial_dq30_balance(self) -> float:
        return self.initial_pool_balance * self.initial_dq30_share

    @property
    def initial_dq60_balance(self) -> float:
        return self.initial_pool_balance * self.initial_dq60_share

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
class ScenarioV2:
    name: str
    cpr_annual: float
    severity: float
    roll_to_30_annual: float
    default_from_60_annual: float
    cure_30_monthly: float
    roll_30_to_60_monthly: float
    cure_60_monthly: float


def annual_to_monthly(annual_rate: float) -> float:
    return 1.0 - (1.0 - annual_rate) ** (1.0 / 12.0)


def pmt(monthly_rate: float, n_periods: int, present_value: float) -> float:
    if n_periods <= 0 or present_value <= 0:
        return 0.0
    if abs(monthly_rate) < 1e-12:
        return present_value / n_periods
    return present_value * monthly_rate / (1.0 - (1.0 + monthly_rate) ** (-n_periods))


def run_scenario_v2(
    params: ModelParams,
    scenario: ScenarioV2,
    trigger_loss_threshold: float,
    trigger_dq_threshold: float,
) -> dict:
    smm = annual_to_monthly(scenario.cpr_annual)
    to30_mdr = annual_to_monthly(scenario.roll_to_30_annual)
    default60_mdr = annual_to_monthly(scenario.default_from_60_annual)
    monthly_rate = params.wac_annual / 12.0

    current_begin = params.initial_current_balance
    dq30_begin = params.initial_dq30_balance
    dq60_begin = params.initial_dq60_balance

    a_begin = params.class_a_initial
    b_begin = params.class_b_initial
    e_begin = params.equity_initial

    trigger_on = False
    first_trigger_month: int | None = None
    cum_loss = 0.0
    cum_default = 0.0
    max_dq_ratio = 0.0
    max_unallocated_principal = 0.0
    max_unallocated_loss = 0.0

    principal_diff_max = 0.0
    interest_diff_max = 0.0
    loss_diff_max = 0.0
    pool_roll_diff_max = 0.0
    min_balance_seen = min(current_begin, dq30_begin, dq60_begin, a_begin, b_begin, e_begin)

    a_principal_weights = 0.0
    b_principal_weights = 0.0
    e_principal_weights = 0.0

    rows: list[dict] = []

    for month in range(1, params.horizon_months + 1):
        pool_begin = current_begin + dq30_begin + dq60_begin
        remaining_term = max(params.term_months - month + 1, 0)

        if month <= params.term_months and current_begin > 0:
            sched_payment = pmt(monthly_rate, remaining_term, current_begin)
            interest = current_begin * monthly_rate
            sched_principal = max(sched_payment - interest, 0.0)
        else:
            sched_payment = 0.0
            interest = 0.0
            sched_principal = 0.0

        prepay = max((current_begin - sched_principal) * smm, 0.0)
        roll_to_30 = max((current_begin - sched_principal - prepay) * to30_mdr, 0.0)

        cure30 = min(dq30_begin * scenario.cure_30_monthly, dq30_begin)
        roll_30_to_60 = min((dq30_begin - cure30) * scenario.roll_30_to_60_monthly, dq30_begin - cure30)
        cure60 = min(dq60_begin * scenario.cure_60_monthly, dq60_begin)
        default = min((dq60_begin - cure60) * default60_mdr, dq60_begin - cure60)

        current_end = max(current_begin - sched_principal - prepay - roll_to_30 + cure30 + cure60, 0.0)
        dq30_end = max(dq30_begin - cure30 - roll_30_to_60 + roll_to_30, 0.0)
        dq60_end = max(dq60_begin - cure60 - default + roll_30_to_60, 0.0)
        pool_end = current_end + dq30_end + dq60_end
        pool_end_expected = max(pool_begin - sched_principal - prepay - default, 0.0)
        pool_roll_diff = pool_end_expected - pool_end

        loss = default * scenario.severity
        fee = pool_begin * params.fee_annual / 12.0
        interest_available = max(interest - fee, 0.0)
        principal_from_pool = max(sched_principal + prepay + default - loss, 0.0)

        dq_ratio = (dq30_end + dq60_end) / params.initial_pool_balance
        max_dq_ratio = max(max_dq_ratio, dq_ratio)
        cum_loss += loss
        cum_default += default

        if (not trigger_on) and (
            (cum_loss / params.initial_pool_balance >= trigger_loss_threshold)
            or (dq_ratio >= trigger_dq_threshold)
        ):
            trigger_on = True
            first_trigger_month = month

        loss_to_e = min(loss, e_begin)
        loss_to_b = min(max(loss - loss_to_e, 0.0), b_begin)
        loss_to_a = min(max(loss - loss_to_e - loss_to_b, 0.0), a_begin)
        unallocated_loss = max(loss - loss_to_e - loss_to_b - loss_to_a, 0.0)
        a_after_loss = max(a_begin - loss_to_a, 0.0)
        b_after_loss = max(b_begin - loss_to_b, 0.0)
        e_after_loss = max(e_begin - loss_to_e, 0.0)

        a_int_due = a_after_loss * monthly_rate
        a_int_paid = min(interest_available, a_int_due)
        b_int_due = b_after_loss * monthly_rate
        b_int_paid = min(max(interest_available - a_int_paid, 0.0), b_int_due)
        residual_interest = max(interest_available - a_int_paid - b_int_paid, 0.0)
        trapped_interest = residual_interest if trigger_on else 0.0
        e_resid_int = residual_interest - trapped_interest

        principal_available = principal_from_pool + trapped_interest

        if trigger_on:
            a_principal_paid = min(principal_available, a_after_loss)
            b_principal_paid = min(max(principal_available - a_principal_paid, 0.0), b_after_loss)
            e_principal_paid = min(
                max(principal_available - a_principal_paid - b_principal_paid, 0.0),
                e_after_loss,
            )
        else:
            ab_total = a_after_loss + b_after_loss
            if ab_total > 0 and principal_available > 0:
                a_target = principal_available * (a_after_loss / ab_total)
                b_target = principal_available - a_target
                a_principal_paid = min(a_target, a_after_loss)
                b_principal_paid = min(b_target, b_after_loss, max(principal_available - a_principal_paid, 0.0))
                remaining = max(principal_available - a_principal_paid - b_principal_paid, 0.0)
                if remaining > 0 and a_principal_paid < a_after_loss:
                    extra_a = min(remaining, a_after_loss - a_principal_paid)
                    a_principal_paid += extra_a
                    remaining -= extra_a
                if remaining > 0 and b_principal_paid < b_after_loss:
                    extra_b = min(remaining, b_after_loss - b_principal_paid)
                    b_principal_paid += extra_b
                    remaining -= extra_b
                e_principal_paid = min(remaining, e_after_loss)
            else:
                a_principal_paid = 0.0
                b_principal_paid = 0.0
                e_principal_paid = min(principal_available, e_after_loss)

        unallocated_principal = max(principal_available - a_principal_paid - b_principal_paid - e_principal_paid, 0.0)
        a_end = max(a_after_loss - a_principal_paid, 0.0)
        b_end = max(b_after_loss - b_principal_paid, 0.0)
        e_end = max(e_after_loss - e_principal_paid, 0.0)

        principal_diff = principal_available - (
            a_principal_paid + b_principal_paid + e_principal_paid + unallocated_principal
        )
        interest_diff = interest_available - (a_int_paid + b_int_paid + e_resid_int + trapped_interest)
        loss_diff = loss - (loss_to_e + loss_to_b + loss_to_a + unallocated_loss)

        principal_diff_max = max(principal_diff_max, abs(principal_diff))
        interest_diff_max = max(interest_diff_max, abs(interest_diff))
        loss_diff_max = max(loss_diff_max, abs(loss_diff))
        pool_roll_diff_max = max(pool_roll_diff_max, abs(pool_roll_diff))
        max_unallocated_principal = max(max_unallocated_principal, unallocated_principal)
        max_unallocated_loss = max(max_unallocated_loss, unallocated_loss)
        min_balance_seen = min(
            min_balance_seen,
            current_end,
            dq30_end,
            dq60_end,
            a_end,
            b_end,
            e_end,
        )

        a_principal_weights += month * a_principal_paid
        b_principal_weights += month * b_principal_paid
        e_principal_weights += month * e_principal_paid

        rows.append(
            {
                "scenario": scenario.name,
                "month": month,
                "trigger_on": 1 if trigger_on else 0,
                "pool_begin": pool_begin,
                "current_begin": current_begin,
                "dq30_begin": dq30_begin,
                "dq60_begin": dq60_begin,
                "pool_end": pool_end,
                "current_end": current_end,
                "dq30_end": dq30_end,
                "dq60_end": dq60_end,
                "dq_ratio": dq_ratio,
                "sched_principal": sched_principal,
                "prepay": prepay,
                "default": default,
                "loss": loss,
                "interest_available": interest_available,
                "trapped_interest": trapped_interest,
                "principal_available": principal_available,
                "unallocated_principal": unallocated_principal,
                "unallocated_loss": unallocated_loss,
                "a_end": a_end,
                "b_end": b_end,
                "e_end": e_end,
                "principal_diff": principal_diff,
                "interest_diff": interest_diff,
                "loss_diff": loss_diff,
                "pool_roll_diff": pool_roll_diff,
            }
        )

        current_begin = current_end
        dq30_begin = dq30_end
        dq60_begin = dq60_end
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
            "final_pool_balance": current_begin + dq30_begin + dq60_begin,
            "final_current_balance": current_begin,
            "final_dq30_balance": dq30_begin,
            "final_dq60_balance": dq60_begin,
            "final_a_balance": a_begin,
            "final_b_balance": b_begin,
            "final_e_balance": e_begin,
            "first_trigger_month": first_trigger_month if first_trigger_month is not None else -1,
            "trigger_activated": 1 if first_trigger_month is not None else 0,
            "max_dq_ratio": max_dq_ratio,
            "max_unallocated_principal": max_unallocated_principal,
            "max_unallocated_loss": max_unallocated_loss,
            "wal_a_years": wal_years(a_principal_weights, params.class_a_initial),
            "wal_b_years": wal_years(b_principal_weights, params.class_b_initial),
            "wal_e_years": wal_years(e_principal_weights, params.equity_initial),
            "principal_diff_max": principal_diff_max,
            "interest_diff_max": interest_diff_max,
            "loss_diff_max": loss_diff_max,
            "pool_roll_diff_max": pool_roll_diff_max,
            "min_balance_seen": min_balance_seen,
        },
    }


def write_summary_csv(results: list[dict], output_csv: Path) -> None:
    fieldnames = [
        "scenario",
        "cum_loss",
        "cum_default",
        "final_pool_balance",
        "final_current_balance",
        "final_dq30_balance",
        "final_dq60_balance",
        "final_a_balance",
        "final_b_balance",
        "final_e_balance",
        "first_trigger_month",
        "trigger_activated",
        "max_dq_ratio",
        "max_unallocated_principal",
        "max_unallocated_loss",
        "wal_a_years",
        "wal_b_years",
        "wal_e_years",
        "principal_diff_max",
        "interest_diff_max",
        "loss_diff_max",
        "pool_roll_diff_max",
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
    if not results:
        return
    fieldnames = list(results[0]["rows"][0].keys())
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for row in result["rows"]:
                writer.writerow(row)


def monotonicity_ok(results: list[dict]) -> bool:
    metrics = {r["scenario"]: r["metrics"] for r in results}
    required = ["Base", "Mild_Stress", "Severe_Stress"]
    if any(name not in metrics for name in required):
        return False
    return (
        metrics["Severe_Stress"]["cum_loss"] >= metrics["Mild_Stress"]["cum_loss"] >= metrics["Base"]["cum_loss"]
        and metrics["Severe_Stress"]["max_dq_ratio"] >= metrics["Mild_Stress"]["max_dq_ratio"] >= metrics["Base"]["max_dq_ratio"]
    )


def write_report(
    params: ModelParams,
    results: list[dict],
    report_path: Path,
    tolerance: float,
    trigger_loss_threshold: float,
    trigger_dq_threshold: float,
) -> None:
    mono_ok = monotonicity_ok(results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = []
    lines.append("# RMBS v2 Validation Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"- Initial pool balance: {params.initial_pool_balance:,.2f}")
    lines.append(f"- Initial delinquency seeding: 30DPD={params.initial_dq30_share:.2%}, 60DPD={params.initial_dq60_share:.2%}")
    lines.append(f"- Trigger loss threshold: {trigger_loss_threshold:.2%}")
    lines.append(f"- Trigger delinquency threshold: {trigger_dq_threshold:.2%}")
    lines.append(f"- Validation tolerance: {tolerance}")
    lines.append("")
    lines.append("## Scenario Summary")
    lines.append("")
    lines.append("| Scenario | Cum Loss | Max DQ Ratio (of initial) | Trigger Month | Final A | Final B | WAL A (yrs) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for result in results:
        m = result["metrics"]
        trig = m["first_trigger_month"] if m["first_trigger_month"] != -1 else "Not Triggered"
        lines.append(
            f"| {result['scenario']} | {m['cum_loss']:,.2f} | {m['max_dq_ratio']:.2%} | {trig} | "
            f"{m['final_a_balance']:,.2f} | {m['final_b_balance']:,.2f} | {m['wal_a_years']:.2f} |"
        )

    lines.append("")
    lines.append("## Integrity Checks")
    lines.append("")
    lines.append("| Check | Status | Detail |")
    lines.append("|---|---|---|")
    for result in results:
        m = result["metrics"]
        lines.append(
            f"| {result['scenario']} principal allocation | "
            f"{'PASS' if m['principal_diff_max'] <= tolerance else 'FAIL'} | "
            f"max abs diff = {m['principal_diff_max']:.6f} |"
        )
        lines.append(
            f"| {result['scenario']} interest allocation | "
            f"{'PASS' if m['interest_diff_max'] <= tolerance else 'FAIL'} | "
            f"max abs diff = {m['interest_diff_max']:.6f} |"
        )
        lines.append(
            f"| {result['scenario']} loss allocation | "
            f"{'PASS' if m['loss_diff_max'] <= tolerance else 'FAIL'} | "
            f"max abs diff = {m['loss_diff_max']:.6f} |"
        )
        lines.append(
            f"| {result['scenario']} pool roll-forward | "
            f"{'PASS' if m['pool_roll_diff_max'] <= tolerance else 'FAIL'} | "
            f"max abs diff = {m['pool_roll_diff_max']:.6f} |"
        )
        lines.append(
            f"| {result['scenario']} non-negative balances | "
            f"{'PASS' if m['min_balance_seen'] >= -tolerance else 'FAIL'} | "
            f"min balance = {m['min_balance_seen']:.6f} |"
        )
        lines.append(
            f"| {result['scenario']} residual buckets tracked | PASS | "
            f"max unallocated principal={m['max_unallocated_principal']:.2f}, "
            f"max unallocated loss={m['max_unallocated_loss']:.2f} |"
        )
    lines.append(
        f"| Stress monotonicity (loss + delinquency) | {'PASS' if mono_ok else 'FAIL'} | "
        "Severe >= Mild >= Base |"
    )

    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- v2 adds delinquency migration and trigger-based cashflow behavior to improve realism.")
    lines.append("- This remains a prototype model and is not calibrated to production-quality performance data.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RMBS v2 engine (delinquency + trigger).")
    parser.add_argument("--out-report", default="rmbs_v2_validation_report.md")
    parser.add_argument("--out-summary-csv", default="rmbs_v2_validation_summary.csv")
    parser.add_argument("--out-monthly-csv", default="rmbs_v2_validation_monthly.csv")
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--trigger-loss-threshold", type=float, default=0.03)
    parser.add_argument("--trigger-dq-threshold", type=float, default=0.06)
    parser.add_argument(
        "--scenario-config",
        default="",
        help="Optional YAML path with v1_scenarios/v2_scenarios. If omitted, built-in defaults are used.",
    )
    args = parser.parse_args()

    params = ModelParams()
    scenario_bundle = load_scenario_bundle(args.scenario_config or None)
    scenarios = [
        ScenarioV2(
            str(item["name"]),
            cpr_annual=float(item["cpr_annual"]),
            severity=float(item["severity"]),
            roll_to_30_annual=float(item["roll_to_30_annual"]),
            default_from_60_annual=float(item["default_from_60_annual"]),
            cure_30_monthly=float(item["cure_30_monthly"]),
            roll_30_to_60_monthly=float(item["roll_30_to_60_monthly"]),
            cure_60_monthly=float(item["cure_60_monthly"]),
        )
        for item in scenario_bundle["v2_scenarios"]
    ]

    results = [
        run_scenario_v2(
            params,
            scenario,
            trigger_loss_threshold=args.trigger_loss_threshold,
            trigger_dq_threshold=args.trigger_dq_threshold,
        )
        for scenario in scenarios
    ]

    out_report = Path(args.out_report)
    out_summary = Path(args.out_summary_csv)
    out_monthly = Path(args.out_monthly_csv)

    write_summary_csv(results, out_summary)
    write_monthly_csv(results, out_monthly)
    write_report(
        params,
        results,
        out_report,
        args.tolerance,
        args.trigger_loss_threshold,
        args.trigger_dq_threshold,
    )

    print(f"Wrote {out_report.resolve()}")
    print(f"Wrote {out_summary.resolve()}")
    print(f"Wrote {out_monthly.resolve()}")


if __name__ == "__main__":
    main()
