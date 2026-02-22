#!/usr/bin/env python3
"""Pull FHFA monthly HPI master dataset to raw data folder."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

FHFA_MONTHLY_HPI_URL = "https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv"


def download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=120) as resp:
        data = resp.read()
    out_path.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull FHFA monthly HPI master CSV.")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[1] / "data/raw/fhfa"),
        help="Output directory for raw FHFA files.",
    )
    parser.add_argument(
        "--url",
        default=FHFA_MONTHLY_HPI_URL,
        help="FHFA monthly HPI CSV URL.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_dir / "hpi_master.csv"
    download(args.url, out_csv)
    print(f"Wrote {out_csv}")

    metadata = {
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": args.url,
        "path": str(out_csv),
    }
    meta_path = out_dir / "fhfa_pull_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
