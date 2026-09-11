"""Local browser workspace for apt-analyzer."""

from __future__ import annotations

import calendar
import hashlib
import json
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from apt_analyzer.analytics import (
    ANNUALIZATION_METHOD,
    PRICE_SERIES_METHOD,
    ROLLING_RETENTION_METHOD,
    ROLLING_TURNOVER_METHOD,
    AnalysisResult,
    DataCoverageStatus,
    HouseholdEvidence,
    analyze,
    build_population,
    derive_completed_month_periods,
    discover_area_groups,
    maximum_drawdown,
    monthly_transaction_trend,
    preview_turnover,
    rolling_retention,
)
from apt_analyzer.apartment_data import (
    KAPT_DETAIL_ENDPOINT,
    KAPT_LIST_ENDPOINT,
    MOLIT_SALE_ENDPOINT,
    ApartmentCandidate,
    ApartmentDataService,
    ApartmentProfile,
    IdentityResolution,
    months,
    normalize_name,
)
from apt_analyzer.building_hub import (
    BASE_URL as BUILDING_HUB_BASE_URL,
)
from apt_analyzer.building_hub import (
    BuildingHubClient,
    BuildingInventoryService,
    InventoryState,
    InventorySummary,
    reconcile_inventory,
)
from apt_analyzer.cli import comparison_to_dict, json_value, result_to_dict
from apt_analyzer.comparison import CommonAnalysisConfig, compare
from apt_analyzer.domain import (
    AnalysisContext,
    AnalysisPeriod,
    Apartment,
    AreaSelection,
    NormalizedTransaction,
    TransactionInclusionPolicy,
    TransactionType,
)
from apt_analyzer.persistence import ApartmentProfileRecord, HouseholdEvidenceRecord, SQLiteStore
from apt_analyzer.regional_screening import (
    SUPPORTED_METHODS,
    SUPPORTED_UNITS,
    CandidateRefreshReport,
    CandidateRefreshState,
    CandidateScreenRule,
    RegionalCandidate,
    SQLiteCandidateCache,
    screen_candidates,
)

_TEMPLATE_DIRECTORY = Path(__file__).parent / "templates"
PROVINCE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("11", "서울특별시"),
    ("26", "부산광역시"),
    ("27", "대구광역시"),
    ("28", "인천광역시"),
    ("29", "광주광역시"),
    ("30", "대전광역시"),
    ("31", "울산광역시"),
    ("36", "세종특별자치시"),
    ("41", "경기도"),
    ("51", "강원특별자치도"),
    ("43", "충청북도"),
    ("44", "충청남도"),
    ("52", "전북특별자치도"),
    ("46", "전라남도"),
    ("47", "경상북도"),
    ("48", "경상남도"),
    ("50", "제주특별자치도"),
)
_PROVINCE_CODES = frozenset(code for code, _label in PROVINCE_OPTIONS)
_UI_LABELS = {
    "idle": "대기 중",
    "searching": "검색 중",
    "not_found": "검색 결과 없음",
    "selected": "선택됨",
    "updated": "갱신 완료",
    "analyzed": "분석 완료",
    "compared": "비교 완료",
    "unavailable": "사용 불가",
    "valid_empty": "유효한 빈 결과",
    "verified": "검증 완료",
    "partial": "부분 수집",
    "mismatch": "근거 불일치",
    "empty": "유효한 빈 결과",
    "mapping_required": "단지 식별 필요",
    "fresh": "최신 데이터",
    "stale": "오래된 데이터",
    "failed": "실패",
    "complete": "완료",
    "brokered": "중개 거래",
    "direct": "직거래",
    "unknown": "거래 유형 미상",
    "observed": "관측됨",
    "missing": "누락됨",
    "skipped": "갱신 생략",
    "coverage-limited": "데이터 범위 제한",
    "cache_miss": "저장된 데이터 없음",
    "external_failure": "외부 데이터 수집 실패",
    "fetched": "새로 수집됨",
    "incomplete": "데이터 불완전",
    "zero baseline": "기준 기간 거래량이 0",
    "requested monthly coverage is incomplete": "요청한 월별 데이터 범위가 불완전합니다",
    "requested area group is absent from candidate evidence": "요청한 면적 그룹의 후보 근거가 없습니다",
    "no eligible transactions": "유효한 거래가 없습니다",
    "period is not complete calendar-year aligned": "기간이 완전한 달력 연도 기준이 아닙니다",
    "household denominator is missing or invalid": "세대수 분모가 없거나 올바르지 않습니다",
    "household source evidence is missing": "세대수 출처 근거가 없습니다",
    "household denominator scope does not match area selection": "세대수 분모 범위가 면적 선택과 일치하지 않습니다",
    "baseline annualized transaction count is zero": "기준 기간 연환산 거래량이 0입니다",
    "baseline transaction count is zero": "기준 기간 거래량이 0입니다",
    "required monthly coverage is incomplete": "필요한 월별 근거가 완전하지 않습니다",
    "rolling turnover requires exactly 12 complete calendar months": "거래회전율은 완전한 연속 12개월이 필요합니다",
    "rolling turnover requires completed calendar months": "거래회전율은 완료된 달력 월만 사용할 수 있습니다",
    "rolling retention requires adjacent 12-month calendar windows": "거래유지율은 인접한 12개월 구간 두 개가 필요합니다",
    "rolling retention requires completed calendar months": "거래유지율은 완료된 달력 월만 사용할 수 있습니다",
    "fewer than two observed months": "관측된 월이 두 개 미만입니다",
    "metric period is outside overall analysis period": "지표 기간이 전체 분석 기간 밖에 있습니다",
    "metric unavailable": "사용 불가",
    "metric rule failed": "규칙 불충족",
    "transaction_count unavailable": "거래량: 사용 불가",
    "transaction_count rule failed": "거래량: 규칙 불충족",
    "median_price_krw unavailable": "중간 거래가격: 사용 불가",
    "median_price_krw rule failed": "중간 거래가격: 규칙 불충족",
    "median_area_sqm unavailable": "중간 전용면적: 사용 불가",
    "median_area_sqm rule failed": "중간 전용면적: 규칙 불충족",
    "turnover_ratio unavailable": "거래회전율: 사용 불가",
    "turnover_ratio rule failed": "거래회전율: 규칙 불충족",
    "retention_ratio unavailable": "거래유지율: 사용 불가",
    "retention_ratio rule failed": "거래유지율: 규칙 불충족",
    "mdd_ratio unavailable": "최대낙폭(MDD): 사용 불가",
    "mdd_ratio rule failed": "최대낙폭(MDD): 규칙 불충족",
}
_UI_METRIC_LABELS = {
    "median_price_krw": "중간 거래가격",
    "median_area_sqm": "중간 전용면적",
    "transaction_count": "거래량",
    "turnover_ratio": "거래회전율",
    "retention_ratio": "거래유지율",
    "mdd_ratio": "최대낙폭(MDD)",
}
_UI_OPERATOR_LABELS = {
    "eq": "같음",
    "ne": "다름",
    "gt": "초과",
    "gte": "이상",
    "lt": "미만",
    "lte": "이하",
}
_UI_METHOD_LABELS = {
    "overall-period eligible population": "전체 기간 유효 모집단",
    "complete-calendar-year-average": "완전한 달력 연도 평균",
    "completed-calendar-month-12-month-window": "완료월 기준 연속 12개월",
    "completed-calendar-month-12-vs-prior-12": "완료월 기준 최근 12개월과 직전 12개월 비교",
    "observed monthly median": "관측 월별 중간값",
}
_UI_UNIT_LABELS = {"KRW": "원", "sqm": "㎡", "count": "건", "ratio": "비율"}
_API_SERVICES = (
    ("kapt_list", "K-APT 단지 목록", "APT_ANALYZER_KAPT_LIST_DAILY_LIMIT", 5_000),
    ("kapt_detail", "K-APT 기본정보", "APT_ANALYZER_KAPT_DETAIL_DAILY_LIMIT", 5_000),
    ("molit_trade", "국토부 아파트 매매", "APT_ANALYZER_MOLIT_TRADE_DAILY_LIMIT", 10_000),
    ("building_hub", "건축HUB 건축물대장", "APT_ANALYZER_BUILDING_HUB_DAILY_LIMIT", 10_000),
)
_ENDPOINT_TO_API_SERVICE = {
    KAPT_LIST_ENDPOINT: "kapt_list",
    KAPT_DETAIL_ENDPOINT: "kapt_detail",
    MOLIT_SALE_ENDPOINT: "molit_trade",
}


