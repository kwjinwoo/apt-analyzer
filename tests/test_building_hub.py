from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apt_analyzer.acquisition import DataGoKrClient, SourceError
from apt_analyzer.apartment_data import ApartmentCandidate
from apt_analyzer.building_hub import (
    BuildingHubClient,
    BuildingInventoryService,
    InventoryRow,
    InventoryScope,
    InventoryState,
    InventorySummary,
    normalize_inventory,
    parse_lot_address,
    resolve_scope,
)
from apt_analyzer.persistence import SQLiteStore


def test_normalize_inventory_counts_exact_residential_exclusive_units() -> None:
    expos = (
        {"mgmBldrgstPk": "a", "dongNm": "101", "hoNm": "1"},
        {"mgmBldrgstPk": "b", "dongNm": "102", "hoNm": "1"},
    )
    areas = (
        {"mgmBldrgstPk": "a", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "59.82"},
        {"mgmBldrgstPk": "b", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "59.82"},
        {"mgmBldrgstPk": "a", "exposPubuseGbCd": "2", "mainPurpsCd": "02001", "area": "10"},
    )
    result = normalize_inventory(expos, areas)
    assert result.state is InventoryState.VERIFIED
    assert result.counts == ((Decimal("59.82"), 2),)


def test_normalize_inventory_rejects_conflicting_area_for_one_unit() -> None:
    expos = ({"mgmBldrgstPk": "a", "dongNm": "101", "hoNm": "1"},)
    areas = (
        {"mgmBldrgstPk": "a", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "59.82"},
        {"mgmBldrgstPk": "a", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "84.90"},
    )
    assert normalize_inventory(expos, areas).state is InventoryState.PARTIAL


def test_hub_pagination_rejects_repeated_page() -> None:
    payload = b"<response><header><resultCode>000</resultCode></header><body><items><item><id>x</id></item></items><totalCount>3</totalCount><pageNo>1</pageNo><numOfRows>1</numOfRows></body></response>"
    client = DataGoKrClient("key", transport=lambda _url, _timeout: payload)
    with pytest.raises(SourceError, match="(repeated page|unexpected page)"):
        BuildingHubClient(client, page_size=1, max_pages=3).fetch_all(
            "getBrExposInfo", {}, source="Building HUB"
        )


def test_inventory_persistence_keeps_last_good_when_new_attempt_is_partial(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "inventory.db")
    good = normalize_inventory(
        ({"mgmBldrgstPk": "a", "dongNm": "101", "hoNm": "1"},),
        ({"mgmBldrgstPk": "a", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "59.82"},),
    )
    good = replace(
        good,
        collected_at=datetime(2026, 9, 9, tzinfo=UTC),
        scope=InventoryScope("root", ("title",), ("a",), (), (), True),
        data_complete=True,
        kapt_total=1,
        kapt_bands=(("≤60㎡", 1),),
    )
    store.save_inventory("apt", good, source="Building HUB")
    store.save_inventory(
        "apt",
        InventorySummary(
            InventoryState.PARTIAL,
            (),
            (),
            None,
            "incomplete",
            datetime(2026, 9, 9, 0, 1, tzinfo=UTC),
        ),
        source="Building HUB",
    )
    loaded = store.load_inventory("apt")
    assert loaded is not None and loaded.summary.counts == ((Decimal("59.82"), 1),)
    attempt = store.load_inventory_attempt("apt")
    assert attempt is not None and attempt.summary.state is InventoryState.PARTIAL


def test_parse_lot_address_rejects_road_only_and_preserves_mountain_flag() -> None:
    candidate = ApartmentCandidate(
        "id", "단지", "1121510300", "서울 광진구 구의동 산 611-2 단지", "도로"
    )
    assert parse_lot_address(candidate) == ("11215", "10300", "1", "611-2")
    road_only = ApartmentCandidate("id", "단지", "1121510300", "서울 광진구 광나루로 32", "도로")
    assert parse_lot_address(road_only) is None


