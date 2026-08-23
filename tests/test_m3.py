from dataclasses import replace
from datetime import date
from decimal import Decimal

from apt_analyzer.analytics import HouseholdEvidence
from apt_analyzer.comparison import CommonAnalysisConfig, compare
from apt_analyzer.domain import (
    AnalysisPeriod,
    Apartment,
    NormalizedTransaction,
    TransactionInclusionPolicy,
    TransactionType,
)
from apt_analyzer.persistence import SQLiteStore


def test_legacy_v1_database_migrates_and_preserves_transaction(tmp_path):
    import sqlite3

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL);
            INSERT INTO schema_version VALUES (1);
            CREATE TABLE apartments (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL);
            CREATE TABLE transactions (
                apartment_id TEXT NOT NULL, contract_date TEXT NOT NULL, price_krw INTEGER NOT NULL,
                exclusive_area_sqm TEXT NOT NULL, transaction_type TEXT NOT NULL, is_cancelled INTEGER NOT NULL,
                source_name TEXT, source_record_id TEXT, source_values TEXT
            );
            INSERT INTO apartments VALUES ('apt-1', 'Example');
            INSERT INTO transactions VALUES ('apt-1', '2025-01-01', 100000000, '84.1', 'brokered', 0, 'fixture', 'row-1', '[["dealAmount","10000"]]');
            """
        )
    store = SQLiteStore(path)
    assert store.schema_version == 2
    assert store.load_transactions("apt-1") == (
        NormalizedTransaction(
            "apt-1",
            date(2025, 1, 1),
            100000000,
            Decimal("84.1"),
            TransactionType.BROKERED,
            False,
            source_name="fixture",
            source_record_id="row-1",
            source_values=(("dealAmount", "10000"),),
        ),
    )


def test_incremental_update_caches_empty_and_skips_fresh_month(tmp_path):
    store = SQLiteStore(tmp_path / "data.db")
    apartment = Apartment("apt-1", "Example")
    calls = []
    period = AnalysisPeriod(date(2025, 1, 1), date(2025, 2, 28))
    report = store.update_incremental(apartment, period, lambda month: calls.append(month) or ())
    second = store.update_incremental(apartment, period, lambda month: calls.append(month) or ())
    assert report.fetched_months == ("202501", "202502")
    assert second.skipped_months == ("202501", "202502")
    assert calls == ["202501", "202502"]


def test_migration_duplicate_is_deterministic_and_source_coverage_isolated(tmp_path):
    import sqlite3

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL); INSERT INTO schema_version VALUES (1);
            CREATE TABLE apartments (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL);
            CREATE TABLE transactions (apartment_id TEXT NOT NULL, contract_date TEXT NOT NULL, price_krw INTEGER NOT NULL, exclusive_area_sqm TEXT NOT NULL, transaction_type TEXT NOT NULL, is_cancelled INTEGER NOT NULL, source_name TEXT, source_record_id TEXT, source_values TEXT);
            INSERT INTO transactions VALUES ('apt-1', '2025-01-01', 100, '84', 'brokered', 0, 'source-a', 'row-1', '[]');
            """
        )
    store = SQLiteStore(path)
    tx = store.load_transactions("apt-1")[0]
    report = store.update_incremental(
        Apartment("apt-1", "Example"),
        AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        lambda _: (tx,),
        source_name="source-a",
    )
    assert report.inserted_count == 0 and report.duplicate_count == 1
    assert len(store.load_transactions("apt-1")) == 1
    source_b = store.update_incremental(
        Apartment("apt-1", "Example"),
        AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        lambda _: (),
        source_name="source-b",
    )
    assert source_b.fetched_months == ("202501",)


