import re
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from apt_analyzer.apartment_data import (
    ApartmentCandidate,
    ApartmentDataService,
    IdentityResolution,
    ResolutionStatus,
)
from apt_analyzer.domain import Apartment, NormalizedTransaction, TransactionType
from apt_analyzer.persistence import SQLiteStore
from apt_analyzer.web import MissingKeyService, _default_service, create_app


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


def test_root_route_returns_local_web_placeholder() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "apt-analyzer local web" in response.text
    assert 'hx-post="/search"' in response.text
    assert "service-key" not in response.text
    assert response.text.count("<option value=") == 17
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
    assert "Select a valid province" in response.text
    assert service.sido_code == ""


def test_health_route_reports_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    assert "Common analysis context" in response.text
    assert 'id="price-chart"' not in response.text
    assert "Underlying volume" not in response.text
    assert "Underlying price" not in response.text
    assert "Overall start" in response.text
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
    assert "Raw" in response.text
    assert "Eligible" in response.text


def test_update_uses_full_calendar_month_and_provenance() -> None:
    store = SQLiteStore(":memory:")
    app = create_app(search_service=FakeSearch(), store=store)
    client = TestClient(app)
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
    assert "fetched" in response.text
    assert "Analysis result" not in response.text
    assert 'id="analysis-data"' not in response.text
    assert "Download equivalent JSON export" not in response.text


def test_all_valid_empty_months_are_analyzable_zero_volume_and_null_price() -> None:
    app = create_app(search_service=EmptySearch(), store=SQLiteStore(":memory:"))
    client = TestClient(app)
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
    assert "Data status: valid_empty" in response.text
    assert "2024-01" in response.text and ">0<" in response.text
    assert "Unavailable" in response.text


def test_comparison_gates_subject_with_missing_coverage() -> None:
    store = SQLiteStore(":memory:")
    app = create_app(search_service=FakeSearch(), store=store)
    client = TestClient(app)
    for source_id, name in (("a", "Alpha"), ("b", "Beta")):
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
    assert "coverage unavailable" in response.text
    exported = client.get("/export?kind=comparison").json()
    assert all(subject["available"] is False for subject in exported["subjects"])


def test_comparison_preserves_valid_empty_subject_status() -> None:
    store = SQLiteStore(":memory:")
    app = create_app(search_service=EmptySearch(), store=store)
    client = TestClient(app)
    for source_id, name in (("a", "Alpha"), ("b", "Beta")):
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
