#!/usr/bin/env python3
"""
Compare Excel-exported monthly outputs against Python monthly outputs.

Excel input should come from the `CompareExport` tab in `rmbs_waterfall_model.xlsx`
after recalculation and CSV export.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path


REQUIRED_FIELDS = [
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

NUMERIC_FIELDS = [field for field in REQUIRED_FIELDS if field not in {"scenario", "month"}]


def _normalize_header(name: str) -> str:
    return name.strip().lower()


def _find_header_map(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise ValueError("CSV has no header row.")
    normalized = {_normalize_header(name): name for name in fieldnames}
    missing = [field for field in REQUIRED_FIELDS if field not in normalized]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
    return {field: normalized[field] for field in REQUIRED_FIELDS}


def load_rows(path: Path, fallback_scenario: str | None = None) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header_map = _find_header_map(reader.fieldnames)
        rows: list[dict] = []
        for raw in reader:
            scenario = raw[header_map["scenario"]].strip() or (fallback_scenario or "").strip()
            if not scenario:
                raise ValueError(f"Missing scenario in row with month={raw.get(header_map['month'])}")
            row = {
                "scenario": scenario,
                "month": int(float(raw[header_map["month"]])),
            }
            for field in NUMERIC_FIELDS:
                row[field] = float(raw[header_map[field]])
            rows.append(row)
    return rows


def filter_by_scenario(rows: list[dict], scenario: str) -> list[dict]:
    return [row for row in rows if row["scenario"] == scenario]


def compare_rows(excel_rows: list[dict], python_rows: list[dict], tolerance: float) -> dict:
    excel_by_month = {row["month"]: row for row in excel_rows}
    python_by_month = {row["month"]: row for row in python_rows}

    excel_months = set(excel_by_month.keys())
    python_months = set(python_by_month.keys())
    common_months = sorted(excel_months & python_months)

    month_coverage_ok = excel_months == python_months
    missing_in_python = sorted(excel_months - python_months)
    missing_in_excel = sorted(python_months - excel_months)

    field_max_abs_diff: dict[str, float] = {field: 0.0 for field in NUMERIC_FIELDS}
    diff_rows: list[dict] = []

    for month in common_months:
        e = excel_by_month[month]
        p = python_by_month[month]
        for field in NUMERIC_FIELDS:
            diff = e[field] - p[field]
            abs_diff = abs(diff)
            if abs_diff > field_max_abs_diff[field]:
                field_max_abs_diff[field] = abs_diff
            diff_rows.append(
                {
                    "month": month,
                    "field": field,
                    "excel_value": e[field],
                    "python_value": p[field],
                    "diff": diff,
                    "abs_diff": abs_diff,
                    "status": "PASS" if abs_diff <= tolerance else "FAIL",
                }
            )

    field_status = {
        field: ("PASS" if field_max_abs_diff[field] <= tolerance else "FAIL")
        for field in NUMERIC_FIELDS
    }
    overall_ok = month_coverage_ok and all(status == "PASS" for status in field_status.values())

    worst = sorted(diff_rows, key=lambda x: x["abs_diff"], reverse=True)[:10]

    return {
        "overall_ok": overall_ok,
        "month_coverage_ok": month_coverage_ok,
        "missing_in_python": missing_in_python,
        "missing_in_excel": missing_in_excel,
        "field_max_abs_diff": field_max_abs_diff,
        "field_status": field_status,
        "diff_rows": diff_rows,
        "worst_rows": worst,
        "excel_month_count": len(excel_months),
        "python_month_count": len(python_months),
        "common_month_count": len(common_months),
    }


def write_diff_csv(path: Path, diff_rows: list[dict]) -> None:
    fieldnames = ["month", "field", "excel_value", "python_value", "diff", "abs_diff", "status"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in diff_rows:
            writer.writerow(row)


def write_report(
    path: Path,
    comparison: dict,
    scenario: str,
    excel_csv: Path,
    python_csv: Path,
    tolerance: float,
    diff_csv: Path,
) -> None:
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("# Excel vs Python Comparison Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## Run Inputs")
    lines.append("")
    lines.append(f"- Scenario: {scenario}")
    lines.append(f"- Excel CSV: `{excel_csv}`")
    lines.append(f"- Python CSV: `{python_csv}`")
    lines.append(f"- Diff CSV: `{diff_csv}`")
    lines.append(f"- Tolerance: {tolerance}")
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- Excel months: {comparison['excel_month_count']}")
    lines.append(f"- Python months: {comparison['python_month_count']}")
    lines.append(f"- Common months compared: {comparison['common_month_count']}")
    lines.append(f"- Month coverage status: {'PASS' if comparison['month_coverage_ok'] else 'FAIL'}")
    if comparison["missing_in_python"]:
        lines.append(f"- Missing in Python: {comparison['missing_in_python']}")
    if comparison["missing_in_excel"]:
        lines.append(f"- Missing in Excel: {comparison['missing_in_excel']}")
    lines.append("")
    lines.append("## Field-Level Results")
    lines.append("")
    lines.append("| Field | Max Abs Diff | Status |")
    lines.append("|---|---:|---|")
    for field in NUMERIC_FIELDS:
        lines.append(
            f"| {field} | {comparison['field_max_abs_diff'][field]:.10f} | {comparison['field_status'][field]} |"
        )

    lines.append("")
    lines.append("## Largest Differences (Top 10)")
    lines.append("")
    lines.append("| Month | Field | Excel | Python | Abs Diff | Status |")
    lines.append("|---:|---|---:|---:|---:|---|")
    for row in comparison["worst_rows"]:
        lines.append(
            f"| {row['month']} | {row['field']} | {row['excel_value']:.10f} | "
            f"{row['python_value']:.10f} | {row['abs_diff']:.10f} | {row['status']} |"
        )

    lines.append("")
    lines.append(f"## Overall Status: {'PASS' if comparison['overall_ok'] else 'FAIL'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Excel-exported monthly outputs against Python outputs.")
    parser.add_argument(
        "--excel-csv",
        required=True,
        help="CSV exported from CompareExport sheet in Excel.",
    )
    parser.add_argument(
        "--python-csv",
        default="rmbs_validation_monthly.csv",
        help="Python monthly CSV generated by rmbs_validation_engine.py.",
    )
    parser.add_argument(
        "--scenario",
        default="",
        help="Scenario to compare (default: inferred from excel CSV scenario column).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Absolute tolerance threshold.",
    )
    parser.add_argument(
        "--out-report",
        default="excel_python_comparison_report.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--out-diff-csv",
        default="excel_python_diffs.csv",
        help="Output detailed diff CSV path.",
    )
    args = parser.parse_args()

    excel_csv = Path(args.excel_csv)
    python_csv = Path(args.python_csv)
    report_path = Path(args.out_report)
    diff_path = Path(args.out_diff_csv)

    excel_rows = load_rows(excel_csv, fallback_scenario=args.scenario if args.scenario else None)
    inferred_scenario = args.scenario.strip() or excel_rows[0]["scenario"]
    excel_rows = filter_by_scenario(excel_rows, inferred_scenario)
    python_rows = load_rows(python_csv)
    python_rows = filter_by_scenario(python_rows, inferred_scenario)
    if not python_rows:
        raise ValueError(f"No Python rows found for scenario '{inferred_scenario}'.")

    comparison = compare_rows(excel_rows, python_rows, args.tolerance)
    write_diff_csv(diff_path, comparison["diff_rows"])
    write_report(
        report_path,
        comparison,
        inferred_scenario,
        excel_csv,
        python_csv,
        args.tolerance,
        diff_path,
    )

    print(f"Wrote {report_path.resolve()}")
    print(f"Wrote {diff_path.resolve()}")
    print(f"Overall status: {'PASS' if comparison['overall_ok'] else 'FAIL'}")


if __name__ == "__main__":
    main()

