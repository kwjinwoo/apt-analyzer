"""Populate and inspect a deterministic representative regional SQLite fixture."""

import argparse
import tempfile
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from apt_analyzer.apartment_data import ApartmentCandidate
from apt_analyzer.domain import AnalysisPeriod, Apartment, NormalizedTransaction, TransactionType
from apt_analyzer.persistence import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=int, default=250)
    parser.add_argument("--months", type=int, default=60)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "scale.sqlite3"
        store = SQLiteStore(path)
        fetched_at = datetime(2029, 1, 1, tzinfo=UTC).isoformat()
        candidates = tuple(
            ApartmentCandidate(
                f"source-{candidate:04d}",
                f"Fixture {candidate:04d}",
                f"11{candidate:08d}",
                f"Seoul lot {candidate}",
                f"Seoul road {candidate}",
            )
            for candidate in range(args.candidates)
        )
        store.save_candidate_snapshot(
            "K-APT apartment list", "11", candidates, fetched_at=fetched_at
        )
        for candidate in range(args.candidates):
            apartment = Apartment(f"apt-{candidate:04d}", f"Fixture {candidate:04d}")
            store.save_apartment(apartment)
            store.link_candidate_resolution(
                "K-APT apartment list",
                "11",
                f"source-{candidate:04d}",
                apartment.internal_id,
                resolved_at=fetched_at,
            )
            for month in range(1, args.months + 1):
                year = 2024 + (month - 1) // 12
                month_number = (month - 1) % 12 + 1
                store.save_transaction(
                    NormalizedTransaction(
                        apartment.internal_id,
                        date(year, month_number, 15),
                        100000000 + candidate,
                        Decimal("84"),
                        TransactionType.BROKERED,
                        False,
                        source_name="fixture",
                        source_record_id=f"{candidate}-{month}",
                    )
                )
        populated_bytes = path.stat().st_size
        with tempfile.TemporaryDirectory() as empty_dir:
            empty_path = Path(empty_dir) / "empty.sqlite3"
            SQLiteStore(empty_path).close()
            empty_bytes = empty_path.stat().st_size
        period = AnalysisPeriod(date(2024, 3, 1), date(2024, 5, 31))
        started = time.perf_counter()
        rows = sum(
            len(store.load_transactions(f"apt-{i:04d}", period)) for i in range(args.candidates)
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        plan = store.transaction_query_plan("apt-0000", period)
        print(f"candidates={args.candidates}")
        print(f"transactions={args.candidates * args.months}")
        print(f"empty_db_bytes={empty_bytes}")
        print(f"populated_db_bytes={populated_bytes}")
        print(f"growth_bytes={populated_bytes - empty_bytes}")
        print(f"requested_period_rows={rows}")
        print(f"requested_period_ms={elapsed_ms:.3f}")
        print(f"index_evidence={plan}")
        store.close()


if __name__ == "__main__":
    main()
