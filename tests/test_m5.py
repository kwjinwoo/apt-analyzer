import json
import subprocess
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apt_analyzer.analytics import HouseholdEvidence
from apt_analyzer.cli import regional_ingest_input, screen_input
from apt_analyzer.comparison import CommonAnalysisConfig
from apt_analyzer.domain import (
    AnalysisPeriod,
    Apartment,
    NormalizedTransaction,
    TransactionInclusionPolicy,
    TransactionType,
)
from apt_analyzer.persistence import SQLiteStore
from apt_analyzer.regional_screening import (
    SUPPORTED_METHODS,
    CandidateCache,
    CandidateRefreshState,
    CandidateScreenRule,
    RegionalCandidate,
    RegionalIngestPlan,
    SQLiteCandidateCache,
    ingest_regional,
    screen_candidates,
)


def _period() -> AnalysisPeriod:
    return AnalysisPeriod(date(2024, 1, 1), date(2024, 3, 31))


def _config(area_group_key: str | None = None) -> CommonAnalysisConfig:
    period = _period()
    return CommonAnalysisConfig(
        period,
        period,
        period,
        period,
        period,
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
        area_group_key=area_group_key,
    )


def test_candidate_refresh_is_fresh_and_second_refresh_skips() -> None:
    cache = CandidateCache()
    candidate = RegionalCandidate("src-1", "Alpha", "11", "lot", "road")

    first = cache.refresh("K-APT", "11", lambda: (candidate,))
    second = cache.refresh("K-APT", "11", lambda: (_ for _ in ()).throw(AssertionError()))

    assert first.state is CandidateRefreshState.FRESH
    assert first.candidates == (candidate,)
    assert second.state is CandidateRefreshState.FRESH
    assert second.skipped is True


def test_candidate_refresh_distinguishes_empty_miss_stale_and_failure() -> None:
    cache = CandidateCache()
    empty = cache.refresh("K-APT", "22", lambda: ())
    assert empty.state is CandidateRefreshState.VALID_EMPTY
    assert empty.candidates == ()

    miss = cache.read("K-APT", "33")
    assert miss.state is CandidateRefreshState.CACHE_MISS

    cache = CandidateCache()
    stale = cache.refresh("K-APT", "11", lambda: (RegionalCandidate("s", "A", "11", "l", "r"),))
    failed = cache.refresh(
        "K-APT", "11", lambda: (_ for _ in ()).throw(RuntimeError("down")), force=True
    )
    assert stale.state is CandidateRefreshState.FRESH
    assert failed.state is CandidateRefreshState.EXTERNAL_FAILURE
    assert failed.previous_state is CandidateRefreshState.FRESH
    assert failed.candidates == stale.candidates


def test_sqlite_candidate_cache_preserves_persisted_snapshot_on_failure(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "m5.db")
    cache = SQLiteCandidateCache(store, clock=lambda: datetime(2024, 4, 1, tzinfo=UTC))
    candidate = RegionalCandidate("src-1", "Alpha", "11", "lot", "road")
    assert cache.read("K-APT", "11").state is CandidateRefreshState.CACHE_MISS
    assert cache.refresh("K-APT", "11", lambda: (candidate,)).state is CandidateRefreshState.FRESH
    assert (
        cache.read("K-APT", "11", cutoff=datetime(2024, 5, 1, tzinfo=UTC)).state
        is CandidateRefreshState.STALE
    )
    failed = cache.refresh(
        "K-APT", "11", lambda: (_ for _ in ()).throw(RuntimeError("down")), force=True
    )
    assert failed.state is CandidateRefreshState.EXTERNAL_FAILURE
    assert failed.candidates == (candidate,)
    assert cache.read("K-APT", "11").state is CandidateRefreshState.EXTERNAL_FAILURE


def test_sqlite_candidate_cache_expires_at_exactly_24_hours(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "boundary.db")
    cache = SQLiteCandidateCache(store, clock=lambda: datetime(2024, 4, 2, tzinfo=UTC))
    candidate = RegionalCandidate("src-1", "Alpha", "11", "lot", "road")
    store.save_candidate_snapshot(
        "K-APT", "11", (candidate,), fetched_at="2024-04-01T00:00:00+00:00"
    )

    assert (
        cache.read("K-APT", "11", cutoff=datetime(2024, 4, 2, tzinfo=UTC)).state
        is CandidateRefreshState.STALE
    )


