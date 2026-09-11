"""SQLite persistence and incremental acquisition boundaries for M3."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

from apt_analyzer.apartment_data import (
    ApartmentCandidate,
    ApartmentProfile,
    AreaHouseholdBand,
    months,
)
from apt_analyzer.building_hub import (
    InventoryPage,
    InventoryRow,
    InventoryScope,
    InventoryState,
    InventorySummary,
)
from apt_analyzer.domain import AnalysisPeriod, Apartment, NormalizedTransaction, TransactionType

CURRENT_SCHEMA_VERSION = 8
SEOUL = ZoneInfo("Asia/Seoul")


def _as_object(value: object) -> object:
    """Stop untyped JSON values at the persistence boundary."""
    return value


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


@dataclass(frozen=True, slots=True)
class HouseholdEvidenceRecord:
    """Persisted whole-complex household denominator evidence."""

    count: int
    scope: str
    source: str
    fetched_at: str


@dataclass(frozen=True, slots=True)
class ApartmentProfileRecord:
    """Persisted K-APT profile with provenance."""

    profile: ApartmentProfile
    source: str
    fetched_at: str


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    """Persisted exact-area inventory summary and its acquisition status."""

    summary: InventorySummary
    source: str
    fetched_at: str


def _inventory_summary_json(summary: InventorySummary) -> str:
    """Encode the complete inventory evidence using JSON-safe exact values."""

    def timestamp(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    scope = None
    if summary.scope is not None:
        scope = {
            "root_key": summary.scope.root_key,
            "title_keys": list(summary.scope.title_keys),
            "unit_keys": list(summary.scope.unit_keys),
            "required_lots": [list(lot) for lot in summary.scope.required_lots],
            "candidates": list(summary.scope.candidates),
            "complete": summary.scope.complete,
            "issues": list(summary.scope.issues),
            "mapping_version": summary.scope.mapping_version,
        }
    payload = {
        "state": summary.state.value,
        "rows": [
            {
                "unit_key": row.unit_key,
                "building": row.building,
                "unit": row.unit,
                "area_sqm": str(row.area_sqm),
            }
            for row in summary.rows
        ],
        "counts": [[str(area), count] for area, count in summary.counts],
        "total_count": summary.total_count,
        "reason": summary.reason,
        "collected_at": timestamp(summary.collected_at),
        "source": summary.source,
        "reference_date": summary.reference_date,
        "normalization_version": summary.normalization_version,
        "mapping_version": summary.mapping_version,
        "scope": scope,
        "data_complete": summary.data_complete,
        "kapt_total": summary.kapt_total,
        "kapt_bands": [[label, count] for label, count in summary.kapt_bands],
        "pages": [
            {
                "operation": page.operation,
                "lot": list(page.lot),
                "page_no": page.page_no,
                "page_size": page.page_size,
                "total_count": page.total_count,
                "record_count": page.record_count,
                "fetched_at": page.fetched_at.isoformat(),
            }
            for page in summary.pages
        ],
    }
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _inventory_summary_from_json(payload: str) -> InventorySummary:
    """Decode and validate a complete persisted inventory summary."""

    def reject_constant(value: str) -> object:
        raise ValueError(f"invalid inventory JSON constant: {value}")

    raw_value: object = json.loads(payload, parse_constant=reject_constant)
    if not isinstance(raw_value, dict):
        raise ValueError("invalid persisted inventory summary")
    raw = cast(dict[str, object], raw_value)

    def text(name: str, required: bool = False) -> str | None:
        value = raw.get(name)
        if isinstance(value, str) and value:
            return value
        if required:
            raise ValueError(f"invalid inventory field: {name}")
        return None

    state_raw = text("state", True)
    try:
        state = InventoryState(cast(str, state_raw))
    except ValueError as exc:
        raise ValueError("invalid persisted inventory state") from exc
    rows_raw = raw.get("rows", [])
    counts_raw = raw.get("counts", [])
    if not isinstance(rows_raw, list) or not isinstance(counts_raw, list):
        raise ValueError("invalid persisted inventory rows")
    row_items: list[object] = cast(list[object], rows_raw)
    count_items: list[object] = cast(list[object], counts_raw)
    rows: list[InventoryRow] = []
    for item in row_items:
        if not isinstance(item, dict):
            raise ValueError("invalid persisted inventory row")
        row = cast(dict[str, object], item)
        unit_key = row.get("unit_key")
        building = row.get("building")
        unit = row.get("unit")
        area_raw = row.get("area_sqm")
        if not all(isinstance(v, str) and v for v in (unit_key, building, unit, area_raw)):
            raise ValueError("invalid persisted inventory row")
        try:
            area = Decimal(cast(str, area_raw))
        except InvalidOperation as exc:
            raise ValueError("invalid persisted inventory area") from exc
        if not area.is_finite() or area <= 0:
            raise ValueError("invalid persisted inventory area")
        rows.append(InventoryRow(cast(str, unit_key), cast(str, building), cast(str, unit), area))
    counts: list[tuple[Decimal, int]] = []
    for item in count_items:
        if not isinstance(item, list):
            raise ValueError("invalid persisted inventory counts")
        pair: list[object] = cast(list[object], item)
        if (
            len(pair) != 2
            or not isinstance(pair[0], str)
            or not isinstance(pair[1], int)
            or isinstance(pair[1], bool)
            or pair[1] <= 0
        ):
            raise ValueError("invalid persisted inventory counts")
        area = Decimal(pair[0])
        if not area.is_finite() or area <= 0:
            raise ValueError("invalid persisted inventory count area")
        counts.append((area, pair[1]))
    scope_raw = raw.get("scope")
    scope = None
    if scope_raw is not None:
        if not isinstance(scope_raw, dict):
            raise ValueError("invalid persisted inventory scope")
        s = cast(dict[str, object], scope_raw)

        def strings(name: str) -> tuple[str, ...]:
            value = s.get(name, [])
            if not isinstance(value, list):
                raise ValueError("invalid persisted inventory scope")
            values: list[object] = cast(list[object], value)
            if not all(isinstance(v, str) for v in values):
                raise ValueError("invalid persisted inventory scope")
            return tuple(v for v in values if isinstance(v, str))

        lots_raw = s.get("required_lots", [])
        lot_items: list[object] = cast(list[object], lots_raw) if isinstance(lots_raw, list) else []
        if not isinstance(lots_raw, list):
            raise ValueError("invalid persisted inventory scope lots")
        typed_lots: list[tuple[str, str, str, str, str]] = []
        for value in lot_items:
            if not isinstance(value, list):
                raise ValueError("invalid persisted inventory scope lots")
            parts: list[object] = cast(list[object], value)
            if len(parts) != 5 or not all(isinstance(part, str) for part in parts):
                raise ValueError("invalid persisted inventory scope lots")
            typed_lots.append(
                cast(
                    tuple[str, str, str, str, str],
                    tuple(part for part in parts if isinstance(part, str)),
                )
            )
        root = s.get("root_key")
        if root is not None and not isinstance(root, str):
            raise ValueError("invalid persisted inventory scope root")
        complete = s.get("complete")
        if not isinstance(complete, bool):
            raise ValueError("invalid persisted inventory scope completeness")
        mapping_version = s.get("mapping_version", "mapping-v1")
        if not isinstance(mapping_version, str) or not mapping_version:
            raise ValueError("invalid persisted inventory scope mapping version")
        scope = InventoryScope(
            root,
            strings("title_keys"),
            strings("unit_keys"),
            tuple(typed_lots),
            strings("candidates"),
            complete,
            strings("issues"),
            mapping_version,
        )
    collected_raw = raw.get("collected_at")
    collected = None
    if collected_raw is not None:
        if not isinstance(collected_raw, str):
            raise ValueError("invalid inventory collection time")
        collected = datetime.fromisoformat(collected_raw)
        if collected.tzinfo is None:
            raise ValueError("inventory collection time must be timezone-aware")
    pages_raw = raw.get("pages", [])
    if not isinstance(pages_raw, list):
        raise ValueError("invalid inventory pages")
    page_items: list[object] = cast(list[object], pages_raw)
    pages: list[InventoryPage] = []
    for item in page_items:
        if not isinstance(item, dict):
            raise ValueError("invalid inventory page")
        p = cast(dict[str, object], item)
        lot = p.get("lot")
        if not isinstance(lot, list):
            raise ValueError("invalid inventory page lot")
        lot_parts: list[object] = cast(list[object], lot)
        if len(lot_parts) != 5 or not all(isinstance(x, str) for x in lot_parts):
            raise ValueError("invalid inventory page lot")
        page_lot = cast(
            tuple[str, str, str, str, str], tuple(x for x in lot_parts if isinstance(x, str))
        )
        vals = [
            p.get(k)
            for k in (
                "operation",
                "page_no",
                "page_size",
                "total_count",
                "record_count",
                "fetched_at",
            )
        ]
        if (
            not isinstance(vals[0], str)
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in vals[1:5])
            or not isinstance(vals[5], str)
        ):
            raise ValueError("invalid inventory page")
        page_no, page_size, page_total, page_records = (
            cast(int, vals[1]),
            cast(int, vals[2]),
            cast(int, vals[3]),
            cast(int, vals[4]),
        )
        if (
            page_no <= 0
            or page_size <= 0
            or page_total < 0
            or page_records < 0
            or page_records > page_size
            or page_records > page_total
        ):
            raise ValueError("invalid inventory page")
        page_time = datetime.fromisoformat(vals[5])
        if page_time.tzinfo is None:
            raise ValueError("inventory page time must be timezone-aware")
        pages.append(
            InventoryPage(
                vals[0],
                page_lot,
                page_no,
                page_size,
                page_total,
                page_records,
                page_time,
            )
        )
    total = raw.get("total_count")
    if total is not None and (not isinstance(total, int) or isinstance(total, bool) or total < 0):
        raise ValueError("invalid inventory total")
    kapt_total = raw.get("kapt_total")
    if kapt_total is not None and (
        not isinstance(kapt_total, int) or isinstance(kapt_total, bool) or kapt_total < 0
    ):
        raise ValueError("invalid K-APT total")
    bands_raw = raw.get("kapt_bands", [])
    if not isinstance(bands_raw, list):
        raise ValueError("invalid K-APT bands")
    band_items: list[object] = cast(list[object], bands_raw)
    parsed_bands: list[tuple[str, int]] = []
    for item in band_items:
        if not isinstance(item, list):
            raise ValueError("invalid K-APT bands")
        pair: list[object] = cast(list[object], item)
        if (
            len(pair) != 2
            or not isinstance(pair[0], str)
            or not isinstance(pair[1], int)
            or isinstance(pair[1], bool)
        ):
            raise ValueError("invalid K-APT bands")
        if pair[1] < 0:
            raise ValueError("invalid K-APT bands")
        parsed_bands.append((pair[0], pair[1]))
    bands = tuple(parsed_bands)
    raw_data_complete = raw.get("data_complete", False)
    if not isinstance(raw_data_complete, bool):
        raise ValueError("invalid inventory completeness")
    summary = InventorySummary(
        state,
        tuple(rows),
        tuple(counts),
        total,
        text("reason"),
        collected,
        text("source") or "Building HUB building register",
        None,
        text("normalization_version") or "inventory-v1",
        text("mapping_version") or "mapping-v1",
        scope,
        raw_data_complete,
        kapt_total,
        bands,
        tuple(pages),
    )
    _validate_inventory_summary(summary)
    return summary


def _validate_inventory_summary(summary: InventorySummary) -> None:
    """Reject summaries that cannot be safely persisted as normalized evidence."""
    if len({row.unit_key for row in summary.rows}) != len(summary.rows):
        raise ValueError("inventory rows must have unique unit keys")
    histogram: dict[Decimal, int] = {}
    for row in summary.rows:
        if not row.area_sqm.is_finite() or row.area_sqm <= 0:
            raise ValueError("inventory areas must be finite and positive")
        histogram[row.area_sqm] = histogram.get(row.area_sqm, 0) + 1
    if tuple(summary.counts) != tuple(sorted(histogram.items())):
        raise ValueError("inventory counts do not match row histogram")
    if summary.total_count is not None and summary.total_count != len(summary.rows):
        raise ValueError("inventory total does not match rows")
    if summary.state is InventoryState.VERIFIED and (
        summary.scope is None
        or not summary.scope.complete
        or not summary.data_complete
        or not summary.rows
        or summary.kapt_total != summary.total_count
    ):
        raise ValueError(
            "verified inventory requires complete scope, data, and K-APT reconciliation"
        )
    if summary.state is InventoryState.VERIFIED:
        calculated = {"≤60㎡": 0, ">60–85㎡": 0, ">85–135㎡": 0, ">135㎡": 0}
        for area, count in summary.counts:
            label = (
                "≤60㎡"
                if area <= 60
                else ">60–85㎡"
                if area <= 85
                else ">85–135㎡"
                if area <= 135
                else ">135㎡"
            )
            calculated[label] += count
        if any(calculated.get(label) != count for label, count in summary.kapt_bands):
            raise ValueError("verified inventory bands do not match K-APT")


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

    def save_household_evidence(
        self, apartment_id: str, count: int, *, scope: str, source: str
    ) -> None:
        """Persist validated household evidence for later offline analysis."""
        if count <= 0 or scope != "complex" or not source.strip():
            raise ValueError("household evidence must be positive, complex-scoped, and sourced")
        self._connection.execute(
            "INSERT INTO household_evidence(apartment_id, household_count, scope, source, fetched_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(apartment_id) DO UPDATE SET household_count=excluded.household_count, "
            "scope=excluded.scope, source=excluded.source, fetched_at=excluded.fetched_at",
            (
                apartment_id,
                count,
                scope,
                source,
                datetime.now(UTC).replace(microsecond=0).isoformat(),
            ),
        )
        self._connection.commit()

    def save_profile(self, apartment_id: str, profile: ApartmentProfile, *, source: str) -> None:
        """Atomically replace persisted profile evidence."""
        if not source.strip():
            raise ValueError("profile source must not be empty")
        self._connection.execute(
            "INSERT INTO apartment_profiles(apartment_id, profile_json, source, fetched_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(apartment_id) DO UPDATE SET profile_json=excluded.profile_json, source=excluded.source, fetched_at=excluded.fetched_at",
            (
                apartment_id,
                json.dumps(asdict(profile), ensure_ascii=False, default=str),
                source,
                datetime.now(UTC).replace(microsecond=0).isoformat(),
            ),
        )
        self._connection.commit()

    def save_profile_and_household(
        self,
        apartment_id: str,
        profile: ApartmentProfile | None,
        household_count: int | None,
        *,
        household_source: str | None,
        profile_source: str,
    ) -> None:
        """Atomically replace the explicit profile and its matching household evidence."""
        if household_count is not None:
            if household_count <= 0:
                raise ValueError("household count must be positive")
            if household_source is None or not household_source.strip():
                raise ValueError("household source must not be empty")
        if profile is not None and not profile_source.strip():
            raise ValueError("profile source must not be empty")
        with self._connection:
            if household_count is not None and household_source:
                self._connection.execute(
                    "INSERT INTO household_evidence(apartment_id, household_count, scope, source, fetched_at) VALUES (?, ?, 'complex', ?, ?) ON CONFLICT(apartment_id) DO UPDATE SET household_count=excluded.household_count, source=excluded.source, fetched_at=excluded.fetched_at",
                    (
                        apartment_id,
                        household_count,
                        household_source,
                        datetime.now(UTC).replace(microsecond=0).isoformat(),
                    ),
                )
            if profile is not None:
                self._connection.execute(
                    "INSERT INTO apartment_profiles(apartment_id, profile_json, source, fetched_at) VALUES (?, ?, ?, ?) ON CONFLICT(apartment_id) DO UPDATE SET profile_json=excluded.profile_json, source=excluded.source, fetched_at=excluded.fetched_at",
                    (
                        apartment_id,
                        json.dumps(asdict(profile), ensure_ascii=False, default=str),
                        profile_source,
                        datetime.now(UTC).replace(microsecond=0).isoformat(),
                    ),
                )

    def load_profile(self, apartment_id: str) -> ApartmentProfileRecord | None:
        """Load profile evidence without external access."""
        row = self._connection.execute(
            "SELECT profile_json, source, fetched_at FROM apartment_profiles WHERE apartment_id=?",
            (apartment_id,),
        ).fetchone()
        if row is None:
            return None
        raw_value: object = json.loads(str(row["profile_json"]))
        raw = raw_value
        if not isinstance(raw, dict):
            raise ValueError("invalid persisted apartment profile")
        typed_raw: dict[str, object] = cast(dict[str, object], raw)
        approval_raw = _as_object(typed_raw.get("approval_date"))
        approval = (
            date.fromisoformat(approval_raw)
            if isinstance(approval_raw, str) and approval_raw
            else None
        )
        bands_raw = _as_object(typed_raw.get("area_bands", []))
        if not isinstance(bands_raw, list):
            raise ValueError("invalid persisted apartment profile")
        typed_bands: list[object] = cast(list[object], bands_raw)
        bands: list[AreaHouseholdBand] = []
        for item in typed_bands:
            band = _as_object(item)
            if not isinstance(band, dict):
                raise ValueError("invalid persisted apartment profile")
            label = _as_object(cast(dict[str, object], band).get("label"))
            count = _as_object(cast(dict[str, object], band).get("count"))
            if not isinstance(label, str) or not isinstance(count, int) or isinstance(count, bool):
                raise ValueError("invalid persisted apartment profile")
            bands.append(AreaHouseholdBand(label, count))

        def optional_int(name: str) -> int | None:
            result = _as_object(typed_raw.get(name))
            return result if isinstance(result, int) else None

        def optional_text(name: str) -> str | None:
            result = _as_object(typed_raw.get(name))
            return result if isinstance(result, str) else None

        profile = ApartmentProfile(
            buildings=optional_int("buildings"),
            approval_date=approval,
            highest_floor=optional_int("highest_floor"),
            heating=optional_text("heating"),
            hall_type=optional_text("hall_type"),
            builder=optional_text("builder"),
            developer=optional_text("developer"),
            management=optional_text("management"),
            sale_type=optional_text("sale_type"),
            area_bands=tuple(bands),
        )
        return ApartmentProfileRecord(profile, str(row["source"]), str(row["fetched_at"]))

    def save_inventory(self, apartment_id: str, summary: InventorySummary, *, source: str) -> None:
        """Atomically save a verified inventory and always retain the latest attempt."""
        if not apartment_id.strip() or not source.strip():
            raise ValueError("inventory source must not be empty")
        if summary.collected_at is None or summary.collected_at.tzinfo is None:
            raise ValueError("inventory collection time must be timezone-aware")
        if not summary.source.strip():
            raise ValueError("inventory summary source must not be empty")
        _validate_inventory_summary(summary)
        fetched_at = summary.collected_at.isoformat()
        payload = _inventory_summary_json(summary)
        with self._connection:
            self._connection.execute(
                "INSERT INTO inventory_attempts(apartment_id,status,reason,summary_json,source,fetched_at) VALUES (?,?,?,?,?,?)",
                (
                    apartment_id,
                    summary.state.value,
                    summary.reason,
                    payload,
                    source,
                    fetched_at,
                ),
            )
            if summary.state is InventoryState.VERIFIED:
                self._connection.execute(
                    "DELETE FROM inventory_rows WHERE apartment_id=?", (apartment_id,)
                )
                for row in summary.rows:
                    self._connection.execute(
                        "INSERT INTO inventory_rows(apartment_id,unit_key,building,unit,area_sqm) VALUES (?,?,?,?,?)",
                        (apartment_id, row.unit_key, row.building, row.unit, str(row.area_sqm)),
                    )
                self._connection.execute(
                    "INSERT INTO inventory_snapshots(apartment_id,status,total_count,summary_json,source,fetched_at) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(apartment_id) DO UPDATE SET status=excluded.status,total_count=excluded.total_count,summary_json=excluded.summary_json,source=excluded.source,fetched_at=excluded.fetched_at",
                    (
                        apartment_id,
                        summary.state.value,
                        summary.total_count,
                        payload,
                        source,
                        fetched_at,
                    ),
                )

    def load_inventory(self, apartment_id: str) -> InventoryRecord | None:
        """Load the last verified inventory without external access."""
        snapshot = self._connection.execute(
            "SELECT status,total_count,summary_json,source,fetched_at FROM inventory_snapshots WHERE apartment_id=?",
            (apartment_id,),
        ).fetchone()
        if snapshot is None:
            return None
        if snapshot["summary_json"]:
            summary = _inventory_summary_from_json(str(snapshot["summary_json"]))
            return InventoryRecord(summary, str(snapshot["source"]), str(snapshot["fetched_at"]))
        rows = tuple(
            InventoryRow(
                str(row["unit_key"]),
                str(row["building"]),
                str(row["unit"]),
                Decimal(str(row["area_sqm"])),
            )
            for row in self._connection.execute(
                "SELECT unit_key,building,unit,area_sqm FROM inventory_rows WHERE apartment_id=? ORDER BY area_sqm,unit_key",
                (apartment_id,),
            )
        )
        counts: dict[Decimal, int] = {}
        for row in rows:
            counts[row.area_sqm] = counts.get(row.area_sqm, 0) + 1
        summary = InventorySummary(
            InventoryState(str(snapshot["status"])),
            rows,
            tuple(sorted(counts.items())),
            snapshot["total_count"],
        )
        return InventoryRecord(summary, str(snapshot["source"]), str(snapshot["fetched_at"]))

    def load_inventory_attempt(self, apartment_id: str) -> InventoryRecord | None:
        """Return the latest attempt status, reason, and timestamp."""
        row = self._connection.execute(
            "SELECT status,summary_json,source,fetched_at FROM inventory_attempts WHERE apartment_id=? ORDER BY id DESC LIMIT 1",
            (apartment_id,),
        ).fetchone()
        if row is None or not row["summary_json"]:
            return None
        return InventoryRecord(
            _inventory_summary_from_json(str(row["summary_json"])),
            str(row["source"]),
            str(row["fetched_at"]),
        )

    def load_household_evidence(self, apartment_id: str) -> HouseholdEvidenceRecord | None:
        """Load persisted household evidence without contacting an external source."""
        row = self._connection.execute(
            "SELECT household_count, scope, source, fetched_at FROM household_evidence WHERE apartment_id=?",
            (apartment_id,),
        ).fetchone()
        if row is None:
            return None
        return HouseholdEvidenceRecord(
            int(row["household_count"]),
            str(row["scope"]),
            str(row["source"]),
            str(row["fetched_at"]),
        )

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
            self._migrate_v6()
            self._migrate_v7()
            self._migrate_v8()
            self._connection.commit()
            return
        version = int(row[0])
        if version not in (1, 2, 3, 4, 5, 6, 7, CURRENT_SCHEMA_VERSION):
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
        self._migrate_v6()
        self._migrate_v7()
        self._migrate_v8()
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

    def _migrate_v6(self) -> None:
        """Add persisted K-APT whole-complex household evidence."""
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS household_evidence (
                apartment_id TEXT PRIMARY KEY,
                household_count INTEGER NOT NULL CHECK(household_count > 0),
                scope TEXT NOT NULL,
                source TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            );
            UPDATE schema_version SET version=6;
            """
        )

    def _migrate_v7(self) -> None:
        """Add persisted optional K-APT profile evidence."""
        self._connection.executescript(
            """CREATE TABLE IF NOT EXISTS apartment_profiles (
                apartment_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL,
                source TEXT NOT NULL, fetched_at TEXT NOT NULL
            ); UPDATE schema_version SET version=7;"""
        )

    def _migrate_v8(self) -> None:
        """Add independent exact-area inventory snapshots and attempt history."""
        self._connection.executescript(
            """CREATE TABLE IF NOT EXISTS inventory_snapshots (
                apartment_id TEXT PRIMARY KEY, status TEXT NOT NULL, total_count INTEGER,
                summary_json TEXT, source TEXT NOT NULL, fetched_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inventory_rows (
                apartment_id TEXT NOT NULL, unit_key TEXT NOT NULL, building TEXT NOT NULL,
                unit TEXT NOT NULL, area_sqm TEXT NOT NULL,
                PRIMARY KEY(apartment_id, unit_key)
            );
            CREATE TABLE IF NOT EXISTS inventory_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, apartment_id TEXT NOT NULL,
                status TEXT NOT NULL, reason TEXT, summary_json TEXT, source TEXT NOT NULL DEFAULT '', fetched_at TEXT NOT NULL
            );
            UPDATE schema_version SET version=8;"""
        )
        columns = {
            str(row["name"])
            for row in self._connection.execute("PRAGMA table_info(inventory_attempts)")
        }
        if "summary_json" not in columns:
            self._connection.execute("ALTER TABLE inventory_attempts ADD COLUMN summary_json TEXT")
        if "source" not in columns:
            self._connection.execute(
                "ALTER TABLE inventory_attempts ADD COLUMN source TEXT NOT NULL DEFAULT ''"
            )
        snapshot_columns = {
            str(row["name"])
            for row in self._connection.execute("PRAGMA table_info(inventory_snapshots)")
        }
        if "summary_json" not in snapshot_columns:
            self._connection.execute("ALTER TABLE inventory_snapshots ADD COLUMN summary_json TEXT")

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
