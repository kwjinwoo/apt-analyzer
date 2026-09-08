from datetime import date
from decimal import Decimal

import pytest

from apt_analyzer.acquisition import DataGoKrClient
from apt_analyzer.apartment_data import (
    ApartmentCandidate,
    ApartmentDataService,
    AreaHouseholdBand,
    IdentityMismatchError,
    ResolutionStatus,
    months,
    normalize_transaction,
    resolve_candidate,
)
from apt_analyzer.domain import AnalysisPeriod, Apartment, TransactionType


def test_selected_candidate_is_enriched_from_kapt_detail_before_resolution() -> None:
    detail = """<response><header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header><body><item><kaptCode>A14383205</kaptCode><kaptName>구의현대2단지</kaptName><bjdCode>1121510300</bjdCode><kaptAddr>서울특별시 광진구 구의동 611</kaptAddr><doroJuso>서울특별시 광진구 광나루로56길 32</doroJuso><hoCnt>1842</hoCnt></item></body></response>""".encode()
    seen = ""

    def transport(url: str, _timeout: float) -> bytes:
        nonlocal seen
        seen = url
        return detail

    service = ApartmentDataService(DataGoKrClient("abc%2Fdef", transport=transport))
    selected = ApartmentCandidate("A14383205", "구의현대2단지", "", "서울 광진구", "")

    enriched, resolution = service.resolve(selected)

    assert "AptBasisInfoServiceV5/getAphusBassInfoV5" in seen
    assert "kaptCode=A14383205" in seen
    assert enriched.legal_dong_code == "1121510300"
    assert enriched.lot_address.endswith("구의동 611")
    assert enriched.road_address.endswith("광나루로56길 32")
    assert enriched.household_count == 1842
    assert enriched.household_source == "K-APT apartment basic information"
    assert resolution.status is ResolutionStatus.RESOLVED
    assert resolution.apartment is not None
    assert resolution.apartment.internal_id.startswith("apt-")


def test_kapt_detail_enriches_typed_profile_and_validates_area_bands() -> None:
    fields = """<kaptDongCnt>14</kaptDongCnt><kaptUsedate>19990503</kaptUsedate><kaptTopFloor>20</kaptTopFloor><codeHeatNm>지역난방</codeHeatNm><codeHallNm>혼합식</codeHallNm><kaptBcompany>한신공영</kaptBcompany><kaptAcompany>LH</kaptAcompany><codeMgrNm>위탁관리</codeMgrNm><codeSaleNm>분양</codeSaleNm><kaptMparea60>1190.0</kaptMparea60><kaptMparea85>0.0</kaptMparea85><kaptMparea135>bad</kaptMparea135><kaptMparea136>-1</kaptMparea136>"""
    detail = (
        "<response><header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header><body><item><kaptCode>A1</kaptCode><kaptName>Example</kaptName><bjdCode>1234567890</bjdCode><kaptAddr>Example lot</kaptAddr><doroJuso>Example road</doroJuso><hoCnt>1190</hoCnt>"
        + fields
        + "</item></body></response>"
    ).encode()
    service = ApartmentDataService(
        DataGoKrClient("encoded", transport=lambda _url, _timeout: detail)
    )
    enriched, resolution = service.resolve(ApartmentCandidate("A1", "Example", "", "lot", "road"))
    assert resolution.status is ResolutionStatus.RESOLVED
    assert enriched.profile is not None
    assert enriched.profile.buildings == 14
    assert enriched.profile.approval_date == date(1999, 5, 3)
    assert enriched.profile.area_bands == (
        AreaHouseholdBand("≤60㎡", 1190),
        AreaHouseholdBand(">60–85㎡", 0),
    )


@pytest.mark.parametrize(
    ("household_xml", "expected"),
    [
        ("<hoCnt>1,842</hoCnt><kaptdaCnt>999.0</kaptdaCnt>", 1842),
        ("<hoCnt>invalid</hoCnt><kaptdaCnt>1842.0</kaptdaCnt>", 1842),
        ("<hoCnt>0</hoCnt><kaptdaCnt>1842.5</kaptdaCnt>", None),
    ],
)
def test_kapt_household_evidence_requires_a_positive_integral_count(
    household_xml: str, expected: int | None
) -> None:
    detail = (
        "<response><header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>"
        "<body><item><kaptCode>A1</kaptCode><kaptName>Example</kaptName>"
        "<bjdCode>1234567890</bjdCode><kaptAddr>Example lot</kaptAddr>"
        f"<doroJuso>Example road</doroJuso>{household_xml}</item></body></response>"
    ).encode()
    service = ApartmentDataService(
        DataGoKrClient("encoded", transport=lambda _url, _timeout: detail)
    )

    enriched, _resolution = service.resolve(
        ApartmentCandidate("A1", "Example", "", "Example lot", "")
    )

    assert enriched.household_count == expected
    assert enriched.household_source == (
        "K-APT apartment basic information" if expected is not None else None
    )


