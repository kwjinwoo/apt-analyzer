"""Conservative Building HUB collection and exact-area normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import cast

from apt_analyzer.acquisition import DataGoKrClient, SourceError
from apt_analyzer.apartment_data import ApartmentCandidate, normalize_name

BASE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService"


class InventoryState(StrEnum):
    """Outcome of an inventory attempt."""

    VERIFIED = "verified"
    PARTIAL = "partial"
    EMPTY = "empty"
    MISMATCH = "mismatch"
    MAPPING_REQUIRED = "mapping_required"
    UNAVAILABLE = "unavailable"


class CollectionLimitError(SourceError):
    """Indicate that a refresh exceeded its local request budget."""


@dataclass(frozen=True, slots=True)
class InventoryPage:
    """Provenance for one bounded source page."""

    operation: str
    lot: tuple[str, str, str, str, str]
    page_no: int
    page_size: int
    total_count: int
    record_count: int
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class InventoryRow:
    """One residential unit with an exact exclusive area."""

    unit_key: str
    building: str
    unit: str
    area_sqm: Decimal


@dataclass(frozen=True, slots=True)
class InventorySummary:
    """Normalized area counts and collection confidence."""

    state: InventoryState
    rows: tuple[InventoryRow, ...]
    counts: tuple[tuple[Decimal, int], ...]
    total_count: int | None
    reason: str | None = None
    collected_at: datetime | None = None
    source: str = "Building HUB building register"
    reference_date: None = None
    normalization_version: str = "inventory-v1"
    mapping_version: str = "mapping-v1"
    scope: InventoryScope | None = None
    data_complete: bool = False
    kapt_total: int | None = None
    kapt_bands: tuple[tuple[str, int], ...] = ()
    pages: tuple[InventoryPage, ...] = ()


def reconcile_inventory(
    summary: InventorySummary,
    *,
    kapt_total: int | None,
    kapt_bands: tuple[tuple[str, int], ...] = (),
) -> InventorySummary:
    """Reconcile an already collected summary against current K-APT evidence."""
    if summary.scope is None or not summary.scope.complete or not summary.data_complete:
        return replace(summary, kapt_total=kapt_total, kapt_bands=kapt_bands)
    if kapt_total is None:
        return replace(
            summary,
            state=InventoryState.PARTIAL,
            reason="K-APT total household evidence is missing",
            kapt_total=None,
            kapt_bands=kapt_bands,
        )
    if summary.total_count != kapt_total:
        return replace(
            summary,
            state=InventoryState.MISMATCH,
            reason="inventory count differs from K-APT total",
            kapt_total=kapt_total,
            kapt_bands=kapt_bands,
        )
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
    if any(label in calculated and calculated[label] != count for label, count in kapt_bands):
        return replace(
            summary,
            state=InventoryState.MISMATCH,
            reason="inventory area bands differ from K-APT",
            kapt_total=kapt_total,
            kapt_bands=kapt_bands,
        )
    return replace(
        summary,
        state=InventoryState.VERIFIED,
        reason=None,
        kapt_total=kapt_total,
        kapt_bands=kapt_bands,
    )


@dataclass(frozen=True, slots=True)
class InventoryScope:
    """Purely resolved Building HUB graph scope before area normalization."""

    root_key: str | None
    title_keys: tuple[str, ...]
    unit_keys: tuple[str, ...]
    required_lots: tuple[tuple[str, str, str, str, str], ...]
    candidates: tuple[str, ...]
    complete: bool
    issues: tuple[str, ...] = ()
    mapping_version: str = "mapping-v2"


def resolve_scope(
    candidate: ApartmentCandidate,
    basis: tuple[Mapping[str, str], ...],
    recaps: tuple[Mapping[str, str], ...],
    titles: tuple[Mapping[str, str], ...],
    attachments: tuple[Mapping[str, str], ...],
    queried_lots: frozenset[tuple[str, str, str, str, str]] = frozenset(),
) -> InventoryScope:
    """Resolve a selected complex through its official parent graph and lots."""
    parcel = parse_lot_address(candidate)
    if parcel is None:
        return InventoryScope(None, (), (), (), (), False, ("selected parcel is not parseable",))
    sigungu, bjdong, plat, lot = parcel
    bun, _, ji = lot.partition("-")
    target = (sigungu, bjdong, plat, bun.zfill(4), (ji or "0").zfill(4))
    issues: list[str] = []
    by_key: dict[str, Mapping[str, str]] = {}
    for row in basis:
        key = _value(row, "mgmBldrgstPk")
        if not key:
            issues.append("basis row has no building-register key")
            continue
        essential = tuple(sorted((k, v) for k, v in row.items() if k not in {"rnum", "crtnDay"}))
        prior = by_key.get(key)
        if (
            prior is not None
            and tuple(sorted((k, v) for k, v in prior.items() if k not in {"rnum", "crtnDay"}))
            != essential
        ):
            issues.append(f"conflicting basis identity for {key}")
            continue
        by_key[key] = row

    def kind(row: Mapping[str, str]) -> str:
        return _value(row, "regstrKindCd") or ""

    def row_parcel(row: Mapping[str, str]) -> tuple[str, str, str, str, str] | None:
        if _value(row, "atchSigunguCd"):
            fields = ("atchSigunguCd", "atchBjdongCd", "atchPlatGbCd", "atchBun", "atchJi")
        else:
            fields = ("sigunguCd", "bjdongCd", "platGbCd", "bun", "ji")
        vals = tuple(_value(row, field) for field in fields)
        return vals if all(vals) else None  # type: ignore[return-value]

    source_by_key = {
        (_value(row, "mgmBldrgstPk") or ""): row
        for row in recaps + titles
        if _value(row, "mgmBldrgstPk")
    }

    def ascend(key: str) -> str | None:
        seen: set[str] = set()
        current = key
        while current:
            if current in seen:
                issues.append(f"cycle in basis graph {key}")
                return None
            seen.add(current)
            row = by_key.get(current)
            if row is None:
                issues.append(f"missing parent in basis graph {key}")
                return None
            parent = _value(row, "mgmUpBldrgstPk") or ""
            if not parent or parent == "0":
                return current
            current = parent
        return None

    recap_roots = [
        r
        for r in recaps
        if kind(r) == "1"
        and row_parcel(r) == target
        and _names_match(_value(r, "bldNm") or "", candidate.name)
    ]
    root_keys = {
        (_value(r, "mgmBldrgstPk") or "")
        for r in recap_roots
        if _value(r, "mgmBldrgstPk") in by_key
    }
    road = _road_key(candidate.road_address)
    for title in titles:
        key = _value(title, "mgmBldrgstPk")
        if kind(title) != "3" or not key or row_parcel(title) != target:
            continue
        if _names_match(_value(title, "bldNm") or "", candidate.name) or (
            road and _road_key(_value(title, "newPlatPlc") or "") == road
        ):
            root = ascend(key)
            if root is not None and (kind(by_key.get(root, {})) == "1" or root == key):
                root_keys.add(root)
    if len(root_keys) > 1:
        return InventoryScope(
            None,
            (),
            (),
            (target,),
            tuple(_value(source_by_key.get(key, {}), "bldNm") or "" for key in root_keys),
            False,
            ("multiple matching recap roots",),
        )
    root_key = next(iter(root_keys), None)
    if root_key is None:
        fallback = [
            r
            for r in titles
            if kind(r) == "3"
            and row_parcel(r) == target
            and _names_match(_value(r, "bldNm") or "", candidate.name)
        ]
        if len(fallback) != 1:
            return InventoryScope(
                None,
                (),
                (),
                (target,),
                tuple(_value(r, "bldNm") or "" for r in fallback),
                False,
                ("no unique matching root",),
            )
        root_key = _value(fallback[0], "mgmBldrgstPk")
        if not root_key or (_value(by_key.get(root_key, {}), "mgmUpBldrgstPk") or "") not in {
            "",
            "0",
        }:
            return InventoryScope(None, (), (), (target,), (), False, ("title root has a parent",))
    root = by_key.get(root_key)
    if root is None or kind(root) not in {"1", "3"} or row_parcel(root) != target:
        return InventoryScope(
            None,
            (),
            (),
            (target,),
            (),
            False,
            ("selected root basis identity is missing or inconsistent",),
        )
    source_root = next((row for row in recaps if _value(row, "mgmBldrgstPk") == root_key), None)
    if kind(root) == "1" and (
        source_root is None or kind(source_root) != "1" or row_parcel(source_root) != target
    ):
        return InventoryScope(
            None,
            (),
            (),
            (target,),
            (),
            False,
            ("selected root source identity is missing or inconsistent",),
        )
    for key, row in by_key.items():
        if kind(row) == "4":
            ascend(key)
    descendants: set[str] = {root_key}
    changed = True
    while changed:
        changed = False
        for key, row in by_key.items():
            parent = _value(row, "mgmUpBldrgstPk") or ""
            if parent in descendants and key not in descendants:
                descendants.add(key)
                changed = True
            if key == parent and parent:
                issues.append(f"self-cycle in basis graph {key}")
    for key in tuple(descendants):
        seen: set[str] = set()
        current = key
        while current and current not in seen:
            seen.add(current)
            current = _value(by_key.get(current, {}), "mgmUpBldrgstPk") or ""
        if current in seen:
            issues.append(f"cycle in basis graph {key}")
    title_keys = tuple(sorted(k for k in descendants if kind(by_key[k]) == "3"))
    unit_keys = tuple(sorted(k for k in descendants if kind(by_key[k]) == "4"))
    source_title_keys = {
        _value(row, "mgmBldrgstPk")
        for row in titles
        if _value(row, "mgmBldrgstPk") in descendants and kind(row) == "3"
    }
    if set(title_keys) - source_title_keys:
        issues.append("selected title is missing from source title records")
    for source_title in titles:
        key = _value(source_title, "mgmBldrgstPk")
        if key in title_keys and row_parcel(source_title) != row_parcel(by_key[key]):
            issues.append(f"source/basis title parcel conflict: {key}")
    confirmed_lots = {target}
    for attachment in attachments:
        if (_value(attachment, "mgmBldrgstPk") or "") not in descendants:
            continue
        attachment_fields = ("atchSigunguCd", "atchBjdongCd", "atchPlatGbCd", "atchBun", "atchJi")
        values = tuple(_value(attachment, field) for field in attachment_fields)
        if all(values):
            confirmed_lots.add(cast(tuple[str, str, str, str, str], values))
    for key in title_keys:
        if row_parcel(by_key[key]) not in confirmed_lots:
            issues.append(f"title parcel does not match selected parcel: {key}")
    for field, flag in (("mainBldCnt", "0"),):
        value = _value(source_root or {}, field)
        if value is not None:
            try:
                expected = sum(
                    1
                    for row in titles
                    if _value(row, "mgmBldrgstPk") in title_keys
                    and (_value(row, "mainAtchGbCd") or "0") == flag
                )
                if int(value) != expected:
                    issues.append(f"recap {field} does not match selected titles")
            except ValueError:
                issues.append(f"recap {field} is invalid")
    if not title_keys or not unit_keys:
        issues.append("selected root has no complete title/unit descendants")
    for key in unit_keys:
        parent = _value(by_key[key], "mgmUpBldrgstPk") or ""
        if kind(by_key.get(parent, {})) != "3":
            issues.append(f"unit parent is not a title: {key}")
    for key in title_keys:
        parent = _value(by_key[key], "mgmUpBldrgstPk") or ""
        if parent not in {root_key, "", "0"} and kind(by_key.get(parent, {})) != "1":
            issues.append(f"title parent is not a root: {key}")
    selected_rows = [r for r in attachments if (_value(r, "mgmBldrgstPk") or "") in descendants]
    lots = {target}
    for row in selected_rows:
        attachment_fields = ("atchSigunguCd", "atchBjdongCd", "atchPlatGbCd", "atchBun", "atchJi")
        raw_lot = tuple(_value(row, field) for field in attachment_fields)
        lot_values = (
            cast(tuple[str, str, str, str, str], tuple(str(value) for value in raw_lot))
            if all(raw_lot)
            else None
        )
        if lot_values is None:
            issues.append("selected attachment has malformed lot coordinates")
        else:
            lots.add(lot_values)
    bylot = _value(root, "bylotCnt")
    if bylot and bylot.isdigit() and int(bylot) != len(lots) - 1:
        issues.append("root attached-lot count does not match discovered lots")
    if not queried_lots or not lots.issubset(queried_lots):
        issues.append("required lot has not been queried")
    return InventoryScope(
        root_key,
        title_keys,
        unit_keys,
        tuple(sorted(lots)),
        (),
        not issues,
        tuple(sorted(set(issues))),
    )


class BuildingHubClient:
    """Call Building HUB endpoints with bounded, consistency-checked pages."""

    def __init__(
        self,
        client: DataGoKrClient,
        *,
        endpoint: str = BASE_URL,
        page_size: int = 100,
        max_pages: int = 200,
    ) -> None:
        """Configure the client and enforce request bounds."""
        if not 1 <= page_size <= 1000 or max_pages < 1:
            raise ValueError("invalid Building HUB pagination bounds")
        self.client = client
        self.endpoint = endpoint.rstrip("/")
        self.page_size = page_size
        self.max_pages = max_pages

    def fetch_all(
        self,
        operation: str,
        params: Mapping[str, str],
        *,
        source: str,
        before_request: Callable[[], None] | None = None,
        on_page: Callable[[InventoryPage], None] | None = None,
    ) -> tuple[dict[str, str], ...]:
        """Fetch all stable pages, rejecting missing or contradictory pagination."""
        rows: list[dict[str, str]] = []
        expected_total: int | None = None
        expected_page_size: int | None = None
        seen_pages: set[tuple[tuple[tuple[str, str], ...], ...]] = set()
        for page in range(1, self.max_pages + 1):
            query = {
                **params,
                "pageNo": str(page),
                "numOfRows": str(self.page_size),
                "_type": "xml",
            }
            result = self.client.get_xml(
                f"{self.endpoint}/{operation}",
                query,
                source=source,
                use_cache=False,
                request_guard=before_request,
            )
            if result.total_count is None or result.page_no is None or result.num_of_rows is None:
                raise SourceError("Building HUB pagination metadata is missing")
            if result.page_no != page:
                raise SourceError("Building HUB returned an unexpected page")
            if result.num_of_rows <= 0 or result.num_of_rows > self.page_size:
                raise SourceError("Building HUB returned an invalid page size")
            if expected_page_size is None:
                expected_page_size = result.num_of_rows
            elif expected_page_size != result.num_of_rows:
                raise SourceError("Building HUB page size changed during collection")
            if result.records and len(result.records) > result.num_of_rows:
                raise SourceError("Building HUB returned more rows than page size")
            if expected_total is None:
                expected_total = result.total_count
            elif expected_total != result.total_count:
                raise SourceError("Building HUB total count changed during collection")
            signature: tuple[tuple[tuple[str, str], ...], ...] = tuple(
                sorted(
                    tuple(sorted((k, v) for k, v in row.items() if k != "rnum"))
                    for row in result.records
                )
            )
            if signature in seen_pages and result.records:
                raise SourceError("Building HUB returned a repeated page")
            seen_pages.add(signature)
            rows.extend(dict(row) for row in result.records)
            if len(rows) > expected_total:
                raise SourceError("Building HUB returned more rows than total count")
            if on_page is not None:
                on_page(
                    InventoryPage(
                        operation,
                        _lot_from_params(params),
                        page,
                        result.num_of_rows,
                        expected_total,
                        len(result.records),
                        result.fetched_at,
                    )
                )
            if not result.records or len(rows) == expected_total:
                break
        else:
            raise SourceError("Building HUB pagination limit exceeded")
        if len(rows) != expected_total:
            raise SourceError("Building HUB collection is incomplete")
        return tuple(rows)


def _lot_from_params(params: Mapping[str, str]) -> tuple[str, str, str, str, str]:
    """Build a redacted fixed-width lot identity from a request."""
    return tuple(
        str(params.get(key, "")) for key in ("sigunguCd", "bjdongCd", "platGbCd", "bun", "ji")
    )  # type: ignore[return-value]


def parse_lot_address(candidate: ApartmentCandidate) -> tuple[str, str, str, str] | None:
    """Parse only a Korean legal-dong/ri and numeric lot from a selected candidate."""
    import re

    if not candidate.legal_dong_code.isdigit() or len(candidate.legal_dong_code) != 10:
        return None
    match = re.search(
        r"(?:^|\s)([가-힣]+(?:동|리))\s+(산\s*)?(\d+)(?:-(\d+))?(?:\s|$)", candidate.lot_address
    )
    if match is None:
        return None
    return (
        candidate.legal_dong_code[:5],
        candidate.legal_dong_code[5:],
        "1" if match.group(2) else "0",
        match.group(3) + (f"-{match.group(4)}" if match.group(4) else ""),
    )


class BuildingInventoryService:
    """Resolve one selected K-APT candidate and collect a conservative snapshot."""

    OPERATIONS = (
        "getBrBasisOulnInfo",
        "getBrRecapTitleInfo",
        "getBrTitleInfo",
        "getBrAtchJibunInfo",
        "getBrExposInfo",
        "getBrExposPubuseAreaInfo",
    )

    def __init__(
        self,
        hub: BuildingHubClient,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_requests: int = 300,
        max_lots: int = 16,
    ) -> None:
        """Configure bounded collection and an injectable acquisition clock."""
        self.hub = hub
        self.clock = clock
        self.max_requests = max_requests
        if max_requests < 1:
            raise ValueError("max_requests must be positive")
        if max_lots < 1:
            raise ValueError("max_lots must be positive")
        self.max_lots = max_lots

    def collect(
        self,
        candidate: ApartmentCandidate,
        *,
        kapt_total: int | None = None,
        kapt_bands: tuple[tuple[str, int], ...] = (),
    ) -> InventorySummary:
        """Collect current register evidence; identity or completeness uncertainty stays explicit."""
        parsed = parse_lot_address(candidate)
        now = self.clock()
        remaining = self.max_requests
        page_trace: list[InventoryPage] = []

        def guard() -> None:
            nonlocal remaining
            if remaining <= 0:
                raise CollectionLimitError("Building HUB collection request limit reached")
            remaining -= 1

        if parsed is None:
            return InventorySummary(
                InventoryState.MAPPING_REQUIRED,
                (),
                (),
                None,
                "selected lot address is not a supported legal lot",
                now,
            )
        sigungu, bjdong, plat, lot = parsed
        bun, _, ji = lot.partition("-")
        params = {
            "sigunguCd": sigungu,
            "bjdongCd": bjdong,
            "platGbCd": plat,
            "bun": bun.zfill(4),
            "ji": (ji or "0").zfill(4),
        }
        try:
            pages = self._fetch_lot(params, before_request=guard, on_page=page_trace.append)
        except CollectionLimitError:
            return InventorySummary(
                InventoryState.PARTIAL,
                (),
                (),
                None,
                "Building HUB collection request limit reached",
                now,
                pages=tuple(page_trace),
            )
        except SourceError:
            return InventorySummary(
                InventoryState.UNAVAILABLE,
                (),
                (),
                None,
                "Building HUB collection failed",
                now,
                pages=tuple(page_trace),
            )
        if all(not pages[operation] for operation in self.OPERATIONS):
            return InventorySummary(
                InventoryState.EMPTY,
                (),
                (),
                0,
                "Building HUB returned a valid empty result",
                now,
                pages=tuple(page_trace),
            )
        parsed_lot = parse_lot_address(candidate)
        queried: frozenset[tuple[str, str, str, str, str]] = frozenset()
        if parsed_lot:
            s, b, p, lot_text = parsed_lot
            n, _, j = lot_text.partition("-")
            queried = frozenset({(s, b, p, n.zfill(4), (j or "0").zfill(4))})
        scope = resolve_scope(
            candidate,
            tuple(pages["getBrBasisOulnInfo"]),
            tuple(pages["getBrRecapTitleInfo"]),
            tuple(pages["getBrTitleInfo"]),
            tuple(pages["getBrAtchJibunInfo"]),
            queried,
        )
        lots = scope.required_lots
        partial_base = InventorySummary(InventoryState.PARTIAL, (), (), None)
        while True:
            pending = [lot for lot in lots if lot not in queried]
            if not pending:
                break
            if len(queried) >= self.max_lots:
                return replace(
                    partial_base,
                    state=InventoryState.PARTIAL,
                    reason="lot collection limit exceeded",
                    scope=scope,
                    collected_at=now,
                    data_complete=False,
                )
            lot = pending[0]
            lot_params = {
                "sigunguCd": lot[0],
                "bjdongCd": lot[1],
                "platGbCd": lot[2],
                "bun": lot[3],
                "ji": lot[4],
            }
            try:
                extra = self._fetch_lot(lot_params, before_request=guard, on_page=page_trace.append)
            except SourceError:
                return InventorySummary(
                    InventoryState.UNAVAILABLE,
                    (),
                    (),
                    None,
                    "Building HUB collection failed",
                    now,
                    scope=scope,
                    pages=tuple(page_trace),
                )
            for operation in self.OPERATIONS:
                pages[operation] = tuple(pages[operation]) + tuple(extra[operation])
            queried = queried | {lot}
            scope = resolve_scope(
                candidate,
                tuple(pages["getBrBasisOulnInfo"]),
                tuple(pages["getBrRecapTitleInfo"]),
                tuple(pages["getBrTitleInfo"]),
                tuple(pages["getBrAtchJibunInfo"]),
                queried,
            )
            lots = scope.required_lots
        scope = resolve_scope(
            candidate,
            tuple(pages["getBrBasisOulnInfo"]),
            tuple(pages["getBrRecapTitleInfo"]),
            tuple(pages["getBrTitleInfo"]),
            tuple(pages["getBrAtchJibunInfo"]),
            queried,
        )
        selected = set(scope.unit_keys)
        result = normalize_inventory(
            tuple(
                row for row in pages["getBrExposInfo"] if _value(row, "mgmBldrgstPk") in selected
            ),
            tuple(
                row
                for row in pages["getBrExposPubuseAreaInfo"]
                if _value(row, "mgmBldrgstPk") in selected
            ),
        )
        exposed_keys = {_value(row, "mgmBldrgstPk") for row in pages["getBrExposInfo"]}
        area_keys = {_value(row, "mgmBldrgstPk") for row in pages["getBrExposPubuseAreaInfo"]}
        basis_keys = {_value(row, "mgmBldrgstPk") for row in pages["getBrBasisOulnInfo"]}
        if selected - exposed_keys:
            result = replace(
                result,
                state=InventoryState.PARTIAL,
                reason="selected graph units are missing exposure records",
            )
        if any(key not in basis_keys for key in exposed_keys):
            result = replace(
                result,
                state=InventoryState.PARTIAL,
                reason="exposure records contain unknown unit keys",
            )
        if any(key not in basis_keys or key not in exposed_keys for key in area_keys):
            result = replace(
                result,
                state=InventoryState.PARTIAL,
                reason="area records contain unknown unit keys",
            )
        if not scope.complete:
            return replace(
                result,
                state=InventoryState.MAPPING_REQUIRED
                if scope.root_key is None
                else InventoryState.PARTIAL,
                reason="Building HUB scope is incomplete",
                scope=scope,
                collected_at=now,
                data_complete=False,
                pages=tuple(page_trace),
            )
        state = result.state
        reason = result.reason
        if kapt_total is None and state is InventoryState.VERIFIED:
            state, reason = InventoryState.PARTIAL, "K-APT total household evidence is missing"
        elif (
            kapt_total is not None
            and result.total_count != kapt_total
            and state is InventoryState.VERIFIED
        ):
            state, reason = (
                InventoryState.MISMATCH,
                f"inventory count {result.total_count} differs from K-APT total {kapt_total}",
            )
        summary = InventorySummary(
            state,
            result.rows,
            result.counts if state is InventoryState.VERIFIED else result.counts,
            result.total_count if kapt_total is None else result.total_count,
            reason,
            now,
            scope=scope,
            data_complete=result.state in {InventoryState.VERIFIED, InventoryState.EMPTY},
            kapt_total=kapt_total,
            kapt_bands=kapt_bands,
            pages=tuple(page_trace),
        )
        return reconcile_inventory(summary, kapt_total=kapt_total, kapt_bands=kapt_bands)

    def _fetch_lot(
        self,
        params: Mapping[str, str],
        *,
        before_request: Callable[[], None] | None = None,
        on_page: Callable[[InventoryPage], None] | None = None,
    ) -> dict[str, tuple[dict[str, str], ...]]:
        """Fetch all six operations for one bounded lot."""
        result: dict[str, tuple[dict[str, str], ...]] = {}
        for op in self.OPERATIONS:
            result[op] = self.hub.fetch_all(
                op,
                params,
                source="Building HUB building register",
                before_request=before_request,
                on_page=on_page,
            )
        return result


def normalize_inventory(
    expos: tuple[Mapping[str, str], ...], areas: tuple[Mapping[str, str], ...]
) -> InventorySummary:
    """Join units to unambiguous residential exclusive areas and count them.

    This is a preliminary unit normalizer.  It does not certify complex scope;
    callers must separately establish complete building and lot coverage.
    """
    units: dict[str, tuple[str, str]] = {}
    invalid_units: set[str] = set()
    missing_identity: set[str] = set()
    seen_expos: set[tuple[tuple[str, str], ...]] = set()
    for row in expos:
        identity_record = tuple(sorted((key, value) for key, value in row.items() if key != "rnum"))
        if identity_record in seen_expos:
            continue
        seen_expos.add(identity_record)
        key = _value(row, "mgmBldrgstPk")
        if not key:
            invalid_units.add(f"missing:{len(invalid_units)}")
            continue
        identity = (_value(row, "dongNm") or "", _value(row, "hoNm") or "")
        if not identity[0] or not identity[1]:
            missing_identity.add(key)
        if key in units and units[key] != identity:
            invalid_units.add(key)
        units[key] = identity
    components: dict[str, dict[tuple[str, str, str], Decimal]] = {}
    unit_invalid = set(invalid_units)
    excluded_nonresidential: set[str] = set()
    invalid = False
    known_nonresidential = {
        "02004",
        "03001",
        "03002",
        "03003",
        "03005",
        "03013",
        "03027",
        "04005",
        "03999",
        "04001",
        "04010",
        "04025",
        "04040",
        "04401",
        "04403",
        "04406",
        "04999",
    }
    area_seen: set[tuple[tuple[str, str], ...]] = set()
    for row in areas:
        area_record = tuple(
            sorted((key, value) for key, value in row.items() if key not in {"rnum", "crtnDay"})
        )
        if area_record in area_seen:
            continue
        area_seen.add(area_record)
        key = _value(row, "mgmBldrgstPk")
        if not key or key not in units:
            invalid = True
            continue
        if key in unit_invalid:
            invalid = True
            continue
        use_code = _value(row, "exposPubuseGbCd") or ""
        purpose_code = _value(row, "mainPurpsCd") or ""
        purpose_name = _value(row, "mainPurpsCdNm") or ""
        use_name = _value(row, "exposPubuseGbCdNm") or ""
        if use_code == "2":
            continue
        if use_code != "1" or not purpose_code:
            invalid = True
            unit_invalid.add(key)
            continue
        if purpose_code in known_nonresidential and purpose_name:
            if key in components:
                unit_invalid.add(key)
                invalid = True
            excluded_nonresidential.add(key)
            continue
        if key in missing_identity:
            invalid = True
            unit_invalid.add(key)
            continue
        if (
            purpose_code != "02001"
            or (purpose_name and "아파트" not in purpose_name)
            or (use_name and "공용" in use_name)
        ):
            invalid = True
            unit_invalid.add(key)
            continue
        if key in excluded_nonresidential:
            invalid = True
            unit_invalid.add(key)
            continue
        compact_text = "".join(
            "".join((_value(row, name) or "").split()) for name in ("etcPurps", "mainPurpsCdNm")
        )
        if (
            "공유면적포함" in compact_text
            or "공용면적포함" in compact_text
            or "공용" in compact_text
            and "아파트" not in compact_text
        ):
            invalid = True
            unit_invalid.add(key)
            continue
        attached = _value(row, "mainAtchGbCd")
        if attached not in (None, "0"):
            invalid = True
            unit_invalid.add(key)
            continue
        raw_area = _value(row, "area")
        try:
            area = Decimal(raw_area or "")
        except InvalidOperation:
            invalid = True
            unit_invalid.add(key)
            continue
        if not area.is_finite() or area <= 0:
            invalid = True
            unit_invalid.add(key)
            continue
        floor_kind = _value(row, "flrGbCd") or ""
        floor_no = _value(row, "flrNo") or ""
        component = (floor_kind, floor_no, _value(row, "mainAtchGbCd") or "0")
        previous_component = components.setdefault(key, {}).get(component)
        if previous_component is not None and previous_component != area:
            unit_invalid.add(key)
            invalid = True
            continue
        components[key][component] = area
    normalized: dict[str, InventoryRow] = {}
    for key, values in components.items():
        if key in unit_invalid or not values:
            continue
        if len(values) > 1 and any(
            not floor_kind or not floor_no for floor_kind, floor_no, _ in values
        ):
            invalid = True
            continue
        building, unit = units[key]
        normalized[key] = InventoryRow(key, building, unit, sum(values.values(), Decimal(0)))
    if (
        set(units) != set(normalized) | excluded_nonresidential
        or unit_invalid
        or (missing_identity - excluded_nonresidential)
    ):
        invalid = True
        for key in unit_invalid:
            normalized.pop(key, None)
    if not normalized:
        if invalid:
            return InventorySummary(
                InventoryState.PARTIAL, (), (), None, "no valid unit remains after validation"
            )
        return InventorySummary(
            InventoryState.EMPTY, (), (), 0, "no valid residential exclusive units"
        )
    counts: dict[Decimal, int] = {}
    for row in normalized.values():
        counts[row.area_sqm] = counts.get(row.area_sqm, 0) + 1
    state = InventoryState.PARTIAL if invalid else InventoryState.VERIFIED
    return InventorySummary(
        state,
        tuple(normalized.values()),
        tuple(sorted(counts.items())),
        len(normalized),
        "some units or area records were invalid" if invalid else None,
    )


def _value(row: Mapping[str, str], key: str) -> str | None:
    value = row.get(key)
    return value.strip() if value is not None else None


def _names_match(source_name: str, selected_name: str) -> bool:
    """Match the register building name with only the documented apartment suffix."""
    source = normalize_name(source_name)
    selected = normalize_name(selected_name)
    return source == selected or source.removesuffix("아파트") == selected


def _road_key(value: str) -> str:
    """Normalize a road address without treating its legal-dong suffix as identity."""
    import re

    return re.sub(r"\s+", "", re.sub(r"\s*\([^)]*\)\s*$", "", value.strip()))
