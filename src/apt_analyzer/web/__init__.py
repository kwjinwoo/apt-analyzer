"""Local browser workspace for apt-analyzer."""

from __future__ import annotations

import calendar
import json
import os
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from apt_analyzer.analytics import (
    AnalysisResult,
    DataCoverageStatus,
    HouseholdEvidence,
    analyze,
    discover_area_groups,
)
from apt_analyzer.apartment_data import (
    ApartmentCandidate,
    ApartmentDataService,
    IdentityResolution,
    months,
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
from apt_analyzer.persistence import SQLiteStore
from apt_analyzer.regional_screening import (
    SUPPORTED_METHODS,
    CandidateRefreshState,
    CandidateScreenRule,
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


class MissingKeyService:
    """Fail live operations clearly when no server-side key is configured."""

    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        """Explain that live credentials are required."""
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY is required for live search")

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        """Explain that live credentials are required."""
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY is required for live selection")

    def retrieve(
        self, candidate: ApartmentCandidate, apartment: Apartment, period: AnalysisPeriod
    ) -> tuple[NormalizedTransaction, ...]:
        """Explain that live credentials are required."""
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY is required for live retrieval")


@dataclass
class Workspace:
    """Current explicit selection and evidence state."""

    candidate: ApartmentCandidate | None = None
    apartment: Apartment | None = None
    period: AnalysisPeriod | None = None
    status: str = "idle"
    search_sido_code: str = "11"
    apartments: dict[str, Apartment] = field(default_factory=lambda: {})
    coverage_by_apartment: dict[str, dict[str, str]] = field(default_factory=lambda: {})
    area_groups_by_apartment: dict[str, tuple[dict[str, str], ...]] = field(
        default_factory=lambda: {}
    )


def create_app(
    *, search_service: SearchService | None = None, store: SQLiteStore | None = None
) -> FastAPI:
    """Create the local app with deterministic dependency injection."""
    app = FastAPI(title="apt-analyzer local web")
    static_directory = Path(__file__).parent / "static"
    if static_directory.exists():
        app.mount("/static", StaticFiles(directory=static_directory), name="static")
    templates = Jinja2Templates(directory=_TEMPLATE_DIRECTORY)
    workspace = Workspace()
    owned_store = store or SQLiteStore(
        os.environ.get("APT_ANALYZER_DB", ":memory:"), check_same_thread=False
    )
    store_owned = store is None
    service = search_service or _default_service()

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
            return _page(request, templates, workspace, (), {"error": "Select a valid province."})
        workspace.search_sido_code = sido_code
        try:
            candidates = service.search(name, sido_code=sido_code)
        except Exception as error:  # noqa: BLE001 - source boundary is user-visible
            workspace.status = "failed"
            return _page(request, templates, workspace, (), {"error": str(error)})
        workspace.status = "searching" if candidates else "not_found"
        return _page(request, templates, workspace, candidates)

    @app.post("/select", response_class=HTMLResponse)
    def select(
        request: Request,
        source_id: str = Form(...),
        name: str = Form(...),
        legal_dong_code: str = Form(...),
        lot_address: str = Form(...),
        road_address: str = Form(...),
    ) -> HTMLResponse:
        selected = ApartmentCandidate(source_id, name, legal_dong_code, lot_address, road_address)
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
            owned_store.save_apartment(resolution.apartment)
            workspace.apartments[resolution.apartment.internal_id] = resolution.apartment
        return _page(request, templates, workspace, (enriched,))

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
        known_area_keys = {
            group["key"]
            for subject_groups in workspace.area_groups_by_apartment.values()
            for group in subject_groups
        }
        workspace.area_groups_by_apartment[apartment.internal_id] = tuple(
            {"key": group.key, "label": group.label}
            for group in discover_area_groups(evidence)
            if group.key not in known_area_keys
        )
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
        transactions = owned_store.load_transactions(workspace.apartment.internal_id, period)
        coverage = owned_store.coverage(
            workspace.apartment.internal_id, "MOLIT apartment sale transactions"
        )
        requested_months = months(period)
        availability = {
            month: ("fresh" if month in coverage else "missing") for month in requested_months
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
        group = (
            next(
                (item for item in discover_area_groups(transactions) if item.key == area_group),
                None,
            )
            if area_group != "all"
            else None
        )
        if area_group != "all" and group is None:
            return JSONResponse({"error": "area group is unavailable"}, status_code=400)
        context = AnalysisContext(
            workspace.apartment,
            period,
            AreaSelection.all() if group is None else AreaSelection.for_group(group),
            TransactionInclusionPolicy(
                include_cancelled,
                frozenset(TransactionType(item) for item in transaction_types),
            ),
        )
        complete_coverage = all(
            availability[item] in {"fresh", "skipped", "fetched", "valid_empty"}
            for item in requested_months
        )
        if not complete_coverage:
            workspace.status = "unavailable"
            volume_series = [
                {
                    "period": f"{month[:4]}-{month[4:]}",
                    "value": 0 if availability[month] == "valid_empty" else None,
                    "status": availability[month],
                }
                for month in requested_months
            ]
            price_series = [
                {"period": f"{month[:4]}-{month[4:]}", "value": None, "status": availability[month]}
                for month in requested_months
            ]
            return _page(
                request,
                templates,
                workspace,
                (),
                {
                    "availability": availability,
                    "volume_series": volume_series,
                    "monthly_series": price_series,
                    "data_status": "coverage-limited",
                    "context": {
                        "period": {"start": start, "end": end},
                        "inclusion_policy": {
                            "include_cancelled": include_cancelled,
                            "transaction_types": transaction_types,
                        },
                        "available_area_groups": discover_area_groups(transactions),
                    },
                },
            )
        result = analyze(
            transactions,
            context,
            turnover_period=_form_period(turnover_start, turnover_end, period),
            household=HouseholdEvidence(household_count, household_scope, household_source or None),
            baseline_period=_form_period(baseline_start, baseline_end, period),
            comparison_period=_form_period(comparison_start, comparison_end, period),
            mdd_period=_form_period(mdd_start, mdd_end, period),
            data_status=DataCoverageStatus.COMPLETE
            if transactions
            else DataCoverageStatus.VALID_EMPTY,
        )
        workspace.status = "analyzed"
        app.state.last_result = result_to_dict(result)
        app.state.last_result["availability"] = availability
        app.state.last_result["coverage"] = {
            month: "observed"
            if any(item.month == f"{month[:4]}-{month[4:]}" for item in result.monthly_prices)
            else "valid_empty"
            for month in requested_months
        }
        app.state.last_result["monthly_series"] = _monthly_series(result, requested_months)
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
                "value": eligible_by_month[month],
                "status": availability[month],
            }
            for month in requested_months
        ]
        app.state.last_result["ui_context"] = {
            "apartment_id": workspace.apartment.internal_id,
            "apartment_name": workspace.apartment.display_name,
            "overall_period": _period_dict(period),
            "area": "all" if group is None else group.label,
            "inclusion_policy": {
                "include_cancelled": include_cancelled,
                "transaction_types": transaction_types,
            },
            "metric_periods": {
                name: _period_dict(value)
                for name, value in (
                    ("turnover", _form_period(turnover_start, turnover_end, period)),
                    ("baseline", _form_period(baseline_start, baseline_end, period)),
                    ("comparison", _form_period(comparison_start, comparison_end, period)),
                    ("mdd", _form_period(mdd_start, mdd_end, period)),
                )
            },
        }
        return _page(request, templates, workspace, (), app.state.last_result)

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
        rules: str = Form(...),
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
            return _page(request, templates, workspace, (), {"error": "regions must be explicit"})
        overall_start = start or screen_start or ""
        overall_end = end or screen_end or ""
        if not overall_start or not overall_end:
            return _page(
                request, templates, workspace, (), {"error": "screening period is required"}
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
                    "disclaimer": "Historical screening only; this is not an investment recommendation.",
                }
            else:
                resolved = owned_store.load_resolved_candidates(
                    source_name, selected_regions, candidate_ids
                )
                if candidate_ids - {candidate.source_id for _, candidate, _ in resolved}:
                    raise ValueError("requested candidate IDs are not resolved in selected regions")
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
                    raise ValueError("households must be a JSON object keyed by apartment ID")
                households: dict[str, HouseholdEvidence] = {}
                apartment_ids = {item.internal_id for item in apartments}
                for apartment_id, raw_value in cast(
                    dict[object, object], household_payload
                ).items():
                    if not isinstance(apartment_id, str) or not isinstance(raw_value, dict):
                        raise ValueError(
                            "each household entry must be an object keyed by apartment ID"
                        )
                    value = cast(dict[str, object], raw_value)
                    if apartment_id not in apartment_ids:
                        continue
                    scope = value.get("scope")
                    if not isinstance(scope, str):
                        raise ValueError("each household entry requires a scope")
                    count = value.get("count")
                    if count is not None and not isinstance(count, int):
                        raise ValueError("household count must be an integer")
                    source = value.get("source")
                    if source is not None and not isinstance(source, str):
                        raise ValueError("household source must be text")
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
                    "disclaimer": "Historical screening only; this is not an investment recommendation.",
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
                {"error": "comparison requires at least two resolved apartments"}, status_code=400
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
                            "comparison coverage unavailable for months: "
                            + ", ".join(
                                f"{month} ({status})"
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

    _ = (root, search, select, update, analysis, export, screening, comparison)
    return app


def _page(
    request: Request,
    templates: Jinja2Templates,
    workspace: Workspace,
    candidates: tuple[ApartmentCandidate, ...],
    result: object = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "apt-analyzer local web",
            "workspace": workspace,
            "province_options": PROVINCE_OPTIONS,
            "candidates": candidates,
            "result": result,
        },
    )


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


def _default_service() -> SearchService:
    from apt_analyzer.acquisition import AuthenticationError, DataGoKrClient, load_service_key

    try:
        key = load_service_key()
    except AuthenticationError:
        return MissingKeyService()
    return ApartmentDataService(DataGoKrClient(key))


app = create_app()
