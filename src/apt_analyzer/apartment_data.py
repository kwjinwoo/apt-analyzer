"""Apartment identity and transaction-retrieval application boundary."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from apt_analyzer.acquisition import DataGoKrClient, ParsingError
from apt_analyzer.domain import AnalysisPeriod, Apartment, NormalizedTransaction, TransactionType

KAPT_LIST_ENDPOINT = "https://apis.data.go.kr/1613000/AptListService4/getSidoAptList4"
KAPT_DETAIL_ENDPOINT = "https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5"
MOLIT_SALE_ENDPOINT = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"


def normalize_name(value: str) -> str:
    """Normalize spacing and punctuation for conservative exact-name evidence."""
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())


@dataclass(frozen=True, slots=True)
class ApartmentCandidate:
    """Expose source identity and address evidence before project resolution."""

    source_id: str
    name: str
    legal_dong_code: str
    lot_address: str
    road_address: str


class ResolutionStatus(StrEnum):
    """Represent whether identity evidence resolves exactly one candidate."""

    RESOLVED = "resolved"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


class IdentityMismatchError(ValueError):
    """Indicate that same-name source rows conflict with selected address evidence."""


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    """Return explicit identity resolution rather than selecting silently."""

    status: ResolutionStatus
    candidates: tuple[ApartmentCandidate, ...]
    apartment: Apartment | None = None


def resolve_candidate(candidates: tuple[ApartmentCandidate, ...]) -> IdentityResolution:
    """Resolve only a single explicitly selected source candidate."""
    if not candidates:
        return IdentityResolution(ResolutionStatus.NOT_FOUND, ())
    if len(candidates) != 1:
        return IdentityResolution(ResolutionStatus.AMBIGUOUS, candidates)
    candidate = candidates[0]
    if not (
        candidate.source_id
        and len(candidate.legal_dong_code) == 10
        and candidate.lot_address
        and candidate.road_address
    ):
        return IdentityResolution(ResolutionStatus.NOT_FOUND, candidates)
    evidence = "|".join(
        (
            candidate.source_id,
            candidate.legal_dong_code,
            candidate.lot_address,
            candidate.road_address,
        )
    )
    internal_id = "apt-" + hashlib.sha256(evidence.encode()).hexdigest()[:20]
    return IdentityResolution(
        ResolutionStatus.RESOLVED,
        candidates,
        Apartment(internal_id, candidate.name),
    )


def months(period: AnalysisPeriod) -> tuple[str, ...]:
    """Return every YYYYMM intersecting an inclusive period."""
    year, month = period.start.year, period.start.month
    values: list[str] = []
    while (year, month) <= (period.end.year, period.end.month):
        values.append(f"{year:04d}{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return tuple(values)


class ApartmentDataService:
    """Coordinate source search, explicit selection, and period retrieval."""

    def __init__(self, client: DataGoKrClient) -> None:
        """Use the provided acquisition boundary for official-source calls."""
        self._client = client

    def search(self, name: str, *, sido_code: str = "11") -> tuple[ApartmentCandidate, ...]:
        """Search K-APT records and return distinguishable matching candidates."""
        needle = normalize_name(name)
        return tuple(
            candidate
            for candidate in self.list_region(sido_code)
            if needle and needle in normalize_name(candidate.name)
        )

    def list_region(self, sido_code: str) -> tuple[ApartmentCandidate, ...]:
        """List all K-APT candidates in one explicitly requested region."""
        candidates: list[ApartmentCandidate] = []
        page = 1
        while True:
            result = self._client.get_xml(
                KAPT_LIST_ENDPOINT,
                {
                    "sidoCode": sido_code,
                    "pageNo": str(page),
                    "numOfRows": "1000",
                    "_type": "xml",
                },
                source="K-APT apartment list",
            )
            for row in result.records:
                candidate_name = _pick(row, "kaptName")
                region = " ".join(
                    value
                    for value in (_pick(row, "as1"), _pick(row, "as2"), _pick(row, "as3"))
                    if value
                )
                candidates.append(
                    ApartmentCandidate(
                        source_id=_pick(row, "kaptCode"),
                        name=candidate_name,
                        legal_dong_code=_pick(row, "bjdCode"),
                        lot_address=_pick(row, "kaptAddr") or region,
                        road_address=_pick(row, "doroJuso", "roadAddress"),
                    )
                )
            if len(result.records) < 1000:
                break
            page += 1
        return tuple(candidates)

    def resolve(
        self, selected: ApartmentCandidate
    ) -> tuple[ApartmentCandidate, IdentityResolution]:
        """Enrich one explicit selection with K-APT identity evidence and resolve it."""
        result = self._client.get_xml(
            KAPT_DETAIL_ENDPOINT,
            {"kaptCode": selected.source_id},
            source="K-APT apartment basic information",
        )
        if len(result.records) != 1:
            return selected, IdentityResolution(ResolutionStatus.NOT_FOUND, (selected,))
        row = result.records[0]
        detail_name = _pick(row, "kaptName")
        detail_id = _pick(row, "kaptCode") or selected.source_id
        if detail_id != selected.source_id or normalize_name(detail_name) != normalize_name(
            selected.name
        ):
            return selected, IdentityResolution(ResolutionStatus.NOT_FOUND, (selected,))
        enriched = ApartmentCandidate(
            source_id=detail_id,
            name=detail_name,
            legal_dong_code=_pick(row, "bjdCode"),
            lot_address=_pick(row, "kaptAddr"),
            road_address=_pick(row, "doroJuso"),
        )
        return enriched, resolve_candidate((enriched,))

    def retrieve(
        self,
        candidate: ApartmentCandidate,
        apartment: Apartment,
        period: AnalysisPeriod,
    ) -> tuple[NormalizedTransaction, ...]:
        """Retrieve all intersecting months and enforce inclusive day boundaries."""
        records: dict[str, NormalizedTransaction] = {}
        mismatched_same_name = False
        lawd = candidate.legal_dong_code[:5]
        if len(lawd) != 5:
            raise ValueError("candidate must provide a legal-dong code")
        for year_month in months(period):
            result = self._client.get_xml(
                MOLIT_SALE_ENDPOINT,
                {"LAWD_CD": lawd, "DEAL_YMD": year_month, "pageNo": "1", "numOfRows": "9999"},
                source="MOLIT apartment sale transactions",
            )
            for row in result.records:
                if normalize_name(_pick(row, "aptNm", "아파트")) != normalize_name(candidate.name):
                    continue
                if not _matches_lot_address(row, candidate.lot_address):
                    mismatched_same_name = True
                    continue
                transaction = normalize_transaction(row, apartment.internal_id)
                if period.includes(transaction.contract_date):
                    records[transaction.source_record_id or ""] = transaction
        if not records and mismatched_same_name:
            raise IdentityMismatchError(
                "same-name transactions conflict with selected lot-address evidence"
            )
        return tuple(
            sorted(
                records.values(), key=lambda item: (item.contract_date, item.source_record_id or "")
            )
        )


def normalize_transaction(row: Mapping[str, str], apartment_id: str) -> NormalizedTransaction:
    """Normalize one MOLIT row while preserving all supplied source values."""
    try:
        contract_date = date(
            int(_pick(row, "dealYear", "년")),
            int(_pick(row, "dealMonth", "월")),
            int(_pick(row, "dealDay", "일")),
        )
        price = int(_pick(row, "dealAmount", "거래금액").replace(",", "").strip()) * 10_000
        area = Decimal(_pick(row, "excluUseAr", "전용면적"))
    except (ValueError, InvalidOperation) as error:
        raise ParsingError("invalid required transaction value") from error
    raw = tuple(sorted((str(key), str(value)) for key, value in row.items()))
    source_record_id = hashlib.sha256(repr(raw).encode()).hexdigest()
    transaction_type_text = _pick(row, "dealingGbn", "거래유형")
    transaction_type = {
        "중개거래": TransactionType.BROKERED,
        "직거래": TransactionType.DIRECT,
    }.get(transaction_type_text, TransactionType.UNKNOWN)
    cancel_value = _pick(row, "cdealType", "해제여부")
    return NormalizedTransaction(
        apartment_id=apartment_id,
        contract_date=contract_date,
        price_krw=price,
        exclusive_area_sqm=area,
        transaction_type=transaction_type,
        is_cancelled=cancel_value not in {"", "0", "N"},
        floor=_optional_int(_pick(row, "floor", "층")),
        building=_optional(_pick(row, "aptDong", "동")),
        unit=_optional(_pick(row, "aptSeq", "일련번호")),
        construction_year=_optional_int(_pick(row, "buildYear", "건축년도")),
        broker_location=_optional(_pick(row, "estateAgentSggNm", "중개사소재지")),
        source_name="MOLIT apartment sale transactions",
        source_record_id=source_record_id,
        source_values=raw,
    )


def _pick(row: Mapping[str, str], *names: str) -> str:
    return next((row[name].strip() for name in names if row.get(name)), "")


def _matches_lot_address(row: Mapping[str, str], lot_address: str) -> bool:
    """Match the transaction legal-dong name and lot number to K-APT evidence."""
    tokens = lot_address.split()
    address_index = next(
        (
            index
            for index in range(len(tokens) - 2, -1, -1)
            if tokens[index].endswith(("동", "가", "읍", "면", "리"))
        ),
        None,
    )
    if address_index is None or address_index + 1 >= len(tokens):
        return False
    dong, lot = tokens[address_index], tokens[address_index + 1]
    return normalize_name(_pick(row, "umdNm", "법정동")) == normalize_name(dong) and normalize_name(
        _pick(row, "jibun", "지번")
    ) == normalize_name(lot)


def _optional(value: str) -> str | None:
    return value or None


def _optional_int(value: str) -> int | None:
    return int(value) if value else None