def test_sqlite_candidate_cache_persists_valid_empty_distinct_from_miss(tmp_path) -> None:
    path = tmp_path / "empty.db"
    store = SQLiteStore(path)
    cache = SQLiteCandidateCache(store, clock=lambda: datetime(2024, 4, 1, tzinfo=UTC))

    assert cache.refresh("K-APT", "11", lambda: ()).state is CandidateRefreshState.VALID_EMPTY
    store.close()

    reopened = SQLiteStore(path)
    assert (
        SQLiteCandidateCache(reopened).read("K-APT", "11").state
        is CandidateRefreshState.VALID_EMPTY
    )
    assert (
        SQLiteCandidateCache(reopened).read("K-APT", "26").state is CandidateRefreshState.CACHE_MISS
    )


def test_regional_ingest_is_bounded_and_persists_resolution_and_molit_coverage(tmp_path) -> None:
    class Source:
        def list_region(self, region):
            return (
                RegionalCandidate("wanted", "A", region, "lot", "road"),
                RegionalCandidate("other", "B", region, "lot", "road"),
            )

        def resolve(self, candidate):
            from apt_analyzer.apartment_data import IdentityResolution, ResolutionStatus

            return candidate, IdentityResolution(
                ResolutionStatus.RESOLVED, (candidate,), Apartment("apt-1", "A")
            )

        def retrieve(self, candidate, apartment, period):
            return (
                NormalizedTransaction(
                    apartment.internal_id,
                    period.start,
                    100,
                    Decimal("84"),
                    TransactionType.BROKERED,
                    False,
                    source_name="MOLIT apartment sale transactions",
                    source_record_id=period.start.isoformat(),
                ),
            )

    store = SQLiteStore(tmp_path / "ingest.db")
    report = ingest_regional(
        RegionalIngestPlan(("11",), _period(), frozenset({"wanted"})), source=Source(), store=store
    )
    assert report.candidates_seen == 1
    assert store.candidate_resolution("K-APT apartment list", "11", "wanted") == "apt-1"
    assert store.coverage("apt-1", "MOLIT apartment sale transactions")


def test_failed_transaction_month_is_persisted_as_failed_not_valid_empty(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "failure.db")
    apartment = Apartment("apt-1", "A")
    report = store.update_incremental(
        apartment,
        AnalysisPeriod(date(2024, 1, 1), date(2024, 1, 31)),
        lambda _month: (_ for _ in ()).throw(RuntimeError("source down")),
        source_name="MOLIT apartment sale transactions",
    )

    assert report.failures
    assert store.coverage_states(apartment.internal_id, "MOLIT apartment sale transactions") == {
        "202401": "failed"
    }


