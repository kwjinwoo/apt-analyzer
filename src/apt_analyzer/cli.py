"""Deterministic JSON/text command-line interface for the M2 analyzer."""

import argparse
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any, cast

from apt_analyzer.analytics import (
    AnalysisResult,
    DataCoverageStatus,
    HouseholdEvidence,
    analyze,
    discover_area_groups,
)
from apt_analyzer.comparison import CommonAnalysisConfig, ComparisonResult, compare
from apt_analyzer.domain import (
    AnalysisContext,
    AnalysisPeriod,
    Apartment,
    AreaSelection,
    NormalizedTransaction,
    TransactionInclusionPolicy,
    TransactionType,
)


def main() -> None:
    """Run ``apt-analyzer analyze INPUT --format text|json``."""
    parser = argparse.ArgumentParser(prog="apt-analyzer")
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("analyze")
    command.add_argument("input")
    command.add_argument("--format", choices=("text", "json"), default="text")
    compare_command = subparsers.add_parser("compare")
    compare_command.add_argument("input")
    compare_command.add_argument("--format", choices=("text", "json"), default="text")
    web_command = subparsers.add_parser("web")
    web_command.add_argument("--host", default="127.0.0.1")
    web_command.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "analyze":
        result = analyze_input(json.loads(open(args.input, encoding="utf-8").read()))
        print(
            json.dumps(result_to_dict(result), ensure_ascii=False, indent=2)
            if args.format == "json"
            else result_to_text(result)
        )
    if args.command == "compare":
        result = compare_input(json.loads(open(args.input, encoding="utf-8").read()))
        print(
            json.dumps(comparison_to_dict(result), ensure_ascii=False, indent=2)
            if args.format == "json"
            else comparison_to_text(result)
        )
    if args.command == "web":
        if args.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("web server must bind to loopback by default")
        import os

        os.environ.setdefault("APT_ANALYZER_DB", "apt-analyzer.sqlite3")
        import uvicorn

        uvicorn.run("apt_analyzer.web:app", host=args.host, port=args.port)


def analyze_input(payload: dict[str, Any]) -> AnalysisResult:
    """Parse the explicit offline input contract and calculate its result."""
    apartment_data = payload["apartment"]
    data_status = payload.get("data_status")
    if data_status not in (DataCoverageStatus.COMPLETE, DataCoverageStatus.VALID_EMPTY):
        raise ValueError("data_status must be 'complete' or 'valid_empty'")
    apartment = Apartment(apartment_data["internal_id"], apartment_data["display_name"])
    period = _period(payload["period"])
    inclusion_data = payload["inclusion_policy"]
    policy = TransactionInclusionPolicy(
        bool(inclusion_data["include_cancelled"]),
        frozenset(TransactionType(value) for value in inclusion_data["transaction_types"]),
    )
    transactions = tuple(_transaction(item) for item in payload["transactions"])
    area_data = payload.get("area_selection", {"kind": "all"})
    if area_data.get("kind") == "all":
        selection = AreaSelection.all()
    else:
        available = discover_area_groups(
            transaction
            for transaction in transactions
            if transaction.apartment_id == apartment.internal_id
            and period.includes(transaction.contract_date)
        )
        matches = tuple(group for group in available if group.key == area_data["key"])
        if not matches:
            raise ValueError("area group key is not present in selected-apartment evidence")
        selection = AreaSelection.for_group(matches[0])
    context = AnalysisContext(apartment, period, selection, policy)
    household_data = payload.get("household")
    household = (
        None
        if household_data is None
        else HouseholdEvidence(
            household_data.get("count"), household_data["scope"], household_data.get("source")
        )
    )
    return analyze(
        transactions,
        context,
        turnover_period=_optional_period(payload.get("turnover_period")),
        household=household,
        baseline_period=_optional_period(payload.get("baseline_period")),
        comparison_period=_optional_period(payload.get("comparison_period")),
        data_status=data_status,
    )


