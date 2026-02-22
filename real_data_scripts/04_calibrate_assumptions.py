#!/usr/bin/env python3
"""Calibrate v1/v2 scenario assumptions from the prepared macro panel."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

import yaml


def percentile(values: list[float], p: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile on empty list")
    if p <= 0:
        return min(values)
    if p >= 1:
        return max(values)
    vals = sorted(values)
    pos = (len(vals) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] + (vals[hi] - vals[lo]) * frac


def clamp(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


def enforce_monotonic(
    scenario_order: list[str],
    scenarios: dict[str, dict[str, float]],
    field: str,
    direction: str,
) -> None:
    if direction == "ascending":
        prev = scenarios[scenario_order[0]][field]
        for name in scenario_order[1:]:
            cur = scenarios[name][field]
            if cur < prev:
                scenarios[name][field] = prev
            prev = scenarios[name][field]
    elif direction == "descending":
        prev = scenarios[scenario_order[0]][field]
        for name in scenario_order[1:]:
            cur = scenarios[name][field]
            if cur > prev:
                scenarios[name][field] = prev
            prev = scenarios[name][field]
    else:
        raise ValueError(f"Unsupported monotonic direction: {direction}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate scenario assumptions from macro panel.")
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--panel-csv",
        default=str(default_root / "data/processed/macro_panel_monthly.csv"),
        help="Prepared macro panel CSV path.",
    )
    parser.add_argument(
        "--rules-yaml",
        default=str(default_root / "config/calibration_rules.yaml"),
        help="Calibration rules YAML path.",
    )
    parser.add_argument(
        "--template-yaml",
        default=str(default_root / "config/scenario_template.yaml"),
        help="Scenario template YAML path.",
    )
    parser.add_argument(
        "--out-yaml",
        default=str(default_root / "config/scenarios_calibrated.yaml"),
        help="Output scenario config YAML path.",
    )
    args = parser.parse_args()

    panel_csv = Path(args.panel_csv).expanduser().resolve()
    rules_yaml = Path(args.rules_yaml).expanduser().resolve()
    template_yaml = Path(args.template_yaml).expanduser().resolve()
    out_yaml = Path(args.out_yaml).expanduser().resolve()

    with rules_yaml.open(encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    with template_yaml.open(encoding="utf-8") as f:
        template = yaml.safe_load(f)

    rows = list(csv.DictReader(panel_csv.open(newline="", encoding="utf-8-sig")))
    if not rows:
        raise ValueError(f"Macro panel is empty: {panel_csv}")

    rows.sort(key=lambda r: r["date"])
    window_months = int(rules.get("window_months", 120))
    window_rows = rows[-window_months:] if len(rows) > window_months else rows

    scenario_order = list(template["scenario_order"])
    pct_targets = rules["percentile_targets"]

    macro_series = {
        "mortgage_rate": [float(r["mortgage_rate"]) for r in window_rows],
        "unemployment_rate": [float(r["unemployment_rate"]) for r in window_rows],
        "hpi_yoy": [float(r["hpi_yoy"]) for r in window_rows],
    }

    scenario_macro: dict[str, dict[str, float]] = {}
    for scenario in scenario_order:
        pt = pct_targets[scenario]
        scenario_macro[scenario] = {
            metric: percentile(macro_series[metric], float(pt[metric]))
            for metric in ["mortgage_rate", "unemployment_rate", "hpi_yoy"]
        }

    base_macro = scenario_macro["Base"]

    calibrated_v1: dict[str, dict[str, float]] = {}
    calibrated_v2: dict[str, dict[str, float]] = {}

    for scenario in scenario_order:
        macro = scenario_macro[scenario]
        features = {
            "mortgage_rate_pp": macro["mortgage_rate"] - base_macro["mortgage_rate"],
            "unemployment_rate_pp": macro["unemployment_rate"] - base_macro["unemployment_rate"],
            "hpi_yoy_pp": (macro["hpi_yoy"] - base_macro["hpi_yoy"]) * 100.0,
        }

        v1_params = {}
        for field, base_val in rules["base_parameters"]["v1"].items():
            sens = rules["sensitivities"]["v1"][field]
            raw = float(base_val) + sum(float(sens[k]) * features[k] for k in sens)
            lo, hi = rules["bounds"]["v1"][field]
            v1_params[field] = clamp(raw, float(lo), float(hi))
        calibrated_v1[scenario] = v1_params

        v2_params = {}
        for field, base_val in rules["base_parameters"]["v2"].items():
            sens = rules["sensitivities"]["v2"][field]
            raw = float(base_val) + sum(float(sens[k]) * features[k] for k in sens)
            lo, hi = rules["bounds"]["v2"][field]
            v2_params[field] = clamp(raw, float(lo), float(hi))
        calibrated_v2[scenario] = v2_params

    for field, direction in template["monotonic_rules"]["v1"].items():
        enforce_monotonic(scenario_order, calibrated_v1, field, direction)
    for field, direction in template["monotonic_rules"]["v2"].items():
        enforce_monotonic(scenario_order, calibrated_v2, field, direction)

    as_of_date = window_rows[-1]["date"]
    output = {
        "meta": {
            "as_of_date": as_of_date,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "calibration_version": str(rules.get("version", "0.1.0")),
            "data_sources": rules.get("source_urls", {}),
            "window_months_used": len(window_rows),
        },
        "v1_scenarios": [
            {
                "name": s,
                "cpr_annual": round(calibrated_v1[s]["cpr_annual"], 6),
                "cdr_annual": round(calibrated_v1[s]["cdr_annual"], 6),
                "severity": round(calibrated_v1[s]["severity"], 6),
            }
            for s in scenario_order
        ],
        "v2_scenarios": [
            {
                "name": s,
                "cpr_annual": round(calibrated_v2[s]["cpr_annual"], 6),
                "severity": round(calibrated_v2[s]["severity"], 6),
                "roll_to_30_annual": round(calibrated_v2[s]["roll_to_30_annual"], 6),
                "default_from_60_annual": round(calibrated_v2[s]["default_from_60_annual"], 6),
                "cure_30_monthly": round(calibrated_v2[s]["cure_30_monthly"], 6),
                "roll_30_to_60_monthly": round(calibrated_v2[s]["roll_30_to_60_monthly"], 6),
                "cure_60_monthly": round(calibrated_v2[s]["cure_60_monthly"], 6),
            }
            for s in scenario_order
        ],
    }

    out_yaml.parent.mkdir(parents=True, exist_ok=True)
    out_yaml.write_text(yaml.safe_dump(output, sort_keys=False), encoding="utf-8")
    print(f"Wrote {out_yaml}")


if __name__ == "__main__":
    main()