class SearchService(Protocol):
    """Injectable search and retrieval boundary."""

    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        """Return distinguishable candidates for a name within one province."""
        ...

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        """Resolve one explicitly selected candidate."""
        ...

    def retrieve(
        self, candidate: ApartmentCandidate, apartment: Apartment, period: AnalysisPeriod
    ) -> tuple[NormalizedTransaction, ...]:
        """Retrieve normalized evidence for the requested period."""
        ...


class InventoryService(Protocol):
    """Explicit exact-area inventory refresh boundary."""

    def collect(
        self,
        candidate: ApartmentCandidate,
        *,
        kapt_total: int | None = None,
        kapt_bands: tuple[tuple[str, int], ...] = (),
    ) -> InventorySummary:
        """Collect one selected apartment's current inventory."""
        ...


class ProvinceListService(SearchService, Protocol):
    """Search boundary that can retrieve a complete province list."""

    def list_region(
        self, sido_code: str, *, use_cache: bool = True
    ) -> tuple[ApartmentCandidate, ...]:
        """Return all candidates for one province."""
        ...


class _PersistentProvinceSearch:
    """Search names from a persisted 24-hour K-APT province snapshot."""

    def __init__(
        self,
        service: ProvinceListService,
        store: SQLiteStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service
        self._cache = SQLiteCandidateCache(store, clock=clock)
        self._clock = clock or (lambda: datetime.now(UTC).replace(microsecond=0))
        self.last_report: CandidateRefreshReport | None = None

    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        """Return matching candidates, refreshing the full province when stale."""
        cutoff = self._clock() - timedelta(hours=24)
        report = self._cache.refresh(
            "K-APT apartment list",
            sido_code,
            lambda: tuple(
                RegionalCandidate(
                    item.source_id,
                    item.name,
                    item.legal_dong_code,
                    item.lot_address,
                    item.road_address,
                )
                for item in self._service.list_region(sido_code, use_cache=False)
            ),
            cutoff=cutoff,
        )
        self.last_report = report
        needle = normalize_name(name)
        return tuple(
            candidate
            for candidate in report.candidates
            if needle and needle in normalize_name(candidate.name)
        )

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        """Delegate explicit identity resolution to the underlying service."""
        return self._service.resolve(selected)

    def retrieve(
        self, candidate: ApartmentCandidate, apartment: Apartment, period: AnalysisPeriod
    ) -> tuple[NormalizedTransaction, ...]:
        """Delegate transaction retrieval to the underlying service."""
        return self._service.retrieve(candidate, apartment, period)


class MissingKeyService:
    """Fail live operations clearly when no server-side key is configured."""

    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        """Explain that live credentials are required."""
        raise RuntimeError("실시간 검색을 사용하려면 DATA_GO_KR_SERVICE_KEY 설정이 필요합니다.")

    def list_region(
        self, sido_code: str, *, use_cache: bool = True
    ) -> tuple[ApartmentCandidate, ...]:
        """Explain that a source refresh requires live credentials."""
        raise RuntimeError(
            "실시간 지역 목록을 갱신하려면 DATA_GO_KR_SERVICE_KEY 설정이 필요합니다."
        )

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        """Explain that live credentials are required."""
        raise RuntimeError("아파트를 선택하려면 DATA_GO_KR_SERVICE_KEY 설정이 필요합니다.")

    def retrieve(
        self, candidate: ApartmentCandidate, apartment: Apartment, period: AnalysisPeriod
    ) -> tuple[NormalizedTransaction, ...]:
        """Explain that live credentials are required."""
        raise RuntimeError("거래 데이터를 갱신하려면 DATA_GO_KR_SERVICE_KEY 설정이 필요합니다.")


@dataclass
class Workspace:
    """Current explicit selection and evidence state."""

    candidate: ApartmentCandidate | None = None
    apartment: Apartment | None = None
    period: AnalysisPeriod | None = None
    status: str = "idle"
    search_sido_code: str = "11"
    selected_sido_code: str | None = None
    search_candidates: tuple[ApartmentCandidate, ...] = ()
    search_cache_notice: str | None = None
    apartments: dict[str, Apartment] = field(default_factory=lambda: {})
    coverage_by_apartment: dict[str, dict[str, str]] = field(default_factory=lambda: {})
    area_groups_by_apartment: dict[str, tuple[dict[str, str], ...]] = field(
        default_factory=lambda: {}
    )


def create_app(
    *,
    search_service: SearchService | None = None,
    store: SQLiteStore | None = None,
    search_clock: Callable[[], datetime] | None = None,
    analysis_today: Callable[[], date] | None = None,
    inventory_service: InventoryService | None = None,
) -> FastAPI:
    """Create the local app with deterministic dependency injection."""
    app = FastAPI(title="apt-analyzer local web")
    static_directory = Path(__file__).parent / "static"
    if static_directory.exists():
        app.mount("/static", StaticFiles(directory=static_directory), name="static")
    app.state.asset_version = _static_asset_version(static_directory)
    templates = Jinja2Templates(directory=_TEMPLATE_DIRECTORY)
    workspace = Workspace()
    app.state.workspace = workspace
    owned_store = store or SQLiteStore(
        os.environ.get("APT_ANALYZER_DB", ":memory:"), check_same_thread=False
    )
    store_owned = store is None
    limits = _daily_api_limits()
    app.state.usage_store = owned_store
    app.state.usage_limits = limits
    service = search_service or _default_service(owned_store)
    inventory = inventory_service or _default_inventory_service(owned_store)
    today = analysis_today or date.today
    if search_service is None or hasattr(service, "list_region"):
        service = _PersistentProvinceSearch(
            cast(ProvinceListService, service), owned_store, clock=search_clock
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """Close only the SQLite store owned by this app after serving."""
        yield
        if store_owned:
            owned_store.close()

    app.router.lifespan_context = lifespan

    @app.get("/", response_class=HTMLResponse)
    def root(request: Request) -> HTMLResponse:
        return _page(request, templates, workspace, ())

    app.add_api_route("/health", lambda: {"status": "ok"})

    @app.post("/search", response_class=HTMLResponse)
    def search(
        request: Request, name: str = Form(...), sido_code: str = Form("11")
    ) -> HTMLResponse:
        if sido_code not in _PROVINCE_CODES:
            workspace.status = "failed"
            return _page(request, templates, workspace, (), {"error": "시·도를 선택해 주세요."})
        workspace.search_sido_code = sido_code
        try:
            candidates = service.search(name, sido_code=sido_code)
        except Exception as error:  # noqa: BLE001 - source boundary is user-visible
            workspace.status = "failed"
            return _page(request, templates, workspace, (), {"error": str(error)})
        workspace.status = "searching" if candidates else "not_found"
        workspace.search_candidates = candidates
        report = getattr(service, "last_report", None)
        workspace.search_cache_notice = _search_cache_notice(report)
        if report is not None and report.state is CandidateRefreshState.EXTERNAL_FAILURE:
            workspace.status = "stale" if candidates else "failed"
        return _page(request, templates, workspace, candidates)

    @app.post("/select", response_class=HTMLResponse)
    def select(
        request: Request,
        source_id: str = Form(...),
    ) -> HTMLResponse:
        selected = next(
            (
                candidate
                for candidate in workspace.search_candidates
                if candidate.source_id == source_id
            ),
            None,
        )
        if selected is None:
            workspace.status = "failed"
            return _page(
                request,
                templates,
                workspace,
                workspace.search_candidates,
                {"error": "최근 검색 결과에서 선택할 수 없는 아파트입니다."},
            )
        try:
            enriched, resolution = service.resolve(selected)
        except Exception as error:  # noqa: BLE001 - source boundary is user-visible
            workspace.status = "failed"
            return _page(request, templates, workspace, (), {"error": str(error)})
        if resolution.apartment is None:
            workspace.status = str(resolution.status)
        else:
            workspace.candidate, workspace.apartment, workspace.status = (
                enriched,
                resolution.apartment,
                "selected",
            )
            workspace.selected_sido_code = workspace.search_sido_code
            owned_store.save_apartment(resolution.apartment)
            owned_store.save_profile_and_household(
                resolution.apartment.internal_id,
                enriched.profile,
                enriched.household_count,
                household_source=enriched.household_source,
                profile_source="K-APT apartment basic information",
            )
            workspace.apartments[resolution.apartment.internal_id] = resolution.apartment
            _hydrate_area_groups(workspace, owned_store, resolution.apartment.internal_id)
        return _page(request, templates, workspace, (enriched,))

    @app.post("/interests/save", response_class=HTMLResponse)
    def save_interest(request: Request) -> HTMLResponse:
        if (
            workspace.apartment is None
            or workspace.candidate is None
            or workspace.selected_sido_code is None
        ):
            workspace.status = "failed"
            return _page(
                request,
                templates,
                workspace,
                (),
                {"error": "먼저 명시적으로 단지를 선택해 주세요."},
            )
        try:
            owned_store.save_interest(
                workspace.candidate,
                workspace.apartment,
                region_code=workspace.selected_sido_code,
            )
        except ValueError as error:
            workspace.status = "failed"
            return _page(request, templates, workspace, (), {"error": str(error)})
        workspace.status = "selected"
        return _page(request, templates, workspace, ())

    @app.post("/interests/select", response_class=HTMLResponse)
    def select_interest(request: Request, apartment_id: str = Form(...)) -> HTMLResponse:
        interest = owned_store.get_interest(apartment_id)
        if interest is None:
            workspace.status = "failed"
            return _page(
                request, templates, workspace, (), {"error": "저장된 관심 단지를 찾을 수 없습니다."}
            )
        workspace.candidate = interest.candidate
        workspace.apartment = interest.apartment
        workspace.search_sido_code = interest.region_code
        workspace.selected_sido_code = interest.region_code
        workspace.status = "selected"
        _hydrate_area_groups(workspace, owned_store, interest.apartment.internal_id)
        return _page(request, templates, workspace, ())

    @app.post("/household/refresh", response_class=HTMLResponse)
    def refresh_household(request: Request) -> HTMLResponse:  # pyright: ignore[reportUnusedFunction]
        """Explicitly refresh K-APT household evidence for the current subject."""
        if workspace.candidate is None or workspace.apartment is None:
            return _page(request, templates, workspace, (), {"error": "먼저 단지를 선택해 주세요."})
        try:
            enriched, resolution = service.resolve(workspace.candidate)
            if (
                resolution.apartment is None
                or resolution.apartment.internal_id != workspace.apartment.internal_id
            ):
                raise ValueError("단지 식별 근거가 변경되어 세대수를 저장하지 않았습니다.")
            if enriched.household_count is None or enriched.household_source is None:
                raise ValueError("K-APT 세대수 근거가 없습니다.")
            owned_store.save_profile_and_household(
                workspace.apartment.internal_id,
                enriched.profile,
                enriched.household_count,
                household_source=enriched.household_source,
                profile_source="K-APT apartment basic information",
            )
            workspace.candidate = enriched
            workspace.status = "selected"
            persisted_inventory = owned_store.load_inventory(workspace.apartment.internal_id)
            if persisted_inventory is None:
                persisted_inventory = owned_store.load_inventory_attempt(
                    workspace.apartment.internal_id
                )
            if persisted_inventory is not None:
                reconciled = reconcile_inventory(
                    persisted_inventory.summary,
                    kapt_total=enriched.household_count,
                    kapt_bands=tuple(
                        (band.label, band.count)
                        for band in (enriched.profile.area_bands if enriched.profile else ())
                    ),
                )
                owned_store.save_inventory(
                    workspace.apartment.internal_id,
                    reconciled,
                    source=persisted_inventory.source,
                )
        except Exception as error:  # noqa: BLE001 - explicit source action is user-visible
            workspace.status = "failed"
            return _page(request, templates, workspace, (), {"error": str(error)})
        return _page(request, templates, workspace, ())

    @app.post("/inventory/refresh", response_class=HTMLResponse)
    def refresh_inventory(request: Request) -> HTMLResponse:
        """Explicitly refresh the selected complex's exact-area inventory."""
        if workspace.candidate is None or workspace.apartment is None:
            return _page(request, templates, workspace, (), {"error": "먼저 단지를 선택해 주세요."})
        candidate = workspace.candidate
        apartment = workspace.apartment
        household = owned_store.load_household_evidence(apartment.internal_id)
        profile = owned_store.load_profile(apartment.internal_id)
        kapt_total = None if household is None else household.count
        bands = (
            ()
            if profile is None
            else tuple((band.label, band.count) for band in profile.profile.area_bands)
        )
        try:
            result = inventory.collect(candidate, kapt_total=kapt_total, kapt_bands=bands)
            if (
                workspace.apartment.internal_id != apartment.internal_id
                or workspace.candidate.source_id != candidate.source_id
            ):
                return _page(
                    request,
                    templates,
                    workspace,
                    (),
                    {"error": "선택한 단지가 변경되어 수집 결과를 저장하지 않았습니다."},
                )
            owned_store.save_inventory(apartment.internal_id, result, source=result.source)
        except Exception:  # noqa: BLE001 - explicit source boundary
            result = InventorySummary(
                InventoryState.UNAVAILABLE,
                (),
                (),
                None,
                "건축물대장 수집을 완료하지 못했습니다.",
                datetime.now(UTC),
            )
            owned_store.save_inventory(apartment.internal_id, result, source="Building HUB")
            return _page(
                request,
                templates,
                workspace,
                (),
                {"error": "건축물대장 수집을 완료하지 못했습니다."},
            )
        return _page(request, templates, workspace, (), {"inventory_refresh": result.state.value})

    @app.post("/interests/remove", response_class=HTMLResponse)
    def remove_interest(request: Request, apartment_id: str = Form(...)) -> HTMLResponse:
        owned_store.remove_interest(apartment_id)
        return _page(request, templates, workspace, ())

    @app.post("/update", response_class=HTMLResponse)
    def update(
        request: Request,
        start: str = Form(...),
        end: str = Form(...),
        refresh_before: str = Form(""),
    ) -> HTMLResponse:
        if workspace.apartment is None or workspace.candidate is None:
            workspace.status = "selection_required"
            return _page(request, templates, workspace, ())
        period = AnalysisPeriod(date.fromisoformat(start), date.fromisoformat(end))
        workspace.period = period
        candidate = workspace.candidate
        apartment = workspace.apartment
        assert candidate is not None and apartment is not None

        def fetch_month(month: str) -> tuple[NormalizedTransaction, ...]:
            year, month_number = int(month[:4]), int(month[4:])
            month_period = AnalysisPeriod(
                date(year, month_number, 1),
                date(year, month_number, calendar.monthrange(year, month_number)[1]),
            )
            return service.retrieve(candidate, apartment, month_period)

        prior_coverage = owned_store.coverage(
            apartment.internal_id, "MOLIT apartment sale transactions"
        )
        cutoff = (
            datetime.fromisoformat(refresh_before).replace(tzinfo=UTC) if refresh_before else None
        )
        report = owned_store.update_incremental(
            apartment,
            period,
            fetch_month,
            source_name="MOLIT apartment sale transactions",
            refresh_before=cutoff,
        )
        workspace.status = "updated"
        report_data = asdict(report)
        states = {
            item.month: (
                "valid_empty"
                if item.status == "fetched" and item.inserted + item.duplicates == 0
                else "fresh"
            )
            if item.status in {"fetched", "skipped"}
            else ("stale" if item.month in prior_coverage else "failed")
            for item in report.updates
        }
        workspace.coverage_by_apartment[apartment.internal_id] = states
        evidence = owned_store.load_transactions(apartment.internal_id, period)
        _hydrate_area_groups(workspace, owned_store, apartment.internal_id)
        return _page(
            request,
            templates,
            workspace,
            (),
            {
                "update": report_data,
                "availability": states,
                "available_area_groups": [
                    {"key": group.key, "label": group.label}
                    for group in discover_area_groups(evidence)
                ],
            },
        )

    @app.post("/analysis", response_class=HTMLResponse, response_model=None)
    def analysis(
        request: Request,
        start: str = Form(...),
        end: str = Form(...),
        area_group: str = Form("all"),
        include_cancelled: bool = Form(False),
        transaction_types: list[str] = Form(["brokered", "direct", "unknown"]),  # noqa: B008
        turnover_start: str = Form(""),
        turnover_end: str = Form(""),
        baseline_start: str = Form(""),
        baseline_end: str = Form(""),
        comparison_start: str = Form(""),
        comparison_end: str = Form(""),
        mdd_start: str = Form(""),
        mdd_end: str = Form(""),
        household_count: int | None = Form(None),
        household_scope: str = Form("complex"),
        household_source: str = Form(""),
    ) -> HTMLResponse | JSONResponse:
        if workspace.apartment is None:
            workspace.status = "selection_required"
            return _page(request, templates, workspace, ())
        period = AnalysisPeriod(date.fromisoformat(start), date.fromisoformat(end))
        analysis_date = today()
        rolling_periods = derive_completed_month_periods(period, today=analysis_date)
        transactions = owned_store.load_transactions(workspace.apartment.internal_id, period)
        persisted_coverage = owned_store.coverage_states(
            workspace.apartment.internal_id, "MOLIT apartment sale transactions"
        )
        requested_months = months(period)
        availability = {
            month: (
                "fresh"
                if persisted_coverage.get(month) == "complete"
                else persisted_coverage.get(month, "missing")
            )
            for month in requested_months
        }
        availability.update(
            {
                month: status
                for month, status in workspace.coverage_by_apartment.get(
                    workspace.apartment.internal_id, {}
                ).items()
                if month in availability
            }
        )
        period_status = {month: "complete" for month in requested_months}
        for month in requested_months:
            year, month_number = int(month[:4]), int(month[4:])
            if (
                date(year, month_number, calendar.monthrange(year, month_number)[1])
                >= analysis_date
            ):
                period_status[month] = "incomplete"
        group = (
            next(
                (item for item in discover_area_groups(transactions) if item.key == area_group),
                None,
            )
            if area_group != "all"
            else None
        )
        if area_group != "all" and group is None:
            return JSONResponse(
                {"error": "선택한 면적 그룹을 사용할 수 없습니다."}, status_code=400
            )
        context = AnalysisContext(
            workspace.apartment,
            period,
            AreaSelection.all() if group is None else AreaSelection.for_group(group),
            TransactionInclusionPolicy(
                include_cancelled,
                frozenset(TransactionType(item) for item in transaction_types),
            ),
        )
        for label, first, second in (
            ("거래회전율", turnover_start, turnover_end),
            ("기준 기간", baseline_start, baseline_end),
            ("비교 기간", comparison_start, comparison_end),
            ("MDD", mdd_start, mdd_end),
        ):
            if bool(first) != bool(second):
                return _page(
                    request,
                    templates,
                    workspace,
                    (),
                    {"error": f"{label} 시작일과 종료일을 함께 입력해 주세요."},
                )
        complete_coverage = all(
            availability[item] in {"fresh", "skipped", "fetched", "valid_empty"}
            for item in requested_months
        )
        default_turnover_period = rolling_periods.turnover
        default_baseline_period = rolling_periods.baseline
        default_comparison_period = rolling_periods.turnover
        persisted_household = owned_store.load_household_evidence(workspace.apartment.internal_id)
        effective_household_count = household_count
        effective_household_scope = household_scope
        effective_household_source = household_source or None
        if (
            effective_household_count is None
            and not household_source
            and household_scope == "complex"
            and group is None
            and persisted_household is not None
        ):
            effective_household_count = persisted_household.count
            effective_household_scope = persisted_household.scope
            effective_household_source = persisted_household.source
        if group is not None and household_count is None:
            effective_household_count = None
            effective_household_source = None
        result = analyze(
            transactions,
            context,
            turnover_period=(
                _form_period(turnover_start, turnover_end, period)
                if turnover_start and turnover_end
                else default_turnover_period
            ),
            household=HouseholdEvidence(
                effective_household_count, effective_household_scope, effective_household_source
            ),
            baseline_period=(
                _form_period(baseline_start, baseline_end, period)
                if baseline_start and baseline_end
                else default_baseline_period
            ),
            comparison_period=(
                _form_period(comparison_start, comparison_end, period)
                if comparison_start and comparison_end
                else default_comparison_period
            ),
            mdd_period=_form_period(mdd_start, mdd_end, period),
            data_status=DataCoverageStatus.COMPLETE
            if transactions
            else DataCoverageStatus.VALID_EMPTY,
            rolling_today=analysis_date,
            monthly_coverage=availability,
            rolling_defaults=True,
        )
        workspace.status = "unavailable" if not complete_coverage else "analyzed"
        app.state.last_result = result_to_dict(result)
        app.state.last_result["complex_profile"] = _complex_profile_dict(
            workspace.candidate,
            workspace.apartment,
            owned_store.load_profile(workspace.apartment.internal_id),
            effective_household_count,
            effective_household_scope,
            effective_household_source,
            persisted_household,
            result.population.eligible,
            analysis_date,
            owned_store.load_inventory(workspace.apartment.internal_id),
            owned_store.load_inventory_attempt(workspace.apartment.internal_id),
        )
        app.state.last_result["data_status"] = (
            "coverage-limited"
            if not complete_coverage
            else app.state.last_result.get("data_status", "complete")
        )
        app.state.last_result["availability"] = availability
        app.state.last_result["coverage"] = dict(availability)
        app.state.last_result["observations"] = {
            month: "observed"
            if any(item.month == f"{month[:4]}-{month[4:]}" for item in result.monthly_prices)
            else "no_observation"
            for month in requested_months
        }
        app.state.last_result["metric_display"] = {
            "turnover": {"unit": "%", "meaning": "기간 내 유효 거래량 ÷ 세대수"},
            "retention": {"unit": "%", "meaning": "비교 기간 거래량 ÷ 기준 기간 거래량"},
            "mdd": {"unit": "%", "meaning": "가격 시계열 최대낙폭"},
        }
        app.state.last_result["monthly_series"] = _monthly_series(result, requested_months)
        for item in app.state.last_result["monthly_series"]:
            key = str(item["period"]).replace("-", "")
            item["coverage_status"] = availability[key]
            item["period_status"] = period_status[key]
            if item["value"] is None and availability[key] not in {
                "complete",
                "fresh",
                "fetched",
                "skipped",
                "valid_empty",
            }:
                item["transaction_count"] = None
        app.state.last_result["trend_series"] = [
            {
                "period": f"{item.month[:4]}-{item.month[4:]}",
                "value": None
                if item.trailing_three_month_mean is None
                else str(item.trailing_three_month_mean),
                "status": item.status.split(":", 1)[-1],
                "coverage_status": item.status.split(":", 1)[0],
                "period_status": item.status.split(":", 1)[-1],
            }
            for item in monthly_transaction_trend(
                result.population, period, availability, today=analysis_date
            )
        ]
        eligible_by_month = {
            month: sum(
                1
                for item in result.population.eligible
                if item.contract_date.strftime("%Y%m") == month
            )
            for month in requested_months
        }
        app.state.last_result["volume_series"] = [
            {
                "period": f"{month[:4]}-{month[4:]}",
                "value": (
                    eligible_by_month[month]
                    if eligible_by_month[month] > 0
                    or availability[month]
                    in {"complete", "fresh", "fetched", "skipped", "valid_empty"}
                    else None
                ),
                "status": availability[month],
                "coverage_status": availability[month],
                "period_status": period_status[month],
            }
            for month in requested_months
        ]
        app.state.last_result["ui_context"] = {
            "apartment_id": workspace.apartment.internal_id,
            "apartment_name": workspace.apartment.display_name,
            "overall_period": _period_dict(period),
            "area": "all" if group is None else group.label,
            "area_group_key": area_group,
            "inclusion_policy": {
                "include_cancelled": include_cancelled,
                "transaction_types": transaction_types,
            },
            "household": {
                "count": effective_household_count,
                "scope": effective_household_scope,
                "source": effective_household_source,
            },
            "metric_periods": {
                name: value
                for name, value in (
                    (
                        "turnover",
                        _metric_period_value(
                            turnover_start, turnover_end, rolling_periods.turnover, period
                        ),
                    ),
                    (
                        "baseline",
                        _metric_period_value(
                            baseline_start, baseline_end, rolling_periods.baseline, period
                        ),
                    ),
                    (
                        "comparison",
                        _metric_period_value(
                            comparison_start, comparison_end, rolling_periods.turnover, period
                        ),
                    ),
                    ("mdd", _period_dict(_form_period(mdd_start, mdd_end, period))),
                )
            },
            "metric_period_sources": {
                "turnover": "override" if turnover_start or turnover_end else "automatic",
                "retention": "override"
                if any((baseline_start, baseline_end, comparison_start, comparison_end))
                else "automatic",
                "mdd": "override" if mdd_start or mdd_end else "overall",
            },
            "rolling_anchor": rolling_periods.anchor,
            "metric_methods": {
                "turnover": (
                    result.turnover.annualization_method
                    if result.turnover is not None
                    else (
                        ANNUALIZATION_METHOD
                        if turnover_start or turnover_end
                        else ROLLING_TURNOVER_METHOD
                    )
                ),
                "retention": (
                    result.retention.annualization_method
                    if result.retention is not None
                    else (
                        ANNUALIZATION_METHOD
                        if any(
                            (
                                baseline_start,
                                baseline_end,
                                comparison_start,
                                comparison_end,
                            )
                        )
                        else ROLLING_RETENTION_METHOD
                    )
                ),
                "mdd": PRICE_SERIES_METHOD,
            },
            "metric_period_overrides": {
                field: value
                for field, value in (
                    ("turnover_start", turnover_start),
                    ("turnover_end", turnover_end),
                    ("baseline_start", baseline_start),
                    ("baseline_end", baseline_end),
                    ("comparison_start", comparison_start),
                    ("comparison_end", comparison_end),
                    ("mdd_start", mdd_start),
                    ("mdd_end", mdd_end),
                )
                if value
            },
        }
        return _page(request, templates, workspace, (), app.state.last_result)

    @app.post("/analysis/preview")
    def _analysis_preview(  # pyright: ignore[reportUnusedFunction]
        start: str = Form(...), end: str = Form(...)
    ) -> JSONResponse:
        """Return a non-mutating preview from the official persisted analysis context."""
        current = getattr(app.state, "last_result", None)
        try:
            selected_start = date.fromisoformat(start)
            selected_end = date.fromisoformat(end)
            selected_period = AnalysisPeriod(selected_start, selected_end)
        except ValueError:
            return JSONResponse({"error": "선택 기간을 확인해 주세요."}, status_code=422)
        if (
            selected_start.day != 1
            or selected_end.day != calendar.monthrange(selected_end.year, selected_end.month)[1]
        ):
            return JSONResponse(
                {"error": "월의 첫날부터 마지막 날까지 선택해 주세요."}, status_code=422
            )
        if not isinstance(current, dict):
            return JSONResponse({"error": "먼저 분석을 실행해 주세요."}, status_code=409)
        current = cast(dict[str, object], current)
        if workspace.apartment is None:
            return JSONResponse({"error": "먼저 분석을 실행해 주세요."}, status_code=409)
        ui_context = cast(dict[str, object], current.get("ui_context", {}))
        overall_value = cast(dict[str, str], ui_context.get("overall_period", {}))
        try:
            overall = AnalysisPeriod(
                date.fromisoformat(overall_value["start"]),
                date.fromisoformat(overall_value["end"]),
            )
        except KeyError, ValueError:
            return JSONResponse({"error": "먼저 분석을 실행해 주세요."}, status_code=409)
        if not (overall.start <= selected_start and selected_end <= overall.end):
            return JSONResponse({"error": "전체 분석 기간 안에서 선택해 주세요."}, status_code=422)
        transactions = owned_store.load_transactions(workspace.apartment.internal_id, overall)
        area_group_key = str(ui_context.get("area_group_key", "all"))
        area_group = (
            next(
                (item for item in discover_area_groups(transactions) if item.key == area_group_key),
                None,
            )
            if area_group_key != "all"
            else None
        )
        if area_group_key != "all" and area_group is None:
            return JSONResponse(
                {"error": "현재 분석의 면적 그룹 근거를 찾을 수 없습니다."}, status_code=409
            )
        policy = cast(dict[str, object], ui_context.get("inclusion_policy", {}))
        types = frozenset(
            TransactionType(value) for value in cast(list[str], policy.get("transaction_types", []))
        )
        context = AnalysisContext(
            workspace.apartment,
            overall,
            AreaSelection.all() if area_group is None else AreaSelection.for_group(area_group),
            TransactionInclusionPolicy(bool(policy.get("include_cancelled", False)), types),
        )
        coverage = {
            str(key): str(value)
            for key, value in cast(dict[object, object], current.get("coverage", {})).items()
        }
        population = build_population(transactions, context)
        household_value = cast(dict[str, object], ui_context.get("household", {}))
        household = HouseholdEvidence(
            cast(int | None, household_value.get("count")),
            str(household_value.get("scope", "complex")),
            cast(str | None, household_value.get("source")),
        )
        selected_month_count = len(months(selected_period))
        turnover_result = preview_turnover(
            population, selected_period, household, coverage, today()
        )
        turnover_method = turnover_result.annualization_method
        if selected_month_count == 24:
            split_index = selected_start.year * 12 + selected_start.month - 1 + 11
            split_year, split_month_index = divmod(split_index, 12)
            split_month = split_month_index + 1
            baseline_start = selected_start
            baseline_end = date(
                split_year, split_month, calendar.monthrange(split_year, split_month)[1]
            )
            comparison_start = baseline_end + timedelta(days=1)
            comparison_period = AnalysisPeriod(comparison_start, selected_end)
        else:
            baseline_end = selected_start - timedelta(days=1)
            baseline_start = date(selected_start.year - 1, selected_start.month, selected_start.day)
            comparison_period = selected_period
        retention_result = rolling_retention(
            population,
            AnalysisPeriod(baseline_start, baseline_end),
            comparison_period,
            coverage,
            today(),
        )
        mdd_result = maximum_drawdown(population, selected_period)
        selected_count = sum(
            1 for item in population.eligible if selected_period.includes(item.contract_date)
        )

        def metric_payload(
            value: Decimal | None,
            evidence: str | None,
            unavailable_reason: str | None,
            method: str = "",
        ) -> dict[str, str | None]:
            return {
                "status": "available" if value is not None else "unavailable",
                "value": None if value is None else str(value),
                "display": "계산 불가" if value is None else _format_percentage(value),
                "unit": "%",
                "evidence": evidence if value is not None else None,
                "method": method,
                "reason": None
                if unavailable_reason is None
                else _UI_LABELS.get(unavailable_reason, unavailable_reason),
            }

        turnover_reason = (
            None if turnover_result.unavailable is None else turnover_result.unavailable.reason
        )
        turnover_evidence = None
        if turnover_result.value is not None:
            if turnover_method == "preview-calendar-month-average":
                turnover_evidence = (
                    f"{turnover_result.eligible_count}건 ÷ "
                    f"{selected_month_count // 12}년 / {household.count}세대"
                )
            elif turnover_method == "preview-cumulative-month-turnover":
                turnover_evidence = (
                    f"{turnover_result.eligible_count}건 누적 / {household.count}세대"
                )
            else:
                turnover_evidence = f"{turnover_result.eligible_count}건 / {household.count}세대"
        retention_reason = (
            None if retention_result.unavailable is None else retention_result.unavailable.reason
        )
        if selected_month_count not in {12, 24}:
            retention_reason = "거래유지율은 선택 기간과 직전 기간이 각각 12개월이어야 합니다"
        mdd_reason = None if mdd_result.unavailable is None else mdd_result.unavailable.reason
        return JSONResponse(
            {
                "selection": {
                    "start": start,
                    "end": end,
                    "label": (f"{selected_start:%Y.%m} ~ {selected_end:%Y.%m}"),
                    "months": len(months(selected_period)),
                },
                "volume": {
                    "value": selected_count,
                    "display": f"{selected_count}건",
                    "unit": "건",
                    "evidence": f"선택 기간 유효 거래 {selected_count}건",
                },
                "turnover": metric_payload(
                    turnover_result.value,
                    turnover_evidence,
                    turnover_reason,
                    turnover_method,
                ),
                "retention": metric_payload(
                    retention_result.value,
                    (
                        f"{retention_result.comparison_period.start:%Y.%m}~"
                        f"{retention_result.comparison_period.end:%Y.%m} "
                        f"{retention_result.comparison_count}건 / "
                        f"{retention_result.baseline_period.start:%Y.%m}~"
                        f"{retention_result.baseline_period.end:%Y.%m} "
                        f"{retention_result.baseline_count}건 (비교 / 기준)"
                    ),
                    retention_reason,
                    ROLLING_RETENTION_METHOD,
                ),
                "mdd": metric_payload(
                    mdd_result.value,
                    (
                        f"{_format_krw(mdd_result.peak.median_krw)} → "
                        f"{_format_krw(mdd_result.trough.median_krw)} "
                        f"({mdd_result.peak.month} → {mdd_result.trough.month})"
                    )
                    if mdd_result.peak is not None and mdd_result.trough is not None
                    else None,
                    mdd_reason,
                    "observed monthly median",
                ),
            }
        )

    @app.get("/export")
    def export(kind: str = "analysis") -> JSONResponse:
        key = (
            "last_comparison"
            if kind == "comparison"
            else "last_screening"
            if kind == "screening"
            else "last_result"
        )
        return JSONResponse(getattr(app.state, key, {"status": "analysis_required"}))

    @app.post("/screen", response_class=HTMLResponse)
    def screening(
        request: Request,
        regions: str = Form(...),
        candidate_source_ids: str = Form(""),
        start: str = Form(""),
        end: str = Form(""),
        screen_start: str | None = Form(None),
        screen_end: str | None = Form(None),
        rules: str = Form(""),
        rule_metric: str = Form("transaction_count"),
        rule_operator: str = Form("gte"),
        rule_value: str = Form("1"),
        rule_unit: str = Form(""),
        rule_method: str = Form(""),
        area_group: str = Form("all"),
        include_cancelled: bool = Form(False),
        transaction_types: list[str] = Form(["brokered", "direct", "unknown"]),  # noqa: B008
        turnover_start: str = Form(""),
        turnover_end: str = Form(""),
        baseline_start: str = Form(""),
        baseline_end: str = Form(""),
        comparison_start: str = Form(""),
        comparison_end: str = Form(""),
        mdd_start: str = Form(""),
        mdd_end: str = Form(""),
        household_json: str = Form(""),
    ) -> HTMLResponse:
        selected_regions = tuple(
            dict.fromkeys(item.strip() for item in regions.split(",") if item.strip())
        )
        if not selected_regions:
            return _page(
                request, templates, workspace, (), {"error": "지역을 하나 이상 명시해 주세요."}
            )
        overall_start = start or screen_start or ""
        overall_end = end or screen_end or ""
        if not overall_start or not overall_end:
            return _page(
                request, templates, workspace, (), {"error": "선별 기준 기간을 입력해 주세요."}
            )
        try:
            overall = AnalysisPeriod(
                date.fromisoformat(overall_start), date.fromisoformat(overall_end)
            )
            config = CommonAnalysisConfig(
                overall,
                _form_period(turnover_start, turnover_end, overall),
                _form_period(baseline_start, baseline_end, overall),
                _form_period(comparison_start, comparison_end, overall),
                _form_period(mdd_start, mdd_end, overall),
                TransactionInclusionPolicy(
                    include_cancelled,
                    frozenset(TransactionType(item) for item in transaction_types),
                ),
                area_group_key=None if area_group == "all" else area_group,
            )
            if not rules.strip():
                rule_metric = {
                    "turnover": "turnover_ratio",
                    "retention": "retention_ratio",
                    "mdd": "mdd_ratio",
                }.get(rule_metric, rule_metric)
                if rule_unit == "count" and rule_metric != "transaction_count":
                    rule_unit = ""
                rules = json.dumps(
                    [
                        {
                            "metric": rule_metric,
                            "operator": rule_operator,
                            "value": rule_value,
                            "method": rule_method or SUPPORTED_METHODS[rule_metric],
                            "unit": rule_unit or SUPPORTED_UNITS[rule_metric],
                        }
                    ]
                )
            rule_payload = json.loads(rules)
            parsed_rules = tuple(
                CandidateScreenRule(
                    item["metric"],
                    item["operator"],
                    Decimal(str(item["value"])),
                    item["unit"],
                    item.get("method", SUPPORTED_METHODS[item["metric"]]),
                )
                for item in rule_payload
            )
            candidate_ids = frozenset(
                item.strip() for item in candidate_source_ids.split(",") if item.strip()
            )
            cache = SQLiteCandidateCache(owned_store)
            source_name = "K-APT apartment list"
            coverage_reports = {
                region: cache.read(source_name, region) for region in selected_regions
            }
            if any(
                report.state not in {CandidateRefreshState.FRESH, CandidateRefreshState.VALID_EMPTY}
                for report in coverage_reports.values()
            ):
                payload: dict[str, object] = {
                    "status": "unavailable",
                    "config": json_value(config),
                    "rules": json_value(parsed_rules),
                    "region_coverage": json_value(coverage_reports),
                    "results": [],
                    "households": {},
                    "context": {
                        "area_group": config.area_group_key or "all",
                        "inclusion_policy": json_value(config.inclusion_policy),
                        "metric_periods": {
                            "turnover": _period_dict(config.turnover_period),
                            "baseline": _period_dict(config.baseline_period),
                            "comparison": _period_dict(config.comparison_period),
                            "mdd": _period_dict(config.mdd_period),
                        },
                    },
                    "disclaimer": "과거 데이터 기반 선별 결과이며 투자 추천이 아닙니다.",
                }
            else:
                resolved = owned_store.load_resolved_candidates(
                    source_name, selected_regions, candidate_ids
                )
                if candidate_ids - {candidate.source_id for _, candidate, _ in resolved}:
                    raise ValueError("요청한 후보 ID가 선택한 지역에서 확인되지 않았습니다.")
                apartments = tuple(apartment for _, _, apartment in resolved)
                transactions = {
                    apartment.internal_id: owned_store.load_transactions(
                        apartment.internal_id, overall
                    )
                    for apartment in apartments
                }
                coverage = {
                    apartment.internal_id: owned_store.coverage_states(
                        apartment.internal_id, "MOLIT apartment sale transactions"
                    )
                    for apartment in apartments
                }
                household_payload: object = json.loads(household_json) if household_json else {}
                if not isinstance(household_payload, dict):
                    raise ValueError("세대수 정보는 아파트 ID를 키로 하는 JSON 객체여야 합니다.")
                households: dict[str, HouseholdEvidence] = {}
                apartment_ids = {item.internal_id for item in apartments}
                for apartment_id, raw_value in cast(
                    dict[object, object], household_payload
                ).items():
                    if not isinstance(apartment_id, str) or not isinstance(raw_value, dict):
                        raise ValueError("각 세대수 항목은 아파트 ID를 키로 하는 객체여야 합니다.")
                    value = cast(dict[str, object], raw_value)
                    if apartment_id not in apartment_ids:
                        continue
                    scope = value.get("scope")
                    if not isinstance(scope, str):
                        raise ValueError("각 세대수 항목에 범위를 입력해 주세요.")
                    count = value.get("count")
                    if count is not None and not isinstance(count, int):
                        raise ValueError("세대수는 정수여야 합니다.")
                    source = value.get("source")
                    if source is not None and not isinstance(source, str):
                        raise ValueError("세대수 출처는 문자여야 합니다.")
                    households[apartment_id] = HouseholdEvidence(count, scope, source)
                results = screen_candidates(
                    apartments,
                    transactions,
                    config,
                    parsed_rules,
                    coverage=coverage,
                    households=households,
                )
                serialized_results = json_value(results)
                names = {apartment.internal_id: apartment.display_name for apartment in apartments}
                for item in serialized_results:
                    item["candidate_name"] = names[item["candidate_id"]]
                    item["context"]["overall_period"] = _period_dict(overall)
                payload = {
                    "status": "complete",
                    "regions": selected_regions,
                    "config": json_value(config),
                    "rules": json_value(parsed_rules),
                    "region_coverage": json_value(coverage_reports),
                    "results": serialized_results,
                    "households": json_value(households),
                    "context": {
                        "area_group": config.area_group_key or "all",
                        "inclusion_policy": json_value(config.inclusion_policy),
                        "metric_periods": {
                            "turnover": _period_dict(config.turnover_period),
                            "baseline": _period_dict(config.baseline_period),
                            "comparison": _period_dict(config.comparison_period),
                            "mdd": _period_dict(config.mdd_period),
                        },
                    },
                    "disclaimer": "과거 데이터 기반 선별 결과이며 투자 추천이 아닙니다.",
                }
            app.state.last_screening = payload
            workspace.status = (
                "screened" if payload["status"] == "complete" else "screening-unavailable"
            )
            return _page(request, templates, workspace, (), payload)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            workspace.status = "screening-failed"
            return _page(request, templates, workspace, (), {"error": str(error)})

    @app.post("/comparison", response_class=HTMLResponse, response_model=None)
    def comparison(
        request: Request,
        apartment_ids: list[str] = Form(...),  # noqa: B008
        start: str = Form(...),
        end: str = Form(...),
        turnover_start: str = Form(""),
        turnover_end: str = Form(""),
        baseline_start: str = Form(""),
        baseline_end: str = Form(""),
        comparison_start: str = Form(""),
        comparison_end: str = Form(""),
        mdd_start: str = Form(""),
        mdd_end: str = Form(""),
        area_group: str = Form("all"),
        include_cancelled: bool = Form(False),
        transaction_types: list[str] = Form(["brokered", "direct", "unknown"]),  # noqa: B008
    ) -> HTMLResponse | JSONResponse:
        ids = tuple(
            item.strip() for value in apartment_ids for item in value.split(",") if item.strip()
        )
        apartments = tuple(
            workspace.apartments[item] for item in ids if item in workspace.apartments
        )
        if len(apartments) < 2:
            return JSONResponse(
                {"error": "비교하려면 확인된 아파트를 두 곳 이상 선택해야 합니다."}, status_code=400
            )
        overall = AnalysisPeriod(date.fromisoformat(start), date.fromisoformat(end))
        config = CommonAnalysisConfig(
            overall,
            _form_period(turnover_start, turnover_end, overall),
            _form_period(baseline_start, baseline_end, overall),
            _form_period(comparison_start, comparison_end, overall),
            _form_period(mdd_start, mdd_end, overall),
            TransactionInclusionPolicy(
                include_cancelled, frozenset(TransactionType(item) for item in transaction_types)
            ),
            area_group_key=None if area_group == "all" else area_group,
        )
        transactions = {
            item.internal_id: owned_store.load_transactions(item.internal_id, overall)
            for item in apartments
        }
        requested_months = months(overall)
        availability_by_subject: dict[str, dict[str, str]] = {}
        for apartment in apartments:
            persisted = owned_store.coverage(
                apartment.internal_id, "MOLIT apartment sale transactions"
            )
            latest = workspace.coverage_by_apartment.get(apartment.internal_id, {})
            availability_by_subject[apartment.internal_id] = {
                month: latest.get(month, "fresh" if month in persisted else "missing")
                for month in requested_months
            }
        limited = {
            subject_id: statuses
            for subject_id, statuses in availability_by_subject.items()
            if any(
                status not in {"fresh", "skipped", "fetched", "valid_empty"}
                for status in statuses.values()
            )
        }
        if limited:
            limited_serialized: dict[str, object] = {
                "config": json_value(config),
                "subjects": [
                    {
                        "apartment": json_value(apartment),
                        "result": None,
                        "available": False,
                        "unavailable_reason": (
                            "비교에 필요한 다음 달의 데이터 범위를 사용할 수 없습니다: "
                            + ", ".join(
                                f"{month} ({_coverage_status_label(status)})"
                                for month, status in availability_by_subject[
                                    apartment.internal_id
                                ].items()
                                if status not in {"fresh", "skipped", "fetched", "valid_empty"}
                            )
                        ),
                        "discovered_area_groups": [],
                        "effective_area_key": config.area_group_key,
                        "data_status": "unavailable",
                    }
                    for apartment in apartments
                ],
                "coverage": availability_by_subject,
            }
            app.state.last_comparison = limited_serialized
            workspace.status = "comparison-unavailable"
            return _page(request, templates, workspace, (), limited_serialized)
        result = compare(apartments, transactions, config)
        serialized = comparison_to_dict(result)
        for subject in serialized["subjects"]:
            subject_result = cast(dict[str, object] | None, subject.get("result"))
            if isinstance(subject_result, dict):
                population = cast(dict[str, object], subject_result.get("population", {}))
                subject["raw_count"] = len(cast(list[object], population.get("raw", [])))
                subject["eligible_count"] = len(cast(list[object], population.get("eligible", [])))
                subject["turnover"] = subject_result.get("turnover")
                subject["retention"] = subject_result.get("retention")
                mdd = cast(dict[str, object], subject_result.get("mdd", {}))
                subject["mdd"] = mdd
                subject["peak"] = mdd.get("peak")
                subject["trough"] = mdd.get("trough")
            subject["data_status"] = (
                "valid_empty"
                if not transactions[subject["apartment"]["internal_id"]]
                and all(
                    status == "valid_empty"
                    for status in availability_by_subject[
                        subject["apartment"]["internal_id"]
                    ].values()
                )
                else "complete"
            )
        serialized["coverage"] = {
            item.internal_id: availability_by_subject[item.internal_id] for item in apartments
        }
        app.state.last_comparison = serialized
        workspace.status = "compared"
        return _page(
            request,
            templates,
            workspace,
            (),
            serialized,
        )

    _ = (
        root,
        search,
        select,
        save_interest,
        select_interest,
        remove_interest,
        update,
        analysis,
        export,
        screening,
        comparison,
        refresh_inventory,
    )
    return app


def _page(
    request: Request,
    templates: Jinja2Templates,
    workspace: Workspace,
    candidates: tuple[ApartmentCandidate, ...],
    result: object = None,
) -> HTMLResponse:
    usage_store: SQLiteStore = request.app.state.usage_store
    usage_counts = usage_store.api_usage_snapshot(
        service_ids=tuple(service_id for service_id, *_ in _API_SERVICES)
    )
    api_usage = tuple(
        {
            "service_id": service_id,
            "label": label,
            "used": usage_counts[service_id],
            "limit": request.app.state.usage_limits[service_id],
            "remaining": max(
                request.app.state.usage_limits[service_id] - usage_counts[service_id], 0
            ),
        }
        for service_id, label, _env_name, _default in _API_SERVICES
    )
    household_evidence = (
        None
        if workspace.apartment is None
        else usage_store.load_household_evidence(workspace.apartment.internal_id)
    )
    inventory_record = (
        None
        if workspace.apartment is None
        else usage_store.load_inventory(workspace.apartment.internal_id)
    )
    inventory_attempt = (
        None
        if workspace.apartment is None
        else usage_store.load_inventory_attempt(workspace.apartment.internal_id)
    )
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "아파트 거래 분석 | apt-analyzer",
            "workspace": workspace,
            "province_options": PROVINCE_OPTIONS,
            "candidates": candidates,
            "result": result,
            "api_usage": api_usage,
            "api_usage_total": sum(int(item["used"]) for item in api_usage),
            "comparison_area_groups": _comparison_area_groups(workspace),
            "interests": usage_store.list_interests(),
            "household_evidence": household_evidence,
            "inventory_record": inventory_record,
            "inventory_attempt": inventory_attempt,
            "ui": {
                "labels": _UI_LABELS,
                "metric_labels": _UI_METRIC_LABELS,
                "operator_labels": _UI_OPERATOR_LABELS,
                "method_labels": _UI_METHOD_LABELS,
                "unit_labels": _UI_UNIT_LABELS,
            },
            "format_percentage": _format_percentage,
            "format_krw": _format_krw,
            "inventory_reason": _inventory_reason,
            "asset_version": request.app.state.asset_version,
        },
    )


