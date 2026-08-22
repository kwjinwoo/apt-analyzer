#!/usr/bin/env python3
"""Bind an explicit Docs/Wiki impact review to the current Git worktree."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DOCS_DECISIONS = {"updated", "no-material"}
WIKI_DECISIONS = {"new", "updated", "disputed", "no-material"}
RECEIPT_VERSION = 1


class ReviewError(RuntimeError):
    """A user-actionable review failure."""


def git(*args: str, root: Path | None = None, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewError(message or f"git {' '.join(args)} failed")
    return result.stdout


def repository_root() -> Path:
    output = git("rev-parse", "--show-toplevel")
    return Path(output.decode().strip()).resolve()


def receipt_path(root: Path) -> Path:
    raw_path = (
        git("rev-parse", "--git-path", "codex/knowledge-review.json", root=root).decode().strip()
    )
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def changed_paths(root: Path) -> list[str]:
    tracked = (
        git("diff", "--name-only", "--relative", "HEAD", "--", root=root)
        .decode("utf-8", errors="surrogateescape")
        .splitlines()
    )
    untracked_raw = git("ls-files", "--others", "--exclude-standard", "-z", root=root)
    untracked = [
        item.decode("utf-8", errors="surrogateescape")
        for item in untracked_raw.split(b"\0")
        if item
    ]
    return sorted(set(tracked + untracked))


def worktree_fingerprint(root: Path) -> tuple[str, list[str]]:
    paths = changed_paths(root)
    digest = hashlib.sha256()
    digest.update(b"apt-analyzer-knowledge-review-v1\0")
    digest.update(git("rev-parse", "HEAD", root=root).strip() + b"\0")
    tracked_diff = git("diff", "--binary", "HEAD", "--", root=root)
    digest.update(tracked_diff)

    tracked_paths = set(
        git("ls-files", "-z", root=root).decode("utf-8", errors="surrogateescape").split("\0")
    )
    for relative in paths:
        if relative in tracked_paths:
            continue
        encoded = relative.encode("utf-8", errors="surrogateescape")
        digest.update(b"untracked\0" + encoded + b"\0")
        path = root / relative
        if path.is_file():
            digest.update(path.read_bytes())
        elif path.is_symlink():
            digest.update(path.readlink().as_posix().encode())
        digest.update(b"\0")
    return digest.hexdigest(), paths


def path_groups(paths: list[str]) -> dict[str, list[str]]:
    return {
        "docs": [path for path in paths if path == "README.md" or path.startswith("docs/")],
        "wiki": [path for path in paths if path.startswith("wiki/")],
        "tests": [path for path in paths if path.startswith("tests/")],
        "implementation": [
            path
            for path in paths
            if not (
                path == "README.md"
                or path == "AGENTS.md"
                or path.startswith(("docs/", "wiki/", "tests/", "scripts/", ".codex/", ".agents/"))
            )
        ],
        "workflow": [
            path
            for path in paths
            if path == "AGENTS.md" or path.startswith(("scripts/", ".codex/", ".agents/"))
        ],
    }


def review_guidance(groups: dict[str, list[str]]) -> list[str]:
    guidance: list[str] = []
    if groups["docs"]:
        guidance.append(
            "Docs changed: verify normative intent, IDs, links, and affected wiki concepts."
        )
    if groups["wiki"]:
        guidance.append(
            "Wiki changed: inspect changed pages, one-hop neighbors, and linked evidence."
        )
    if groups["implementation"]:
        guidance.append(
            "Implementation changed: check durable requirements/decisions and wiki evidence links."
        )
    if groups["tests"]:
        guidance.append(
            "Tests changed: check whether representative Requirement verification links should change."
        )
    if groups["workflow"]:
        guidance.append(
            "Agent workflow changed: check repository guidance and knowledge-maintenance consistency."
        )
    return guidance


def load_receipt(root: Path) -> dict[str, object]:
    path = receipt_path(root)
    if not path.is_file():
        raise ReviewError("knowledge review is missing")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"knowledge review is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewError("knowledge review has an invalid format")
    return value


def validate_receipt(root: Path) -> tuple[dict[str, object] | None, list[str]]:
    fingerprint, paths = worktree_fingerprint(root)
    if not paths:
        return None, []

    receipt = load_receipt(root)
    if receipt.get("version") != RECEIPT_VERSION:
        raise ReviewError("knowledge review version is unsupported; record it again")
    if receipt.get("fingerprint") != fingerprint:
        raise ReviewError("knowledge review is stale because the worktree changed")
    if receipt.get("docs") not in DOCS_DECISIONS:
        raise ReviewError("knowledge review has an invalid Docs decision")
    if receipt.get("wiki") not in WIKI_DECISIONS:
        raise ReviewError("knowledge review has an invalid Wiki decision")
    for field in ("docs_reason", "wiki_reason"):
        reason = receipt.get(field)
        if not isinstance(reason, str) or len(reason.strip()) < 12:
            raise ReviewError(f"{field} must be specific (at least 12 characters)")

    groups = path_groups(paths)
    if groups["docs"] and receipt.get("docs") == "no-material":
        raise ReviewError("Docs files changed, so Docs impact cannot be no-material")
    if groups["wiki"] and receipt.get("wiki") == "no-material":
        raise ReviewError("Wiki files changed, so Wiki impact cannot be no-material")
    if receipt.get("docs") == "updated" and not groups["docs"]:
        raise ReviewError("Docs impact is updated, but the current diff has no Docs changes")
    if receipt.get("wiki") in {"new", "updated", "disputed"} and not groups["wiki"]:
        raise ReviewError("Wiki impact records a change, but the current diff has no Wiki changes")
    return receipt, paths


def command_inspect(root: Path) -> int:
    fingerprint, paths = worktree_fingerprint(root)
    print(f"Worktree fingerprint: {fingerprint}")
    if not paths:
        print("No worktree changes; no knowledge review is required.")
        return 0

    groups = path_groups(paths)
    print(f"Changed paths: {len(paths)}")
    for name in ("docs", "wiki", "tests", "implementation", "workflow"):
        members = groups[name]
        if members:
            print(f"  {name}: {len(members)}")
            for path in members[:12]:
                print(f"    - {path}")
            if len(members) > 12:
                print(f"    - ... and {len(members) - 12} more")

    print("\nReview prompts:")
    for prompt in review_guidance(groups):
        print(f"  - {prompt}")
    try:
        receipt, _ = validate_receipt(root)
    except ReviewError as exc:
        print(f"\nReview status: required ({exc})")
    else:
        assert receipt is not None
        print(f"\nReview status: current (Docs={receipt['docs']}, Wiki={receipt['wiki']})")
    return 0


def command_record(
    root: Path,
    docs: str,
    wiki: str,
    docs_reason: str,
    wiki_reason: str,
) -> int:
    fingerprint, paths = worktree_fingerprint(root)
    if not paths:
        raise ReviewError("there are no worktree changes to review")
    groups = path_groups(paths)
    if groups["docs"] and docs == "no-material":
        raise ReviewError("Docs files changed; record Docs impact as updated")
    if groups["wiki"] and wiki == "no-material":
        raise ReviewError("Wiki files changed; record Wiki impact as new, updated, or disputed")
    if docs == "updated" and not groups["docs"]:
        raise ReviewError("Docs impact cannot be updated without a Docs change")
    if wiki in {"new", "updated", "disputed"} and not groups["wiki"]:
        raise ReviewError("Wiki impact cannot record a change without a Wiki file change")
    if len(docs_reason.strip()) < 12:
        raise ReviewError("Docs reason must be specific (at least 12 characters)")
    if len(wiki_reason.strip()) < 12:
        raise ReviewError("Wiki reason must be specific (at least 12 characters)")

    receipt = {
        "version": RECEIPT_VERSION,
        "fingerprint": fingerprint,
        "docs": docs,
        "wiki": wiki,
        "docs_reason": docs_reason.strip(),
        "wiki_reason": wiki_reason.strip(),
        "reviewed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "changed_paths": len(paths),
    }
    path = receipt_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded knowledge review for {len(paths)} changed paths.")
    print(f"  Docs: {docs}")
    print(f"  Wiki: {wiki}")
    print(f"  Docs reason: {docs_reason.strip()}")
    print(f"  Wiki reason: {wiki_reason.strip()}")
    print(f"  Receipt: {path}")
    return 0


def command_check(root: Path, quiet: bool) -> int:
    receipt, paths = validate_receipt(root)
    if not paths:
        if not quiet:
            print("knowledge review: passed (clean worktree)")
        return 0
    assert receipt is not None
    if not quiet:
        print("knowledge review: passed")
        print(f"  Changed paths: {len(paths)}")
        print(f"  Docs impact:   {receipt['docs']}")
        print(f"  Wiki impact:   {receipt['wiki']}")
        print(f"  Docs reason:   {receipt['docs_reason']}")
        print(f"  Wiki reason:   {receipt['wiki_reason']}")
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    commands = value.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect", help="show changed paths, prompts, and receipt status")

    record = commands.add_parser("record", help="record impact decisions for the current diff")
    record.add_argument("--docs", choices=sorted(DOCS_DECISIONS), required=True)
    record.add_argument("--wiki", choices=sorted(WIKI_DECISIONS), required=True)
    record.add_argument("--docs-reason", required=True)
    record.add_argument("--wiki-reason", required=True)

    check = commands.add_parser("check", help="verify that the review matches the current diff")
    check.add_argument("--quiet", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        root = repository_root()
        if args.command == "inspect":
            return command_inspect(root)
        if args.command == "record":
            return command_record(
                root,
                args.docs,
                args.wiki,
                args.docs_reason,
                args.wiki_reason,
            )
        if args.command == "check":
            return command_check(root, args.quiet)
    except ReviewError as exc:
        print(f"knowledge review: failed: {exc}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
