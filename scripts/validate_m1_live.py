import argparse
from datetime import date
from pathlib import Path

from apt_analyzer.acquisition import DataGoKrClient, load_service_key
from apt_analyzer.domain import AnalysisPeriod
from apt_analyzer.m1 import ApartmentCandidate, M1Service, ResolutionStatus

COMPLEXES = (
    ("A14383205", "구의현대2단지"),
    ("A14383203", "구의현대6단지"),
    ("A15776004", "현대3"),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run low-volume, credential-redacted M1 validation"
    )
    parser.add_argument("--live", action="store_true", help="authorize official API requests")
    parser.add_argument("--start", default="202501", help="first validation month in YYYYMM form")
    parser.add_argument("--end", default="202502", help="last validation month in YYYYMM form")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required")
    start_year, start_month = int(args.start[:4]), int(args.start[4:])
    end_year, end_month = int(args.end[:4]), int(args.end[4:])
    period = AnalysisPeriod(date(start_year, start_month, 1), _month_end(end_year, end_month))
    service = M1Service(DataGoKrClient(load_service_key(Path.cwd()), retries=1, timeout=20))

    ambiguous = service.search("현대")
    print(f"ambiguous_query=현대 candidates={len(ambiguous)} auto_selected=false")
    for source_id, name in COMPLEXES:
        selected = ApartmentCandidate(source_id, name, "", "", "")
        enriched, resolution = service.resolve(selected)
        if resolution.status is not ResolutionStatus.RESOLVED or resolution.apartment is None:
            raise RuntimeError(f"identity resolution failed for {source_id}")
        transactions = service.retrieve(enriched, resolution.apartment, period)
        print(
            f"name={name} kapt_id={source_id} legal_code_present=true "
            f"lot_address_present={bool(enriched.lot_address)} "
            f"road_address_present={bool(enriched.road_address)} "
            f"period={args.start}-{args.end} transactions={len(transactions)}"
        )


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1).fromordinal(date(year, month + 1, 1).toordinal() - 1)


if __name__ == "__main__":
    main()
