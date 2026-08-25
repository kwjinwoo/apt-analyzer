"""Local browser workspace for apt-analyzer."""

from __future__ import annotations

import calendar
import os
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
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
from apt_analyzer.m1 import ApartmentCandidate, IdentityResolution, M1Service, months
from apt_analyzer.persistence import SQLiteStore

_TEMPLATE_DIRECTORY = Path(__file__).parent / "templates"


class SearchService(Protocol):
    """Injectable search and retrieval boundary."""

    def search(self, name: str) -> tuple[ApartmentCandidate, ...]:
        """Return distinguishable candidates for a name."""
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

    def search(self, name: str) -> tuple[ApartmentCandidate, ...]:
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
    def search(request: Request, name: str = Form(...)) -> HTMLResponse:
        try:
            candidates = service.search(name)
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
        key = "last_comparison" if kind == "comparison" else "last_result"
        return JSONResponse(getattr(app.state, key, {"status": "analysis_required"}))

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

    _ = (root, search, select, update, analysis, export, comparison)
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
    return M1Service(DataGoKrClient(key))


app = create_app()
