#!/usr/bin/env python3
"""Codex Stop hook that enforces the repository knowledge-review loop."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def read_input() -> dict[str, object]:
    """Read the Codex hook payload from standard input."""
    try:
        value = json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def repository_root() -> Path:
    """Return the absolute root of the current Git repository."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.decode(errors="replace").strip() or "not in a Git repository"
        )
    return Path(result.stdout.decode().strip()).resolve()


def run_check(root: Path, command: list[str]) -> tuple[bool, str]:
    """Run one knowledge-gate command.

    Args:
        root: Repository root used as the command's working directory.
        command: Command and arguments to execute.

    Returns:
        A pair containing the success state and combined command output.
    """
    try:
        result = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=20,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{' '.join(command)}: {exc}"
    output = result.stdout.strip()
    return result.returncode == 0, output


def concise_failure(name: str, output: str) -> str:
    """Condense a failed check's output for the hook response.

    Args:
        name: Human-readable check name.
        output: Captured command output.

    Returns:
        A bounded, single-line failure description.
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = " | ".join(lines[-4:]) if lines else "failed without output"
    return f"{name}: {detail}"[:900]


def main() -> int:
    """Run knowledge checks and emit the Codex Stop hook response."""
    hook_input = read_input()
    try:
        root = repository_root()
    except RuntimeError as exc:
        print(json.dumps({"systemMessage": f"Knowledge gate skipped: {exc}"}))
        return 0

    checks = [
        ("Docs lint", [sys.executable, "scripts/docs_lint.py"]),
        ("Wiki lint", [sys.executable, "scripts/wiki_lint.py"]),
        ("Knowledge review", [sys.executable, "scripts/knowledge_review.py", "check", "--quiet"]),
    ]
    failures: list[str] = []
    for name, command in checks:
        passed, output = run_check(root, command)
        if not passed:
            failures.append(concise_failure(name, output))

    if not failures:
        print("{}")
        return 0

    reason = (
        "Knowledge gate failed. Inspect the final diff, update Docs/Wiki or record an honest "
        "No material decision, run both linters, then record the review again. "
        "Failures: " + " || ".join(failures)
    )
    if hook_input.get("stop_hook_active") is True:
        print(
            json.dumps(
                {
                    "continue": False,
                    "stopReason": "Knowledge gate remains unresolved after one continuation.",
                    "systemMessage": reason,
                }
            )
        )
    else:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
