"""SQLite persistence and incremental acquisition boundaries for M3."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from apt_analyzer.domain import AnalysisPeriod, Apartment, NormalizedTransaction, TransactionType
from apt_analyzer.m1 import months

CURRENT_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class MonthUpdate:
    """Report one month's fetch status and write counts."""

    month: str
    status: str
    inserted: int = 0
    duplicates: int = 0
    fetched_at: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateReport:
    """Summarize an incremental update across all requested months."""

    fetched_months: tuple[str, ...]
    skipped_months: tuple[str, ...]
    inserted_count: int
    duplicate_count: int
    failures: tuple[MonthUpdate, ...]
    updates: tuple[MonthUpdate, ...] = ()


class SQLiteStore:
    """Store normalized evidence, coverage, and freshness in a versioned SQLite file."""

    def __init__(self, path: str | Path) -> None:
        """Open or create a SQLite database and migrate it to the current schema."""
        self.path = str(path)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._migrate()

    @property
    def schema_version(self) -> int:
        """Return the deterministic current schema version."""
        return int(self._connection.execute("SELECT version FROM schema_version").fetchone()[0])

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._connection.close()

    def save_apartment(self, apartment: Apartment) -> None:
        """Insert or refresh an apartment identity."""
        self._connection.execute(
            "INSERT INTO apartments(internal_id, display_name) VALUES (?, ?) "
            "ON CONFLICT(internal_id) DO UPDATE SET display_name=excluded.display_name",
            (apartment.internal_id, apartment.display_name),
        )
        self._connection.commit()

    def load_transactions(
        self, apartment_id: str, period: AnalysisPeriod | None = None
    ) -> tuple[NormalizedTransaction, ...]:
        """Load stored normalized transactions, optionally bounded by an inclusive period."""
        rows = self._connection.execute(
            "SELECT * FROM transactions WHERE apartment_id=? ORDER BY contract_date, id",
            (apartment_id,),
        ).fetchall()
        values = tuple(_transaction_from_row(row) for row in rows)
        return (
            values
            if period is None
            else tuple(item for item in values if period.includes(item.contract_date))
        )

    def coverage(self, apartment_id: str, source_name: str = "unknown") -> dict[str, str]:
        """Return successful monthly coverage as month to fetched-at mapping."""
        rows = self._connection.execute(
            "SELECT month, fetched_at FROM monthly_coverage WHERE apartment_id=? AND source_name=? ORDER BY month",
            (apartment_id, source_name),
        )
        return {str(row[0]): str(row[1]) for row in rows}

    def update_incremental(
        self,
        apartment: Apartment,
        period: AnalysisPeriod,
        fetch_month: Callable[[str], Iterable[NormalizedTransaction]],
        *,
        refresh_before: datetime | None = None,
        source_name: str = "unknown",
    ) -> UpdateReport:
        """Fetch missing/stale months and persist valid-empty coverage distinctly from failures."""
        self.save_apartment(apartment)
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        fetched: list[str] = []
        skipped: list[str] = []
        failures: list[MonthUpdate] = []
        updates: list[MonthUpdate] = []
        inserted = duplicates = 0
        for month in months(period):
            row = self._connection.execute(
                "SELECT fetched_at FROM monthly_coverage WHERE apartment_id=? AND source_name=? AND month=?",
                (apartment.internal_id, source_name, month),
            ).fetchone()
            if row is not None and (
                refresh_before is None or str(row[0]) >= refresh_before.isoformat()
            ):
                skipped.append(month)
                updates.append(MonthUpdate(month, "skipped", fetched_at=str(row[0])))
                continue
            try:
                records = tuple(fetch_month(month))
                month_inserted = month_duplicates = 0
                for transaction in records:
                    if (
                        transaction.apartment_id != apartment.internal_id
                        or transaction.contract_date.strftime("%Y%m") != month
                    ):
                        raise ValueError(
                            "fetched transaction does not belong to requested apartment/month"
                        )
                    if transaction.source_name != source_name:
                        raise ValueError(
                            "fetched transaction source provenance does not match requested source"
                        )
                    added = self._insert_transaction(transaction)
                    month_inserted += int(added)
                    month_duplicates += int(not added)
                self._connection.execute(
                    "INSERT INTO monthly_coverage(apartment_id, source_name, month, fetched_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(apartment_id, source_name, month) DO UPDATE SET fetched_at=excluded.fetched_at",
                    (apartment.internal_id, source_name, month, now),
                )
                self._connection.commit()
                fetched.append(month)
                updates.append(MonthUpdate(month, "fetched", month_inserted, month_duplicates, now))
                inserted += month_inserted
                duplicates += month_duplicates
            except Exception as error:  # noqa: BLE001 - source boundary preserves failures
                self._connection.rollback()
                failures.append(MonthUpdate(month, "failed", error=str(error)))
                updates.append(failures[-1])
        return UpdateReport(
            tuple(fetched), tuple(skipped), inserted, duplicates, tuple(failures), tuple(updates)
        )

    def _insert_transaction(self, transaction: NormalizedTransaction) -> bool:
        key = _transaction_key(transaction)
        cursor = self._connection.execute(
            "INSERT OR IGNORE INTO transactions(apartment_id, contract_date, price_krw, exclusive_area_sqm, "
            "transaction_type, is_cancelled, floor, building, unit, construction_year, broker_location, "
            "source_name, source_record_id, source_values, source_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                transaction.apartment_id,
                transaction.contract_date.isoformat(),
                transaction.price_krw,
                str(transaction.exclusive_area_sqm),
                transaction.transaction_type.value,
                int(transaction.is_cancelled),
                transaction.floor,
                transaction.building,
                transaction.unit,
                transaction.construction_year,
                transaction.broker_location,
                transaction.source_name,
                transaction.source_record_id,
                json.dumps(transaction.source_values, ensure_ascii=False),
                key,
            ),
        )
        return cursor.rowcount == 1

    def _migrate(self) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
        )
        row = self._connection.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            self._connection.executescript(
                """
                CREATE TABLE apartments (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL);
                CREATE TABLE transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, apartment_id TEXT NOT NULL, contract_date TEXT NOT NULL, price_krw INTEGER NOT NULL, exclusive_area_sqm TEXT NOT NULL, transaction_type TEXT NOT NULL, is_cancelled INTEGER NOT NULL, floor INTEGER, building TEXT, unit TEXT, construction_year INTEGER, broker_location TEXT, source_name TEXT, source_record_id TEXT, source_values TEXT NOT NULL, source_key TEXT NOT NULL);
                CREATE UNIQUE INDEX uq_transactions_source ON transactions(apartment_id, COALESCE(source_name, ''), source_key);
                CREATE TABLE monthly_coverage (apartment_id TEXT NOT NULL, source_name TEXT NOT NULL, month TEXT NOT NULL, fetched_at TEXT NOT NULL, PRIMARY KEY(apartment_id, source_name, month));
                INSERT INTO schema_version VALUES (2);
                """
            )
            self._connection.commit()
            return
        version = int(row[0])
        if version not in (1, CURRENT_SCHEMA_VERSION):
            raise ValueError(f"unsupported schema version: {version}")
        if version == 1:
            self._migrate_v1()
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS apartments (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL)"
        )
        self._connection.commit()

    def _migrate_v1(self) -> None:
        """Migrate legacy data atomically with deterministic duplicate collapse."""
        try:
            self._connection.execute("BEGIN")
            for statement in (
                "ALTER TABLE transactions ADD COLUMN id INTEGER",
                "ALTER TABLE transactions ADD COLUMN floor INTEGER",
                "ALTER TABLE transactions ADD COLUMN building TEXT",
                "ALTER TABLE transactions ADD COLUMN unit TEXT",
                "ALTER TABLE transactions ADD COLUMN construction_year INTEGER",
                "ALTER TABLE transactions ADD COLUMN broker_location TEXT",
                "ALTER TABLE transactions ADD COLUMN source_key TEXT",
            ):
                self._connection.execute(statement)
            rows = self._connection.execute(
                "SELECT rowid, * FROM transactions ORDER BY rowid"
            ).fetchall()
            seen: set[tuple[str, str | None, str]] = set()
            for legacy in rows:
                transaction = _transaction_from_row(legacy)
                identity = (
                    transaction.apartment_id,
                    transaction.source_name,
                    _transaction_key(transaction),
                )
                if identity in seen:
                    self._connection.execute(
                        "DELETE FROM transactions WHERE rowid=?", (legacy["rowid"],)
                    )
                else:
                    seen.add(identity)
                    self._connection.execute(
                        "UPDATE transactions SET source_key=? WHERE rowid=?",
                        (_transaction_key(transaction), legacy["rowid"]),
                    )
            self._connection.execute("DROP INDEX IF EXISTS uq_transactions_source")
            self._connection.execute(
                "CREATE UNIQUE INDEX uq_transactions_source ON transactions(apartment_id, COALESCE(source_name, ''), source_key)"
            )
            old_coverage = self._connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='monthly_coverage'"
            ).fetchone()
            if old_coverage:
                self._connection.execute(
                    "ALTER TABLE monthly_coverage RENAME TO monthly_coverage_legacy"
                )
            self._connection.execute(
                "CREATE TABLE monthly_coverage (apartment_id TEXT NOT NULL, source_name TEXT NOT NULL, month TEXT NOT NULL, fetched_at TEXT NOT NULL, PRIMARY KEY(apartment_id, source_name, month))"
            )
            if old_coverage:
                self._connection.execute(
                    "INSERT INTO monthly_coverage SELECT apartment_id, source_name, month, fetched_at FROM monthly_coverage_legacy"
                )
                self._connection.execute("DROP TABLE monthly_coverage_legacy")
            self._connection.execute("UPDATE schema_version SET version=2")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise


def _transaction_key(transaction: NormalizedTransaction) -> str:
    value = (
        transaction.source_name,
        transaction.source_record_id,
        transaction.contract_date.isoformat(),
        transaction.price_krw,
        str(transaction.exclusive_area_sqm),
        transaction.transaction_type.value,
        transaction.is_cancelled,
        transaction.floor,
        transaction.building,
        transaction.unit,
        transaction.construction_year,
        transaction.broker_location,
        transaction.source_values,
    )
    return hashlib.sha256(repr(value).encode()).hexdigest()


def _transaction_from_row(row: sqlite3.Row) -> NormalizedTransaction:
    return NormalizedTransaction(
        row["apartment_id"],
        date.fromisoformat(row["contract_date"]),
        int(row["price_krw"]),
        Decimal(row["exclusive_area_sqm"]),
        TransactionType(row["transaction_type"]),
        bool(row["is_cancelled"]),
        row["floor"],
        row["building"],
        row["unit"],
        row["construction_year"],
        row["broker_location"],
        row["source_name"],
        row["source_record_id"],
        tuple(tuple(item) for item in json.loads(row["source_values"] or "[]")),
    )
