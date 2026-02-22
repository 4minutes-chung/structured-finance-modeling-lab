#!/usr/bin/env python3
"""
Shared scenario configuration loader for v1/v2 RMBS scripts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


SCENARIO_ORDER = ["Base", "Mild_Stress", "Severe_Stress"]

DEFAULT_V1_SCENARIOS = [
    {"name": "Base", "cpr_annual": 0.08, "cdr_annual": 0.015, "severity": 0.25},
    {"name": "Mild_Stress", "cpr_annual": 0.05, "cdr_annual": 0.03, "severity": 0.35},
    {"name": "Severe_Stress", "cpr_annual": 0.03, "cdr_annual": 0.05, "severity": 0.45},
]

DEFAULT_V2_SCENARIOS = [
    {
        "name": "Base",
        "cpr_annual": 0.08,
        "severity": 0.25,
        "roll_to_30_annual": 0.04,
        "default_from_60_annual": 0.10,
        "cure_30_monthly": 0.35,
        "roll_30_to_60_monthly": 0.20,
        "cure_60_monthly": 0.12,
    },
    {
        "name": "Mild_Stress",
        "cpr_annual": 0.05,
        "severity": 0.35,
        "roll_to_30_annual": 0.07,
        "default_from_60_annual": 0.18,
        "cure_30_monthly": 0.25,
        "roll_30_to_60_monthly": 0.28,
        "cure_60_monthly": 0.08,
    },
    {
        "name": "Severe_Stress",
        "cpr_annual": 0.03,
        "severity": 0.45,
        "roll_to_30_annual": 0.10,
        "default_from_60_annual": 0.28,
        "cure_30_monthly": 0.18,
        "roll_30_to_60_monthly": 0.35,
        "cure_60_monthly": 0.05,
    },
]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "PyYAML is required when using --scenario-config. Install with: pip install pyyaml"
        ) from exc

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Scenario config must be a mapping at top-level: {path}")
    return data


def _validate_scenarios(
    raw_items: list[dict[str, Any]],
    *,
    required_fields: list[str],
    label: str,
) -> list[dict[str, float | str]]:
    by_name: dict[str, dict[str, float | str]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError(f"{label} scenario entries must be mappings.")
        name = str(item.get("name", "")).strip()
        if not name:
            raise ValueError(f"{label} scenario entry is missing 'name'.")
        parsed: dict[str, float | str] = {"name": name}
        for field in required_fields:
            if field not in item:
                raise ValueError(f"{label} scenario '{name}' missing field: {field}")
            parsed[field] = float(item[field])
        by_name[name] = parsed

    missing = [name for name in SCENARIO_ORDER if name not in by_name]
    if missing:
        raise ValueError(f"{label} scenarios missing required names: {missing}")

    # Normalize order and ignore extra scenarios to keep existing model flow fixed.
    return [by_name[name] for name in SCENARIO_ORDER]


def load_scenario_bundle(scenario_config_path: str | Path | None) -> dict[str, Any]:
    if not scenario_config_path:
        return {
            "meta": {"source": "defaults"},
            "v1_scenarios": [dict(item) for item in DEFAULT_V1_SCENARIOS],
            "v2_scenarios": [dict(item) for item in DEFAULT_V2_SCENARIOS],
        }

    path = Path(scenario_config_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Scenario config not found: {path}")

    raw = _load_yaml(path)
    v1_raw = raw.get("v1_scenarios")
    v2_raw = raw.get("v2_scenarios")
    if not isinstance(v1_raw, list) or not isinstance(v2_raw, list):
        raise ValueError("Scenario config must define list fields: v1_scenarios and v2_scenarios")

    v1 = _validate_scenarios(
        v1_raw,
        required_fields=["cpr_annual", "cdr_annual", "severity"],
        label="v1",
    )
    v2 = _validate_scenarios(
        v2_raw,
        required_fields=[
            "cpr_annual",
            "severity",
            "roll_to_30_annual",
            "default_from_60_annual",
            "cure_30_monthly",
            "roll_30_to_60_monthly",
            "cure_60_monthly",
        ],
        label="v2",
    )
    meta = raw.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}

    return {"meta": meta, "v1_scenarios": v1, "v2_scenarios": v2}