def compare_input(payload: dict[str, Any]) -> ComparisonResult:
    """Parse a deterministic offline comparison input."""
    apartments = tuple(
        Apartment(item["internal_id"], item["display_name"]) for item in payload["apartments"]
    )
    config_data = payload["config"]
    policy_data = config_data["inclusion_policy"]
    config = CommonAnalysisConfig(
        _period(config_data["overall_period"]),
        _period(config_data["turnover_period"]),
        _period(config_data["baseline_period"]),
        _period(config_data["comparison_period"]),
        _period(config_data["mdd_period"]),
        TransactionInclusionPolicy(
            bool(policy_data["include_cancelled"]),
            frozenset(TransactionType(value) for value in policy_data["transaction_types"]),
        ),
        config_data.get("area_grouping_policy", "integer-floor-exclusive-area"),
        config_data.get("area_group_key"),
        config_data.get("price_series_method", "observed monthly median"),
    )
    transactions: dict[str, tuple[NormalizedTransaction, ...]] = {}
    for apartment_id, values in payload.get("transactions", {}).items():
        transactions[apartment_id] = tuple(_transaction(item) for item in values)
    households = {
        apartment_id: HouseholdEvidence(value.get("count"), value["scope"], value.get("source"))
        for apartment_id, value in payload.get("households", {}).items()
    }
    return compare(apartments, transactions, config, households)


def result_to_dict(result: AnalysisResult) -> dict[str, Any]:
    """Serialize an analysis without converting Decimal monetary values to float."""
    return {
        "context": json_value(result.population.context),
        "raw_count": len(result.population.raw),
        "eligible_count": len(result.population.eligible),
        "yearly_summaries": json_value(result.yearly_summaries),
        "monthly_prices": json_value(result.monthly_prices),
        "turnover": json_value(result.turnover),
        "retention": json_value(result.retention),
        "mdd": json_value(result.mdd),
        "annual_turnover": json_value(result.annual_turnover),
        "available_area_groups": json_value(result.available_area_groups),
        "area_grouping_policy": result.area_grouping_policy,
        "area_discovery_period": json_value(result.area_discovery_period),
        "data_status": result.data_status,
    }


def result_to_text(result: AnalysisResult) -> str:
    """Serialize every material result field in deterministic readable JSON text."""
    return "Analysis result\n" + json.dumps(result_to_dict(result), ensure_ascii=False, indent=2)


def comparison_to_dict(result: ComparisonResult) -> dict[str, Any]:
    """Serialize comparison context and equivalent subject evidence."""
    return {
        "config": json_value(result.config),
        "subjects": [json_value(subject) for subject in result.subjects],
    }


def comparison_to_text(result: ComparisonResult) -> str:
    """Serialize a readable deterministic comparison export."""
    return "Comparison result\n" + json.dumps(
        comparison_to_dict(result), ensure_ascii=False, indent=2
    )


def _transaction(data: dict[str, Any]) -> NormalizedTransaction:
    return NormalizedTransaction(
        data["apartment_id"],
        date.fromisoformat(data["contract_date"]),
        int(data["price_krw"]),
        Decimal(str(data["exclusive_area_sqm"])),
        TransactionType(data["transaction_type"]),
        bool(data["is_cancelled"]),
        data.get("floor"),
        data.get("building"),
        data.get("unit"),
        data.get("construction_year"),
        data.get("broker_location"),
        data.get("source_name"),
        data.get("source_record_id"),
        tuple(tuple(item) for item in data.get("source_values", [])),
    )


def _period(data: dict[str, str]) -> AnalysisPeriod:
    return AnalysisPeriod(date.fromisoformat(data["start"]), date.fromisoformat(data["end"]))


def _optional_period(data: dict[str, str] | None) -> AnalysisPeriod | None:
    return None if data is None else _period(data)


def json_value(value: Any) -> Any:
    """Convert domain values into deterministic JSON-compatible primitives."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        sequence = cast(tuple[Any, ...] | list[Any], value)
        return [json_value(item) for item in sequence]
    if isinstance(value, (frozenset, set)):
        sequence = cast(frozenset[Any] | set[Any], value)
        return sorted(json_value(item) for item in sequence)
    if hasattr(value, "__dataclass_fields__"):
        return {key: json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        mapping = cast(dict[Any, Any], value)
        return {str(key): json_value(item) for key, item in mapping.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
