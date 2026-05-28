#!/usr/bin/env python3
"""Run Federal Register and GovInfo ingestion for all configured instruments."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db
from app.ingest.federal_register import fetch_all_executive_orders
from app.ingest.govinfo import fetch_all_public_laws


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        print("Fetching executive orders from Federal Register API...")
        eo = fetch_all_executive_orders(db)
        for slug, status in sorted(eo.items()):
            print(f"  {slug}: {status}")

        print("\nFetching public laws from GovInfo API...")
        laws = fetch_all_public_laws(db)
        for slug, status in sorted(laws.items()):
            print(f"  {slug}: {status}")

        total_new = sum(1 for s in list(eo.values()) + list(laws.values()) if "new" in s and not s.startswith("failed"))
        print(f"\nDone. Review dashboard at http://127.0.0.1:8000/")
    finally:
        db.close()


if __name__ == "__main__":
    main()
