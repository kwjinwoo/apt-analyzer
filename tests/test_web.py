import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from apt_analyzer.apartment_data import (
    KAPT_DETAIL_ENDPOINT,
    KAPT_LIST_ENDPOINT,
    MOLIT_SALE_ENDPOINT,
    ApartmentCandidate,
    ApartmentDataService,
    ApartmentProfile,
    AreaHouseholdBand,
    IdentityResolution,
    ResolutionStatus,
)
from apt_analyzer.building_hub import InventoryRow, InventoryScope, InventoryState, InventorySummary
from apt_analyzer.domain import (
    AnalysisPeriod,
    Apartment,
    AreaGroup,
    NormalizedTransaction,
    TransactionType,
)
from apt_analyzer.persistence import InventoryRecord, SQLiteStore
from apt_analyzer.web import (
    _ENDPOINT_TO_API_SERVICE,
    MissingKeyService,
    _default_service,
    _inventory_group_households,
    _profile_age,
    _static_asset_version,
    create_app,
)


class FakeSearch:
    def __init__(self) -> None:
        self.apartments = {"a": Apartment("a", "Alpha"), "b": Apartment("b", "Beta")}
        self.retrieve_calls = 0

    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        return tuple(
            ApartmentCandidate(
                key,
                value.display_name,
                "1234567890",
                f"{value.display_name} lot",
                f"{value.display_name} road",
            )
            for key, value in self.apartments.items()
            if name.lower() in value.display_name.lower()
        )

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        apartment = self.apartments[selected.source_id]
        return selected, IdentityResolution(ResolutionStatus.RESOLVED, (selected,), apartment)

    def retrieve(
        self, candidate: ApartmentCandidate, apartment: Apartment, period: object
    ) -> tuple[NormalizedTransaction, ...]:
        self.retrieve_calls += 1
        return (
            NormalizedTransaction(
                apartment.internal_id,
                date(2024, 1, 15),
                100,
                Decimal("84"),
                TransactionType.BROKERED,
                False,
                source_name="MOLIT apartment sale transactions",
                source_record_id="day-15",
            ),
        )


class HouseholdSearch(FakeSearch):
    def __init__(self, household_count: int = 1842) -> None:
        super().__init__()
        self.household_count = household_count
        self.profile_buildings = 3
        self.profile_highest_floor = 20
        self.resolve_calls = 0
        self.fail = False

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        self.resolve_calls += 1
        if self.fail:
            raise RuntimeError("fixture K-APT failure")
        enriched = ApartmentCandidate(
            selected.source_id,
            selected.name,
            selected.legal_dong_code,
            selected.lot_address,
            selected.road_address,
            self.household_count,
            "K-APT apartment basic information",
            ApartmentProfile(
                buildings=self.profile_buildings,
                highest_floor=self.profile_highest_floor,
                approval_date=date(1999, 5, 3),
                heating="지역난방",
                hall_type="혼합식",
                builder="한신공영",
                developer="한국토지주택공사 LH",
                management="위탁관리",
                sale_type="분양",
                area_bands=(
                    AreaHouseholdBand("≤60㎡", 80),
                    AreaHouseholdBand(">60–85㎡", 20),
                    AreaHouseholdBand(">85–135㎡", 0),
                ),
            ),
        )
        apartment = self.apartments[selected.source_id]
        return enriched, IdentityResolution(ResolutionStatus.RESOLVED, (enriched,), apartment)


def test_static_asset_version_changes_with_bundle_content_and_is_rendered(tmp_path) -> None:
    static_directory = tmp_path / "static"
    assets = static_directory / "assets"
    assets.mkdir(parents=True)
    script = assets / "apt-analyzer-web.js"
    stylesheet = assets / "apt-analyzer-web.css"
    script.write_text("old bundle", encoding="utf-8")
    stylesheet.write_text("old styles", encoding="utf-8")
    old_version = _static_asset_version(static_directory)

    script.write_text("new direct-drag bundle", encoding="utf-8")

    assert _static_asset_version(static_directory) != old_version
    app = create_app(search_service=FakeSearch(), store=SQLiteStore(":memory:"))
    response = TestClient(app).get("/")
    version = app.state.asset_version
    assert f"/static/assets/apt-analyzer-web.js?v={version}" in response.text
    assert f"/static/assets/apt-analyzer-web.css?v={version}" in response.text


def _save_two_year_metric_evidence(store: SQLiteStore, apartment: Apartment) -> None:
    source_name = "MOLIT apartment sale transactions"

    def records(month: str) -> tuple[NormalizedTransaction, ...]:
        year = int(month[:4])
        month_number = int(month[4:])
        count = 1 if year == 2023 else 2
        price = 50_000_000 if month == "202402" else 100_000_000
        return tuple(
            NormalizedTransaction(
                apartment.internal_id,
                date(year, month_number, 15 + index),
                price,
                Decimal("84"),
                TransactionType.BROKERED,
                False,
                source_name=source_name,
                source_record_id=f"{month}-{index}",
            )
            for index in range(count)
        )

    store.update_incremental(
        apartment,
        AnalysisPeriod(date(2023, 1, 1), date(2024, 12, 31)),
        records,
        source_name=source_name,
    )


def test_interest_routes_persist_idempotently_and_restore_without_comparison_membership(tmp_path):
    store = SQLiteStore(tmp_path / "data.db")
    app = create_app(search_service=FakeSearch(), store=store)
    client = TestClient(app)
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})

    saved = client.post("/interests/save")
    assert saved.status_code == 200
    assert "관심 단지" in saved.text
    client.post("/interests/save")
    assert len(store.list_interests()) == 1

    restarted = create_app(search_service=FakeSearch(), store=store)
    restarted_client = TestClient(restarted)
    listed = restarted_client.get("/")
    assert "Alpha" in listed.text
    selected = restarted_client.post("/interests/select", data={"apartment_id": "a"})
    assert selected.status_code == 200
    assert "선택한 단지: <strong>Alpha</strong>" in selected.text
    assert restarted.state.workspace.apartment == Apartment("a", "Alpha")
    assert restarted.state.workspace.apartments == {}


def test_saved_interest_selection_and_analysis_load_profile_without_resolve(tmp_path):
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(
            search_service=service,
            store=store,
            analysis_today=lambda: date(2025, 1, 15),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post("/interests/save")
    profile_before = store.load_profile("a")
    assert profile_before is not None

    service.resolve_calls = 0
    selected = client.post("/interests/select", data={"apartment_id": "a"})
    analyzed = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "transaction_types": ["brokered"],
        },
    )

    assert selected.status_code == analyzed.status_code == 200
    assert service.resolve_calls == 0
    assert store.load_profile("a") == profile_before


def test_profile_household_atomic_save_rejects_invalid_evidence_without_partial_write(tmp_path):
    store = SQLiteStore(tmp_path / "data.db")
    store.save_profile_and_household(
        "a", ApartmentProfile(buildings=3), 100, household_source="fixture", profile_source="K-APT"
    )
    with pytest.raises(ValueError, match="household count must be positive"):
        store.save_profile_and_household(
            "a", ApartmentProfile(buildings=9), 0, household_source="bad", profile_source="K-APT"
        )
    evidence = store.load_household_evidence("a")
    profile = store.load_profile("a")
    assert evidence is not None and evidence.count == 100
    assert profile is not None and profile.profile.buildings == 3


