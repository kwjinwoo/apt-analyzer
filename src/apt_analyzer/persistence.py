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
from zoneinfo import ZoneInfo

from apt_analyzer.apartment_data import ApartmentCandidate, months
from apt_analyzer.domain import AnalysisPeriod, Apartment, NormalizedTransaction, TransactionType

CURRENT_SCHEMA_VERSION = 5
SEOUL = ZoneInfo("Asia/Seoul")


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


@dataclass(frozen=True, slots=True)
class SavedApartmentInterest:
    """Persisted apartment preference with the evidence needed to restore it."""

    candidate: ApartmentCandidate
    apartment: Apartment
    source_name: str
    region_code: str


class SQLiteStore:
    """Store normalized evidence, coverage, and freshness in a versioned SQLite file."""

    def __init__(self, path: str | Path, *, check_same_thread: bool = False) -> None:
        """Open or create a SQLite database and migrate it to the current schema."""
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, check_same_thread=check_same_thread)
        self._connection.row_factory = sqlite3.Row
        self._migrate()

    @property
    def schema_version(self) -> int:
        """Return the deterministic current schema version."""
        version = int(self._connection.execute("SELECT version FROM schema_version").fetchone()[0])
        return version

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._connection.close()

    def increment_api_usage(self, service_id: str, *, recorded_date: str | None = None) -> None:
        """Atomically record one outbound public-API attempt for a Seoul calendar date."""
        if not service_id.strip():
            raise ValueError("service_id must not be empty")
        usage_date = recorded_date or datetime.now(SEOUL).date().isoformat()
        with self._connection:
            self._connection.execute(
                "INSERT INTO api_usage(usage_date, service_id, request_count) VALUES (?, ?, 1) "
                "ON CONFLICT(usage_date, service_id) DO UPDATE SET request_count=request_count + 1",
                (usage_date, service_id),
            )

    def api_usage_snapshot(
        self, usage_date: str | None = None, service_ids: tuple[str, ...] = ()
    ) -> dict[str, int]:
        """Return zero-inclusive request counts for the requested Seoul calendar date."""
        target_date = usage_date or datetime.now(SEOUL).date().isoformat()
        if not service_ids:
            return {}
        placeholders = ",".join("?" for _ in service_ids)
        rows = self._connection.execute(
            f"SELECT service_id, request_count FROM api_usage WHERE usage_date=? AND service_id IN ({placeholders})",
            (target_date, *service_ids),
        ).fetchall()
        values = {str(row["service_id"]): int(row["request_count"]) for row in rows}
        return {service_id: values.get(service_id, 0) for service_id in service_ids}

    def save_apartment(self, apartment: Apartment) -> None:
        """Insert or refresh an apartment identity."""
        self._connection.execute(
            "INSERT INTO apartments(internal_id, display_name) VALUES (?, ?) "
            "ON CONFLICT(internal_id) DO UPDATE SET display_name=excluded.display_name",
            (apartment.internal_id, apartment.display_name),
        )
        self._connection.commit()

    def save_interest(
        self,
        candidate: ApartmentCandidate,
        apartment: Apartment,
        *,
        region_code: str,
        source_name: str = "K-APT apartment list",
    ) -> None:
        """Save one resolved apartment preference and its identity evidence idempotently."""
        if not (
            candidate.source_id
            and len(candidate.legal_dong_code) == 10
            and candidate.lot_address
            and candidate.road_address
            and region_code
            and source_name
        ):
            raise ValueError("saved interest requires complete apartment identity evidence")
        with self._connection:
            self._connection.execute(
                "INSERT INTO apartments(internal_id, display_name) VALUES (?, ?) "
                "ON CONFLICT(internal_id) DO UPDATE SET display_name=excluded.display_name",
                (apartment.internal_id, apartment.display_name),
            )
            self._connection.execute(
                "INSERT INTO saved_interests(apartment_id, display_name, source_name, region_code, "
                "source_id, candidate_name, legal_dong_code, lot_address, road_address, saved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(apartment_id) DO UPDATE SET display_name=excluded.display_name, "
                "source_name=excluded.source_name, region_code=excluded.region_code, "
                "source_id=excluded.source_id, candidate_name=excluded.candidate_name, "
                "legal_dong_code=excluded.legal_dong_code, lot_address=excluded.lot_address, "
                "road_address=excluded.road_address",
                (
                    apartment.internal_id,
                    apartment.display_name,
                    source_name,
                    region_code,
                    candidate.source_id,
                    candidate.name,
                    candidate.legal_dong_code,
                    candidate.lot_address,
                    candidate.road_address,
                    datetime.now(UTC).replace(microsecond=0).isoformat(),
                ),
            )

    def list_interests(self) -> tuple[SavedApartmentInterest, ...]:
        """Return saved interests in deterministic internal-identity order."""
        rows = self._connection.execute(
            "SELECT apartment_id, display_name, source_name, region_code, source_id, "
            "candidate_name, legal_dong_code, lot_address, road_address "
            "FROM saved_interests ORDER BY apartment_id"
        ).fetchall()
        return tuple(
            SavedApartmentInterest(
                ApartmentCandidate(
                    str(row["source_id"]),
                    str(row["candidate_name"]),
                    str(row["legal_dong_code"]),
                    str(row["lot_address"]),
                    str(row["road_address"]),
                ),
                Apartment(str(row["apartment_id"]), str(row["display_name"])),
                str(row["source_name"]),
                str(row["region_code"]),
            )
            for row in rows
        )

    def get_interest(self, apartment_id: str) -> SavedApartmentInterest | None:
        """Return one saved interest by its server-owned internal apartment ID."""
        return next(
            (item for item in self.list_interests() if item.apartment.internal_id == apartment_id),
            None,
        )

    def remove_interest(self, apartment_id: str) -> bool:
        """Remove only the preference row, preserving apartment and transaction evidence."""
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM saved_interests WHERE apartment_id=?", (apartment_id,)
            )
        return cursor.rowcount == 1

    def save_transaction(self, transaction: NormalizedTransaction) -> bool:
        """Persist one normalized transaction, returning whether it was new."""
        added = self._insert_transaction(transaction)
        self._connection.commit()
        return added

    def load_transactions(
        self, apartment_id: str, period: AnalysisPeriod | None = None
    ) -> tuple[NormalizedTransaction, ...]:
        """Load stored normalized transactions, optionally bounded by an inclusive period."""
        if period is None:
            rows = self._connection.execute(
                "SELECT * FROM transactions WHERE apartment_id=? ORDER BY contract_date, id",
                (apartment_id,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM transactions WHERE apartment_id=? AND contract_date>=? AND contract_date<=? "
                "ORDER BY contract_date, id",
                (apartment_id, period.start.isoformat(), period.end.isoformat()),
            ).fetchall()
        values = tuple(_transaction_from_row(row) for row in rows)
        return values

    def save_candidate_snapshot(
        self,
        source_name: str,
        region_code: str,
        candidates: Iterable[ApartmentCandidate],
        *,
        fetched_at: str,
    ) -> None:
        """Atomically replace candidate metadata and mark successful region coverage."""
        values = tuple(candidates)
        with self._connection:
            self._connection.execute(
                "DELETE FROM region_candidates WHERE source_name=? AND region_code=?",
                (source_name, region_code),
            )
            for candidate in values:
                self._connection.execute(
                    "INSERT INTO region_candidates(source_name, region_code, source_id, name, legal_dong_code, lot_address, road_address) VALUES (?,?,?,?,?,?,?)",
                    (
                        source_name,
                        region_code,
                        candidate.source_id,
                        candidate.name,
                        candidate.legal_dong_code,
                        candidate.lot_address,
                        candidate.road_address,
                    ),
                )
            self._connection.execute(
                "INSERT INTO region_coverage(source_name, region_code, fetched_at, result_state) VALUES (?,?,?,?) "
                "ON CONFLICT(source_name, region_code) DO UPDATE SET fetched_at=excluded.fetched_at, result_state=excluded.result_state",
                (source_name, region_code, fetched_at, "valid_empty" if not values else "complete"),
            )
            self._connection.execute(
                "INSERT INTO region_attempts(source_name, region_code, attempted_at, status, error) "
                "VALUES (?,?,?,?,NULL) ON CONFLICT(source_name, region_code) DO UPDATE SET "
                "attempted_at=excluded.attempted_at, status=excluded.status, error=NULL",
                (
                    source_name,
                    region_code,
                    fetched_at,
                    "valid_empty" if not values else "complete",
                ),
            )

    def load_candidate_snapshot(
        self, source_name: str, region_code: str
    ) -> tuple[dict[str, object], ...]:
        """Return source/region candidates in stable source-id order."""
        rows = self._connection.execute(
            "SELECT * FROM region_candidates WHERE source_name=? AND region_code=? ORDER BY source_id",
            (source_name, region_code),
        ).fetchall()
        return tuple(
            {
                "source_name": str(row["source_name"]),
                "region_code": str(row["region_code"]),
                "source_id": str(row["source_id"]),
                "name": str(row["name"]),
                "legal_dong_code": str(row["legal_dong_code"]),
                "lot_address": str(row["lot_address"]),
                "road_address": str(row["road_address"]),
            }
            for row in rows
        )

    def region_coverage(self, source_name: str, region_code: str) -> dict[str, str] | None:
        """Return persisted region coverage, or ``None`` for a cache miss."""
        row = self._connection.execute(
            "SELECT fetched_at, result_state FROM region_coverage WHERE source_name=? AND region_code=?",
            (source_name, region_code),
        ).fetchone()
        return None if row is None else {"fetched_at": str(row[0]), "result_state": str(row[1])}

    def region_attempt(self, source_name: str, region_code: str) -> dict[str, str] | None:
        """Return the latest persisted candidate-refresh attempt."""
        row = self._connection.execute(
            "SELECT attempted_at, status, error FROM region_attempts "
            "WHERE source_name=? AND region_code=?",
            (source_name, region_code),
        ).fetchone()
        return (
            None
            if row is None
            else {
                "attempted_at": str(row["attempted_at"]),
                "status": str(row["status"]),
                "error": "" if row["error"] is None else str(row["error"]),
            }
        )

    def record_region_failure(
        self, source_name: str, region_code: str, *, attempted_at: str, error: str
    ) -> None:
        """Persist an external candidate-source failure without replacing good metadata."""
        self._connection.execute(
            "INSERT INTO region_attempts(source_name, region_code, attempted_at, status, error) "
            "VALUES (?,?,?,?,?) ON CONFLICT(source_name, region_code) DO UPDATE SET "
            "attempted_at=excluded.attempted_at, status='failed', error=excluded.error",
            (source_name, region_code, attempted_at, "failed", error),
        )
        self._connection.commit()

    def link_candidate_resolution(
        self,
        source_name: str,
        region_code: str,
        source_id: str,
        apartment_id: str,
        *,
        resolved_at: str,
    ) -> None:
        """Persist deterministic source-candidate to internal identity linkage."""
        self._connection.execute(
            "INSERT INTO candidate_resolution(source_name, region_code, source_id, apartment_id, resolved_at) VALUES (?,?,?,?,?) ON CONFLICT(source_name, region_code, source_id) DO UPDATE SET apartment_id=excluded.apartment_id, resolved_at=excluded.resolved_at",
            (source_name, region_code, source_id, apartment_id, resolved_at),
        )
        self._connection.commit()

    def candidate_resolution(
        self, source_name: str, region_code: str, source_id: str
    ) -> str | None:
        """Load one candidate's linked internal apartment ID."""
        row = self._connection.execute(
            "SELECT apartment_id FROM candidate_resolution WHERE source_name=? AND region_code=? AND source_id=?",
            (source_name, region_code, source_id),
        ).fetchone()
        return None if row is None else str(row[0])

    def load_resolved_candidates(
        self,
        source_name: str,
        region_codes: Iterable[str],
        source_ids: Iterable[str] = (),
    ) -> tuple[tuple[str, ApartmentCandidate, Apartment], ...]:
        """Load current regional candidates that have a persisted internal identity."""
        regions = tuple(dict.fromkeys(region_codes))
        selected_ids = frozenset(source_ids)
        if not regions:
            return ()
        placeholders = ",".join("?" for _ in regions)
        rows = self._connection.execute(
            "SELECT c.region_code, c.source_id, c.name, c.legal_dong_code, c.lot_address, "
            "c.road_address, a.internal_id, a.display_name "
            "FROM region_candidates c "
            "JOIN candidate_resolution r ON r.source_name=c.source_name "
            "AND r.region_code=c.region_code AND r.source_id=c.source_id "
            "JOIN apartments a ON a.internal_id=r.apartment_id "
            f"WHERE c.source_name=? AND c.region_code IN ({placeholders}) "
            "ORDER BY c.region_code, c.source_id",
            (source_name, *regions),
        ).fetchall()
        return tuple(
            (
                str(row["region_code"]),
                ApartmentCandidate(
                    str(row["source_id"]),
                    str(row["name"]),
                    str(row["legal_dong_code"]),
                    str(row["lot_address"]),
                    str(row["road_address"]),
                ),
                Apartment(str(row["internal_id"]), str(row["display_name"])),
            )
            for row in rows
            if not selected_ids or str(row["source_id"]) in selected_ids
        )

    def coverage(self, apartment_id: str, source_name: str = "unknown") -> dict[str, str]:
        """Return successful monthly coverage as month to fetched-at mapping."""
        rows = self._connection.execute(
            "SELECT month, fetched_at FROM monthly_coverage WHERE apartment_id=? AND source_name=? ORDER BY month",
            (apartment_id, source_name),
        )
        return {str(row[0]): str(row[1]) for row in rows}

    def coverage_states(self, apartment_id: str, source_name: str = "unknown") -> dict[str, str]:
        """Return successful months as complete or valid-empty persisted evidence."""
        rows = self._connection.execute(
            "SELECT c.month, a.status AS attempt_status, EXISTS("
            "SELECT 1 FROM transactions t WHERE t.apartment_id=c.apartment_id "
            "AND COALESCE(t.source_name, '')=c.source_name "
            "AND REPLACE(SUBSTR(t.contract_date, 1, 7), '-', '')=c.month"
            ") AS has_records "
            "FROM monthly_coverage c LEFT JOIN monthly_attempts a "
            "ON a.apartment_id=c.apartment_id AND a.source_name=c.source_name AND a.month=c.month "
            "WHERE c.apartment_id=? AND c.source_name=? "
            "ORDER BY c.month",
            (apartment_id, source_name),
        ).fetchall()
        states = {
            str(row["month"]): (
                str(row["attempt_status"])
                if row["attempt_status"] is not None
                else ("complete" if bool(row["has_records"]) else "valid_empty")
            )
            for row in rows
        }
        failed_without_coverage = self._connection.execute(
            "SELECT month FROM monthly_attempts WHERE apartment_id=? AND source_name=? "
            "AND status='failed' ORDER BY month",
            (apartment_id, source_name),
        ).fetchall()
        states.update({str(row["month"]): "failed" for row in failed_without_coverage})
        return dict(sorted(states.items()))

    def transaction_query_plan(self, apartment_id: str, period: AnalysisPeriod) -> str:
        """Return SQLite's requested-period query plan for scale validation."""
        row = self._connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM transactions "
            "WHERE apartment_id=? AND contract_date>=? AND contract_date<=?",
            (apartment_id, period.start.isoformat(), period.end.isoformat()),
        ).fetchone()
        return str(row["detail"])

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
                self._connection.execute(
                    "INSERT INTO monthly_attempts(apartment_id, source_name, month, attempted_at, status, error) "
                    "VALUES (?,?,?,?,?,NULL) ON CONFLICT(apartment_id, source_name, month) DO UPDATE SET "
                    "attempted_at=excluded.attempted_at, status=excluded.status, error=NULL",
                    (
                        apartment.internal_id,
                        source_name,
                        month,
                        now,
                        "valid_empty" if not records else "complete",
                    ),
                )
                self._connection.commit()
                fetched.append(month)
                updates.append(MonthUpdate(month, "fetched", month_inserted, month_duplicates, now))
                inserted += month_inserted
                duplicates += month_duplicates
            except Exception as error:  # noqa: BLE001 - source boundary preserves failures
                self._connection.rollback()
                self._connection.execute(
                    "INSERT INTO monthly_attempts(apartment_id, source_name, month, attempted_at, status, error) "
                    "VALUES (?,?,?,?,?,?) ON CONFLICT(apartment_id, source_name, month) DO UPDATE SET "
                    "attempted_at=excluded.attempted_at, status='failed', error=excluded.error",
                    (apartment.internal_id, source_name, month, now, "failed", str(error)),
                )
                self._connection.commit()
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
                INSERT INTO schema_version VALUES (4);
                """
            )
            self._migrate_v3()
            self._migrate_v4()
            self._migrate_v5()
            self._connection.commit()
            return
        version = int(row[0])
        if version not in (1, 2, 3, 4, CURRENT_SCHEMA_VERSION):
            raise ValueError(f"unsupported schema version: {version}")
        if version == 1:
            self._migrate_v1()
            version = 2
        if version in (2, 3, 4, CURRENT_SCHEMA_VERSION):
            self._migrate_v3()
            self._migrate_v4()
            self._migrate_v5()
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS apartments (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL)"
        )
        self._migrate_v5()
        self._connection.commit()

    def _migrate_v3(self) -> None:
        """Add regional metadata and SQL-bounded transaction loading indexes."""
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS region_candidates (
                source_name TEXT NOT NULL, region_code TEXT NOT NULL, source_id TEXT NOT NULL,
                name TEXT NOT NULL, legal_dong_code TEXT NOT NULL, lot_address TEXT NOT NULL,
                road_address TEXT NOT NULL, PRIMARY KEY(source_name, region_code, source_id)
            );
            CREATE TABLE IF NOT EXISTS region_coverage (
                source_name TEXT NOT NULL, region_code TEXT NOT NULL, fetched_at TEXT NOT NULL,
                result_state TEXT NOT NULL CHECK(result_state IN ('complete', 'valid_empty')),
                PRIMARY KEY(source_name, region_code)
            );
            CREATE TABLE IF NOT EXISTS region_attempts (
                source_name TEXT NOT NULL, region_code TEXT NOT NULL, attempted_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('complete', 'valid_empty', 'failed')),
                error TEXT, PRIMARY KEY(source_name, region_code)
            );
            CREATE TABLE IF NOT EXISTS candidate_resolution (
                source_name TEXT NOT NULL, region_code TEXT NOT NULL, source_id TEXT NOT NULL,
                apartment_id TEXT NOT NULL, resolved_at TEXT NOT NULL,
                PRIMARY KEY(source_name, region_code, source_id)
            );
            CREATE TABLE IF NOT EXISTS monthly_attempts (
                apartment_id TEXT NOT NULL, source_name TEXT NOT NULL, month TEXT NOT NULL,
                attempted_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('complete', 'valid_empty', 'failed')),
                error TEXT, PRIMARY KEY(apartment_id, source_name, month)
            );
            CREATE INDEX IF NOT EXISTS ix_transactions_apartment_contract
                ON transactions(apartment_id, contract_date, id);
            UPDATE schema_version SET version=3;
            """
        )

    def _migrate_v4(self) -> None:
        """Add persisted daily outbound-request accounting without changing evidence."""
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_usage (
                usage_date TEXT NOT NULL,
                service_id TEXT NOT NULL,
                request_count INTEGER NOT NULL CHECK(request_count >= 0),
                PRIMARY KEY(usage_date, service_id)
            );
            UPDATE schema_version SET version=4;
            """
        )

    def _migrate_v5(self) -> None:
        """Add persisted local apartment-interest preferences and identity evidence."""
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS saved_interests (
                apartment_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
                source_name TEXT NOT NULL, region_code TEXT NOT NULL,
                source_id TEXT NOT NULL, candidate_name TEXT NOT NULL,
                legal_dong_code TEXT NOT NULL, lot_address TEXT NOT NULL,
                road_address TEXT NOT NULL, saved_at TEXT NOT NULL
            );
            UPDATE schema_version SET version=5;
            """
        )

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