def test_legacy_exact_duplicates_collapse_during_atomic_migration(tmp_path):
    import sqlite3

    path = tmp_path / "duplicates.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_version (version INTEGER NOT NULL); INSERT INTO schema_version VALUES (1);
            CREATE TABLE apartments (internal_id TEXT PRIMARY KEY, display_name TEXT NOT NULL);
            CREATE TABLE transactions (apartment_id TEXT NOT NULL, contract_date TEXT NOT NULL, price_krw INTEGER NOT NULL, exclusive_area_sqm TEXT NOT NULL, transaction_type TEXT NOT NULL, is_cancelled INTEGER NOT NULL, source_name TEXT, source_record_id TEXT, source_values TEXT);
            INSERT INTO transactions VALUES ('apt-1', '2025-01-01', 100, '84', 'brokered', 0, 'source-a', 'row-1', '[]');
            INSERT INTO transactions VALUES ('apt-1', '2025-01-01', 100, '84', 'brokered', 0, 'source-a', 'row-1', '[]');
            """
        )
    store = SQLiteStore(path)
    assert store.schema_version == 2
    assert len(store.load_transactions("apt-1")) == 1


def test_invalid_schema_version_and_mismatched_month_are_failures(tmp_path):
    import sqlite3

    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version VALUES (3)")
    import pytest

    with pytest.raises(ValueError, match="unsupported schema version"):
        SQLiteStore(path)
    store = SQLiteStore(tmp_path / "valid.db")
    result = store.update_incremental(
        Apartment("apt-1", "Example"),
        AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        lambda _: (
            NormalizedTransaction(
                "other", date(2025, 1, 1), 1, Decimal("84"), TransactionType.BROKERED, False
            ),
        ),
    )
    assert result.failures and not store.coverage("apt-1", "unknown")


def test_source_provenance_mismatch_does_not_create_coverage(tmp_path):
    store = SQLiteStore(tmp_path / "data.db")
    result = store.update_incremental(
        Apartment("apt-1", "Example"),
        AnalysisPeriod(date(2025, 1, 1), date(2025, 1, 31)),
        lambda _: (
            NormalizedTransaction(
                "apt-1",
                date(2025, 1, 1),
                1,
                Decimal("84"),
                TransactionType.BROKERED,
                False,
                source_name="source-b",
            ),
        ),
        source_name="source-a",
    )
    assert result.failures and not store.coverage("apt-1", "source-a")


def test_comparison_rejects_duplicate_subjects_and_cross_subject_records():
    from apt_analyzer.comparison import CommonAnalysisConfig, compare

    period = AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31))
    config = CommonAnalysisConfig(
        period,
        period,
        period,
        period,
        period,
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
    )
    apartment = Apartment("a", "A")
    tx = NormalizedTransaction(
        "other", date(2025, 1, 1), 1, Decimal("84"), TransactionType.BROKERED, False
    )
    import pytest

    with pytest.raises(ValueError, match="at least two"):
        compare((apartment,), {"a": ()}, config)
    with pytest.raises(ValueError, match="does not match"):
        compare((apartment, Apartment("b", "B")), {"a": (tx,), "b": ()}, config)


def test_missing_household_serializes_unavailable_distinct_from_zero_mdd():
    from apt_analyzer.cli import result_to_dict
    from apt_analyzer.comparison import CommonAnalysisConfig, compare

    period = AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31))
    config = CommonAnalysisConfig(
        period,
        period,
        period,
        period,
        period,
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
    )
    txs = tuple(
        NormalizedTransaction(
            "a", date(2025, month, 1), 100, Decimal("84"), TransactionType.BROKERED, False
        )
        for month in (1, 3)
    )
    result = compare((Apartment("a", "A"), Apartment("b", "B")), {"a": txs, "b": txs[:0]}, config)
    serialized = result_to_dict(result.subjects[0].result)  # type: ignore[arg-type]
    assert serialized["turnover"]["value"] is None
    assert serialized["turnover"]["unavailable"]["status"] == "unavailable"
    assert serialized["mdd"]["value"] == "0"


def test_comparison_has_one_common_config_and_missing_group_is_unavailable():
    apartments = (Apartment("a", "A"), Apartment("b", "B"))
    tx = NormalizedTransaction(
        "a", date(2025, 1, 1), 100, Decimal("84.1"), TransactionType.BROKERED, False
    )
    period = AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31))
    config = CommonAnalysisConfig(
        period,
        period,
        period,
        period,
        period,
        TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED})),
        area_group_key="floor-84",
    )
    result = compare(
        apartments,
        {"a": (tx,), "b": ()},
        config,
        {"a": HouseholdEvidence(10, "floor-84", "fixture")},
    )
    assert result.subjects[0].available
    assert not result.subjects[1].available
    assert result.subjects[1].unavailable_reason


def test_two_available_subjects_share_all_metric_context_and_persisted_evidence(tmp_path):
    period = AnalysisPeriod(date(2025, 1, 1), date(2025, 12, 31))
    policy = TransactionInclusionPolicy(False, frozenset({TransactionType.BROKERED}))
    config = CommonAnalysisConfig(
        period, period, period, period, period, policy, area_group_key="floor-84"
    )
    apartments = (Apartment("a", "A"), Apartment("b", "B"))
    stores = [SQLiteStore(tmp_path / f"{item.internal_id}.db") for item in apartments]
    for apartment, store in zip(apartments, stores, strict=True):
        store.update_incremental(
            apartment,
            period,
            lambda month, apartment_id=apartment.internal_id: (
                ()
                if month not in {"202501", "202503"}
                else (
                    NormalizedTransaction(
                        apartment_id,
                        date(2025, 1 if month == "202501" else 3, 1),
                        100 if month == "202501" else 80,
                        Decimal("84.1"),
                        TransactionType.BROKERED,
                        False,
                        source_name="fixture",
                    ),
                )
            ),
            source_name="fixture",
        )
    loaded = {
        apartment.internal_id: stores[index].load_transactions(apartment.internal_id)
        for index, apartment in enumerate(apartments)
    }
    result = compare(
        apartments,
        loaded,
        config,
        {item.internal_id: HouseholdEvidence(100, "floor-84", "fixture") for item in apartments},
    )
    assert all(subject.available for subject in result.subjects)
    assert all(subject.result is not None for subject in result.subjects)
    assert all(
        subject.result.population.context
        == replace(result.subjects[0].result.population.context, apartment=subject.apartment)
        for subject in result.subjects
    )  # type: ignore[union-attr]
    assert all(
        subject.result.turnover and subject.result.retention and subject.result.mdd
        for subject in result.subjects
    )
    assert all(
        subject.result.turnover.value is not None and subject.result.mdd.value is not None
        for subject in result.subjects
    )  # type: ignore[union-attr]


def test_compare_cli_json_and_text_are_equivalent(tmp_path):
    import json
    import subprocess

    period = {"start": "2025-01-01", "end": "2025-12-31"}
    payload = {
        "apartments": [
            {"internal_id": "a", "display_name": "A"},
            {"internal_id": "b", "display_name": "B"},
        ],
        "config": {
            "overall_period": period,
            "turnover_period": period,
            "baseline_period": period,
            "comparison_period": period,
            "mdd_period": period,
            "inclusion_policy": {"include_cancelled": False, "transaction_types": ["brokered"]},
        },
        "transactions": {"a": [], "b": []},
        "households": {
            "a": {"count": 100, "scope": "complex", "source": "fixture"},
            "b": {"count": 100, "scope": "complex", "source": "fixture"},
        },
    }
    path = tmp_path / "comparison.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    json_result = subprocess.run(
        ["uv", "run", "--locked", "apt-analyzer", "compare", str(path), "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    text_result = subprocess.run(
        ["uv", "run", "--locked", "apt-analyzer", "compare", str(path), "--format", "text"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(json_result.stdout)["config"]["mdd_period"] == period
    assert "Comparison result" in text_result.stdout
    assert (
        json.loads(text_result.stdout.removeprefix("Comparison result\n"))["config"]
        == json.loads(json_result.stdout)["config"]
    )