def test_selected_kapt_households_are_persisted_and_used_offline_for_percent_metrics(
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(
            search_service=service,
            store=store,
            analysis_today=lambda: date(2025, 1, 15),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})

    selected = client.post("/select", data={"source_id": "a"})

    assert selected.status_code == 200
    evidence = store.load_household_evidence("a")
    assert evidence is not None and evidence.count == 100
    assert 'action="/household/refresh"' in selected.text
    assert service.resolve_calls == 1

    analyzed = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "transaction_types": ["brokered"],
        },
    )
    reanalyzed = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "transaction_types": ["brokered"],
        },
    )

    assert analyzed.status_code == reanalyzed.status_code == 200
    assert service.resolve_calls == 1
    assert service.retrieve_calls == 0
    assert "24.00%" in analyzed.text
    assert 'aria-label="핵심 분석 지표"' in analyzed.text
    assert "24건 / 100세대" in analyzed.text
    assert "24건 / 12건" in analyzed.text
    assert "100,000,000원 → 50,000,000원" in analyzed.text
    assert "200.00%" in analyzed.text
    assert "-50.00%" in analyzed.text
    assert "100%는 동일" in analyzed.text
    payload = client.get("/export?kind=analysis").json()
    assert payload["complex_profile"]["apartment"] == {
        "id": "a",
        "name": "Alpha",
        "source_id": "a",
        "road_address": "Alpha road",
        "lot_address": "Alpha lot",
    }
    assert payload["complex_profile"]["profile"]["buildings"] == 3
    assert payload["complex_profile"]["profile"]["approval_date"] == "1999-05-03"
    assert payload["complex_profile"]["profile"]["heating"] == "지역난방"
    assert payload["complex_profile"]["profile"]["area_bands"] == [
        {"label": "≤60㎡", "count": 80, "share_percent": "80.00"},
        {"label": ">60–85㎡", "count": 20, "share_percent": "20.00"},
    ]
    assert payload["complex_profile"]["households"]["count"] == 100
    assert payload["complex_profile"]["households"]["fetched_at"]
    assert analyzed.text.index("complex-profile") < analyzed.text.index("핵심 분석 지표")
    assert "단지 기본 정보" in analyzed.text
    assert "Alpha road" in analyzed.text
    assert "거래 관측 면적" in analyzed.text
    assert payload["complex_profile"]["observed_area_groups"] == [
        {"key": "floor-84", "label": "84㎡", "eligible_transaction_count": 36}
    ]
    assert "84㎡" in analyzed.text
    assert "세대수 근거: K-APT apartment basic information" in analyzed.text
    assert "K-APT 면적 구간별 참고 근거" in analyzed.text
    assert "검증된 전용면적별 세대수는 아직 확인되지 않았습니다" in analyzed.text
    assert "세대 재고나 단지 전체 구성의 증거가 아닙니다." in analyzed.text
    assert payload["turnover"]["value"] == "0.24"
    assert payload["retention"]["value"] == "2"
    assert payload["mdd"]["value"] == "-0.5"
    assert payload["metric_display"] == {
        "turnover": {"unit": "%", "meaning": "기간 내 유효 거래량 ÷ 세대수"},
        "retention": {"unit": "%", "meaning": "비교 기간 거래량 ÷ 기준 기간 거래량"},
        "mdd": {"unit": "%", "meaning": "가격 시계열 최대낙폭"},
    }


def test_profile_age_is_exported_and_rendered_as_of_analysis_date(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(
            search_service=service,
            store=store,
            analysis_today=lambda: date(2026, 9, 8),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    response = client.post(
        "/analysis",
        data={"start": "2023-01-01", "end": "2024-12-31", "transaction_types": ["brokered"]},
    )
    payload = client.get("/export?kind=analysis").json()
    assert response.status_code == 200
    assert payload["complex_profile"]["profile"]["age"] == {
        "elapsed_years": 27,
        "elapsed_months": 4,
        "as_of": "2026-09-08",
    }
    assert "연식 27년 4개월 · 2026-09-08 기준" in response.text


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        (date(2026, 5, 2), {"elapsed_years": 26, "elapsed_months": 11, "as_of": "2026-05-02"}),
        (date(2026, 5, 3), {"elapsed_years": 27, "elapsed_months": 0, "as_of": "2026-05-03"}),
        (date(1999, 5, 2), None),
        (date(1999, 5, 4), {"elapsed_years": 0, "elapsed_months": 0, "as_of": "1999-05-04"}),
    ],
)
def test_profile_age_uses_completed_calendar_months(as_of, expected) -> None:
    assert _profile_age(date(1999, 5, 3), as_of) == expected
    assert _profile_age(date(2027, 1, 1), as_of) is None


def test_analysis_preview_uses_offline_context_without_mutating_official_result(
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    store.save_transaction(
        NormalizedTransaction(
            "a",
            date(2024, 3, 28),
            75_000_000,
            Decimal("84"),
            TransactionType.DIRECT,
            False,
            source_name="MOLIT apartment sale transactions",
            source_record_id="excluded-preview-direct",
        )
    )
    store.save_transaction(
        NormalizedTransaction(
            "a",
            date(2024, 4, 28),
            80_000_000,
            Decimal("59"),
            TransactionType.BROKERED,
            False,
            source_name="MOLIT apartment sale transactions",
            source_record_id="excluded-preview-area",
        )
    )
    app = create_app(
        search_service=service,
        store=store,
        analysis_today=lambda: date(2025, 1, 15),
    )
    client = TestClient(app)
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "area_group": "floor-84",
            "transaction_types": ["brokered"],
            "household_count": "100",
            "household_scope": "floor-84",
            "household_source": "fixture",
        },
    )
    official_before = client.get("/export?kind=analysis").json()

    response = client.post(
        "/analysis/preview",
        data={"start": "2024-01-01", "end": "2024-12-31"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "selection": {
            "start": "2024-01-01",
            "end": "2024-12-31",
            "label": "2024.01 ~ 2024.12",
            "months": 12,
        },
        "volume": {
            "value": 24,
            "display": "24건",
            "unit": "건",
            "evidence": "선택 기간 유효 거래 24건",
        },
        "turnover": {
            "status": "available",
            "value": "0.24",
            "display": "24.00%",
            "unit": "%",
            "evidence": "24건 / 100세대",
            "reason": None,
            "method": "completed-calendar-month-12-month-window",
        },
        "retention": {
            "status": "available",
            "value": "2",
            "display": "200.00%",
            "unit": "%",
            "evidence": "2024.01~2024.12 24건 / 2023.01~2023.12 12건 (비교 / 기준)",
            "reason": None,
            "method": "completed-calendar-month-12-vs-prior-12",
        },
        "mdd": {
            "status": "available",
            "value": "-0.5",
            "display": "-50.00%",
            "unit": "%",
            "evidence": "100,000,000원 → 50,000,000원 (2024-01 → 2024-02)",
            "reason": None,
            "method": "observed monthly median",
        },
    }
    assert client.get("/export?kind=analysis").json() == official_before
    assert service.retrieve_calls == 0


def test_analysis_preview_uses_cumulative_turnover_and_unavailable_retention(
    tmp_path,
) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(
            search_service=service,
            store=store,
            analysis_today=lambda: date(2025, 1, 15),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "transaction_types": ["brokered"],
        },
    )

    preview = client.post(
        "/analysis/preview",
        data={"start": "2024-01-01", "end": "2024-06-30"},
    )

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["selection"]["months"] == 6
    assert payload["volume"]["value"] == 12
    assert payload["turnover"]["status"] == "available"
    assert payload["turnover"]["value"] == "0.12"
    assert payload["turnover"]["method"] == "preview-cumulative-month-turnover"
    assert payload["turnover"]["evidence"] == "12건 누적 / 100세대"
    assert payload["retention"] == {
        "status": "unavailable",
        "value": None,
        "display": "계산 불가",
        "unit": "%",
        "evidence": None,
        "reason": "거래유지율은 선택 기간과 직전 기간이 각각 12개월이어야 합니다",
        "method": "completed-calendar-month-12-vs-prior-12",
    }
    assert payload["mdd"]["display"] == "-50.00%"
    assert payload["mdd"]["method"] == "observed monthly median"


