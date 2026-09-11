import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apt_analyzer.building_hub import (
    InventoryPage,
    InventoryRow,
    InventoryScope,
    InventoryState,
    InventorySummary,
)
from apt_analyzer.persistence import SQLiteStore

COLLECTED = datetime(2026, 9, 9, 1, 2, 3, tzinfo=UTC)


def summary(state: InventoryState = InventoryState.VERIFIED) -> InventorySummary:
    rows = (
        InventoryRow("u1", "101", "1", Decimal("59.82")),
        InventoryRow("u2", "102", "1", Decimal("84.75")),
    )
    scope = InventoryScope(
        "root", ("t1",), ("u1", "u2"), (("11215", "10300", "0", "0611", "0000"),), (), True
    )
    return InventorySummary(
        state,
        rows if state is InventoryState.VERIFIED else rows[:1],
        ((Decimal("59.82"), 1), (Decimal("84.75"), 1))
        if state is InventoryState.VERIFIED
        else ((Decimal("59.82"), 1),),
        2 if state is InventoryState.VERIFIED else 1,
        None if state is InventoryState.VERIFIED else "incomplete source",
        COLLECTED,
        "Building HUB",
        None,
        "normalization-v2",
        "mapping-v3",
        scope,
        state is InventoryState.VERIFIED,
        2 if state is InventoryState.VERIFIED else None,
        (("≤60㎡", 1), (">60–85㎡", 1)) if state is InventoryState.VERIFIED else (),
        (InventoryPage("basis", scope.required_lots[0], 1, 100, 2, 2, COLLECTED),),
    )


def test_full_inventory_metadata_roundtrips_after_reopen(tmp_path) -> None:
    path = tmp_path / "inventory.db"
    store = SQLiteStore(path)
    store.save_inventory("apt", summary(), source="Building HUB")
    store.close()
    reopened = SQLiteStore(path)
    record = reopened.load_inventory("apt")
    assert record is not None
    assert record.summary == summary()
    assert record.source == "Building HUB"
    assert record.fetched_at == COLLECTED.isoformat()


def test_partial_and_unavailable_attempts_preserve_last_verified(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "inventory.db")
    store.save_inventory("apt", summary(), source="hub")
    store.save_inventory("apt", summary(InventoryState.PARTIAL), source="hub")
    assert store.load_inventory("apt").summary == summary()  # type: ignore[union-attr]
    assert store.load_inventory_attempt("apt").summary.state is InventoryState.PARTIAL  # type: ignore[union-attr]
    unavailable = summary(InventoryState.UNAVAILABLE)
    store.save_inventory("apt", unavailable, source="hub")
    assert store.load_inventory("apt").summary.state is InventoryState.VERIFIED  # type: ignore[union-attr]
    assert store.load_inventory_attempt("apt").summary.state is InventoryState.UNAVAILABLE  # type: ignore[union-attr]


def test_first_partial_attempt_is_readable_with_full_summary(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "inventory.db")
    attempt = summary(InventoryState.PARTIAL)
    store.save_inventory("apt", attempt, source="hub")
    loaded = store.load_inventory_attempt("apt")
    assert loaded is not None and loaded.summary == attempt and loaded.source == "hub"
    assert store.load_inventory("apt") is None


@pytest.mark.parametrize("mutation", ["nan", "unscoped"])
def test_invalid_verified_inventory_is_rejected_before_write(tmp_path, mutation: str) -> None:
    store = SQLiteStore(tmp_path / "inventory.db")
    invalid = summary()
    if mutation == "unscoped":
        invalid = InventorySummary(
            invalid.state,
            invalid.rows,
            invalid.counts,
            invalid.total_count,
            collected_at=COLLECTED,
            data_complete=True,
            kapt_total=2,
            kapt_bands=invalid.kapt_bands,
        )
    else:
        invalid = InventorySummary(
            invalid.state,
            (InventoryRow("u1", "101", "1", Decimal("NaN")),),
            ((Decimal("NaN"), 1),),
            1,
            collected_at=COLLECTED,
        )
    with pytest.raises(ValueError):
        store.save_inventory("apt", invalid, source="hub")
    assert store.load_inventory_attempt("apt") is None


def test_inventory_write_is_atomic(tmp_path) -> None:
    path = tmp_path / "inventory.db"
    store = SQLiteStore(path)
    store._connection.execute(
        "CREATE TRIGGER fail_inventory AFTER INSERT ON inventory_attempts BEGIN SELECT RAISE(ABORT, 'forced'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="forced"):
        store.save_inventory("apt", summary(), source="hub")
    assert store.load_inventory_attempt("apt") is None
    assert store.load_inventory("apt") is None


def test_corrupt_summary_json_fails_closed(tmp_path) -> None:
    path = tmp_path / "inventory.db"
    store = SQLiteStore(path)
    store.save_inventory("apt", summary(), source="hub")
    store._connection.execute(
        "UPDATE inventory_snapshots SET summary_json=?",
        (json.dumps({"state": "verified", "rows": [{"area_sqm": "NaN"}]}),),
    )
    store._connection.commit()
    with pytest.raises(ValueError):
        store.load_inventory("apt")
