#!/usr/bin/env python3
"""Build a monthly macro panel from raw FRED + FHFA files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def month_key(d: date) -> tuple[int, int]:
    return (d.year, d.month)


def month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def load_fred_series_monthly(path: Path) -> dict[date, float]:
    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        date_col = None
        for candidate in ("DATE", "date", "observation_date"):
            if candidate in fields:
                date_col = candidate
                break
        if date_col is None:
            raise ValueError(f"Missing date column in FRED file {path}: {fields}")
        value_field = [c for c in fields if c != date_col]
        if len(value_field) != 1:
            raise ValueError(f"Unexpected FRED columns in {path}: {fields}")
        val_col = value_field[0]
        for row in reader:
            raw = (row.get(val_col) or "").strip()
            if raw in {"", "."}:
                continue
            d = parse_iso_date(row[date_col])
            buckets[month_key(d)].append(float(raw))

    out: dict[date, float] = {}
    for (y, m), vals in buckets.items():
        out[month_start(y, m)] = sum(vals) / len(vals)
    return out


def load_fhfa_us_monthly_hpi(path: Path) -> dict[date, float]:
    out: dict[date, float] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("hpi_type") or "").strip().lower() != "traditional":
                continue
            if (row.get("hpi_flavor") or "").strip().lower() != "purchase-only":
                continue
            if (row.get("frequency") or "").strip().lower() != "monthly":
                continue
            if (row.get("place_name") or "").strip().lower() != "united states":
                continue

            yr = int(float(row["yr"]))
            period = int(float(row["period"]))
            index_sa = (row.get("index_sa") or "").strip()
            index_nsa = (row.get("index_nsa") or "").strip()
            idx = float(index_sa) if index_sa else float(index_nsa)
            out[month_start(yr, period)] = idx
    if not out:
        raise ValueError(f"No FHFA United States monthly rows found in {path}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare monthly macro panel from raw FRED/FHFA files.")
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--fred-dir",
        default=str(default_root / "data/raw/fred"),
        help="Directory with MORTGAGE30US.csv and UNRATE.csv",
    )
    parser.add_argument(
        "--fhfa-csv",
        default=str(default_root / "data/raw/fhfa/hpi_master.csv"),
        help="FHFA hpi_master.csv path",
    )
    parser.add_argument(
        "--out-csv",
        default=str(default_root / "data/processed/macro_panel_monthly.csv"),
        help="Output monthly panel CSV path",
    )
    args = parser.parse_args()

    fred_dir = Path(args.fred_dir).expanduser().resolve()
    fhfa_csv = Path(args.fhfa_csv).expanduser().resolve()
    out_csv = Path(args.out_csv).expanduser().resolve()

    mortgage = load_fred_series_monthly(fred_dir / "MORTGAGE30US.csv")
    unrate = load_fred_series_monthly(fred_dir / "UNRATE.csv")
    hpi = load_fhfa_us_monthly_hpi(fhfa_csv)

    all_dates = sorted(set(mortgage) & set(unrate) & set(hpi))
    if not all_dates:
        raise ValueError("No overlapping monthly dates across mortgage, unemployment, and HPI series.")

    rows: list[dict[str, str]] = []
    source_timestamp = datetime.now(timezone.utc).isoformat()
    hpi_by_date = {d: hpi[d] for d in all_dates}

    for d in all_dates:
        prev = date(d.year - 1, d.month, 1)
        if prev not in hpi_by_date:
            continue
        hpi_index = hpi_by_date[d]
        hpi_prev = hpi_by_date[prev]
        if hpi_prev == 0:
            continue
        hpi_yoy = hpi_index / hpi_prev - 1.0
        rows.append(
            {
                "date": d.isoformat(),
                "mortgage_rate": f"{mortgage[d]:.6f}",
                "unemployment_rate": f"{unrate[d]:.6f}",
                "hpi_index": f"{hpi_index:.6f}",
                "hpi_yoy": f"{hpi_yoy:.6f}",
                "source_timestamp": source_timestamp,
            }
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "mortgage_rate",
                "unemployment_rate",
                "hpi_index",
                "hpi_yoy",
                "source_timestamp",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_at_utc": source_timestamp,
        "rows": len(rows),
        "start_date": rows[0]["date"] if rows else None,
        "end_date": rows[-1]["date"] if rows else None,
        "inputs": {
            "mortgage_rate_csv": str(fred_dir / "MORTGAGE30US.csv"),
            "unemployment_rate_csv": str(fred_dir / "UNRATE.csv"),
            "fhfa_hpi_csv": str(fhfa_csv),
        },
        "output_csv": str(out_csv),
    }
    summary_path = out_csv.with_name("macro_panel_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote {out_csv}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