def test_normalization_preserves_required_optional_and_source_values() -> None:
    row = {
        "dealYear": "2025",
        "dealMonth": "1",
        "dealDay": "7",
        "dealAmount": "90,000",
        "excluUseAr": "84.92",
        "floor": "12",
        "dealingGbn": "중개거래",
        "cdealType": "O",
        "aptDong": "101",
        "buildYear": "2005",
        "estateAgentSggNm": "서울 종로구",
        "aptSeq": "x-1",
    }

    transaction = normalize_transaction(row, "apt-1")

    assert transaction.contract_date == date(2025, 1, 7)
    assert transaction.price_krw == 900_000_000
    assert transaction.exclusive_area_sqm == Decimal("84.92")
    assert transaction.floor == 12
    assert transaction.transaction_type is TransactionType.BROKERED
    assert transaction.is_cancelled is True
    assert transaction.building == "101"
    assert transaction.unit == "x-1"
    assert transaction.construction_year == 2005
    assert transaction.broker_location == "서울 종로구"
    assert dict(transaction.source_values)["dealAmount"] == "90,000"


def test_resolution_never_auto_selects_ambiguous_candidates() -> None:
    candidates = tuple(
        ApartmentCandidate(str(index), "현대", f"11{index}", f"주소 {index}", "")
        for index in range(2)
    )
    assert resolve_candidate(candidates).status is ResolutionStatus.AMBIGUOUS
    assert resolve_candidate(candidates).apartment is None


def test_month_coverage_includes_partial_boundary_months() -> None:
    assert months(AnalysisPeriod(date(2024, 12, 31), date(2025, 2, 1))) == (
        "202412",
        "202501",
        "202502",
    )


def test_retrieval_is_idempotent_and_enforces_date_boundaries() -> None:
    xml = """<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>
      <body><items>
       <item><aptNm>Example</aptNm><umdNm>청운동</umdNm><jibun>1</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>1</dealDay><dealAmount>1,000</dealAmount><excluUseAr>84.9</excluUseAr><floor>1</floor></item>
       <item><aptNm>Example</aptNm><umdNm>청운동</umdNm><jibun>1</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>1</dealDay><dealAmount>1,000</dealAmount><excluUseAr>84.9</excluUseAr><floor>1</floor></item>
       <item><aptNm>Example</aptNm><umdNm>청운동</umdNm><jibun>1</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>2</dealDay><dealAmount>1,100</dealAmount><excluUseAr>84.9</excluUseAr><floor>2</floor></item>
      </items><totalCount>3</totalCount></body></response>""".encode()
    client = DataGoKrClient("encoded", transport=lambda _url, _timeout: xml)
    service = ApartmentDataService(client)
    candidate = ApartmentCandidate("k1", "Example", "1111010100", "서울 종로구 청운동 1", "road")

    result = service.retrieve(
        candidate, Apartment("apt-1", "Example"), AnalysisPeriod(date(2025, 1, 2), date(2025, 1, 2))
    )

    assert len(result) == 1
    assert result[0].contract_date == date(2025, 1, 2)


def test_retrieval_uses_legal_code_and_rejects_name_only_address_mismatch() -> None:
    xml = """<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items><item><aptNm>구의현대2단지</aptNm><umdNm>다른동</umdNm><jibun>999</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>2</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item></items></body></response>""".encode()
    seen = ""

    def transport(url: str, _timeout: float) -> bytes:
        nonlocal seen
        seen = url
        return xml

    service = ApartmentDataService(DataGoKrClient("encoded", transport=transport))
    candidate = ApartmentCandidate(
        "A1", "구의현대2단지", "1121510300", "서울 광진구 구의동 611", "road"
    )
    with pytest.raises(IdentityMismatchError):
        service.retrieve(
            candidate,
            Apartment("apt-1", candidate.name),
            AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        )
    assert "LAWD_CD=11215" in seen


def test_retrieval_accepts_verified_molit_aliases_for_kapt_aggregate() -> None:
    names = ("벽적골두산", "벽적골한신", "벽적골우성")
    items = "".join(
        f"<item><aptNm>{name}</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun>"
        "<dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>2</dealDay>"
        "<dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>"
        for name in names
    )
    xml = (
        "<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>"
        f"<body><items>{items}</items></body></response>"
    ).encode()
    service = ApartmentDataService(DataGoKrClient("encoded", transport=lambda _url, _timeout: xml))
    candidate = ApartmentCandidate(
        "A44347025", "벽적골두산한신우성", "4111710500", "경기도 수원시 영통동 973-3", "road"
    )

    result = service.retrieve(
        candidate,
        Apartment("apt-1", candidate.name),
        AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
    )

    assert len(result) == 3
    assert {dict(item.source_values)["aptNm"] for item in result} == set(names)


