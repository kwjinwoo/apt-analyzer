from datetime import UTC, datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apt_analyzer.apartment_data import (
    ApartmentCandidate,
    ApartmentProfile,
    AreaHouseholdBand,
    IdentityResolution,
    ResolutionStatus,
)
from apt_analyzer.building_hub import InventoryRow, InventoryScope, InventoryState, InventorySummary
from apt_analyzer.domain import AnalysisPeriod, Apartment, NormalizedTransaction
from apt_analyzer.persistence import SQLiteStore
from apt_analyzer.web import create_app


class FakeInventory:
    def __init__(self) -> None:
        self.calls = 0
        self.result = _verified_summary()

    def collect(
        self,
        candidate: ApartmentCandidate,
        *,
        kapt_total: int | None = None,
        kapt_bands: tuple[tuple[str, int], ...] = (),
    ) -> InventorySummary:
        self.calls += 1
        return self.result


def _verified_summary() -> InventorySummary:
    return InventorySummary(
        InventoryState.VERIFIED,
        (InventoryRow("u1", "101", "1", Decimal("59.82")),),
        ((Decimal("59.82"), 1),),
        1,
        collected_at=datetime(2026, 9, 9, tzinfo=UTC),
        scope=InventoryScope("root", ("title",), ("u1",), (), (), True),
        data_complete=True,
        kapt_total=1,
        kapt_bands=(("≤60㎡", 1),),
    )


def test_inventory_refresh_renders_counts_shares_and_provenance() -> None:
    fake = FakeInventory()
    store = SQLiteStore(":memory:")
    app = create_app(search_service=None, store=store, inventory_service=fake)
    candidate = ApartmentCandidate("a", "Alpha", "1234567890", "lot", "road")
    app.state.workspace.candidate = candidate
    app.state.workspace.apartment = Apartment("a", "Alpha")
    with TestClient(app) as client:
        response = client.post("/inventory/refresh")
    assert response.status_code == 200
    assert fake.calls == 1
    assert "59.82㎡" in response.text
    assert "100.00%" in response.text
    assert "건축물대장 검증 결과" in response.text
    assert "범위: 선택 단지 전체" in response.text
    assert "unit_key" not in response.text
    assert "root_key" not in response.text


class ConfigurableInventory(FakeInventory):
    def __init__(self, result: InventorySummary) -> None:
        super().__init__()
        self.result = result

    def collect(
        self,
        candidate: ApartmentCandidate,
        *,
        kapt_total: int | None = None,
        kapt_bands: tuple[tuple[str, int], ...] = (),
    ) -> InventorySummary:
        self.calls += 1
        return self.result


class SearchFixture:
    def __init__(self) -> None:
        self.candidate = ApartmentCandidate("a", "Alpha", "1234567890", "lot", "road")
        self.apartment = Apartment("a", "Alpha")

    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        return (self.candidate,)

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        enriched = ApartmentCandidate(
            "a",
            "Alpha",
            "1234567890",
            "lot",
            "road",
            1,
            "KAPT",
            ApartmentProfile(area_bands=(AreaHouseholdBand("≤60㎡", 1),)),
        )
        return enriched, IdentityResolution(ResolutionStatus.RESOLVED, (enriched,), self.apartment)

    def retrieve(
        self, candidate: ApartmentCandidate, apartment: Apartment, period: AnalysisPeriod
    ) -> tuple[NormalizedTransaction, ...]:
        return ()


def _prepared_app(inventory: FakeInventory) -> tuple[FastAPI, SQLiteStore]:
    store = SQLiteStore(":memory:")
    app = create_app(search_service=SearchFixture(), store=store, inventory_service=inventory)
    app.state.workspace.candidate = SearchFixture().candidate
    app.state.workspace.apartment = Apartment("a", "Alpha")
    return app, store


def test_failed_inventory_refresh_preserves_last_verified_table_and_shows_latest_attempt() -> None:
    good = FakeInventory()
    app, _ = _prepared_app(good)
    with TestClient(app) as client:
        client.post("/inventory/refresh")
        good.result = InventorySummary(
            InventoryState.UNAVAILABLE,
            (),
            (),
            None,
            "서비스 오류",
            datetime(2026, 9, 10, tzinfo=UTC),
        )
        response = client.post("/inventory/refresh")
    assert "59.82㎡" in response.text
    assert "사용 불가" in response.text


