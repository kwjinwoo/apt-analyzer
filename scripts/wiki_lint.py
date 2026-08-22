#!/usr/bin/env python3
"""Deterministic structural lint for the repository's Markdown knowledge graph."""

from __future__ import annotations

import re
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
INDEX = WIKI / "index.md"

ALLOWED_TYPES = {"domain", "metric", "data", "project", "archive"}
TYPE_DIRECTORIES = {
    "domain": "domain",
    "metric": "metrics",
    "data": "data",
    "project": "project",
    "archive": "archive",
}
ALLOWED_ROLES = {"topic", "hub"}
ALLOWED_STATUSES = {"active", "disputed", "outdated", "archived"}
REQUIRED_FIELDS = {"title", "type", "role", "status", "updated", "aliases", "tags"}
REQUIRED_SECTIONS = {
    "Scope",
    "Knowledge",
    "Graph connections",
    "Requirements",
    "Decisions and open questions",
    "Evidence and interpretation risks",
    "Verify in the repository",
    "Related pages",
}
ARCHIVE_REQUIRED_SECTIONS = {"Question", "Answer", "Sources", "Limitations"}
MEANINGLESS_NAME = re.compile(
    r"(?:^|[-_])(part[-_]?\d+|details?|misc|miscellaneous|notes?|more)(?:$|[-_])",
    re.IGNORECASE,
)
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
TOP_LEVEL_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s*(.*))?$")


@dataclass
class Page:
    path: Path
    relative: Path
    text: str
    metadata: dict[str, str]
    headings: set[str]
    links: list[str]
    words: int


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
    current_list: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            if current_list and line.strip().startswith("-"):
                item = line.strip()[1:].strip().strip("\"'")
                metadata[current_list] = "\n".join(filter(None, (metadata[current_list], item)))
                continue
            return metadata, f"unsupported indented frontmatter line: {line.strip()}"
        field = TOP_LEVEL_FIELD_RE.match(line)
        if not field:
            return metadata, f"invalid frontmatter line: {line}"
        key, raw_value = field.groups()
        metadata[key] = (raw_value or "").strip().strip("\"'")
        current_list = key if not raw_value else None
    return metadata, None


def load_pages() -> tuple[list[Page], list[str]]:
    errors: list[str] = []
    pages: list[Page] = []
    for path in sorted(WIKI.rglob("*.md")):
        if path in {INDEX, WIKI / "AGENTS.md"}:
            continue
        text = path.read_text(encoding="utf-8")
        metadata, error = parse_frontmatter(text)
        relative = path.relative_to(WIKI)
        if error:
            errors.append(f"{relative}: {error}")
        pages.append(
            Page(
                path=path,
                relative=relative,
                text=text,
                metadata=metadata,
                headings={heading for _, heading in HEADING_RE.findall(text)},
                links=LINK_RE.findall(text),
                words=len(re.findall(r"\b[\w'-]+\b", text, re.UNICODE)),
            )
        )
    return pages, errors


def local_target(source: Path, target: str) -> tuple[Path, str | None] | None:
    target = target.strip()
    if re.match(r"^[a-z][a-z0-9+.-]*://", target, re.IGNORECASE) or target.startswith("mailto:"):
        return None
    path_text, separator, anchor = target.partition("#")
    path = source if not path_text else (source.parent / path_text).resolve()
    return path, anchor if separator else None