def _static_asset_version(static_directory: Path) -> str:
    """Return a content version that invalidates stale local web bundles."""
    digest = hashlib.sha256()
    for name in ("apt-analyzer-web.css", "apt-analyzer-web.js"):
        path = static_directory / "assets" / name
        digest.update(name.encode())
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return digest.hexdigest()[:12]


def _format_percentage(value: str | float | Decimal | int | None) -> str:
    """Format an exact ratio as a human-readable percentage."""
    return "사용 불가" if value is None else f"{Decimal(str(value)) * 100:.2f}%"


def _format_krw(value: str | float | Decimal | int | None) -> str:
    """Format an observed won amount for human-readable metric evidence."""
    return "-" if value is None else f"{int(value):,}원"


def _hydrate_area_groups(workspace: Workspace, store: SQLiteStore, apartment_id: str) -> None:
    """Refresh one apartment's UI groups from all persisted transaction evidence."""
    evidence = store.load_transactions(apartment_id)
    workspace.area_groups_by_apartment[apartment_id] = tuple(
        {"key": group.key, "label": group.label} for group in discover_area_groups(evidence)
    )


def _comparison_area_groups(workspace: Workspace) -> tuple[dict[str, str], ...]:
    """Return unique comparison group options while retaining per-apartment groups."""
    groups: dict[str, dict[str, str]] = {}
    for apartment_groups in workspace.area_groups_by_apartment.values():
        for group in apartment_groups:
            groups.setdefault(group["key"], group)
    return tuple(groups[key] for key in sorted(groups))