def test_selection_analysis_and_export_never_refresh_inventory() -> None:
    inventory = FakeInventory()
    app, _ = _prepared_app(inventory)
    with TestClient(app) as client:
        client.post("/search", data={"name": "Alpha", "sido_code": "11"})
        assert inventory.calls == 0
        client.post("/select", data={"source_id": "a"})
        assert inventory.calls == 0
        client.post("/interests/save")
        client.post("/interests/select", data={"apartment_id": "a"})
        assert inventory.calls == 0
        client.post(
            "/analysis",
            data={"start": "2024-01-01", "end": "2024-12-31", "household_count": "1"},
        )
        assert inventory.calls == 0
        client.get("/export?kind=analysis")
    assert inventory.calls == 0


def test_changed_selection_during_inventory_collection_is_not_saved() -> None:
    inventory = FakeInventory()
    app, store = _prepared_app(inventory)
    original = app.state.workspace.apartment

    def mutate(
        candidate: ApartmentCandidate,
        *,
        kapt_total: int | None = None,
        kapt_bands: tuple[tuple[str, int], ...] = (),
    ) -> InventorySummary:
        app.state.workspace.apartment = Apartment("other", "Other")
        return inventory.result

    inventory.collect = mutate
    with TestClient(app) as client:
        client.post("/inventory/refresh")
    assert store.load_inventory("a") is None
    assert original is not None


def test_household_refresh_reconciles_latest_mismatch_without_inventory_network() -> None:
    inventory = FakeInventory()
    app, store = _prepared_app(inventory)
    mismatch = _verified_summary()
    mismatch = InventorySummary(
        InventoryState.MISMATCH,
        mismatch.rows,
        mismatch.counts,
        1,
        "old K-APT mismatch",
        mismatch.collected_at,
        mismatch.source,
        None,
        mismatch.normalization_version,
        mismatch.mapping_version,
        mismatch.scope,
        True,
        2,
        (("≤60㎡", 2),),
    )
    store.save_inventory("a", mismatch, source="Building HUB")
    with TestClient(app) as client:
        before = inventory.calls
        client.post("/household/refresh")
    assert inventory.calls == before
    loaded = store.load_inventory("a")
    assert loaded is not None and loaded.summary.state is InventoryState.VERIFIED


def test_analysis_export_contains_inventory_aggregate_without_unit_identifiers() -> None:
    inventory = FakeInventory()
    app, store = _prepared_app(inventory)
    store.save_inventory("a", inventory.result, source="Building HUB")
    with TestClient(app) as client:
        response = client.post(
            "/analysis", data={"start": "2024-01-01", "end": "2024-12-31", "household_count": "1"}
        )
        assert response.status_code == 200
        payload = client.get("/export?kind=analysis").json()
    assert payload["complex_profile"]["inventory"]["status"] == "verified"
    assert payload["complex_profile"]["inventory"]["counts"][0]["share_percent"] == "100.00"
    assert "unit_key" not in str(payload)


def test_analysis_export_keeps_attempt_only_inventory_status_and_reason() -> None:
    inventory = FakeInventory()
    app, store = _prepared_app(inventory)
    failed = InventorySummary(
        InventoryState.MISMATCH,
        (InventoryRow("u1", "101", "1", Decimal("59.82")),),
        ((Decimal("59.82"), 1),),
        1,
        "inventory count differs from K-APT total",
        datetime(2026, 9, 10, tzinfo=UTC),
        "Building HUB",
        None,
        "normalization-v2",
        "mapping-v3",
        InventoryScope("root", ("title",), ("u1",), (), (), True),
        True,
        2,
    )
    store.save_inventory("a", failed, source="Building HUB")
    with TestClient(app) as client:
        client.post(
            "/analysis", data={"start": "2024-01-01", "end": "2024-12-31", "household_count": "1"}
        )
        payload = client.get("/export?kind=analysis").json()
    inventory_payload = payload["complex_profile"]["inventory"]
    assert inventory_payload["status"] == "mismatch"
    assert inventory_payload["counts"] == []
    assert (
        inventory_payload["latest_attempt"]["reason"]
        == "건축물대장 세대수가 K-APT 전체 세대수와 다릅니다."
    )
    assert "unit_key" not in str(payload)
