#!/usr/bin/env python3
"""Pull public macro series from FRED CSV endpoints."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

SERIES = {
    "MORTGAGE30US": "mortgage_rate_weekly",
    "UNRATE": "unemployment_rate_monthly",
}


def download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=120) as resp:
        data = resp.read()
    out_path.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull FRED CSV series to raw data folder.")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[1] / "data/raw/fred"),
        help="Output directory for raw FRED CSV files.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pulled_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "pulled_at_utc": pulled_at,
        "series": [],
    }

    for series_id, label in SERIES.items():
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        out_csv = out_dir / f"{series_id}.csv"
        download(url, out_csv)
        metadata["series"].append(
            {
                "series_id": series_id,
                "label": label,
                "url": url,
                "path": str(out_csv),
            }
        )
        print(f"Wrote {out_csv}")

    meta_path = out_dir / "fred_pull_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
