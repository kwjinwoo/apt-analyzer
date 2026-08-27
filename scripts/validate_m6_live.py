import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from apt_analyzer.acquisition import DataGoKrClient, load_service_key
from apt_analyzer.analytics import HouseholdEvidence
from apt_analyzer.apartment_data import (
    KAPT_DETAIL_ENDPOINT,
    ApartmentDataService,
    ResolutionStatus,
)
from apt_analyzer.comparison import CommonAnalysisConfig
from apt_analyzer.domain import AnalysisPeriod, TransactionInclusionPolicy, TransactionType
from apt_analyzer.regional_profile import MetricDefinition, MetricObservation, profile_metrics
from apt_analyzer.regional_screening import (
    SUPPORTED_METHODS,
    SUPPORTED_UNITS,
    measure_candidates,
)

SAMPLES = {
    "11": (
        "A14383203",
        "A14383205",
        "A10026162",
        "A14375301",
        "A14319305",
        "A14319306",
        "A14376501",
    ),
    "26": (
        "A61280801",
        "A61280802",
        "A10025558",
        "A61206114",
        "A61271919",
        "A61279802",
        "A61281117",
    ),
    "41": (
        "A46382913",
        "A46382916",
        "A46383012",
        "A46383017",
        "A10020890",
        "A10027703",
        "A10027704",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run bounded, credential-redacted M6 regional-profile validation"
    )
    parser.add_argument("--live", action="store_true", help="authorize official API requests")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required")

    overall = AnalysisPeriod(date(2022, 1, 1), date(2024, 12, 31))
    config = CommonAnalysisConfig(
        overall,
        AnalysisPeriod(date(2024, 1, 1), date(2024, 12, 31)),
        AnalysisPeriod(date(2022, 1, 1), date(2022, 12, 31)),
        AnalysisPeriod(date(2023, 1, 1), date(2023, 12, 31)),
        overall,
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
    )
    definitions = tuple(
        MetricDefinition(metric, SUPPORTED_UNITS[metric], SUPPORTED_METHODS[metric])
        for metric in SUPPORTED_UNITS
    )
    client = DataGoKrClient(load_service_key(Path.cwd()), retries=1, timeout=20)
    service = ApartmentDataService(client)
    all_observations: list[MetricObservation] = []
    output: dict[str, Any] = {
        "periods": {
            "overall": "2022-01-01/2024-12-31",
            "turnover": "2024-01-01/2024-12-31",
            "baseline": "2022-01-01/2022-12-31",
            "comparison": "2023-01-01/2023-12-31",
        },
        "inclusion_policy": "brokered, non-cancelled",
        "regions": {},
    }
    for region, source_ids in SAMPLES.items():
        listed = {candidate.source_id: candidate for candidate in service.list_region(region)}
        apartments = []
        transactions = {}
        households = {}
        labels = {}
        for source_id in source_ids:
            selected = listed.get(source_id)
            if selected is None:
                raise RuntimeError(
                    f"selected candidate disappeared from region {region}: {source_id}"
                )
            enriched, resolution = service.resolve(selected)
            if resolution.status is not ResolutionStatus.RESOLVED or resolution.apartment is None:
                raise RuntimeError(f"identity resolution failed for {source_id}")
            apartment = resolution.apartment
            records = service.retrieve(enriched, apartment, overall)
            detail = client.get_xml(
                KAPT_DETAIL_ENDPOINT,
                {"kaptCode": source_id},
                source="K-APT apartment basic information",
            )
            household_text = detail.records[0].get("kaptdaCnt", "").replace(",", "").strip()
            household_count = int(Decimal(household_text)) if household_text else None
            apartments.append(apartment)
            transactions[apartment.internal_id] = records
            households[apartment.internal_id] = HouseholdEvidence(
                household_count, "complex", "K-APT basic information V5"
            )
            labels[apartment.internal_id] = {
                "source_id": source_id,
                "name": selected.name,
            }
        measurements = measure_candidates(
            tuple(apartments), transactions, config, households=households
        )
        observations = tuple(
            MetricObservation(item.candidate_id, item.values, item.unavailable)
            for item in measurements
        )
        all_observations.extend(observations)
        profile = profile_metrics(observations, definitions)
        output["regions"][region] = {
            "candidate_count": len(observations),
            "candidates": [
                {
                    **labels[item.candidate_id],
                    "values": item.values,
                    "unavailable": item.unavailable,
                }
                for item in measurements
            ],
            "distributions": profile.distributions,
        }
    combined = profile_metrics(tuple(all_observations), definitions)
    output["combined_candidate_count"] = len(all_observations)
    output["combined_distributions"] = combined.distributions
    output["combined_correlations"] = combined.correlations
    output["disclaimer"] = combined.disclaimer
    print(json.dumps(_json_value(output), ensure_ascii=False, indent=2, sort_keys=True))


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


if __name__ == "__main__":
    main()
