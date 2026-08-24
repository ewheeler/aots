from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

VALID_PAGE_TYPES = {
    "tutorial",
    "how-to",
    "reference",
    "explanation",
    "project",
    "contributor",
    "adr",
    "landing",
}

LEGACY_TOP_LEVEL_PAGES = {
    "usage.qmd",
    "architecture.qmd",
    "snowflake-agnostic-report-publication.qmd",
    "comparison-cases.qmd",
    "alert-email-design.qmd",
    "alert-email-sop-alignment-plan.qmd",
    "alert-product-flexibility-plan.qmd",
    "alert-product-v2-readiness.qmd",
}

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
FENCED_BLOCK = re.compile(r"^\s*(```|~~~).*?^\s*\1\s*$", re.MULTILINE | re.DOTALL)
READINESS_COUNTS = re.compile(
    r"\b(?:11|eleven)\s+(?:strict\s+)?schemas?\b"
    r"|\b(?:32|thirty-two)\s+(?:V2\s+)?vectors?\b"
    r"|\bfour\s+exact\s+(?:compact\s+|canonical\s+|full-document\s+)*"
    r"(?:byte\s+)?(?:files?|fixtures?)\b"
    r"|\beight\s+(?:synthetic\s+)?V1\s+(?:conformance\s+)?(?:bundles?|freezes?|cases?)\b",
    re.IGNORECASE,
)
STALE_PARITY_PHRASES = re.compile(r"\b(?:claim-based parity|alert parity results)\b", re.IGNORECASE)


def _front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line or line[:1].isspace():
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")
    return fields


def _project_documentation() -> list[Path]:
    paths = [*DOCS.rglob("*.md"), *DOCS.rglob("*.qmd")]
    paths.extend(
        path for name in ("README.md", "plan.md", "CONTEXT.md") if (path := ROOT / name).exists()
    )
    return sorted(set(paths))


def _reader_facing_qmd() -> list[Path]:
    return [
        path
        for path in DOCS.rglob("*.qmd")
        if not (path.parent == DOCS and path.name in LEGACY_TOP_LEVEL_PAGES)
        and path != DOCS / "agents" / "repository-map.qmd"
    ]


def _is_redirect_or_supersession(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    fields = _front_matter(path)
    if any(key in fields for key in ("redirect", "redirect-to")):
        return True
    body = text.split("---", 2)[-1] if text.startswith("---") else text
    words = re.findall(r"\b\w+\b", body)
    return len(words) <= 60 and bool(re.search(r"\b(?:moved|redirect|superseded)\b", body, re.I))


def _link_destination(source: Path, raw_destination: str) -> Path | None:
    destination = raw_destination.strip().split(maxsplit=1)[0].strip("<>")
    split = urlsplit(destination)
    if split.scheme or split.netloc or destination.startswith(("#", "/")):
        return None
    path_text = unquote(split.path)
    if not path_text:
        return None
    target = (source.parent / path_text).resolve()
    if target.suffix in {".md", ".qmd"}:
        alternatives = [target, target.with_suffix(".qmd"), target.with_suffix(".md")]
        return next((candidate for candidate in alternatives if candidate.is_file()), target)
    return target


def test_reader_facing_quarto_pages_have_diataxis_front_matter() -> None:
    failures: list[str] = []
    for path in _reader_facing_qmd():
        fields = _front_matter(path)
        relative = path.relative_to(ROOT)
        if not fields:
            failures.append(f"{relative}: missing YAML front matter")
        elif fields.get("page-type") not in VALID_PAGE_TYPES:
            failures.append(f"{relative}: invalid or missing page-type")
    assert not failures, "\n" + "\n".join(failures)


def test_adr_index_links_every_numbered_record() -> None:
    index = DOCS / "adr" / "index.qmd"
    indexed = index.read_text(encoding="utf-8")
    missing = [
        path.name for path in sorted((DOCS / "adr").glob("[0-9]*.md")) if path.name not in indexed
    ]
    assert not missing, f"ADRs missing from index: {missing}"


def test_legacy_top_level_pages_are_absent_or_redirect_only() -> None:
    substantive = [
        path.relative_to(ROOT)
        for name in sorted(LEGACY_TOP_LEVEL_PAGES)
        if (path := DOCS / name).exists() and not _is_redirect_or_supersession(path)
    ]
    assert not substantive, f"Substantive legacy pages remain: {substantive}"


def test_internal_markdown_links_resolve() -> None:
    broken: list[str] = []
    for source in sorted([*DOCS.rglob("*.md"), *DOCS.rglob("*.qmd")]):
        text = FENCED_BLOCK.sub("", source.read_text(encoding="utf-8"))
        for match in MARKDOWN_LINK.finditer(text):
            target = _link_destination(source, match.group(1))
            if target is not None and not target.exists():
                broken.append(f"{source.relative_to(ROOT)} -> {match.group(1)}")
    assert not broken, "Broken internal links:\n" + "\n".join(broken)


def test_v2_readiness_counts_live_only_in_the_reference() -> None:
    allowed = DOCS / "reference" / "alert-product-v2-readiness.qmd"
    offenders = [
        path.relative_to(ROOT)
        for path in _project_documentation()
        if path != allowed and READINESS_COUNTS.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"Duplicated V2 readiness counts: {offenders}"


def test_obsolete_people_in_need_asset_name_is_absent() -> None:
    offenders = [
        path.relative_to(ROOT)
        for path in _project_documentation()
        if "people-in-need-composition-50kt.png" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"Obsolete asset reference remains: {offenders}"


def test_unqualified_stale_parity_phrases_are_absent() -> None:
    offenders = [
        path.relative_to(ROOT)
        for path in _project_documentation()
        if STALE_PARITY_PHRASES.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"Stale parity language remains: {offenders}"