def _monthly_series(
    result: AnalysisResult, requested_months: tuple[str, ...]
) -> list[dict[str, object]]:
    """Expand observed prices to requested calendar months without interpolation."""
    observations = {item.month: item for item in result.monthly_prices}
    values: list[dict[str, object]] = []
    for month in requested_months:
        label = f"{month[:4]}-{month[4:]}"
        observation = observations.get(label)
        values.append(
            {
                "period": label,
                "value": None if observation is None else str(observation.median_krw),
                "transaction_count": 0 if observation is None else observation.transaction_count,
                "status": "valid_empty" if observation is None else "observed",
            }
        )
    return values


def _complex_profile_dict(
    candidate: ApartmentCandidate | None,
    apartment: Apartment,
    profile_record: ApartmentProfileRecord | None,
    household_count: int | None,
    household_scope: str,
    household_source: str | None,
    persisted_household: HouseholdEvidenceRecord | None,
    eligible: tuple[NormalizedTransaction, ...],
    as_of: date,
    inventory_record: object = None,
    inventory_attempt: object = None,
) -> dict[str, object]:
    """Serialize persisted complex facts and current transaction-area observations."""
    profile: ApartmentProfile | None = None if profile_record is None else profile_record.profile
    total = household_count if household_count and household_count > 0 else None
    household_fetched_at = None
    if (
        persisted_household is not None
        and persisted_household.count == household_count
        and persisted_household.scope == household_scope
        and persisted_household.source == household_source
    ):
        household_fetched_at = persisted_household.fetched_at
    bands: list[dict[str, object]] = []
    if profile is not None:
        for band in profile.area_bands:
            if band.count == 0:
                continue
            bands.append(
                {
                    "label": band.label,
                    "count": band.count,
                    "share_percent": None
                    if total is None
                    else f"{Decimal(band.count * 100) / Decimal(total):.2f}",
                }
            )
    age = None if profile is None else _profile_age(profile.approval_date, as_of)
    observed = [
        {
            "key": group.key,
            "label": group.label,
            "eligible_transaction_count": sum(
                1
                for transaction in eligible
                if transaction.exclusive_area_sqm in group.raw_areas_sqm
            ),
        }
        for group in discover_area_groups(eligible)
    ]
    inventory = _inventory_dict(inventory_record, inventory_attempt)
    return {
        "apartment": {
            "id": apartment.internal_id,
            "name": apartment.display_name,
            "source_id": None if candidate is None else candidate.source_id,
            "road_address": None if candidate is None else candidate.road_address,
            "lot_address": None if candidate is None else candidate.lot_address,
        },
        "households": {
            "count": total,
            "scope": household_scope,
            "source": household_source,
            "fetched_at": household_fetched_at,
        },
        "profile": None
        if profile is None
        else {
            "buildings": profile.buildings,
            "approval_date": None
            if profile.approval_date is None
            else profile.approval_date.isoformat(),
            "highest_floor": profile.highest_floor,
            "heating": profile.heating,
            "hall_type": profile.hall_type,
            "builder": profile.builder,
            "developer": profile.developer,
            "management": profile.management,
            "sale_type": profile.sale_type,
            "age": age,
            "area_bands": bands,
            "source": profile_record.source if profile_record is not None else None,
            "fetched_at": profile_record.fetched_at if profile_record is not None else None,
        },
        "observed_area_groups": observed,
        "inventory": inventory,
    }