def test_normalization_excludes_known_nonresidential_and_flags_unknown_or_common_only() -> None:
    expos = (
        {"mgmBldrgstPk": "r", "dongNm": "101", "hoNm": "1"},
        {"mgmBldrgstPk": "s", "dongNm": "101", "hoNm": "2"},
        {"mgmBldrgstPk": "u", "dongNm": "101", "hoNm": "3"},
    )
    areas = (
        {"mgmBldrgstPk": "r", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "59.82"},
        {
            "mgmBldrgstPk": "s",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02004",
            "mainPurpsCdNm": "생활편익시설",
            "area": "20",
        },
        {"mgmBldrgstPk": "u", "exposPubuseGbCd": "1", "area": "20"},
    )
    result = normalize_inventory(expos, areas)
    assert result.state is InventoryState.PARTIAL
    assert result.counts == ((Decimal("59.82"), 1),)


def test_known_shop_alone_is_excluded_without_tainting_residential_inventory() -> None:
    expos = (
        {"mgmBldrgstPk": "r", "dongNm": "101", "hoNm": "1"},
        {"mgmBldrgstPk": "s", "dongNm": "상가", "hoNm": "1"},
    )
    areas = (
        {"mgmBldrgstPk": "r", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "59.82"},
        {
            "mgmBldrgstPk": "s",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02004",
            "mainPurpsCdNm": "생활편익시설",
            "area": "20",
        },
    )
    result = normalize_inventory(expos, areas)
    assert result.state is InventoryState.VERIFIED
    assert result.counts == ((Decimal("59.82"), 1),)


def test_official_purpose_name_field_detects_code_name_contradictions() -> None:
    expos = ({"mgmBldrgstPk": "a", "dongNm": "101", "hoNm": "1"},)
    code_name = normalize_inventory(
        expos,
        (
            {
                "mgmBldrgstPk": "a",
                "exposPubuseGbCd": "1",
                "mainPurpsCd": "02001",
                "mainPurpsCdNm": "상가",
                "area": "20",
            },
        ),
    )
    common_name = normalize_inventory(
        expos,
        (
            {
                "mgmBldrgstPk": "a",
                "exposPubuseGbCd": "1",
                "exposPubuseGbCdNm": "공용",
                "mainPurpsCd": "02001",
                "mainPurpsCdNm": "아파트",
                "area": "20",
            },
        ),
    )
    assert code_name.state is InventoryState.PARTIAL and code_name.rows == ()
    assert common_name.state is InventoryState.PARTIAL and common_name.rows == ()


def test_resolve_scope_follows_root_titles_and_units_and_lot_attachment() -> None:
    candidate = ApartmentCandidate(
        "id", "단지", "1121510300", "서울 광진구 구의동 611", "광나루로56길32"
    )
    basis = (
        {
            "mgmBldrgstPk": "root",
            "regstrKindCd": "1",
            "mgmUpBldrgstPk": "0",
            "sigunguCd": "11215",
            "bjdongCd": "10300",
            "platGbCd": "0",
            "bun": "0611",
            "ji": "0000",
        },
        {
            "mgmBldrgstPk": "title",
            "regstrKindCd": "3",
            "mgmUpBldrgstPk": "root",
            "sigunguCd": "11215",
            "bjdongCd": "10300",
            "platGbCd": "0",
            "bun": "0611",
            "ji": "0000",
        },
        {
            "mgmBldrgstPk": "unit",
            "regstrKindCd": "4",
            "mgmUpBldrgstPk": "title",
            "sigunguCd": "11215",
            "bjdongCd": "10300",
            "platGbCd": "0",
            "bun": "0611",
            "ji": "0000",
        },
    )
    recaps = (
        {
            "mgmBldrgstPk": "root",
            "regstrKindCd": "1",
            "bldNm": "단지아파트",
            "sigunguCd": "11215",
            "bjdongCd": "10300",
            "platGbCd": "0",
            "bun": "0611",
            "ji": "0000",
            "bylotCnt": "1",
        },
    )
    titles = (
        {
            "mgmBldrgstPk": "title",
            "regstrKindCd": "3",
            "mgmUpBldrgstPk": "root",
            **{k: recaps[0][k] for k in ("sigunguCd", "bjdongCd", "platGbCd", "bun", "ji")},
        },
    )
    attachments = (
        {
            "mgmBldrgstPk": "root",
            "atchSigunguCd": "11215",
            "atchBjdongCd": "10300",
            "atchPlatGbCd": "0",
            "atchBun": "0611",
            "atchJi": "0001",
        },
    )
    scope = resolve_scope(
        candidate,
        basis,
        recaps,
        titles,
        attachments,
        frozenset(
            {("11215", "10300", "0", "0611", "0000"), ("11215", "10300", "0", "0611", "0001")}
        ),
    )
    assert (
        scope.complete
        and scope.root_key == "root"
        and scope.title_keys == ("title",)
        and scope.unit_keys == ("unit",)
    )


