#!/usr/bin/env python3
"""Deterministic structural lint for normative project documentation."""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REQUIREMENTS = DOCS / "requirements"
DECISIONS = DOCS / "decisions"

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$")
REQUIREMENT_FILE_RE = re.compile(r"^(R-\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
ADR_FILE_RE = re.compile(r"^(ADR-\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
REFERENCE_RE = re.compile(r"\b(R-\d{3}|ADR-\d{4})\b")

REQUIREMENT_FIELDS = {
    "id",
    "title",
    "status",
    "priority",
    "created",
    "updated",
    "origin",
    "supersedes",
    "superseded_by",
    "related_requirements",
    "related_decisions",
}
REQUIREMENT_SECTIONS = {
    "Intent",
    "Requirement",
    "Acceptance criteria",
    "Constraints",
    "Non-goals",
    "Verification",
    "Open questions",
    "Related documentation",
}
REQUIREMENT_STATUSES = {"proposed", "accepted", "deprecated", "superseded", "rejected"}

ADR_FIELDS = {
    "id",
    "title",
    "status",
    "date",
    "supersedes",
    "superseded_by",
    "related_requirements",
}
ADR_SECTIONS = {
    "Status",
    "Context",
    "Decision",
    "Rationale",
    "Alternatives considered",
    "Consequences",
    "Related documentation",
}
ADR_STATUSES = {"proposed", "accepted", "superseded", "rejected"}


@dataclass
class Document:
    path: Path
    text: str
    metadata: dict[str, str]
    headings: set[str]


def github_slug(value: str) -> str:
    value = re.sub(r"[`*_~]", "", value.lower())
    value = "".join(char for char in value if char.isalnum() or char in {" ", "-", "_"})
    return re.sub(r"\s+", "-", value.strip())


def heading_anchors(text: str) -> set[str]:
    counts: dict[str, int] = defaultdict(int)
    anchors: set[str] = set()
    for _, heading in HEADING_RE.findall(text):
        base = github_slug(heading)
        anchor = base if counts[base] == 0 else f"{base}-{counts[base]}"
        counts[base] += 1
        anchors.add(anchor)
    return anchors


def parse_frontmatter(text: str) -> tuple[dict[str, str], str | None]:
    match = FRONTMATTER_RE.search(text)
    if not match:
        return {}, "missing YAML frontmatter"

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            return metadata, f"unsupported indented frontmatter line: {line.strip()}"
        field = FIELD_RE.match(line)
        if not field:
            return metadata, f"invalid frontmatter line: {line}"
        key, raw_value = field.groups()
        metadata[key] = (raw_value or "").strip().strip("\"'")
    return metadata, None


def parse_document(path: Path) -> tuple[Document, str | None]:
    text = path.read_text(encoding="utf-8")
    metadata, error = parse_frontmatter(text)
    return Document(
        path, text, metadata, {heading for _, heading in HEADING_RE.findall(text)}
    ), error


def metadata_references(raw_value: str) -> set[str]:
    return set(REFERENCE_RE.findall(raw_value))


def validate_date(label: str, field: str, raw_value: str, errors: list[str]) -> None:
    try:
        date.fromisoformat(raw_value)
    except ValueError:
        errors.append(f"{label}: {field} must be an ISO date, got {raw_value!r}")


def local_target(source: Path, target: str) -> tuple[Path, str | None] | None:
    target = target.strip()
    if re.match(r"^[a-z][a-z0-9+.-]*://", target, re.IGNORECASE) or target.startswith("mailto:"):
        return None
    path_text, separator, anchor = target.partition("#")
    path = source if not path_text else (source.parent / path_text).resolve()
    return path, anchor if separator else None


def indexed_documents(index: Path, known: set[Path]) -> list[Path]:
    indexed: list[Path] = []
    for target in LINK_RE.findall(index.read_text(encoding="utf-8")):
        resolved = local_target(index.resolve(), target)
        if resolved and resolved[0] in known:
            indexed.append(resolved[0])
    return indexed


def validate() -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []

    requirement_docs: list[Document] = []
    adr_docs: list[Document] = []
    ids: dict[str, Path] = {}

    for path in sorted(REQUIREMENTS.glob("R-*.md")):
        document, error = parse_document(path)
        requirement_docs.append(document)
        if error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")

    for path in sorted(DECISIONS.glob("ADR-*.md")):
        document, error = parse_document(path)
        adr_docs.append(document)
        if error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")

    for document in requirement_docs + adr_docs:
        document_id = document.metadata.get("id", "")
        if not document_id:
            continue
        if document_id in ids:
            errors.append(
                f"{document.path.relative_to(ROOT)}: duplicate ID {document_id}; "
                f"also used by {ids[document_id].relative_to(ROOT)}"
            )
        ids[document_id] = document.path

    known_requirement_ids = {doc.metadata.get("id", "") for doc in requirement_docs}
    known_adr_ids = {doc.metadata.get("id", "") for doc in adr_docs}

    for document in requirement_docs:
        label = document.path.relative_to(ROOT).as_posix()
        match = REQUIREMENT_FILE_RE.match(document.path.name)
        if not match:
            errors.append(f"{label}: filename must match R-NNN-descriptive-name.md")
        missing = REQUIREMENT_FIELDS - document.metadata.keys()
        if missing:
            errors.append(f"{label}: missing frontmatter fields: {', '.join(sorted(missing))}")
        requirement_id = document.metadata.get("id", "")
        if match and requirement_id != match.group(1):
            errors.append(f"{label}: frontmatter ID {requirement_id!r} does not match filename")
        title = document.metadata.get("title", "")
        if f"# {requirement_id}: {title}" not in document.text.splitlines():
            errors.append(f"{label}: H1 must match frontmatter ID and title")
        if document.metadata.get("status") not in REQUIREMENT_STATUSES:
            errors.append(
                f"{label}: invalid requirement status {document.metadata.get('status')!r}"
            )
        if not re.fullmatch(r"P[0-3]", document.metadata.get("priority", "")):
            errors.append(f"{label}: priority must be P0, P1, P2, or P3")
        validate_date(label, "created", document.metadata.get("created", ""), errors)
        validate_date(label, "updated", document.metadata.get("updated", ""), errors)
        missing_sections = REQUIREMENT_SECTIONS - document.headings
        if missing_sections:
            errors.append(f"{label}: missing sections: {', '.join(sorted(missing_sections))}")
        for field in ("supersedes", "superseded_by", "related_requirements"):
            for reference in metadata_references(document.metadata.get(field, "")):
                if reference not in known_requirement_ids:
                    errors.append(f"{label}: {field} references unknown requirement {reference}")
        for reference in metadata_references(document.metadata.get("related_decisions", "")):
            if reference not in known_adr_ids:
                errors.append(f"{label}: related_decisions references unknown ADR {reference}")

    for document in adr_docs:
        label = document.path.relative_to(ROOT).as_posix()
        match = ADR_FILE_RE.match(document.path.name)
        if not match:
            errors.append(f"{label}: filename must match ADR-NNNN-descriptive-name.md")
        missing = ADR_FIELDS - document.metadata.keys()
        if missing:
            errors.append(f"{label}: missing frontmatter fields: {', '.join(sorted(missing))}")
        adr_id = document.metadata.get("id", "")
        if match and adr_id != match.group(1):
            errors.append(f"{label}: frontmatter ID {adr_id!r} does not match filename")
        title = document.metadata.get("title", "")
        if f"# {adr_id}: {title}" not in document.text.splitlines():
            errors.append(f"{label}: H1 must match frontmatter ID and title")
        if document.metadata.get("status") not in ADR_STATUSES:
            errors.append(f"{label}: invalid ADR status {document.metadata.get('status')!r}")
        validate_date(label, "date", document.metadata.get("date", ""), errors)
        missing_sections = ADR_SECTIONS - document.headings
        if missing_sections:
            errors.append(f"{label}: missing sections: {', '.join(sorted(missing_sections))}")
        for field in ("supersedes", "superseded_by"):
            for reference in metadata_references(document.metadata.get(field, "")):
                if reference not in known_adr_ids:
                    errors.append(f"{label}: {field} references unknown ADR {reference}")
        for reference in metadata_references(document.metadata.get("related_requirements", "")):
            if reference not in known_requirement_ids:
                errors.append(
                    f"{label}: related_requirements references unknown requirement {reference}"
                )

    for directory, documents, index_name in (
        (REQUIREMENTS, requirement_docs, "requirements/index.md"),
        (DECISIONS, adr_docs, "decisions/index.md"),
    ):
        index = directory / "index.md"
        known = {doc.path.resolve() for doc in documents}
        indexed = indexed_documents(index, known)
        for missing_path in sorted(known - set(indexed)):
            errors.append(f"docs/{index_name}: missing entry for {missing_path.name}")
        duplicates = [path for path, count in Counter(indexed).items() if count > 1]
        for duplicate in duplicates:
            errors.append(f"docs/{index_name}: duplicate entry for {duplicate.name}")

    anchors_by_path: dict[Path, set[str]] = {}

    checked_links = 0
    for path in sorted(DOCS.rglob("*.md")):
        if path.name == "TEMPLATE.md":
            continue
        label = path.relative_to(ROOT).as_posix()
        for raw_target in LINK_RE.findall(path.read_text(encoding="utf-8")):
            resolved = local_target(path.resolve(), raw_target)
            if resolved is None:
                continue
            checked_links += 1
            target_path, anchor = resolved
            if not target_path.exists():
                errors.append(f"{label}: broken local link {raw_target}")
                continue
            if anchor and target_path.suffix == ".md":
                if target_path not in anchors_by_path:
                    anchors_by_path[target_path] = heading_anchors(
                        target_path.read_text(encoding="utf-8")
                    )
                if anchor not in anchors_by_path[target_path]:
                    errors.append(f"{label}: missing anchor in link {raw_target}")

    open_questions = (DOCS / "open-questions.md").read_text(encoding="utf-8")
    question_ids = re.findall(r"^## (OQ-\d{3}):", open_questions, re.MULTILINE)
    for question_id, count in Counter(question_ids).items():
        if count > 1:
            errors.append(f"docs/open-questions.md: duplicate question ID {question_id}")
    if not question_ids:
        warnings.append("docs/open-questions.md: no open questions found")

    metrics = {
        "requirements": len(requirement_docs),
        "adrs": len(adr_docs),
        "open_questions": len(question_ids),
        "local_links": checked_links,
    }
    return errors, warnings, metrics


def main() -> int:
    required = [DOCS / "index.md", REQUIREMENTS / "index.md", DECISIONS / "index.md"]
    missing = [path.relative_to(ROOT) for path in required if not path.is_file()]
    if missing:
        print(f"docs lint error: missing {', '.join(map(str, missing))}", file=sys.stderr)
        return 1

    errors, warnings, metrics = validate()
    print("Documentation")
    print(f"  Requirements:       {metrics['requirements']}")
    print(f"  ADRs:               {metrics['adrs']}")
    print(f"  Open questions:     {metrics['open_questions']}")
    print(f"  Local links checked:{metrics['local_links']:>6}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if errors:
        print("\nErrors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("\ndocs lint: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