def test_v2_migration_preserves_coverage_and_adds_period_index(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "v2.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL);
            INSERT INTO schema_version VALUES (2);
            CREATE TABLE apartments (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL);
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, apartment_id TEXT NOT NULL,
                contract_date TEXT NOT NULL, price_krw INTEGER NOT NULL,
                exclusive_area_sqm TEXT NOT NULL, transaction_type TEXT NOT NULL,
                is_cancelled INTEGER NOT NULL, floor INTEGER, building TEXT, unit TEXT,
                construction_year INTEGER, broker_location TEXT, source_name TEXT,
                source_record_id TEXT, source_values TEXT NOT NULL, source_key TEXT NOT NULL
            );
            CREATE UNIQUE INDEX uq_transactions_source
                ON transactions(apartment_id, COALESCE(source_name, ''), source_key);
            CREATE TABLE monthly_coverage (
                apartment_id TEXT NOT NULL, source_name TEXT NOT NULL, month TEXT NOT NULL,
                fetched_at TEXT NOT NULL, PRIMARY KEY(apartment_id, source_name, month)
            );
            INSERT INTO apartments VALUES ('apt-1', 'A');
            INSERT INTO monthly_coverage VALUES ('apt-1', 'fixture', '202401', '2024-02-01T00:00:00+00:00');
            """
        )

    store = SQLiteStore(path)

    assert store.schema_version == 7
    assert store.coverage_states("apt-1", "fixture") == {"202401": "valid_empty"}
    assert "ix_transactions_apartment_contract" in store.transaction_query_plan(
        "apt-1", AnalysisPeriod(date(2024, 1, 1), date(2024, 1, 31))
    )


def test_ingest_rejects_candidate_returned_outside_requested_region(tmp_path) -> None:
    class Source:
        def list_region(self, region):
            return (RegionalCandidate("wrong", "Wrong", "99", "lot", "road"),)

    with pytest.raises(ValueError, match="region"):
        ingest_regional(
            RegionalIngestPlan(("11",), _period()),
            source=Source(),
            store=SQLiteStore(tmp_path / "x.db"),
        )


def test_persisted_screening_round_trip_uses_one_candidate_and_common_context(tmp_path) -> None:
    db = tmp_path / "cli.db"
    ingested = regional_ingest_input(
        {
            "regions": ["11"],
            "period": {"start": "2024-01-01", "end": "2024-03-31"},
            "candidate_source_ids": ["src-1"],
            "candidates_by_region": {
                "11": [
                    {
                        "source_id": "src-1",
                        "name": "A",
                        "legal_dong_code": "1111010100",
                        "lot_address": "lot",
                        "road_address": "road",
                    }
                ]
            },
            "resolutions": {"src-1": {"internal_id": "apt-1", "display_name": "A"}},
            "transactions": {"src-1": []},
        },
        str(db),
    )
    assert ingested["report"]["candidates_resolved"] == 1
    payload = {
        "regions": ["11"],
        "candidate_source_ids": ["src-1"],
        "config": {
            "overall_period": {"start": "2024-01-01", "end": "2024-03-31"},
            "turnover_period": {"start": "2024-01-01", "end": "2024-03-31"},
            "baseline_period": {"start": "2024-01-01", "end": "2024-03-31"},
            "comparison_period": {"start": "2024-01-01", "end": "2024-03-31"},
            "mdd_period": {"start": "2024-01-01", "end": "2024-03-31"},
            "inclusion_policy": {"include_cancelled": False, "transaction_types": ["brokered"]},
        },
        "rules": [{"metric": "transaction_count", "operator": "gte", "value": 0, "unit": "count"}],
    }
    output = screen_input(payload, str(db))
    assert output["status"] == "complete"
    assert output["results"][0]["included"] is True
    assert output["results"][0]["context"]["apartment"]["display_name"] == "A"
    assert output["rules"][0]["method"] == SUPPORTED_METHODS["transaction_count"]
    assert "not an investment recommendation" in output["disclaimer"]


def test_real_m5_cli_json_and_text_are_equivalent(tmp_path) -> None:
    db = tmp_path / "cli.sqlite3"
    ingest_path = tmp_path / "ingest.json"
    screen_path = tmp_path / "screen.json"
    period = {"start": "2024-01-01", "end": "2024-01-31"}
    ingest_path.write_text(
        json.dumps(
            {
                "regions": ["11"],
                "period": period,
                "candidates_by_region": {
                    "11": [
                        {
                            "source_id": "src-1",
                            "name": "A",
                            "legal_dong_code": "1111010100",
                            "lot_address": "lot",
                            "road_address": "road",
                        }
                    ]
                },
                "resolutions": {"src-1": {"internal_id": "apt-1", "display_name": "A"}},
                "transactions": {"src-1": []},
            }
        ),
        encoding="utf-8",
    )
    screen_path.write_text(
        json.dumps(
            {
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
                "rules": [
                    {
                        "metric": "transaction_count",
                        "operator": "eq",
                        "value": 0,
                        "unit": "count",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ingested = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "apt-analyzer",
            "regional-ingest",
            str(ingest_path),
            "--db",
            str(db),
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    json_result = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "apt-analyzer",
            "screen",
            str(screen_path),
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
            "screen",
            str(screen_path),
            "--db",
            str(db),
            "--format",
            "text",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(ingested.stdout)["report"]["candidates_resolved"] == 1
    assert json.loads(json_result.stdout) == json.loads(
        text_result.stdout.removeprefix("Screening result\n")
    )


def test_screening_validates_units_methods_and_ne_unavailable() -> None:
    apartment = Apartment("apt-1", "A")
    with pytest.raises(ValueError):
        screen_candidates(
            (apartment,),
            {},
            _config(),
            (
                CandidateScreenRule(
                    "median_price_krw",
                    "eq",
                    Decimal(1),
                    "sqm",
                    "overall-period eligible population",
                ),
            ),
        )
    result = screen_candidates(
        (apartment,),
        {"apt-1": ()},
        _config(),
        (
            CandidateScreenRule(
                "median_price_krw",
                "ne",
                Decimal(1),
                "KRW",
                SUPPORTED_METHODS["median_price_krw"],
            ),
        ),
    )
    assert result[0].included is False
    assert "median_price_krw" in result[0].unavailable
    assert "not an investment recommendation" in result[0].disclaimer

    with pytest.raises(ValueError, match="method"):
        screen_candidates(
            (apartment,),
            {"apt-1": ()},
            _config(),
            (CandidateScreenRule("transaction_count", "eq", Decimal(0), "count", "wrong method"),),
        )


def test_screening_computes_all_metrics_with_common_area_and_household_context() -> None:
    apartment = Apartment("apt-1", "A")
    period = AnalysisPeriod(date(2023, 1, 1), date(2024, 12, 31))
    year_2023 = AnalysisPeriod(date(2023, 1, 1), date(2023, 12, 31))
    year_2024 = AnalysisPeriod(date(2024, 1, 1), date(2024, 12, 31))
    config = CommonAnalysisConfig(
        period,
        year_2024,
        year_2023,
        year_2024,
        period,
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
        area_group_key="floor-84",
    )
    transactions = tuple(
        NormalizedTransaction("apt-1", day, price, Decimal("84.1"), TransactionType.BROKERED, False)
        for day, price in (
            (date(2023, 1, 1), 100),
            (date(2023, 2, 1), 120),
            (date(2024, 1, 1), 90),
            (date(2024, 2, 1), 80),
        )
    )
    expected = {
        "median_price_krw": Decimal(95),
        "median_area_sqm": Decimal("84.1"),
        "transaction_count": Decimal(4),
        "turnover_ratio": Decimal("0.02"),
        "retention_ratio": Decimal(1),
        "mdd_ratio": Decimal(80) / Decimal(120) - 1,
    }
    rules = tuple(
        CandidateScreenRule(metric, "eq", value, unit, SUPPORTED_METHODS[metric])
        for metric, value in expected.items()
        for unit in [
            {
                "median_price_krw": "KRW",
                "median_area_sqm": "sqm",
                "transaction_count": "count",
                "turnover_ratio": "ratio",
                "retention_ratio": "ratio",
                "mdd_ratio": "ratio",
            }[metric]
        ]
    )

    result = screen_candidates(
        (apartment,),
        {"apt-1": transactions},
        config,
        rules,
        households={"apt-1": HouseholdEvidence(100, "floor-84", "fixture")},
    )[0]

    assert result.included is True
    assert result.values == expected
    assert result.context.area_selection.group is not None
    assert result.context.area_selection.group.key == "floor-84"


def test_screening_distinguishes_valid_empty_from_incomplete_coverage() -> None:
    apartment = Apartment("apt-1", "A")
    rule = CandidateScreenRule(
        "transaction_count",
        "eq",
        Decimal(0),
        "count",
        SUPPORTED_METHODS["transaction_count"],
    )
    complete_empty = {"apt-1": {month: "valid_empty" for month in ("202401", "202402", "202403")}}

    valid_empty = screen_candidates(
        (apartment,), {"apt-1": ()}, _config(), (rule,), coverage=complete_empty
    )[0]
    incomplete = screen_candidates(
        (apartment,),
        {"apt-1": ()},
        _config(),
        (rule,),
        coverage={"apt-1": {"202401": "valid_empty"}},
    )[0]

    assert valid_empty.included is True
    assert valid_empty.data_status == "valid_empty"
    assert incomplete.included is False
    assert "coverage" in incomplete.unavailable


def test_missing_common_area_group_cannot_pass_even_a_not_equal_rule() -> None:
    apartment = Apartment("apt-1", "A")
    transaction = NormalizedTransaction(
        "apt-1", date(2024, 1, 1), 100, Decimal("84.1"), TransactionType.BROKERED, False
    )
    result = screen_candidates(
        (apartment,),
        {"apt-1": (transaction,)},
        _config("floor-59"),
        (
            CandidateScreenRule(
                "transaction_count",
                "ne",
                Decimal(999),
                "count",
                SUPPORTED_METHODS["transaction_count"],
            ),
        ),
    )[0]

    assert result.included is False
    assert "area_group" in result.unavailable


@pytest.mark.parametrize("operator", ("eq", "ne", "gt", "gte", "lt", "lte"))
def test_screening_supports_all_explicit_operators(operator: str) -> None:
    apartment = Apartment("apt-1", "A")
    transaction = NormalizedTransaction(
        "apt-1", date(2024, 1, 1), 100, Decimal("84"), TransactionType.BROKERED, False
    )
    result = screen_candidates(
        (apartment,),
        {"apt-1": (transaction,)},
        _config(),
        (
            CandidateScreenRule(
                "transaction_count",
                operator,
                Decimal(1),
                "count",
                SUPPORTED_METHODS["transaction_count"],
            ),
        ),
    )
    assert result[0].included is (operator in {"eq", "gte", "lte"})