def test_unregistered_compound_name_components_require_explicit_mapping() -> None:
    xml = """<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items>
    <item><aptNm>벽적골두산</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>2</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    <item><aptNm>벽적골한신</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>3</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    <item><aptNm>벽적골우성</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>4</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    </items></body></response>""".encode()
    service = ApartmentDataService(DataGoKrClient("encoded", transport=lambda _url, _timeout: xml))
    candidate = ApartmentCandidate(
        "synthetic", "벽적골두산한신우성", "4111710500", "경기도 수원시 영통동 973-3", "road"
    )

    with pytest.raises(IdentityMismatchError, match="explicit alias mapping"):
        service.retrieve(
            candidate,
            Apartment("apt-1", candidate.name),
            AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        )


def test_unregistered_compound_components_fail_even_with_an_exact_record() -> None:
    xml = """<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items>
    <item><aptNm>벽적골두산한신우성</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>1</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    <item><aptNm>벽적골한신</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>2</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    <item><aptNm>벽적골우성</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>3</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    </items></body></response>""".encode()
    service = ApartmentDataService(DataGoKrClient("encoded", transport=lambda _url, _timeout: xml))
    candidate = ApartmentCandidate(
        "synthetic", "벽적골두산한신우성", "4111710500", "경기도 수원시 영통동 973-3", "road"
    )

    with pytest.raises(IdentityMismatchError, match="explicit alias mapping"):
        service.retrieve(
            candidate,
            Apartment("apt-1", candidate.name),
            AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        )


def test_unrelated_same_lot_name_does_not_mask_compound_component_mismatch() -> None:
    xml = """<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items>
    <item><aptNm>벽적골두산</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>1</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    <item><aptNm>벽적골한신</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>2</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    <item><aptNm>벽적골우성</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>3</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    <item><aptNm>청운주공</aptNm><umdNm>영통동</umdNm><jibun>973-3</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>4</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    </items></body></response>""".encode()
    service = ApartmentDataService(DataGoKrClient("encoded", transport=lambda _url, _timeout: xml))
    candidate = ApartmentCandidate(
        "synthetic", "벽적골두산한신우성", "4111710500", "경기도 수원시 영통동 973-3", "road"
    )

    with pytest.raises(IdentityMismatchError, match="explicit alias mapping"):
        service.retrieve(
            candidate,
            Apartment("apt-1", candidate.name),
            AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        )


def test_verified_alias_never_overrides_lot_or_legal_dong_evidence() -> None:
    xml = """<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items>
    <item><aptNm>벽적골두산</aptNm><umdNm>영통동</umdNm><jibun>999-1</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>2</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    </items></body></response>""".encode()
    service = ApartmentDataService(DataGoKrClient("encoded", transport=lambda _url, _timeout: xml))
    candidate = ApartmentCandidate(
        "A44347025", "벽적골두산한신우성", "4111710500", "경기도 수원시 영통동 973-3", "road"
    )

    with pytest.raises(IdentityMismatchError):
        service.retrieve(
            candidate,
            Apartment("apt-1", candidate.name),
            AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        )


def test_unrelated_same_lot_name_remains_a_valid_empty_result() -> None:
    xml = """<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items>
    <item><aptNm>청운주공</aptNm><umdNm>청운동</umdNm><jibun>1</jibun><dealYear>2025</dealYear><dealMonth>1</dealMonth><dealDay>2</dealDay><dealAmount>10,000</dealAmount><excluUseAr>84.9</excluUseAr></item>
    </items></body></response>""".encode()
    service = ApartmentDataService(DataGoKrClient("encoded", transport=lambda _url, _timeout: xml))
    candidate = ApartmentCandidate("ordinary", "청운현대", "1111010100", "서울 청운동 1", "road")

    assert (
        service.retrieve(
            candidate,
            Apartment("apt-1", candidate.name),
            AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        )
        == ()
    )


def test_cache_result_cannot_masquerade_as_live() -> None:
    calls = 0

    def transport(_url: str, _timeout: float) -> bytes:
        nonlocal calls
        calls += 1
        return b"<response><header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header><body><items/></body></response>"

    client = DataGoKrClient("encoded", transport=transport)
    first = client.get_xml("https://example.test", {"q": "1"}, source="test")
    second = client.get_xml("https://example.test", {"q": "1"}, source="test")
    assert first.from_cache is False
    assert second.from_cache is True
    assert second.fetched_at == first.fetched_at
    assert second.query == (("q", "1"),)
    assert calls == 1


def test_search_uses_correct_kapt_operation_and_region_evidence() -> None:
    xml = b"""<response><header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
      <body><items><item><kaptCode>A1</kaptCode><kaptName>Hyundai</kaptName><as1>Seoul</as1><as2>Jongno</as2><as3>Cheongun</as3></item></items></body></response>"""
    seen = ""

    def transport(url: str, _timeout: float) -> bytes:
        nonlocal seen
        seen = url
        return xml

    service = ApartmentDataService(DataGoKrClient("abc%2Fdef", transport=transport))
    candidates = service.search("Hyundai")
    assert "AptListService4/getSidoAptList4" in seen
    assert "sidoCode=11" in seen
    assert "serviceKey=abc%2Fdef" in seen
    assert candidates[0].lot_address == "Seoul Jongno Cheongun"