def _inventory_dict(record: object, attempt: object) -> dict[str, object] | None:
    """Serialize aggregate inventory evidence without unit-level identifiers."""
    from apt_analyzer.persistence import InventoryRecord

    if not isinstance(record, InventoryRecord) and not isinstance(attempt, InventoryRecord):
        return None
    current = record if isinstance(record, InventoryRecord) else attempt
    assert isinstance(current, InventoryRecord)
    summary = current.summary
    total = summary.total_count
    return {
        "status": summary.state.value,
        "total": total if isinstance(record, InventoryRecord) else None,
        "counts": [
            {
                "area_sqm": str(area),
                "count": count,
                "share_percent": None if not total else f"{count * 100 / total:.2f}",
            }
            for area, count in (summary.counts if isinstance(record, InventoryRecord) else ())
        ],
        "source": current.source,
        "collected_at": current.fetched_at,
        "scope": "선택 단지 전체" if summary.scope and summary.scope.complete else "확인 필요",
        "latest_attempt": None
        if not isinstance(attempt, InventoryRecord)
        else {
            "status": attempt.summary.state.value,
            "reason": _inventory_reason(attempt.summary.reason),
            "collected_at": attempt.fetched_at,
        },
    }


def _inventory_reason(reason: str | None) -> str | None:
    """Translate stable source-boundary reasons for product presentation."""
    if reason is None:
        return None
    labels = {
        "inventory count differs from K-APT total": "건축물대장 세대수가 K-APT 전체 세대수와 다릅니다.",
        "inventory area bands differ from K-APT": "건축물대장 면적대가 K-APT 근거와 다릅니다.",
        "K-APT total household evidence is missing": "K-APT 전체 세대수 근거가 없습니다.",
        "Building HUB collection failed": "건축물대장 수집에 실패했습니다.",
        "Building HUB collection request limit reached": "건축물대장 요청 한도에 도달했습니다.",
        "lot collection limit exceeded": "확인할 필지 범위를 완료하지 못했습니다.",
        "Building HUB scope is incomplete": "건축물대장 단지 범위를 완전히 확인하지 못했습니다.",
    }
    return labels.get(reason, reason)