def test_normalization_rejects_missing_identity_and_same_key_identity_conflict() -> None:
    expos = (
        {"mgmBldrgstPk": "a", "dongNm": "101", "hoNm": "1"},
        {"mgmBldrgstPk": "a", "dongNm": "102", "hoNm": "1"},
        {"mgmBldrgstPk": "b", "dongNm": "101", "hoNm": ""},
        {"mgmBldrgstPk": "c", "dongNm": "101"},
    )
    areas = (
        {"mgmBldrgstPk": "a", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "59.82"},
    )
    result = normalize_inventory(expos, areas)
    assert result.state is InventoryState.PARTIAL
    assert result.rows == ()


def test_normalization_sums_duplex_components_and_keeps_basement_distinct() -> None:
    expos = (
        {"mgmBldrgstPk": "d", "dongNm": "101", "hoNm": "1"},
        {"mgmBldrgstPk": "b", "dongNm": "101", "hoNm": "2"},
    )
    areas = (
        {
            "mgmBldrgstPk": "d",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02001",
            "flrGbCd": "20",
            "flrNo": "1",
            "area": "30",
        },
        {
            "mgmBldrgstPk": "d",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02001",
            "flrGbCd": "20",
            "flrNo": "2",
            "area": "30",
        },
        {
            "mgmBldrgstPk": "b",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02001",
            "flrGbCd": "10",
            "flrNo": "1",
            "area": "10",
        },
        {
            "mgmBldrgstPk": "b",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02001",
            "flrGbCd": "20",
            "flrNo": "1",
            "area": "20",
        },
        {
            "mgmBldrgstPk": "d",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02001",
            "flrGbCd": "20",
            "flrNo": "1",
            "area": "30",
            "rnum": "99",
        },
    )
    result = normalize_inventory(expos, areas)
    assert result.state is InventoryState.VERIFIED
    assert result.counts == ((Decimal("30"), 1), (Decimal("60"), 1))


def test_normalization_excludes_unit_on_component_conflict_or_shared_area_text() -> None:
    expos = (
        {"mgmBldrgstPk": "c", "dongNm": "101", "hoNm": "1"},
        {"mgmBldrgstPk": "s", "dongNm": "101", "hoNm": "2"},
    )
    areas = (
        {
            "mgmBldrgstPk": "c",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02001",
            "flrNo": "1",
            "area": "20",
        },
        {
            "mgmBldrgstPk": "c",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02001",
            "flrNo": "1",
            "area": "21",
        },
        {
            "mgmBldrgstPk": "s",
            "exposPubuseGbCd": "1",
            "mainPurpsCd": "02001",
            "etcPurps": "아파트 ( 공유면적포함 )",
            "area": "30",
        },
    )
    result = normalize_inventory(expos, areas)
    assert result.state is InventoryState.PARTIAL
    assert result.rows == ()


def test_normalization_distinguishes_empty_from_all_invalid_and_rejects_bad_area() -> None:
    empty = normalize_inventory((), ())
    assert empty.state is InventoryState.EMPTY and empty.total_count == 0
    invalid = normalize_inventory(
        ({"mgmBldrgstPk": "a", "dongNm": "101", "hoNm": "1"},),
        ({"mgmBldrgstPk": "a", "exposPubuseGbCd": "1", "mainPurpsCd": "02001", "area": "NaN"},),
    )
    assert invalid.state is InventoryState.PARTIAL and invalid.total_count is None


def test_service_reports_mapping_required_for_unmatched_recap() -> None:
    candidate = ApartmentCandidate("id", "선택단지", "1121510300", "서울 광진구 구의동 611", "도로")

    class StubHub:
        def fetch_all(self, operation, params, *, source, **kwargs):
            if operation == "getBrRecapTitleInfo":
                return ({"bldNm": "다른단지"},)
            return ()

    service = BuildingInventoryService(StubHub())
    assert service.collect(candidate).state is InventoryState.MAPPING_REQUIRED