def validate() -> tuple[list[str], list[str], dict[str, int]]:
    pages, errors = load_pages()
    warnings: list[str] = []
    page_by_path = {page.path.resolve(): page for page in pages}
    anchors_by_path: dict[Path, set[str]] = {}
    for path in ROOT.rglob("*.md"):
        anchors_by_path[path.resolve()] = heading_anchors(path.read_text(encoding="utf-8"))

    names: dict[str, tuple[Path, str]] = {}
    internal_edges: dict[Path, set[Path]] = defaultdict(set)
    evidence_edges = 0

    for page in pages:
        label = page.relative.as_posix()
        missing = REQUIRED_FIELDS - page.metadata.keys()
        if missing:
            errors.append(f"{label}: missing frontmatter fields: {', '.join(sorted(missing))}")

        page_type = page.metadata.get("type")
        role = page.metadata.get("role")
        status = page.metadata.get("status")
        if page_type not in ALLOWED_TYPES:
            errors.append(f"{label}: invalid type {page_type!r}")
        if role not in ALLOWED_ROLES:
            errors.append(f"{label}: invalid role {role!r}")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{label}: invalid status {status!r}")

        updated = page.metadata.get("updated", "")
        try:
            date.fromisoformat(updated)
        except ValueError:
            errors.append(f"{label}: updated must be an ISO date, got {updated!r}")

        title = page.metadata.get("title", "").casefold()
        if title:
            if title in names:
                existing_path, existing_kind = names[title]
                errors.append(
                    f"{label}: title collides with {existing_kind} in {existing_path.relative_to(WIKI)}"
                )
            names[title] = (page.path, "title")
        aliases = page.metadata.get("aliases", "")
        if aliases != "[]":
            for alias in filter(None, aliases.splitlines()):
                normalized = alias.casefold()
                if normalized in names:
                    existing_path, existing_kind = names[normalized]
                    errors.append(
                        f"{label}: alias {alias!r} collides with {existing_kind} in "
                        f"{existing_path.relative_to(WIKI)}"
                    )
                names[normalized] = (page.path, "alias")

        if len(page.relative.parts) != 2:
            errors.append(f"{label}: topic pages must be exactly one directory below wiki/")
        elif (
            page_type in TYPE_DIRECTORIES and page.relative.parts[0] != TYPE_DIRECTORIES[page_type]
        ):
            errors.append(
                f"{label}: type {page_type!r} does not match directory {page.relative.parts[0]!r}"
            )
        if page_type == "archive" and status != "archived":
            errors.append(f"{label}: archive pages must use status 'archived'")
        if page_type != "archive" and status == "archived":
            errors.append(f"{label}: archived status is only valid under wiki/archive/")
        if MEANINGLESS_NAME.search(page.relative.stem):
            errors.append(f"{label}: filename does not identify a stable concept")

        expected_sections = (
            ARCHIVE_REQUIRED_SECTIONS if page_type == "archive" else REQUIRED_SECTIONS
        )
        missing_sections = expected_sections - page.headings
        if missing_sections:
            errors.append(f"{label}: missing sections: {', '.join(sorted(missing_sections))}")

        if page.words >= 5000 and not page.metadata.get("size_exception"):
            errors.append(f"{label}: {page.words} words requires a size_exception")
        elif page.words >= 2500:
            warnings.append(f"{label}: {page.words} words; split independently queryable concepts")
        elif page.words >= 1500:
            warnings.append(f"{label}: {page.words} words; review for possible decomposition")

        has_evidence = False
        for raw_target in page.links:
            resolved = local_target(page.path.resolve(), raw_target)
            if resolved is None:
                continue
            target_path, anchor = resolved
            if not target_path.exists():
                errors.append(f"{label}: broken local link {raw_target}")
                continue
            if anchor and target_path.suffix == ".md":
                if anchor not in anchors_by_path.get(target_path, set()):
                    errors.append(f"{label}: missing anchor in link {raw_target}")
            if target_path in page_by_path:
                internal_edges[page.path.resolve()].add(target_path)
            elif target_path.is_relative_to(ROOT / "docs") or target_path.is_relative_to(
                ROOT / "tests"
            ):
                evidence_edges += 1
                has_evidence = True
            elif target_path.is_relative_to(ROOT) and target_path.suffix in {".py", ".md"}:
                evidence_edges += 1
                has_evidence = True

        if page.metadata.get("status") != "archived" and not internal_edges[page.path.resolve()]:
            warnings.append(f"{label}: no outgoing edge to another living wiki page")
        if page.metadata.get("status") != "archived" and not has_evidence:
            warnings.append(f"{label}: no local evidence link to docs, code, or tests")

    index_text = INDEX.read_text(encoding="utf-8")
    indexed_pages: list[Path] = []
    for raw_target in LINK_RE.findall(index_text):
        resolved = local_target(INDEX.resolve(), raw_target)
        if resolved and resolved[0] in page_by_path:
            indexed_pages.append(resolved[0])
    indexed_set = set(indexed_pages)
    living_set = {
        page.path.resolve() for page in pages if page.metadata.get("status") != "archived"
    }
    for missing in sorted(living_set - indexed_set):
        errors.append(f"index.md: missing entry for {missing.relative_to(WIKI)}")
    if len(indexed_pages) != len(indexed_set):
        errors.append("index.md: duplicate living-page entry")

    inbound: dict[Path, int] = defaultdict(int)
    undirected: dict[Path, set[Path]] = defaultdict(set)
    for source, targets in internal_edges.items():
        for target in targets:
            inbound[target] += 1
            undirected[source].add(target)
            undirected[target].add(source)

    for page in pages:
        if page.metadata.get("role") != "hub":
            continue
        label = page.relative.as_posix()
        topics = re.search(
            r"^## Topics\s*$\n(.*?)(?=^##\s|\Z)", page.text, re.MULTILINE | re.DOTALL
        )
        if not topics:
            errors.append(f"{label}: hub pages require a Topics section")
            continue
        children: set[Path] = set()
        for raw_target in LINK_RE.findall(topics.group(1)):
            resolved = local_target(page.path.resolve(), raw_target)
            if resolved and resolved[0] in page_by_path:
                children.add(resolved[0])
        if not children:
            errors.append(f"{label}: Topics must link to at least one living child page")
        for child in sorted(children):
            if page.path.resolve() not in internal_edges[child]:
                errors.append(
                    f"{child.relative_to(WIKI)}: child page must link back to hub {page.relative}"
                )

    for page_path in sorted(living_set):
        if inbound[page_path] == 0:
            warnings.append(
                f"{page_path.relative_to(WIKI)}: orphan; index links do not count as graph edges"
            )

    components = 0
    remaining = set(living_set)
    while remaining:
        components += 1
        start = next(iter(remaining))
        queue = deque([start])
        remaining.remove(start)
        while queue:
            current = queue.popleft()
            for neighbor in undirected[current] & remaining:
                remaining.remove(neighbor)
                queue.append(neighbor)
    if components > 1:
        warnings.append(f"living graph has {components} disconnected components")

    metrics = {
        "living_pages": len(living_set),
        "internal_edges": sum(len(targets) for targets in internal_edges.values()),
        "evidence_edges": evidence_edges,
        "orphans": sum(1 for path in living_set if inbound[path] == 0),
        "components": components,
    }
    return errors, warnings, metrics


def main() -> int:
    if not WIKI.is_dir() or not INDEX.is_file():
        print("wiki lint error: wiki/index.md is required", file=sys.stderr)
        return 1

    errors, warnings, metrics = validate()
    print("Wiki graph")
    print(f"  Living pages:        {metrics['living_pages']}")
    print(f"  Internal edges:      {metrics['internal_edges']}")
    print(f"  Evidence links:      {metrics['evidence_edges']}")
    print(f"  Orphan pages:        {metrics['orphans']}")
    print(f"  Components:          {metrics['components']}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  - {warning}")
    if errors:
        print("\nErrors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("\nwiki lint: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