def _profile_age(approval_date: date | None, as_of: date) -> dict[str, int | str] | None:
    """Return completed calendar years/months from approval through an as-of date."""
    if approval_date is None or approval_date > as_of:
        return None
    total_months = (as_of.year - approval_date.year) * 12 + as_of.month - approval_date.month
    if as_of.day < approval_date.day:
        total_months -= 1
    years, months_remaining = divmod(total_months, 12)
    return {
        "elapsed_years": years,
        "elapsed_months": months_remaining,
        "as_of": as_of.isoformat(),
    }


def _form_period(start: str, end: str, fallback: AnalysisPeriod) -> AnalysisPeriod:
    """Parse a visible metric period, defaulting to the visible overall period."""
    return (
        fallback
        if not start or not end
        else AnalysisPeriod(date.fromisoformat(start), date.fromisoformat(end))
    )


def _period_dict(period: AnalysisPeriod) -> dict[str, str]:
    """Serialize a visible metric period."""
    return {"start": period.start.isoformat(), "end": period.end.isoformat()}


def _metric_period_value(
    start: str, end: str, automatic: AnalysisPeriod | None, overall: AnalysisPeriod
) -> dict[str, str] | None:
    """Serialize an explicit override or nullable automatic period."""
    if start and end:
        return _period_dict(AnalysisPeriod(date.fromisoformat(start), date.fromisoformat(end)))
    return None if automatic is None else _period_dict(automatic)