def test_analysis_preview_uses_annual_average_for_complete_24_month_selection(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(search_service=service, store=store, analysis_today=lambda: date(2025, 1, 15))
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post(
        "/analysis",
        data={"start": "2023-01-01", "end": "2024-12-31", "transaction_types": ["brokered"]},
    )
    response = client.post("/analysis/preview", data={"start": "2023-01-01", "end": "2024-12-31"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["selection"]["months"] == 24
    assert payload["turnover"] == {
        "status": "available",
        "value": "0.18",
        "display": "18.00%",
        "unit": "%",
        "evidence": "36건 ÷ 2년 / 100세대",
        "reason": None,
        "method": "preview-calendar-month-average",
    }


def test_analysis_preview_splits_24_month_retention_into_baseline_and_comparison(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(search_service=service, store=store, analysis_today=lambda: date(2025, 1, 15))
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post("/analysis", data={"start": "2023-01-01", "end": "2024-12-31"})
    payload = client.post(
        "/analysis/preview", data={"start": "2023-01-01", "end": "2024-12-31"}
    ).json()
    assert payload["retention"]["value"] == "2"
    assert payload["retention"]["display"] == "200.00%"
    assert (
        payload["retention"]["evidence"]
        == "2024.01~2024.12 24건 / 2023.01~2023.12 12건 (비교 / 기준)"
    )


def test_analysis_preview_rejects_incompatible_household_scope_for_duration(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(search_service=service, store=store, analysis_today=lambda: date(2025, 1, 15))
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "area_group": "floor-84",
            "household_count": "100",
            "household_scope": "complex",
            "household_source": "fixture",
        },
    )
    payload = client.post(
        "/analysis/preview", data={"start": "2023-01-01", "end": "2024-12-31"}
    ).json()
    assert payload["turnover"]["status"] == "unavailable"
    assert payload["turnover"]["reason"] == "세대수 분모 범위가 면적 선택과 일치하지 않습니다"


def test_analysis_preview_preserves_coverage_and_completion_reasons(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    store._connection.execute(
        "DELETE FROM monthly_coverage WHERE apartment_id=? AND month=?",
        ("a", "202401"),
    )
    store._connection.commit()
    client = TestClient(
        create_app(search_service=service, store=store, analysis_today=lambda: date(2025, 1, 15))
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post("/analysis", data={"start": "2023-01-01", "end": "2024-12-31"})
    missing = client.post(
        "/analysis/preview", data={"start": "2023-01-01", "end": "2024-12-31"}
    ).json()
    assert missing["turnover"]["reason"] == "필요한 월별 근거가 완전하지 않습니다"
    partial_store = SQLiteStore(tmp_path / "partial.db")
    _save_two_year_metric_evidence(partial_store, Apartment("a", "Alpha"))
    incomplete = TestClient(
        create_app(
            search_service=service,
            store=partial_store,
            analysis_today=lambda: date(2024, 7, 15),
        )
    )
    incomplete.post("/search", data={"name": "Alpha", "sido_code": "11"})
    incomplete.post("/select", data={"source_id": "a"})
    incomplete.post("/analysis", data={"start": "2023-01-01", "end": "2024-12-31"})
    partial = incomplete.post(
        "/analysis/preview", data={"start": "2024-01-01", "end": "2024-07-31"}
    ).json()
    assert partial["turnover"]["reason"] == "거래회전율은 완료된 달력 월만 사용할 수 있습니다"


def test_analysis_preview_rejects_non_month_boundaries_and_outside_period(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(create_app(search_service=service, store=store))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "transaction_types": ["brokered"],
        },
    )

    boundary = client.post(
        "/analysis/preview",
        data={"start": "2024-01-02", "end": "2024-12-31"},
    )
    outside = client.post(
        "/analysis/preview",
        data={"start": "2022-01-01", "end": "2022-12-31"},
    )

    assert boundary.status_code == 422
    assert boundary.json()["error"] == "월의 첫날부터 마지막 날까지 선택해 주세요."
    assert outside.status_code == 422
    assert outside.json()["error"] == "전체 분석 기간 안에서 선택해 주세요."


def test_explicit_household_refresh_preserves_last_good_evidence_on_failure(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    client = TestClient(create_app(search_service=service, store=store))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    initial_profile = store.load_profile("a")
    initial_household = store.load_household_evidence("a")
    assert initial_profile is not None and initial_profile.profile.buildings == 3
    assert initial_household is not None and initial_household.count == 100
    service.household_count = 120
    service.profile_buildings = 4
    service.profile_highest_floor = 24

    refreshed = client.post("/household/refresh")

    assert refreshed.status_code == 200
    evidence = store.load_household_evidence("a")
    assert evidence is not None and evidence.count == 120
    profile = store.load_profile("a")
    assert profile is not None
    assert profile.profile.buildings == 4
    assert profile.profile.highest_floor == 24
    service.fail = True
    failed = client.post("/household/refresh")
    preserved = store.load_household_evidence("a")
    preserved_profile = store.load_profile("a")
    assert failed.status_code == 200
    assert "fixture K-APT failure" in failed.text
    assert preserved is not None and preserved.count == 120
    assert preserved_profile is not None
    assert preserved_profile.profile.buildings == 4
    assert preserved_profile.profile.highest_floor == 24


def test_persisted_complex_households_do_not_leak_into_area_group_turnover(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    service = HouseholdSearch(household_count=100)
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(
            search_service=service,
            store=store,
            analysis_today=lambda: date(2025, 1, 15),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})

    automatic = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "area_group": "floor-84",
            "transaction_types": ["brokered"],
        },
    )
    automatic_payload = client.get("/export?kind=analysis").json()
    assert automatic.status_code == 200
    assert "선택한 면적 그룹의 세대수 근거가 필요합니다." in automatic.text
    assert "분석 전 K-APT 세대수 근거를 갱신해 주세요." not in automatic.text
    assert automatic_payload["turnover"]["value"] is None
    assert automatic_payload["turnover"]["unavailable"]["reason"] == (
        "household denominator is missing or invalid"
    )

    explicit = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "area_group": "floor-84",
            "transaction_types": ["brokered"],
            "household_count": "100",
            "household_scope": "floor-84",
            "household_source": "fixture area evidence",
        },
    )
    explicit_payload = client.get("/export?kind=analysis").json()
    assert explicit.status_code == 200
    assert explicit_payload["turnover"]["value"] == "0.24"
    assert service.resolve_calls == 1
    assert service.retrieve_calls == 0


def test_verified_inventory_derives_floor_group_denominator_and_provenance(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    apartment = Apartment("a", "Alpha")
    source = "MOLIT apartment sale transactions"

    def records(month: str) -> tuple[NormalizedTransaction, ...]:
        year, month_number = int(month[:4]), int(month[4:])
        transactions = [
            NormalizedTransaction(
                apartment.internal_id,
                date(year, month_number, 15),
                100_000_000,
                Decimal("59.2"),
                TransactionType.BROKERED,
                False,
                source_name=source,
                source_record_id=month,
            ),
        ]
        if month == "202301":
            transactions.append(
                NormalizedTransaction(
                    apartment.internal_id,
                    date(year, month_number, 20),
                    100_000_000,
                    Decimal("49.76"),
                    TransactionType.BROKERED,
                    False,
                    source_name=source,
                    source_record_id="49-202301",
                )
            )
        return tuple(transactions)

    store.update_incremental(
        apartment, AnalysisPeriod(date(2023, 1, 1), date(2024, 12, 31)), records, source_name=source
    )
    store.save_profile_and_household(
        apartment.internal_id,
        ApartmentProfile(area_bands=(AreaHouseholdBand("≤60㎡", 1190),)),
        1190,
        household_source="K-APT",
        profile_source="K-APT",
    )
    area_counts = (
        (Decimal("49.76"), 76),
        (Decimal("59.39"), 15),
        (Decimal("59.80"), 195),
        (Decimal("59.94"), 74),
        (Decimal("59.99"), 830),
    )
    rows_list: list[InventoryRow] = []
    index = 0
    for area, count in area_counts:
        for _ in range(count):
            rows_list.append(InventoryRow(f"u{index}", "101", str(index), area))
            index += 1
    rows = tuple(rows_list)
    summary = InventorySummary(
        InventoryState.VERIFIED,
        rows,
        area_counts,
        1190,
        collected_at=datetime(2026, 9, 10, tzinfo=UTC),
        source="Building HUB",
        scope=InventoryScope("root", ("title",), ("u1",), (), (), True),
        data_complete=True,
        kapt_total=1190,
        kapt_bands=(("≤60㎡", 1190),),
    )
    store.save_inventory(apartment.internal_id, summary, source="Building HUB")
    client = TestClient(
        create_app(
            search_service=HouseholdSearch(1190),
            store=store,
            analysis_today=lambda: date(2025, 1, 15),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    response = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "area_group": "floor-59",
            "household_count": "1190",
            "household_scope": "complex",
            "household_source": "K-APT",
        },
    )
    payload = client.get("/export?kind=analysis").json()
    assert response.status_code == 200
    assert payload["ui_context"]["household"] == {
        "count": 1114,
        "scope": "floor-59",
        "source": "Building HUB",
        "fetched_at": "2026-09-10T00:00:00+00:00",
    }
    assert Decimal(payload["turnover"]["value"]) == Decimal("0.01077199281867145421903052065")
    assert "1114" in response.text
    assert "Building HUB" in response.text
    assert "확인 시각: 2026-09-10T00:00:00+00:00" in response.text
    assert "전체 세대수" in response.text
    assert "1190세대" in response.text
    assert "100.00%" in response.text
    assert "선택 면적 그룹 거래 활동" in response.text
    assert "검증된 전용면적별 세대수" in response.text
    assert "49.76㎡" in response.text and "76세대" in response.text
    assert "59.99㎡" in response.text and "830세대" in response.text
    assert "K-APT 면적 구간별 참고 근거" in response.text
    assert "K-APT 공식 면적대별 세대 재고" not in response.text
    assert "세대수 근거가 필요" not in response.text

    editor_round_trip = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "area_group": "floor-59",
            "household_count": "1114",
            "household_scope": "floor-59",
            "household_source": "Building HUB",
        },
    )
    assert editor_round_trip.status_code == 200
    assert (
        client.get("/export?kind=analysis").json()["ui_context"]["household"]
        == payload["ui_context"]["household"]
    )

    preview = client.post(
        "/analysis/preview",
        data={"start": "2023-01-01", "end": "2024-12-31"},
    )
    assert preview.status_code == 200
    assert Decimal(preview.json()["turnover"]["value"]) == Decimal(
        "0.01077199281867145421903052065"
    )
    assert "1114세대" in preview.json()["turnover"]["evidence"]

    floor_49 = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "area_group": "floor-49",
            "household_count": "1190",
            "household_scope": "complex",
            "household_source": "K-APT",
        },
    )
    assert floor_49.status_code == 200
    floor_49_payload = client.get("/export?kind=analysis").json()
    assert floor_49_payload["ui_context"]["household"]["count"] == 76
    assert floor_49_payload["ui_context"]["household"]["scope"] == "floor-49"
    assert Decimal(floor_49_payload["turnover"]["value"]) == Decimal("0")

    all_area = client.post(
        "/analysis",
        data={"start": "2023-01-01", "end": "2024-12-31", "area_group": "all"},
    )
    assert all_area.status_code == 200
    assert "전체 단지 거래 활동" in all_area.text