def _scope_rows() -> tuple[ApartmentCandidate, dict[str, str], dict[str, str], dict[str, str]]:
    candidate = ApartmentCandidate(
        "id", "선택단지", "1121510300", "서울 광진구 구의동 611", "광나루로56길32"
    )
    parcel = {
        "sigunguCd": "11215",
        "bjdongCd": "10300",
        "platGbCd": "0",
        "bun": "0611",
        "ji": "0000",
    }
    root = {
        "mgmBldrgstPk": "root",
        "regstrKindCd": "1",
        "mgmUpBldrgstPk": "0",
        **parcel,
        "bldNm": "선택단지",
    }
    title = {
        "mgmBldrgstPk": "title",
        "regstrKindCd": "3",
        "mgmUpBldrgstPk": "root",
        **parcel,
        "bldNm": "선택단지",
        "newPlatPlc": "광나루로56길32",
    }
    unit = {"mgmBldrgstPk": "unit", "regstrKindCd": "4", "mgmUpBldrgstPk": "title", **parcel}
    return candidate, root, title, unit


def test_scope_two_road_titles_ascend_to_one_root() -> None:
    candidate, root, title, unit = _scope_rows()
    title2 = {
        **title,
        "mgmBldrgstPk": "title2",
        "newPlatPlc": "광나루로56길32",
        "bldNm": "다른표기",
    }
    basis = (root, title, title2, unit)
    scope = resolve_scope(
        candidate,
        basis,
        (root,),
        (title, title2),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert scope.complete and scope.root_key == "root"


def test_scope_name_and_road_support_different_roots_is_ambiguous() -> None:
    candidate, root, title, unit = _scope_rows()
    root_b = {**root, "mgmBldrgstPk": "root-b", "bldNm": "다른표기"}
    title_b = {
        **title,
        "mgmBldrgstPk": "title-b",
        "mgmUpBldrgstPk": "root-b",
        "bldNm": "다른표기",
        "newPlatPlc": "광나루로56길32",
    }
    scope = resolve_scope(
        candidate,
        (root, title, unit, root_b, title_b),
        (root,),
        (title, title_b),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete and scope.root_key is None


def test_scope_single_title_parent_zero_can_be_root_by_exact_road() -> None:
    candidate, _, title, unit = _scope_rows()
    title = {**title, "mgmUpBldrgstPk": "0", "bldNm": "다른표기"}
    scope = resolve_scope(
        candidate,
        (title, unit),
        (),
        (title,),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert scope.complete and scope.root_key == "title"


def test_scope_orphan_unit_makes_scope_incomplete() -> None:
    candidate, root, title, unit = _scope_rows()
    orphan = {**unit, "mgmBldrgstPk": "orphan", "mgmUpBldrgstPk": "missing"}
    scope = resolve_scope(
        candidate,
        (root, title, unit, orphan),
        (root,),
        (title,),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete


def test_scope_unit_cycle_makes_scope_incomplete() -> None:
    candidate, root, title, _ = _scope_rows()
    cycle = {"mgmBldrgstPk": "cycle-a", "regstrKindCd": "4", "mgmUpBldrgstPk": "cycle-b"}
    cycle_b = {**cycle, "mgmBldrgstPk": "cycle-b", "mgmUpBldrgstPk": "cycle-a"}
    scope = resolve_scope(
        candidate,
        (root, title, cycle, cycle_b),
        (root,),
        (title,),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete


def test_scope_excludes_fully_resolved_sibling_root() -> None:
    candidate, root, title, unit = _scope_rows()
    sibling_root = {**root, "mgmBldrgstPk": "sroot", "bldNm": "형제단지"}
    sibling_title = {
        **title,
        "mgmBldrgstPk": "stitle",
        "mgmUpBldrgstPk": "sroot",
        "bldNm": "형제단지",
        "newPlatPlc": "형제길1",
    }
    sibling_unit = {**unit, "mgmBldrgstPk": "sunit", "mgmUpBldrgstPk": "stitle"}
    scope = resolve_scope(
        candidate,
        (root, title, unit, sibling_root, sibling_title, sibling_unit),
        (root, sibling_root),
        (title, sibling_title),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert scope.complete and scope.unit_keys == ("unit",)


@pytest.mark.parametrize(
    "queried", [frozenset(), frozenset({("11215", "10300", "0", "0611", "0000")})]
)
def test_scope_requires_unqueried_attached_lot(
    queried: frozenset[tuple[str, str, str, str, str]],
) -> None:
    candidate, root, title, unit = _scope_rows()
    root = {**root, "bylotCnt": "1"}
    attachment = {
        "mgmBldrgstPk": "root",
        "atchSigunguCd": "11215",
        "atchBjdongCd": "10300",
        "atchPlatGbCd": "0",
        "atchBun": "0611",
        "atchJi": "0001",
    }
    scope = resolve_scope(candidate, (root, title, unit), (root,), (title,), (attachment,), queried)
    assert not scope.complete


def test_scope_selected_attachment_without_attachment_coordinates_is_incomplete() -> None:
    candidate, root, title, unit = _scope_rows()
    attachment = {
        "mgmBldrgstPk": "root",
        "sigunguCd": "11215",
        "bjdongCd": "10300",
        "platGbCd": "0",
        "bun": "0611",
        "ji": "0001",
    }
    scope = resolve_scope(
        candidate,
        (root, title, unit),
        (root,),
        (title,),
        (attachment,),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete


def test_scope_recap_building_count_mismatch_is_incomplete() -> None:
    candidate, root, title, unit = _scope_rows()
    root = {**root, "mainBldCnt": "2"}
    scope = resolve_scope(
        candidate,
        (root, title, unit),
        (root,),
        (title,),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete


def test_scope_inconsistent_basis_and_source_parcel_is_incomplete() -> None:
    candidate, root, title, unit = _scope_rows()
    title = {**title, "bun": "0999"}
    scope = resolve_scope(
        candidate,
        (root, title, unit),
        (root,),
        (title,),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete


def test_scope_missing_root_basis_record_is_nonverified() -> None:
    candidate, _, title, unit = _scope_rows()
    scope = resolve_scope(
        candidate, (), (), (title,), (), frozenset({("11215", "10300", "0", "0611", "0000")})
    )
    assert not scope.complete and scope.root_key is None


def _xml_page(rows: list[dict[str, str]], page: int, total: int, size: int = 100) -> bytes:
    items = "".join(
        "<item>" + "".join(f"<{key}>{value}</{key}>" for key, value in row.items()) + "</item>"
        for row in rows
    )
    return f"<response><header><resultCode>000</resultCode></header><body><items>{items}</items><totalCount>{total}</totalCount><pageNo>{page}</pageNo><numOfRows>{size}</numOfRows></body></response>".encode()


def test_service_contract_exposes_verified_scope_and_provenance() -> None:
    candidate = ApartmentCandidate(
        "id", "단지", "1121510300", "서울 광진구 구의동 611", "광나루로56길32"
    )
    parcel = {
        "sigunguCd": "11215",
        "bjdongCd": "10300",
        "platGbCd": "0",
        "bun": "0611",
        "ji": "0000",
    }
    rows = {
        "getBrBasisOulnInfo": [
            {"mgmBldrgstPk": "root", "regstrKindCd": "1", "mgmUpBldrgstPk": "0", **parcel},
            {"mgmBldrgstPk": "title", "regstrKindCd": "3", "mgmUpBldrgstPk": "root", **parcel},
            {"mgmBldrgstPk": "unit", "regstrKindCd": "4", "mgmUpBldrgstPk": "title", **parcel},
        ],
        "getBrRecapTitleInfo": [
            {
                "mgmBldrgstPk": "root",
                "regstrKindCd": "1",
                "bldNm": "단지",
                **parcel,
                "mainBldCnt": "1",
            }
        ],
        "getBrTitleInfo": [
            {
                "mgmBldrgstPk": "title",
                "regstrKindCd": "3",
                "mgmUpBldrgstPk": "root",
                "mainAtchGbCd": "0",
                **parcel,
            }
        ],
        "getBrAtchJibunInfo": [],
        "getBrExposInfo": [
            {
                "mgmBldrgstPk": "unit",
                "regstrKindCd": "4",
                "mgmUpBldrgstPk": "title",
                "dongNm": "101",
                "hoNm": "1",
                **parcel,
            }
        ],
        "getBrExposPubuseAreaInfo": [
            {
                "mgmBldrgstPk": "unit",
                "exposPubuseGbCd": "1",
                "mainPurpsCd": "02001",
                "mainPurpsCdNm": "아파트",
                "area": "59.82",
            }
        ],
    }

    def transport(url: str, _timeout: float) -> bytes:
        operation = url.split("/")[-1].split("?")[0]
        return _xml_page(rows[operation], 1, len(rows[operation]))

    service = BuildingInventoryService(
        BuildingHubClient(DataGoKrClient("key", transport=transport)),
        clock=lambda: datetime(2026, 1, 2, tzinfo=UTC),
    )
    result = service.collect(candidate, kapt_total=1, kapt_bands=(("≤60㎡", 1),))
    assert result.state is InventoryState.VERIFIED
    assert result.scope.complete
    assert result.collected_at == datetime(2026, 1, 2, tzinfo=UTC)


def test_offline_reconciliation_can_change_kapt_comparison_without_network() -> None:
    from apt_analyzer.building_hub import reconcile_inventory

    summary = InventorySummary(
        InventoryState.VERIFIED,
        (),
        ((Decimal("59.82"), 1),),
        1,
        scope=InventoryScope("root", ("title",), ("unit",), (), (), True),
        data_complete=True,
    )
    assert (
        reconcile_inventory(summary, kapt_total=2, kapt_bands=(("≤60㎡", 2),)).state
        is InventoryState.MISMATCH
    )


def test_paginated_source_rejects_rows_over_declared_total() -> None:
    payload = _xml_page([{"id": "a"}], 1, 0)
    client = DataGoKrClient("key", transport=lambda _url, _timeout: payload)
    with pytest.raises(SourceError, match="more rows than total count"):
        BuildingHubClient(client, page_size=100).fetch_all(
            "getBrExposInfo", {}, source="Building HUB"
        )


def test_reconcile_never_verifies_without_scope() -> None:
    from apt_analyzer.building_hub import reconcile_inventory

    summary = InventorySummary(
        InventoryState.MISMATCH,
        (InventoryRow("u", "101", "1", Decimal("59.82")),),
        ((Decimal("59.82"), 1),),
        1,
        data_complete=True,
    )
    restored = reconcile_inventory(summary, kapt_total=1, kapt_bands=(("≤60㎡", 1),))
    assert restored.state is not InventoryState.VERIFIED


def test_service_missing_expos_for_selected_graph_unit_is_partial() -> None:
    candidate, root, title, unit = _scope_rows()

    class Hub:
        def fetch_all(self, operation, params, *, source, **kwargs):
            if operation == "getBrBasisOulnInfo":
                return (root, title, unit)
            if operation == "getBrRecapTitleInfo":
                return ({**root, "bldNm": "선택단지", "mainBldCnt": "1"},)
            if operation == "getBrTitleInfo":
                return ({**title, "mainAtchGbCd": "0"},)
            if operation == "getBrExposInfo":
                return ()
            if operation == "getBrExposPubuseAreaInfo":
                return ()
            return ()

    result = BuildingInventoryService(Hub()).collect(candidate, kapt_total=1)
    assert result.state is InventoryState.PARTIAL and not result.data_complete


def test_scope_rejects_unit_directly_under_recap() -> None:
    candidate, root, _, unit = _scope_rows()
    bad = {**unit, "mgmUpBldrgstPk": "root"}
    scope = resolve_scope(
        candidate,
        (root, bad),
        (root,),
        (),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete


def test_scope_rejects_unit_whose_immediate_parent_is_recap() -> None:
    candidate, root, title, unit = _scope_rows()
    bad = {**unit, "mgmUpBldrgstPk": "root"}
    scope = resolve_scope(
        candidate,
        (root, title, bad),
        (root,),
        (title,),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete


def test_scope_rejects_source_title_parcel_conflict() -> None:
    candidate, root, title, unit = _scope_rows()
    source_title = {**title, "bun": "0999"}
    scope = resolve_scope(
        candidate,
        (root, title, unit),
        (root,),
        (source_title,),
        (),
        frozenset({("11215", "10300", "0", "0611", "0000")}),
    )
    assert not scope.complete


def test_service_unknown_expos_key_cannot_certify_equal_total() -> None:
    candidate, root, title, unit = _scope_rows()

    class Hub:
        def fetch_all(self, operation, params, *, source, **kwargs):
            if operation == "getBrBasisOulnInfo":
                return (root, title, unit)
            if operation == "getBrRecapTitleInfo":
                return ({**root, "bldNm": "선택단지", "mainBldCnt": "1"},)
            if operation == "getBrTitleInfo":
                return ({**title, "mainAtchGbCd": "0"},)
            if operation == "getBrExposInfo":
                return (
                    {**unit, "dongNm": "101", "hoNm": "1"},
                    {"mgmBldrgstPk": "unknown", "dongNm": "x", "hoNm": "1"},
                )
            if operation == "getBrExposPubuseAreaInfo":
                return (
                    {
                        "mgmBldrgstPk": "unit",
                        "exposPubuseGbCd": "1",
                        "mainPurpsCd": "02001",
                        "mainPurpsCdNm": "아파트",
                        "area": "59.82",
                    },
                    {
                        "mgmBldrgstPk": "unknown",
                        "exposPubuseGbCd": "1",
                        "mainPurpsCd": "02001",
                        "mainPurpsCdNm": "아파트",
                        "area": "59.82",
                    },
                )
            return ()

    result = BuildingInventoryService(Hub()).collect(candidate, kapt_total=1)
    assert result.state is InventoryState.PARTIAL and not result.data_complete


def test_service_rejects_nonpositive_max_lots() -> None:
    with pytest.raises(ValueError, match="max_lots"):
        BuildingInventoryService(BuildingHubClient(DataGoKrClient("key")), max_lots=0)


def test_service_attached_lot_source_error_is_contained() -> None:
    candidate, root, title, unit = _scope_rows()
    main = {
        op: ((root, title, unit) if op == "getBrBasisOulnInfo" else ())
        for op in BuildingInventoryService.OPERATIONS
    }
    calls = []

    class Hub:
        def fetch_all(self, operation, params, *, source, **kwargs):
            calls.append((operation, params["bun"]))
            if params["bun"] == "0610":
                raise SourceError("transport")
            return main[operation]

    original = __import__("apt_analyzer.building_hub", fromlist=["resolve_scope"]).resolve_scope

    def fake_scope(*args, **kwargs):
        return InventoryScope(
            "root",
            ("title",),
            ("unit",),
            (("11215", "10300", "0", "0610", "0000"), ("11215", "10300", "0", "0611", "0000")),
            (),
            False,
        )

    import apt_analyzer.building_hub as module

    module.resolve_scope = fake_scope
    try:
        result = BuildingInventoryService(Hub(), max_lots=2).collect(candidate)
    finally:
        module.resolve_scope = original
    assert result.state is InventoryState.UNAVAILABLE and "key" not in (result.reason or "")
    assert any(bun == "0610" for _, bun in calls)


def test_service_traversal_uses_pending_lot_set() -> None:
    candidate, root, title, unit = _scope_rows()
    calls = []

    class Hub:
        def fetch_all(self, operation, params, *, source, **kwargs):
            calls.append((operation, params["bun"]))
            return ({"x": "1"},)

    import apt_analyzer.building_hub as module

    original = module.resolve_scope

    def fake_scope(*args, **kwargs):
        queried = kwargs.get("queried_lots", args[-1] if args else frozenset())
        lots = (("11215", "10300", "0", "0610", "0000"), ("11215", "10300", "0", "0611", "0000"))
        return InventoryScope(
            "root", ("title",), ("unit",), lots, (), not ("0610" not in {x[3] for x in queried}), ()
        )

    module.resolve_scope = fake_scope
    try:
        result = BuildingInventoryService(Hub(), max_lots=2).collect(candidate)
    finally:
        module.resolve_scope = original
    assert result.state is InventoryState.PARTIAL
    assert any(bun == "0610" for _, bun in calls)


def test_fetch_all_budget_callback_runs_before_each_page() -> None:
    calls = 0
    payload = _xml_page([{"id": "a"}], 1, 2, 1)
    client = DataGoKrClient("key", transport=lambda _url, _timeout: payload)

    def guard() -> None:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise SourceError("budget")

    with pytest.raises(SourceError, match="budget"):
        BuildingHubClient(client, page_size=1).fetch_all(
            "getBrExposInfo", {}, source="x", before_request=guard
        )
    assert calls == 2
