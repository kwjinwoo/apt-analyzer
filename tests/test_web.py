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
    IdentityResolution,
    ResolutionStatus,
)
from apt_analyzer.domain import AnalysisPeriod, Apartment, NormalizedTransaction, TransactionType
from apt_analyzer.persistence import SQLiteStore
from apt_analyzer.web import (
    _ENDPOINT_TO_API_SERVICE,
    MissingKeyService,
    _default_service,
    create_app,
)


class FakeSearch:
    def __init__(self) -> None:
        self.apartments = {"a": Apartment("a", "Alpha"), "b": Apartment("b", "Beta")}

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
    for text in (
        "분석 조건과 지표",
        "Alpha",
        "면적",
        "거래 포함 정책",
        "회전율 기간",
        "기준 기간",
        "비교 기간",
        "MDD 기간",
        "거래회전율",
        "거래유지율",
        "최대낙폭(MDD)",
        "월별 가격 중간값",
        "거래 건수",
        "유효한 빈 결과",
    ):
        assert text in response.text
    assert ">turnover_start<" not in response.text


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
    app = create_app(search_service=EmptySearch(), store=SQLiteStore(":memory:"))
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
