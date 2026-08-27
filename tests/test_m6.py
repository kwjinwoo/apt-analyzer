import json
import subprocess
from decimal import Decimal

from apt_analyzer.cli import regional_ingest_input, regional_profile_input
from apt_analyzer.regional_profile import (
    MetricDefinition,
    MetricObservation,
    profile_metrics,
)

DEFINITIONS = (
    MetricDefinition("median_price_krw", "KRW", "overall-period eligible population"),
    MetricDefinition("transaction_count", "count", "overall-period eligible population"),
    MetricDefinition("mdd_ratio", "ratio", "observed monthly median"),
)


def test_profile_exposes_distribution_midrank_percentiles_and_pairwise_correlation() -> None:
    observations = (
        MetricObservation(
            "a",
            {
                "median_price_krw": Decimal(100),
                "transaction_count": Decimal(1),
                "mdd_ratio": Decimal("-0.2"),
            },
            {},
        ),
        MetricObservation(
            "b",
            {"median_price_krw": Decimal(200), "transaction_count": Decimal(2)},
            {"mdd_ratio": "fewer than two observed months"},
        ),
        MetricObservation(
            "c",
            {
                "median_price_krw": Decimal(200),
                "transaction_count": Decimal(3),
                "mdd_ratio": Decimal("-0.1"),
            },
            {},
        ),
        MetricObservation(
            "d",
            {"median_price_krw": Decimal(400), "mdd_ratio": Decimal("-0.3")},
            {"transaction_count": "metric unavailable"},
        ),
    )

    profile = profile_metrics(observations, DEFINITIONS)

    price = profile.distributions["median_price_krw"]
    assert price.sample_size == 4
    assert price.missing_count == 0
    assert (price.minimum, price.q1, price.median, price.q3, price.maximum) == (
        Decimal(100),
        Decimal(175),
        Decimal(200),
        Decimal(250),
        Decimal(400),
    )
    candidates = {candidate.candidate_id: candidate for candidate in profile.candidates}
    assert candidates["a"].percentiles["median_price_krw"] == Decimal("0.125")
    assert candidates["b"].percentiles["median_price_krw"] == Decimal("0.5")
    assert candidates["c"].percentiles["median_price_krw"] == Decimal("0.5")
    assert candidates["d"].percentiles["median_price_krw"] == Decimal("0.875")
    assert "transaction_count" in candidates["d"].unavailable

    correlation = next(
        item
        for item in profile.correlations
        if (item.left_metric, item.right_metric) == ("median_price_krw", "transaction_count")
    )
    assert correlation.sample_size == 3
    assert correlation.value == Decimal("0.866025")
    assert correlation.unavailable_reason is None
    assert "not an investment recommendation" in profile.disclaimer
    assert "higher percentile does not mean better" in profile.disclaimer


def test_profile_marks_empty_and_constant_pairwise_evidence_unavailable() -> None:
    observations = (
        MetricObservation(
            "a", {"median_price_krw": Decimal(100), "transaction_count": Decimal(1)}, {}
        ),
        MetricObservation(
            "b", {"median_price_krw": Decimal(100), "transaction_count": Decimal(2)}, {}
        ),
    )

    profile = profile_metrics(observations, DEFINITIONS)

    assert profile.distributions["mdd_ratio"].sample_size == 0
    assert profile.distributions["mdd_ratio"].missing_count == 2
    constant = profile.correlations[0]
    assert constant.sample_size == 2
    assert constant.value is None
    assert constant.unavailable_reason == "constant pairwise observations"
    insufficient = profile.correlations[1]
    assert insufficient.sample_size == 0
    assert insufficient.value is None
    assert insufficient.unavailable_reason == "fewer than two pairwise-complete observations"


def test_real_m6_cli_json_and_text_are_equivalent(tmp_path) -> None:
    db = tmp_path / "m6.sqlite3"
    period = {"start": "2024-01-01", "end": "2024-02-29"}
    ingest_period = {"start": "2023-12-01", "end": "2024-02-29"}
    candidates = []
    resolutions = {}
    transactions = {}
    for index, price in enumerate((100, 200, 300), start=1):
        source_id = f"src-{index}"
        apartment_id = f"apt-{index}"
        candidates.append(
            {
                "source_id": source_id,
                "name": f"A{index}",
                "legal_dong_code": "1111010100",
                "lot_address": f"lot-{index}",
                "road_address": f"road-{index}",
            }
        )
        resolutions[source_id] = {
            "internal_id": apartment_id,
            "display_name": f"A{index}",
        }
        transactions[source_id] = [
            {
                "apartment_id": apartment_id,
                "contract_date": "2024-01-15",
                "price_krw": price,
                "exclusive_area_sqm": 84,
                "transaction_type": "brokered",
                "is_cancelled": False,
                "source_name": "MOLIT apartment sale transactions",
            },
            {
                "apartment_id": apartment_id,
                "contract_date": "2024-02-15",
                "price_krw": price - 10,
                "exclusive_area_sqm": 84,
                "transaction_type": "brokered",
                "is_cancelled": False,
                "source_name": "MOLIT apartment sale transactions",
            },
        ]
    regional_ingest_input(
        {
            "regions": ["11"],
            "period": ingest_period,
            "candidates_by_region": {"11": candidates},
            "resolutions": resolutions,
            "transactions": transactions,
        },
        str(db),
    )
    payload = {
        "regions": ["11"],
        "config": {
            "overall_period": period,
            "turnover_period": period,
            "baseline_period": period,
            "comparison_period": period,
            "mdd_period": period,
            "inclusion_policy": {
                "include_cancelled": False,
                "transaction_types": ["brokered"],
            },
        },
    }
    direct = regional_profile_input(payload, str(db))
    assert direct["status"] == "complete"
    assert direct["peer_group"]["regions"] == ["11"]
    assert len(direct["peer_group"]["candidates"]) == 3
    assert direct["profile"]["distributions"]["median_price_krw"]["sample_size"] == 3

    input_path = tmp_path / "profile.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    json_result = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "apt-analyzer",
            "regional-profile",
            str(input_path),
            "--db",
            str(db),
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    text_result = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "apt-analyzer",
            "regional-profile",
            str(input_path),
            "--db",
            str(db),
            "--format",
            "text",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(json_result.stdout) == json.loads(
        text_result.stdout.removeprefix("Regional profile result\n")
    )