def _coverage_status_label(status: str) -> str:
    """Return the Korean presentation label for a coverage status."""
    return {
        "missing": "누락됨",
        "fresh": "최신 데이터",
        "skipped": "갱신 생략",
        "fetched": "새로 수집됨",
        "valid_empty": "유효한 빈 결과",
        "stale": "오래된 데이터",
        "failed": "실패",
    }.get(status, status)


def _search_cache_notice(report: CandidateRefreshReport | None) -> str | None:
    """Describe persisted province-list freshness without exposing source details."""
    if report is None:
        return None
    if report.state in (CandidateRefreshState.FRESH, CandidateRefreshState.VALID_EMPTY):
        if report.skipped:
            return f"저장된 지역 목록을 사용했습니다. 마지막 갱신: {report.refreshed_at or '알 수 없음'}"
        return "지역 목록을 새로 갱신했습니다."
    if report.state is CandidateRefreshState.EXTERNAL_FAILURE:
        if report.candidates and report.refreshed_at:
            return (
                "지역 목록 갱신에 실패해 마지막으로 성공한 저장 데이터를 사용합니다. "
                f"마지막 갱신: {report.refreshed_at}"
            )
        return "지역 목록을 갱신하지 못해 검색 결과가 없습니다. 잠시 후 다시 시도해 주세요."
    return None