def test_missing_complex_household_shows_refresh_guidance_and_machine_reason(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    _save_two_year_metric_evidence(store, Apartment("a", "Alpha"))
    client = TestClient(
        create_app(
            search_service=FakeSearch(),
            store=store,
            analysis_today=lambda: date(2025, 1, 15),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    response = client.post(
        "/analysis",
        data={"start": "2023-01-01", "end": "2024-12-31", "transaction_types": ["brokered"]},
    )
    payload = client.get("/export?kind=analysis").json()
    assert response.status_code == 200
    assert "계산 불가: 세대수 분모가 없거나 올바르지 않습니다" in response.text
    assert "분석 전 K-APT 세대수 근거를 갱신해 주세요." in response.text
    assert "단지 기본 정보" in response.text
    assert "K-APT 단지 기본정보가 확인되지 않았습니다." in response.text
    assert payload["turnover"]["value"] is None
    assert payload["complex_profile"]["profile"] is None
    assert payload["complex_profile"]["apartment"]["road_address"] == "Alpha road"
    assert payload["turnover"]["unavailable"]["reason"] == (
        "household denominator is missing or invalid"
    )


def test_saving_current_selection_keeps_the_selection_region_after_a_later_search(tmp_path):
    store = SQLiteStore(tmp_path / "data.db")
    client = TestClient(create_app(search_service=FakeSearch(), store=store))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post("/search", data={"name": "Beta", "sido_code": "41"})

    response = client.post("/interests/save")

    assert response.status_code == 200
    assert store.list_interests()[0].region_code == "11"


def test_interest_remove_preserves_evidence_and_requires_resolved_selection(tmp_path):
    store = SQLiteStore(tmp_path / "data.db")
    app = create_app(search_service=FakeSearch(), store=store)
    client = TestClient(app)
    assert client.post("/interests/save").status_code == 200
    assert store.list_interests() == ()

    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post("/interests/save")
    transaction = NormalizedTransaction(
        "a",
        date(2024, 1, 15),
        100,
        Decimal("84"),
        TransactionType.BROKERED,
        False,
        source_name="MOLIT apartment sale transactions",
        source_record_id="fixture-1",
    )
    store.update_incremental(
        Apartment("a", "Alpha"),
        AnalysisPeriod(date(2024, 1, 1), date(2024, 1, 31)),
        lambda _month: (transaction,),
        source_name="MOLIT apartment sale transactions",
    )
    removed = client.post("/interests/remove", data={"apartment_id": "a"})
    assert removed.status_code == 200
    assert store.list_interests() == ()
    assert store.load_transactions("a") == (transaction,)
    assert tuple(store.coverage("a", "MOLIT apartment sale transactions")) == ("202401",)
    assert store.coverage_states("a", "MOLIT apartment sale transactions") == {"202401": "complete"}
    assert app.state.workspace.apartment == Apartment("a", "Alpha")


class EmptySearch(FakeSearch):
    def retrieve(
        self, candidate: ApartmentCandidate, apartment: Apartment, period: object
    ) -> tuple[NormalizedTransaction, ...]:
        return ()


class RegionalSearch(FakeSearch):
    def __init__(self) -> None:
        super().__init__()
        self.sido_code = ""

    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        self.sido_code = sido_code
        if sido_code != "41":
            return ()
        return (
            ApartmentCandidate(
                "gyeonggi", "원천레이크파크", "4146352000", "수원시 영통구", "경기도 수원시"
            ),
        )


class AddresslessSearch(FakeSearch):
    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        return (ApartmentCandidate("a", "Alpha", "1234567890", "Alpha lot", ""),)


class ProvinceListSearch(FakeSearch):
    def __init__(self, *, fail: bool = False) -> None:
        super().__init__()
        self.calls = 0
        self.cache_flags: list[bool] = []
        self.fail = fail

    def list_region(
        self, sido_code: str, *, use_cache: bool = True
    ) -> tuple[ApartmentCandidate, ...]:
        self.calls += 1
        self.cache_flags.append(use_cache)
        if self.fail:
            raise RuntimeError("fixture source unavailable")
        return tuple(
            ApartmentCandidate(
                key,
                value.display_name,
                "1234567890",
                f"{value.display_name} lot",
                f"{value.display_name} road",
            )
            for key, value in self.apartments.items()
        )


def test_search_result_selects_by_source_id_only() -> None:
    client = TestClient(create_app(search_service=FakeSearch(), store=SQLiteStore(":memory:")))
    searched = client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    assert searched.status_code == 200
    assert 'type="hidden" name="name"' not in searched.text
    assert 'type="hidden" name="source_id"' not in searched.text
    assert re.search(
        r'<button[^>]+type="submit"[^>]+name="source_id"[^>]+value="a"',
        searched.text,
    )
    response = client.post("/select", data={"source_id": "a"})
    assert response.status_code == 200
    assert "선택됨" in response.text
    assert "선택한 단지: <strong>Alpha</strong>" in response.text


def test_main_page_shows_local_api_usage_and_request_indicators(monkeypatch) -> None:
    monkeypatch.setenv("APT_ANALYZER_KAPT_LIST_DAILY_LIMIT", "7")
    store = SQLiteStore(":memory:")
    store.increment_api_usage("kapt_list")
    response = TestClient(create_app(search_service=FakeSearch(), store=store)).get("/")

    assert response.status_code == 200
    assert "공공 API 호출 현황" in response.text
    assert "1 / 7회" in response.text
    assert "포털 전체 사용량" in response.text
    assert 'hx-indicator="#search-progress"' in response.text
    assert 'hx-disabled-elt="find button"' in response.text
    assert 'id="update-progress"' not in response.text


def test_invalid_daily_api_limit_fails_at_composition(monkeypatch) -> None:
    monkeypatch.setenv("APT_ANALYZER_MOLIT_TRADE_DAILY_LIMIT", "0")

    with pytest.raises(ValueError, match="APT_ANALYZER_MOLIT_TRADE_DAILY_LIMIT"):
        create_app(search_service=FakeSearch(), store=SQLiteStore(":memory:"))


def test_default_usage_mapping_covers_all_external_endpoints() -> None:
    assert _ENDPOINT_TO_API_SERVICE == {
        KAPT_LIST_ENDPOINT: "kapt_list",
        KAPT_DETAIL_ENDPOINT: "kapt_detail",
        MOLIT_SALE_ENDPOINT: "molit_trade",
    }


def test_fresh_persistent_province_search_avoids_upstream_and_reuses_full_snapshot() -> None:
    store = SQLiteStore(":memory:")
    fetched_at = "2026-08-27T12:00:00+00:00"
    store.save_candidate_snapshot(
        "K-APT apartment list",
        "11",
        (ApartmentCandidate("a", "Alpha", "1234567890", "Alpha lot", "Alpha road"),),
        fetched_at=fetched_at,
    )
    source = ProvinceListSearch()
    client = TestClient(
        create_app(
            search_service=source,
            store=store,
            search_clock=lambda: datetime(2026, 8, 28, 11, 59, tzinfo=UTC),
        )
    )

    alpha = client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    beta = client.post("/search", data={"name": "Beta", "sido_code": "11"})

    assert source.calls == 0
    assert store.api_usage_snapshot(service_ids=("kapt_list",))["kapt_list"] == 0
    assert "Alpha" in alpha.text
    assert "검색 결과 없음" in beta.text
    assert "저장된 지역 목록" in alpha.text


def test_fresh_persistent_search_works_without_source_credentials(monkeypatch) -> None:
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    store = SQLiteStore(":memory:")
    store.save_candidate_snapshot(
        "K-APT apartment list",
        "11",
        (ApartmentCandidate("a", "Alpha", "1234567890", "Alpha lot", "Alpha road"),),
        fetched_at="2026-08-28T00:00:00+00:00",
    )
    client = TestClient(
        create_app(
            store=store,
            search_clock=lambda: datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
        )
    )

    response = client.post("/search", data={"name": "Alpha", "sido_code": "11"})

    assert response.status_code == 200
    assert "Alpha" in response.text
    assert "지역 목록을 갱신하지 못했습니다" not in response.text


def test_expired_province_search_revalidates_and_falls_back_to_stale_snapshot() -> None:
    store = SQLiteStore(":memory:")
    store.save_candidate_snapshot(
        "K-APT apartment list",
        "11",
        (ApartmentCandidate("a", "Alpha", "1234567890", "Alpha lot", "Alpha road"),),
        fetched_at="2026-08-27T11:59:00+00:00",
    )
    source = ProvinceListSearch(fail=True)
    client = TestClient(
        create_app(
            search_service=source,
            store=store,
            search_clock=lambda: datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
        )
    )

    response = client.post("/search", data={"name": "Alpha", "sido_code": "11"})

    assert source.calls == 1
    assert source.cache_flags == [False]
    assert "Alpha" in response.text
    assert "갱신에 실패해 마지막으로 성공한 저장 데이터를 사용합니다" in response.text
    assert (
        store.region_coverage("K-APT apartment list", "11")["fetched_at"]
        == "2026-08-27T11:59:00+00:00"
    )


def test_expired_province_search_replaces_snapshot_after_successful_refresh() -> None:
    store = SQLiteStore(":memory:")
    store.save_candidate_snapshot(
        "K-APT apartment list",
        "11",
        (ApartmentCandidate("a", "Alpha", "1234567890", "Alpha lot", "Alpha road"),),
        fetched_at="2026-08-27T11:59:00+00:00",
    )
    source = ProvinceListSearch()
    source.apartments = {"b": Apartment("b", "Beta")}
    clock_time = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    client = TestClient(
        create_app(search_service=source, store=store, search_clock=lambda: clock_time)
    )

    response = client.post("/search", data={"name": "Beta", "sido_code": "11"})

    assert source.calls == 1
    assert source.cache_flags == [False]
    assert "Beta" in response.text
    assert "Alpha" not in response.text
    coverage = store.region_coverage("K-APT apartment list", "11")
    assert coverage is not None and coverage["fetched_at"] == clock_time.isoformat()
    assert store.load_candidate_snapshot("K-APT apartment list", "11")[0]["source_id"] == "b"


def test_cache_miss_refresh_failure_shows_no_result_notice() -> None:
    store = SQLiteStore(":memory:")
    source = ProvinceListSearch(fail=True)
    client = TestClient(
        create_app(
            search_service=source,
            store=store,
            search_clock=lambda: datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
        )
    )

    response = client.post("/search", data={"name": "Alpha", "sido_code": "11"})

    assert response.status_code == 200
    assert "검색 결과가 없습니다" in response.text
    assert "지역 목록을 갱신하지 못해" in response.text
    assert "fixture source unavailable" not in response.text
    assert "https://" not in response.text


def test_select_hydrates_area_groups_from_persisted_transactions() -> None:
    store = SQLiteStore(":memory:")
    apartment = Apartment("a", "Alpha")
    store.save_apartment(apartment)
    for transaction_id, area in (("wide", "84"), ("compact", "59")):
        store.save_transaction(
            NormalizedTransaction(
                "a",
                date(2024, 1, 15),
                100,
                Decimal(area),
                TransactionType.BROKERED,
                False,
                source_name="MOLIT apartment sale transactions",
                source_record_id=transaction_id,
            )
        )
    client = TestClient(create_app(search_service=FakeSearch(), store=store))

    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    response = client.post("/select", data={"source_id": "a"})

    assert '<option value="floor-59">59㎡</option>' in response.text
    assert '<option value="floor-84">84㎡</option>' in response.text


def test_repeated_update_preserves_all_known_area_groups() -> None:
    store = SQLiteStore(":memory:")
    client = TestClient(create_app(search_service=FakeSearch(), store=store))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    store.save_transaction(
        NormalizedTransaction(
            "a",
            date(2024, 1, 15),
            100,
            Decimal("59"),
            TransactionType.BROKERED,
            False,
            source_name="MOLIT apartment sale transactions",
            source_record_id="compact",
        )
    )

    first = client.post("/update", data={"start": "2024-01-01", "end": "2024-01-31"})
    second = client.post("/update", data={"start": "2024-01-01", "end": "2024-01-31"})

    for response in (first, second):
        assert '<option value="floor-59">59㎡</option>' in response.text
        assert '<option value="floor-84">84㎡</option>' in response.text


def test_comparison_renders_shared_area_group_once_for_two_apartments() -> None:
    store = SQLiteStore(":memory:")
    for apartment_id in ("a", "b"):
        store.save_transaction(
            NormalizedTransaction(
                apartment_id,
                date(2024, 1, 15),
                100,
                Decimal("84"),
                TransactionType.BROKERED,
                False,
                source_name="MOLIT apartment sale transactions",
                source_record_id=f"{apartment_id}-84",
            )
        )
    client = TestClient(create_app(search_service=FakeSearch(), store=store))

    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    alpha = client.post("/select", data={"source_id": "a"})
    client.post("/search", data={"name": "Beta", "sido_code": "11"})
    beta = client.post("/select", data={"source_id": "b"})

    assert '<option value="floor-84">84㎡</option>' in alpha.text
    assert '<option value="floor-84">84㎡</option>' in beta.text
    comparison_form = beta.text.split('action="/comparison"', 1)[1].split("</form>", 1)[0]
    assert comparison_form.count('value="floor-84"') == 1


def test_select_rejects_stale_source_id_as_korean_page_error() -> None:
    client = TestClient(create_app(search_service=FakeSearch(), store=SQLiteStore(":memory:")))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    response = client.post("/select", data={"source_id": "stale-id"})
    assert response.status_code == 200
    assert "최근 검색 결과에서 선택할 수 없는 아파트입니다" in response.text


def test_empty_road_address_starts_with_lot_address_without_leading_break() -> None:
    client = TestClient(
        create_app(search_service=AddresslessSearch(), store=SQLiteStore(":memory:"))
    )
    response = client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    assert response.status_code == 200
    assert "candidate-results" in response.text
    assert "Alpha lot" in response.text
    assert "<div>Alpha lot</div>" in response.text


def test_root_route_returns_local_web_placeholder() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="ko">' in response.text
    assert "아파트 거래 흐름과 가격 변화를 살펴보세요" in response.text
    assert "아파트 검색 및 선택" in response.text
    assert "현재 상태" in response.text
    assert 'hx-post="/search"' in response.text
    assert "service-key" not in response.text
    assert response.text.count('<select name="sido_code"') == 1
    assert re.search(r'<option value="11"\s+selected>서울특별시</option>', response.text)


def test_search_forwards_selected_province_to_service() -> None:
    service = RegionalSearch()
    client = TestClient(create_app(search_service=service, store=SQLiteStore(":memory:")))

    response = client.post("/search", data={"name": "원천레이크파크", "sido_code": "41"})

    assert response.status_code == 200
    assert service.sido_code == "41"
    assert "원천레이크파크" in response.text
    assert "경기도 수원시" in response.text
    assert re.search(r'<option value="41"\s+selected>경기도</option>', response.text)


def test_search_rejects_unknown_province_code() -> None:
    service = RegionalSearch()
    client = TestClient(create_app(search_service=service, store=SQLiteStore(":memory:")))

    response = client.post("/search", data={"name": "원천레이크파크", "sido_code": "999"})

    assert response.status_code == 200
    assert "시·도를 선택해 주세요" in response.text
    assert service.sido_code == ""


def test_health_route_reports_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_screening_flow_uses_persisted_regional_coverage_and_exports_equivalent_context() -> None:
    store = SQLiteStore(":memory:")
    period = AnalysisPeriod(date(2024, 1, 1), date(2024, 1, 31))
    candidates = []
    for source_id, name in (("a", "Alpha"), ("b", "Beta")):
        apartment = Apartment(source_id, name)
        store.save_apartment(apartment)
        candidates.append(
            ApartmentCandidate(source_id, name, "1111010100", f"{name} lot", f"{name} road")
        )
        store.link_candidate_resolution(
            "K-APT apartment list",
            "11",
            source_id,
            source_id,
            resolved_at="2024-01-01T00:00:00+00:00",
        )
    store.save_candidate_snapshot(
        "K-APT apartment list", "11", candidates, fetched_at="2024-01-01T00:00:00+00:00"
    )
    store.update_incremental(
        Apartment("a", "Alpha"),
        period,
        lambda _month: (
            NormalizedTransaction(
                "a",
                date(2024, 1, 15),
                100,
                Decimal("84"),
                TransactionType.BROKERED,
                False,
                source_name="MOLIT apartment sale transactions",
                source_record_id="a-1",
            ),
        ),
        refresh_before=None,
        source_name="MOLIT apartment sale transactions",
    )
    app = create_app(store=store)
    client = TestClient(app)

    response = client.post(
        "/screen",
        data={
            "regions": "11",
            "candidate_source_ids": "a,b",
            "start": "2024-01-01",
            "end": "2024-01-31",
            "area_group": "all",
            "transaction_types": ["brokered"],
            "household_json": json.dumps(
                {
                    "a": {"count": 100, "scope": "complex", "source": "fixture-a"},
                    "b": {"count": 200, "scope": "complex", "source": "fixture-b"},
                }
            ),
            "rules": json.dumps(
                [
                    {
                        "metric": "transaction_count",
                        "operator": "gte",
                        "value": "1",
                        "unit": "count",
                        "method": "overall-period eligible population",
                    }
                ]
            ),
        },
    )

    assert response.status_code == 200
    assert "과거 데이터 기반 선별 결과" in response.text
    assert "Alpha" in response.text and "Beta" in response.text
    assert "포함" in response.text
    assert "분석 결과" not in response.text
    assert 'id="price-chart"' not in response.text
    assert "Download equivalent JSON export" not in response.text
    assert "선별 결과" in response.text
    assert "세대수 JSON" in response.text
    assert "지역 데이터 범위" in response.text
    assert "기준 기간" in response.text
    assert "비교 기간" in response.text
    assert "MDD 기간" in response.text
    assert "취소 거래 제외" in response.text
    assert "중개 거래" in response.text
    exported = client.get("/export?kind=screening")
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["status"] == "complete"
    assert payload["config"]["overall_period"] == {"start": "2024-01-01", "end": "2024-01-31"}
    assert payload["rules"][0]["metric"] == "transaction_count"
    assert payload["rules"][0]["method"] == "overall-period eligible population"
    assert payload["config"]["inclusion_policy"]["included_transaction_types"] == ["brokered"]
    assert payload["households"]["a"]["count"] == 100
    assert payload["households"]["b"]["count"] == 200
    results = {item["candidate_id"]: item for item in payload["results"]}
    assert results["a"]["included"] is True
    assert results["a"]["values"]["transaction_count"] == "1"
    assert results["b"]["included"] is False
    assert "coverage" in results["b"]["unavailable"]


def test_configured_secret_never_reaches_html_or_export(monkeypatch) -> None:
    secret = "encoded-secret-value"
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", secret)
    client = TestClient(create_app(store=SQLiteStore(":memory:")))
    assert secret not in client.get("/").text
    assert secret not in client.get("/export").text


def test_default_service_uses_dotenv_credential_loader(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    (tmp_path / ".env").write_text("DATA_GO_KR_SERVICE_KEY=dotenv-sentinel\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    service = _default_service()

    assert isinstance(service, ApartmentDataService)
    assert not isinstance(service, MissingKeyService)


def test_default_service_retains_missing_credential_behavior(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    assert isinstance(_default_service(), MissingKeyService)


def test_comparison_flow_renders_shared_context_and_export() -> None:
    app = create_app(search_service=FakeSearch(), store=SQLiteStore(":memory:"))
    client = TestClient(app)
    for source_id, name in (("a", "Alpha"), ("b", "Beta")):
        client.post("/search", data={"name": name, "sido_code": "11"})
        response = client.post(
            "/select",
            data={
                "source_id": source_id,
                "name": name,
                "legal_dong_code": "1234567890",
                "lot_address": f"{name} lot",
                "road_address": f"{name} road",
            },
        )
        assert response.status_code == 200
    response = client.post(
        "/comparison",
        data={
            "apartment_ids": "a,b",
            "area_group": "floor-84",
            "transaction_types": ["brokered"],
            "start": "2024-01-01",
            "end": "2024-12-31",
            "turnover_start": "2024-01-01",
            "turnover_end": "2024-12-31",
            "baseline_start": "2024-01-01",
            "baseline_end": "2024-06-30",
            "comparison_start": "2024-07-01",
            "comparison_end": "2024-12-31",
            "mdd_start": "2024-01-01",
            "mdd_end": "2024-12-31",
        },
    )
    assert response.status_code == 200
    assert "아파트 비교 결과" in response.text
    assert 'id="price-chart"' not in response.text
    assert "월별 거래량" not in response.text
    assert "월별 가격" not in response.text
    exported = client.get("/export?kind=comparison")
    assert exported.status_code == 200
    assert exported.json()["config"]["overall_period"] == {
        "start": "2024-01-01",
        "end": "2024-12-31",
    }
    assert [subject["apartment"]["display_name"] for subject in exported.json()["subjects"]] == [
        "Alpha",
        "Beta",
    ]
    assert "전체 거래" in response.text
    assert "유효 거래" in response.text
    assert "적용한 공통 분석 조건" in response.text
    assert "거래회전율 기간" in response.text
    assert "취소 거래 제외" in response.text
    assert "중개 거래" in response.text
    assert "floor-84" in response.text


def test_update_uses_full_calendar_month_and_provenance() -> None:
    store = SQLiteStore(":memory:")
    app = create_app(search_service=FakeSearch(), store=store)
    client = TestClient(app)
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post(
        "/select",
        data={
            "source_id": "a",
            "name": "Alpha",
            "legal_dong_code": "1234567890",
            "lot_address": "Alpha lot",
            "road_address": "Alpha road",
        },
    )
    response = client.post("/update", data={"start": "2024-01-01", "end": "2024-01-31"})
    assert response.status_code == 200
    assert len(store.load_transactions("a")) == 1
    assert "갱신 완료" in response.text
    assert "근거 데이터 갱신 결과" in response.text
    assert "202401" in response.text
    assert "새로 수집됨" in response.text
    assert "분석 결과" not in response.text
    assert 'id="analysis-data"' not in response.text
    assert "Download equivalent JSON export" not in response.text


def test_analysis_renders_korean_reproducible_context() -> None:
    client = TestClient(create_app(search_service=FakeSearch(), store=SQLiteStore(":memory:")))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post(
        "/select",
        data={
            "source_id": "a",
            "name": "Alpha",
            "legal_dong_code": "x",
            "lot_address": "x",
            "road_address": "x",
        },
    )
    client.post("/update", data={"start": "2024-01-01", "end": "2024-01-01"})
    response = client.post(
        "/analysis",
        data={
            "start": "2024-01-01",
            "end": "2024-01-01",
            "household_count": "100",
            "household_scope": "complex",
            "household_source": "fixture",
        },
    )
    assert response.status_code == 200
    assert 'aria-label="핵심 분석 지표"' in response.text
    for header in ("지표", "결과", "계산 근거", "적용 기간", "해석"):
        assert header in response.text
    assert "분석 조건 자세히 보기" in response.text
    assert "· 지표: 거래회전율" not in response.text
    assert "계산 불가: 거래회전율은 완전한 연속 12개월이 필요합니다" in response.text
    assert "계산 불가: 거래유지율은 인접한 12개월 구간 두 개가 필요합니다" in response.text
    assert "계산 불가: 관측된 월이 두 개 미만입니다" in response.text
    for text in (
        "Alpha",
        "면적",
        "거래 포함 정책",
        "거래회전율",
        "거래유지율",
        "최대낙폭(MDD)",
        "월별 가격 중간값",
        "거래 건수",
        "유효한 빈 결과",
    ):
        assert text in response.text
    assert ">turnover_start<" not in response.text


def test_single_analysis_centers_overall_period_and_result_editor() -> None:
    client = TestClient(create_app(search_service=FakeSearch(), store=SQLiteStore(":memory:")))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    selected = client.post("/select", data={"source_id": "a"})
    assert selected.status_code == 200
    assert 'name="start"' in selected.text and 'name="end"' in selected.text
    assert "고급 분석 설정" in selected.text

    client.post("/update", data={"start": "2024-01-01", "end": "2024-01-01"})
    result = client.post("/analysis", data={"start": "2024-01-01", "end": "2024-01-01"})
    assert 'id="analysis-result-editor"' in result.text
    assert 'hx-post="/analysis"' in result.text


def test_analysis_keeps_monthly_gap_without_retrieval() -> None:
    service = FakeSearch()
    client = TestClient(create_app(search_service=service, store=SQLiteStore(":memory:")))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post("/update", data={"start": "2024-01-01", "end": "2024-01-31"})
    response = client.post("/analysis", data={"start": "2024-01-01", "end": "2024-02-29"})
    assert response.status_code == 200
    assert "2024-01" in response.text and "2024-02" in response.text
    assert "누락됨" in response.text
    payload = client.get("/export?kind=analysis").json()
    missing_price = next(item for item in payload["monthly_series"] if item["period"] == "2024-02")
    missing_volume = next(item for item in payload["volume_series"] if item["period"] == "2024-02")
    assert missing_price["transaction_count"] is None
    assert missing_volume["value"] is None
    assert payload["coverage"]["202402"] == "missing"


def test_analysis_marks_current_month_incomplete_with_injected_today() -> None:
    client = TestClient(
        create_app(
            search_service=FakeSearch(),
            store=SQLiteStore(":memory:"),
            analysis_today=lambda: date(2026, 8, 30),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    response = client.post("/analysis", data={"start": "2026-08-01", "end": "2026-08-30"})
    assert response.status_code == 200
    assert "불완전" in response.text


def test_result_editor_round_trips_advanced_context_and_overrides() -> None:
    service = FakeSearch()
    client = TestClient(create_app(search_service=service, store=SQLiteStore(":memory:")))
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    client.post("/update", data={"start": "2024-01-01", "end": "2024-01-31"})
    response = client.post(
        "/analysis",
        data={
            "start": "2024-01-01",
            "end": "2024-01-31",
            "area_group": "floor-84",
            "include_cancelled": "true",
            "transaction_types": ["brokered"],
            "household_count": "100",
            "household_scope": "floor-84",
            "household_source": "fixture",
            "turnover_start": "2024-01-01",
            "turnover_end": "2024-01-31",
            "mdd_start": "2024-01-01",
            "mdd_end": "2024-01-31",
        },
    )
    assert response.status_code == 200
    retrieve_calls_after_update = service.retrieve_calls
    editor_html = response.text.split('id="analysis-result-editor"', 1)[1].split("</form>", 1)[0]
    assert re.search(r'<option value="floor-84"\s+selected>', editor_html)
    assert re.search(r'name="transaction_types"\s+value="brokered"\s+checked', editor_html)
    assert not re.search(r'name="transaction_types"\s+value="direct"\s+checked', editor_html)
    assert re.search(r'name="include_cancelled"\s+checked', editor_html)
    assert 'value="2024-01-01"' in editor_html
    payload = client.get("/export?kind=analysis").json()
    assert payload["ui_context"]["area_group_key"] == "floor-84"
    assert payload["ui_context"]["metric_period_overrides"]["turnover_start"] == "2024-01-01"
    assert payload["ui_context"]["metric_period_sources"]["mdd"] == "override"
    assert payload["ui_context"]["household"]["count"] == 100
    assert payload["ui_context"]["inclusion_policy"]["transaction_types"] == ["brokered"]

    reanalyzed = client.post(
        "/analysis",
        data={
            "start": "2024-01-01",
            "end": "2024-01-31",
            "area_group": "floor-84",
            "include_cancelled": "true",
            "transaction_types": ["brokered"],
            "household_count": "100",
            "household_scope": "floor-84",
            "household_source": "fixture",
            "turnover_start": "2024-01-01",
            "turnover_end": "2024-01-31",
            "mdd_start": "2024-01-01",
            "mdd_end": "2024-01-31",
        },
    )
    assert reanalyzed.status_code == 200
    assert service.retrieve_calls == retrieve_calls_after_update
    assert client.get("/export?kind=analysis").json()["ui_context"]["area_group_key"] == "floor-84"


def test_rolling_export_uses_fixed_completed_months_and_keeps_partial_month_evidence() -> None:
    service = FakeSearch()
    store = SQLiteStore(":memory:")
    apartment = Apartment("a", "Alpha")
    source_name = "MOLIT apartment sale transactions"

    def transaction_for_month(month: str) -> tuple[NormalizedTransaction, ...]:
        return (
            NormalizedTransaction(
                apartment.internal_id,
                date(int(month[:4]), int(month[4:]), 15),
                100_000_000 + int(month),
                Decimal("84"),
                TransactionType.BROKERED,
                False,
                source_name=source_name,
                source_record_id=f"rolling-{month}",
            ),
        )

    store.update_incremental(
        apartment,
        AnalysisPeriod(date(2024, 8, 1), date(2026, 8, 31)),
        transaction_for_month,
        source_name=source_name,
    )
    client = TestClient(
        create_app(
            search_service=service,
            store=store,
            analysis_today=lambda: date(2026, 8, 30),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    response = client.post(
        "/analysis",
        data={
            "start": "2024-08-01",
            "end": "2026-08-30",
            "transaction_types": ["brokered"],
            "household_count": "100",
            "household_scope": "complex",
            "household_source": "fixture",
        },
    )
    assert response.status_code == 200
    assert service.retrieve_calls == 0
    payload = client.get("/export?kind=analysis").json()
    assert payload["ui_context"]["metric_periods"] == {
        "turnover": {"start": "2025-08-01", "end": "2026-07-31"},
        "baseline": {"start": "2024-08-01", "end": "2025-07-31"},
        "comparison": {"start": "2025-08-01", "end": "2026-07-31"},
        "mdd": {"start": "2024-08-01", "end": "2026-08-30"},
    }
    assert payload["ui_context"]["metric_period_sources"] == {
        "turnover": "automatic",
        "retention": "automatic",
        "mdd": "overall",
    }
    assert payload["ui_context"]["rolling_anchor"] == "2026-07"
    assert payload["ui_context"]["metric_methods"] == {
        "turnover": "completed-calendar-month-12-month-window",
        "retention": "completed-calendar-month-12-vs-prior-12",
        "mdd": "observed monthly median",
    }
    assert payload["turnover"]["annualization_method"] == (
        "completed-calendar-month-12-month-window"
    )
    assert payload["retention"]["annualization_method"] == (
        "completed-calendar-month-12-vs-prior-12"
    )
    august_price = next(item for item in payload["monthly_series"] if item["period"] == "2026-08")
    august_volume = next(item for item in payload["volume_series"] if item["period"] == "2026-08")
    august_trend = next(item for item in payload["trend_series"] if item["period"] == "2026-08")
    assert august_price["value"] is not None
    assert august_volume["value"] == 1
    assert august_price["coverage_status"] == august_volume["coverage_status"] == "fresh"
    assert august_price["period_status"] == august_volume["period_status"] == "incomplete"
    assert august_trend["value"] is None and august_trend["period_status"] == "incomplete"
    assert payload["data_status"] != "coverage-limited"
    assert payload["coverage"]["202608"] == "fresh"
    assert payload["observations"]["202608"] == "observed"


def test_screening_structured_controls_cover_supported_metrics_and_infer_units() -> None:
    client = TestClient(create_app(store=SQLiteStore(":memory:")))
    response = client.get("/")
    for metric in (
        "median_price_krw",
        "median_area_sqm",
        "transaction_count",
        "turnover_ratio",
        "retention_ratio",
        "mdd_ratio",
    ):
        assert f'value="{metric}"' in response.text
    for label in (
        "중간 거래가격",
        "중간 전용면적",
        "거래량",
        "거래회전율",
        "거래유지율",
        "최대낙폭(MDD)",
        "다름",
    ):
        assert label in response.text
    assert ">turnover_start<" not in response.text


def test_screening_structured_submission_preserves_inferred_machine_contract() -> None:
    client = TestClient(create_app(store=SQLiteStore(":memory:")))
    response = client.post(
        "/screen",
        data={
            "regions": "11",
            "screen_start": "2024-01-01",
            "screen_end": "2024-01-31",
            "rule_metric": "median_price_krw",
            "rule_operator": "gte",
            "rule_value": "100000000",
            "rule_unit": "",
            "rule_method": "",
            "rules": "",
            "household_json": "{}",
        },
    )
    assert response.status_code == 200
    assert "중간 거래가격" in response.text
    payload = client.get("/export?kind=screening").json()
    assert payload["status"] == "unavailable"
    assert payload["rules"][0] == {
        "metric": "median_price_krw",
        "operator": "gte",
        "value": "100000000",
        "unit": "KRW",
        "method": "overall-period eligible population",
    }


def test_all_valid_empty_months_are_analyzable_zero_volume_and_null_price() -> None:
    store = SQLiteStore(":memory:")
    app = create_app(search_service=EmptySearch(), store=store)
    client = TestClient(app)
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post(
        "/select",
        data={
            "source_id": "a",
            "name": "Alpha",
            "legal_dong_code": "x",
            "lot_address": "x",
            "road_address": "x",
        },
    )
    client.post("/update", data={"start": "2024-01-01", "end": "2024-01-31"})
    response = client.post("/analysis", data={"start": "2024-01-01", "end": "2024-01-31"})
    assert response.status_code == 200
    assert "데이터 상태: 유효한 빈 결과" in response.text
    assert "2024-01" in response.text and ">0<" in response.text
    assert "사용 불가" in response.text

    restarted = TestClient(create_app(search_service=EmptySearch(), store=store))
    restarted.post("/search", data={"name": "Alpha", "sido_code": "11"})
    restarted.post("/select", data={"source_id": "a"})
    restarted.post("/analysis", data={"start": "2024-01-01", "end": "2024-01-31"})
    assert restarted.get("/export?kind=analysis").json()["coverage"]["202401"] == "valid_empty"


def test_comparison_gates_subject_with_missing_coverage() -> None:
    store = SQLiteStore(":memory:")
    app = create_app(search_service=FakeSearch(), store=store)
    client = TestClient(app)
    for source_id, name in (("a", "Alpha"), ("b", "Beta")):
        client.post("/search", data={"name": name, "sido_code": "11"})
        client.post(
            "/select",
            data={
                "source_id": source_id,
                "name": name,
                "legal_dong_code": "x",
                "lot_address": "x",
                "road_address": "x",
            },
        )
    response = client.post(
        "/comparison",
        data={
            "apartment_ids": ["a", "b"],
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
    )
    assert response.status_code == 200
    assert "데이터 범위를 사용할 수 없습니다" in response.text
    assert "전체 기간" in response.text
    assert "거래회전율 기간" in response.text
    assert "기준 기간" in response.text
    assert "비교 기간" in response.text
    assert "MDD 기간" in response.text
    assert "누락됨" in response.text
    exported = client.get("/export?kind=comparison").json()
    assert all(subject["available"] is False for subject in exported["subjects"])
    assert exported["coverage"]["a"]["202401"] == "missing"


def test_comparison_preserves_valid_empty_subject_status() -> None:
    store = SQLiteStore(":memory:")
    app = create_app(search_service=EmptySearch(), store=store)
    client = TestClient(app)
    for source_id, name in (("a", "Alpha"), ("b", "Beta")):
        client.post("/search", data={"name": name, "sido_code": "11"})
        client.post(
            "/select",
            data={
                "source_id": source_id,
                "name": name,
                "legal_dong_code": "x",
                "lot_address": "x",
                "road_address": "x",
            },
        )
        client.post("/update", data={"start": "2024-01-01", "end": "2024-01-31"})
    response = client.post(
        "/comparison",
        data={"apartment_ids": ["a", "b"], "start": "2024-01-01", "end": "2024-01-31"},
    )
    assert response.status_code == 200
    exported = client.get("/export?kind=comparison").json()
    assert all(subject["data_status"] == "valid_empty" for subject in exported["subjects"])


def test_inventory_zero_matching_group_is_unavailable() -> None:
    record = InventorySummary(
        InventoryState.VERIFIED,
        (InventoryRow("u1", "101", "1", Decimal("49.76")),),
        ((Decimal("49.76"), 1),),
        1,
        collected_at=datetime(2026, 9, 10, tzinfo=UTC),
        source="Building HUB",
        scope=InventoryScope("root", ("title",), ("u1",), (), (), True),
        data_complete=True,
        kapt_total=1,
        kapt_bands=(("≤60㎡", 1),),
    )
    group = AreaGroup("floor-59", "59㎡", frozenset({Decimal("59.2")}))
    assert (
        _inventory_group_households(
            InventoryRecord(record, "Building HUB", "2026-09-10T00:00:00+00:00"), group
        )
        is None
    )


def test_verified_inventory_profile_is_visible_without_kapt_profile(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    apartment = Apartment("a", "Alpha")
    _save_two_year_metric_evidence(store, apartment)
    summary = InventorySummary(
        InventoryState.VERIFIED,
        (InventoryRow("u1", "101", "1", Decimal("84.92")),),
        ((Decimal("84.92"), 1),),
        1,
        collected_at=datetime(2026, 9, 10, tzinfo=UTC),
        source="Building HUB",
        scope=InventoryScope("root", ("title",), ("u1",), (), (), True),
        data_complete=True,
        kapt_total=1,
        kapt_bands=((">60–85㎡", 1),),
    )
    store.save_inventory("a", summary, source="Building HUB")
    client = TestClient(
        create_app(
            search_service=FakeSearch(),
            store=store,
            analysis_today=lambda: date(2025, 1, 15),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    response = client.post(
        "/analysis",
        data={"start": "2023-01-01", "end": "2024-12-31", "area_group": "floor-84"},
    )
    assert response.status_code == 200
    assert "검증된 전용면적별 세대수" in response.text
    assert "84.92㎡" in response.text
    assert "Building HUB" in response.text
    assert "2026-09-10T00:00:00+00:00" in response.text
    assert "선택 단지 전체" in response.text


def test_manual_matching_group_source_does_not_receive_inventory_timestamp(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "data.db")
    apartment = Apartment("a", "Alpha")
    _save_two_year_metric_evidence(store, apartment)
    inventory_rows = tuple(
        InventoryRow(f"u{index}", "101", str(index), Decimal("84.92")) for index in range(99)
    )
    inventory = InventorySummary(
        InventoryState.VERIFIED,
        inventory_rows,
        ((Decimal("84.92"), 99),),
        99,
        collected_at=datetime(2026, 9, 10, tzinfo=UTC),
        source="Building HUB",
        scope=InventoryScope(
            "root", ("title",), tuple(row.unit_key for row in inventory_rows), (), (), True
        ),
        data_complete=True,
        kapt_total=99,
        kapt_bands=((">60–85㎡", 99),),
    )
    store.save_inventory(apartment.internal_id, inventory, source="Building HUB")
    client = TestClient(
        create_app(
            search_service=FakeSearch(),
            store=store,
            analysis_today=lambda: date(2025, 1, 15),
        )
    )
    client.post("/search", data={"name": "Alpha", "sido_code": "11"})
    client.post("/select", data={"source_id": "a"})
    response = client.post(
        "/analysis",
        data={
            "start": "2023-01-01",
            "end": "2024-12-31",
            "area_group": "floor-84",
            "household_count": "100",
            "household_scope": "floor-84",
            "household_source": "Building HUB",
        },
    )
    assert response.status_code == 200
    assert client.get("/export?kind=analysis").json()["ui_context"]["household"] == {
        "count": 100,
        "scope": "floor-84",
        "source": "Building HUB",
        "fetched_at": None,
    }