def _daily_api_limits() -> dict[str, int]:
    """Parse positive per-service local request limits from the environment."""
    values: dict[str, int] = {}
    for service_id, _label, env_name, default in _API_SERVICES:
        raw = os.environ.get(env_name)
        if raw is None:
            values[service_id] = default
            continue
        try:
            value = int(raw)
        except ValueError as error:
            raise ValueError(f"{env_name} must be a positive integer") from error
        if value <= 0:
            raise ValueError(f"{env_name} must be a positive integer")
        values[service_id] = value
    return values


def _default_inventory_service(store: SQLiteStore | None = None) -> InventoryService:
    """Build the explicit Building HUB client using the configured shared key."""
    from apt_analyzer.acquisition import AuthenticationError, DataGoKrClient, load_service_key

    try:
        key = os.environ.get("BUILDING_HUB_SERVICE_KEY") or load_service_key()
    except AuthenticationError:
        return _MissingInventoryService()

    def observe(endpoint: str) -> None:
        if endpoint.startswith(BUILDING_HUB_BASE_URL) and store is not None:
            store.increment_api_usage("building_hub")

    return BuildingInventoryService(
        BuildingHubClient(
            DataGoKrClient(
                key,
                retries=5,
                retry_backoff=0.5,
                min_interval=0.25,
                request_observer=observe,
            )
        )
    )


class _MissingInventoryService:
    """Return a safe unavailable result when no service credential is configured."""

    def collect(
        self,
        candidate: ApartmentCandidate,
        *,
        kapt_total: int | None = None,
        kapt_bands: tuple[tuple[str, int], ...] = (),
    ) -> InventorySummary:
        del candidate, kapt_total, kapt_bands
        return InventorySummary(
            InventoryState.UNAVAILABLE,
            (),
            (),
            None,
            "건축물대장 서비스 설정이 없습니다.",
            datetime.now(UTC),
        )


def _default_service(store: SQLiteStore | None = None) -> SearchService:
    from apt_analyzer.acquisition import AuthenticationError, DataGoKrClient, load_service_key

    try:
        key = load_service_key()
    except AuthenticationError:
        return MissingKeyService()

    def observe(endpoint: str) -> None:
        service_id = _ENDPOINT_TO_API_SERVICE.get(endpoint)
        if service_id is not None and store is not None:
            store.increment_api_usage(service_id)

    return ApartmentDataService(DataGoKrClient(key, request_observer=observe))


app = create_app()
