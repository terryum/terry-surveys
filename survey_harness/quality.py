"""Human-aligned deterministic scorecard for survey books.

The score is diagnostic. Release still requires every configured hard gate and
an independent reviewer artifact, so high word or citation counts cannot buy a
pass for unsupported claims or wall-text chapters.
"""

from __future__ import annotations

import json
import hashlib
import math
import re
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import load_profile
from .config import CONFIG_PATH
from .schema_utils import validate_schema
from .state import chapter_numbers, survey_dir

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]*")
KOREAN_RE = re.compile(r"[가-힣]+")
FIGURE_RE = re.compile(r"!\[[^\]]*\]\([^\)]+\)")
REFERENCE_HEADING_RE = re.compile(r"^##+\s+(References|Bibliography|참고문헌)\s*$", re.I | re.M)
LATIN_PROSE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z'-]*(?![A-Za-z0-9_])")
LATIN_UNIT_TOKENS = {
    "cm", "mm", "km", "kg", "mg", "ms", "hz", "khz", "mhz", "ghz",
    "mv", "ma", "kw", "mw", "rpm", "fps", "db", "nm", "rad", "deg",
}
LATIN_PROSE_EXCLUDED_TOKENS = {
    "al", "et", "argmax", "argmin", "bar", "begin", "cdot", "cmd",
    "ddot", "dot", "end", "frac", "hat", "left", "mathbb", "mathbf", "mathcal",
    "mathrm", "operatorname", "overline", "partial", "prod", "right",
    "sqrt", "sum", "text", "tilde", "times", "underline", "vec",
}
ALLOWED_KO_TECHNICAL_TERMS = (
    "abort",
    "acquisition",
    "action",
    "action head",
    "calibration",
    "closure",
    "contact",
    "controller",
    "cycle",
    "damage",
    "diffusion policy",
    "evaluation",
    "end-effector",
    "event",
    "failure",
    "feedback",
    "finger",
    "fixture",
    "force",
    "gate",
    "graph",
    "grasp",
    "grasping",
    "grip",
    "hand",
    "hardware",
    "hold",
    "id",
    "impedance",
    "in-hand",
    "internal",
    "intervention",
    "manipulation",
    "margin",
    "mode",
    "model-based",
    "motion",
    "multi-object",
    "normal",
    "object",
    "operator",
    "override",
    "patch",
    "phase",
    "planning",
    "pose",
    "rate",
    "rearrangement",
    "reference",
    "reflex",
    "retry",
    "shear",
    "sim-to-real",
    "slip",
    "support",
    "task",
    "teacher-student",
    "time",
    "backdrivability",
    "proprioceptive",
    "proprioception",
    "rollout",
    "checkpoint",
    "fine-tuning",
    "co-training",
    "pre-training",
    "post-training",
    "tokenizer",
    "embodiment",
)
LOWERCASE_PROPER_NAMES = {"libfranka", "openai", "codex", "mujoco"}
METADATA_NAME_FIELDS = {
    "affiliation", "affiliations", "author", "authors", "booktitle", "company",
    "companies", "framework", "frameworks", "institution", "institutions",
    "journal", "lead_author", "libraries", "library", "model", "models",
    "organization", "organizations", "product", "products", "publisher", "venue",
    "vendors", "vendor",
}

PROCESS_CONTRACTS = [
    "_research/kg_seed.json",
    "_research/search_protocol.md",
    "_research/papers_foundations.json",
    "_research/papers_frontier.json",
    "_research/source_ledger.jsonl",
    "_analysis/claim_evidence.jsonl",
    "_workspace/image_plan.json",
    "_quality/reviewer_scores.json",
    "_quality/build_validation.json",
]


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def ratio_score(value: float, target: float) -> float:
    if target <= 0:
        return 100.0
    return clamp(100.0 * value / target)


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_jsonl(path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    if not path.exists():
        return rows, errors
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{line_no}: {exc}")
            continue
        if not isinstance(row, dict):
            errors.append(f"{path.name}:{line_no}: expected object")
            continue
        rows.append(row)
    return rows, errors


def _frontmatter_value(text: str, key: str) -> Optional[str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, flags=re.S)
    if not match:
        return None
    value = re.search(rf'^\s*{re.escape(key)}:\s*["\']?(.*?)["\']?\s*$', match.group(1), flags=re.M)
    return value.group(1).strip() if value else None


def title_style_metrics(path: Path) -> Dict[str, Any]:
    """Measure title brevity and metadata drift without dictating exact wording."""
    config = load_json(path / "survey.json", {})
    parts = config.get("parts", []) if isinstance(config, dict) else []
    result: Dict[str, Any] = {"part_lengths": {}, "chapter_lengths": {}, "chapter_medians": {}, "metadata_drift": []}
    for lang in ("ko", "en"):
        part_rows = []
        chapter_rows = []
        for part in parts if isinstance(parts, list) else []:
            if not isinstance(part, dict):
                continue
            part_name = part.get("name", {})
            expected_part = str(part_name.get(lang) or "") if isinstance(part_name, dict) else ""
            if expected_part:
                part_rows.append({"title": expected_part, "chars": len(expected_part)})
            for chapter in part.get("chapters", []) if isinstance(part.get("chapters"), list) else []:
                if not isinstance(chapter, dict):
                    continue
                try:
                    chapter_num = int(chapter.get("num", 0))
                except (TypeError, ValueError):
                    continue
                chapter_title = chapter.get("title", {})
                expected_title = str(chapter_title.get(lang) or "") if isinstance(chapter_title, dict) else ""
                if expected_title:
                    chapter_rows.append({"chapter": chapter_num, "title": expected_title, "chars": len(expected_title)})
                manuscript = path / "book" / lang / f"ch{chapter_num:02d}.md"
                if not manuscript.exists():
                    continue
                text = manuscript.read_text(encoding="utf-8", errors="ignore")
                observed_title = _frontmatter_value(text, "title")
                observed_part = _frontmatter_value(text, "part")
                if observed_title != expected_title:
                    result["metadata_drift"].append({"lang": lang, "chapter": chapter_num, "field": "title", "expected": expected_title, "observed": observed_title})
                if observed_part != expected_part:
                    result["metadata_drift"].append({"lang": lang, "chapter": chapter_num, "field": "part", "expected": expected_part, "observed": observed_part})
                h1 = re.search(r"^#\s+(?:제\s*\d+장|Chapter\s+\d+)\s*:\s*(.+?)\s*$", text, flags=re.I | re.M)
                if h1 and h1.group(1).strip() != expected_title:
                    result["metadata_drift"].append({"lang": lang, "chapter": chapter_num, "field": "h1", "expected": expected_title, "observed": h1.group(1).strip()})
        result["part_lengths"][lang] = part_rows
        result["chapter_lengths"][lang] = chapter_rows
        result["chapter_medians"][lang] = float(median([row["chars"] for row in chapter_rows])) if chapter_rows else 0.0
    return result


def prose(text: str) -> str:
    match = REFERENCE_HEADING_RE.search(text)
    if match:
        text = text[:match.start()]
    text = re.sub(r"^---\s*$.*?^---\s*$", "", text, count=1, flags=re.M | re.S)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"https?://\S+", "", text)
    return text


def survey_metadata_latin_terms(path: Path) -> set[str]:
    """Collect proper-name tokens declared by this survey's source metadata."""
    allowed: set[str] = set()

    def add_value(value: Any) -> None:
        if isinstance(value, str):
            allowed.update(token.casefold() for token in LATIN_PROSE_TOKEN_RE.findall(value))
        elif isinstance(value, list):
            for item in value:
                add_value(item)

    def add_proper_names(value: Any) -> None:
        if not isinstance(value, str):
            return
        for token in LATIN_PROSE_TOKEN_RE.findall(value):
            letters = token.replace("'", "").replace("-", "")
            if letters.isupper() or token[0].isupper() or any(char.isupper() for char in token[1:]):
                allowed.add(token.casefold())

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).casefold() in METADATA_NAME_FIELDS:
                    add_value(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        else:
            add_proper_names(value)

    for rel in ("_research/papers.json", "survey.json"):
        walk(load_json(path / rel, {}))
    for rel in ("bibtex/references.bib", "book/references.bib"):
        bib_path = path / rel
        if not bib_path.exists():
            continue
        raw = bib_path.read_text(encoding="utf-8", errors="ignore")
        add_proper_names(raw)
        for match in re.finditer(
            r"^\s*(?:author|booktitle|journal|organization|publisher)\s*=\s*[\{\"](.*?)[\}\"]\s*,?\s*$",
            raw,
            flags=re.I | re.M,
        ):
            add_value(match.group(1))
        allowed.update(name for name in LOWERCASE_PROPER_NAMES if re.search(rf"\b{re.escape(name)}\b", raw, flags=re.I))
    metadata_blob = " ".join(
        (path / rel).read_text(encoding="utf-8", errors="ignore")
        for rel in ("_research/papers.json", "survey.json")
        if (path / rel).exists()
    )
    allowed.update(name for name in LOWERCASE_PROPER_NAMES if re.search(rf"\b{re.escape(name)}\b", metadata_blob, flags=re.I))
    return allowed


def korean_prose_language_stats(text: str, allowed_latin_tokens: Iterable[str] = ()) -> Dict[str, Any]:
    """Measure untranslated Latin prose in a Korean manuscript.

    This is deliberately narrower than a blanket ASCII ratio. It removes
    material where Latin text is expected (code, math, link labels, citations,
    references, comments, and a Korean term's immediate parenthetical gloss),
    and it does not count acronyms or capitalized/camel-case proper names.
    Figure captions remain visible because they are reader-facing prose.
    Repeated lower-case English terms and ordinary English sentences remain
    visible to the gate.
    """
    # Remove Markdown links before prose() strips their URL target; otherwise
    # the orphaned label would look like ordinary English prose.
    body = re.sub(r"!\[([^\]]*)\]\([^\)]*\)", r" \1 ", text)
    body = re.sub(r"\[[^\]]+\]\([^\)]*\)", " ", body)
    body = prose(body)
    body = re.sub(r"~~~.*?~~~", " ", body, flags=re.S)
    body = re.sub(r"^ {4}.*$", " ", body, flags=re.M)
    body = re.sub(r"<https?://[^>]+>", " ", body)
    body = re.sub(r"`+[^`\n]*`+", " ", body)
    body = re.sub(r"\$\$.*?\$\$|\$[^$\n]*\$", " ", body, flags=re.S)
    body = re.sub(r"\[[^\]\n]*(?:19|20)\d{2}[a-z]?[^\]\n]*\]", " ", body, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    for term in sorted(ALLOWED_KO_TECHNICAL_TERMS, key=len, reverse=True):
        pattern = re.escape(term).replace(r"\ ", r"\s+")
        body = re.sub(rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])", " ", body, flags=re.I)
    # A chapter may introduce a technical term once as 속도(velocity). Keep a
    # repeated gloss visible and report it separately. The no-whitespace
    # boundary keeps the exception specific and hard to game.
    gloss_counts: Dict[str, int] = {}

    def remove_first_gloss(match: re.Match[str]) -> str:
        key = " ".join(token.casefold() for token in LATIN_PROSE_TOKEN_RE.findall(match.group(0)))
        gloss_counts[key] = gloss_counts.get(key, 0) + 1
        return " " if gloss_counts[key] == 1 else match.group(0)

    body = re.sub(
        r"(?<=[가-힣])\((?=[^()\n]{1,160}\))(?=[^()\n]*[A-Za-z])(?![^()\n]*[가-힣])[^()\n]*\)",
        remove_first_gloss,
        body,
    )

    allowed = {token.casefold() for token in allowed_latin_tokens}
    allowed.update(LATIN_PROSE_EXCLUDED_TOKENS)
    allowed.update(LATIN_UNIT_TOKENS)
    korean_tokens = len(re.findall(r"[가-힣]+", body))
    latin_tokens: List[str] = []
    for match in LATIN_PROSE_TOKEN_RE.finditer(body):
        token = match.group(0)
        letters = token.replace("'", "").replace("-", "")
        if len(letters) <= 1:
            continue
        if letters.isupper():
            continue
        if token[0].isupper() or any(char.isupper() for char in token[1:]):
            continue
        normalized = token.casefold()
        if normalized in allowed:
            continue
        latin_tokens.append(normalized)
    denominator = korean_tokens + len(latin_tokens)
    counts: Dict[str, int] = {}
    for token in latin_tokens:
        counts[token] = counts.get(token, 0) + 1
    top_tokens = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    repeated_glosses = sorted(
        ((term, count - 1) for term, count in gloss_counts.items() if term and count > 1),
        key=lambda item: (-item[1], item[0]),
    )
    return {
        "latin_prose_tokens": len(latin_tokens),
        "korean_tokens": korean_tokens,
        "latin_prose_fraction": len(latin_tokens) / max(1, denominator),
        "top_latin_tokens": [{"token": token, "count": count} for token, count in top_tokens],
        "repeated_english_glosses": sum(count for _, count in repeated_glosses),
        "top_repeated_english_glosses": [{"term": term, "count": count} for term, count in repeated_glosses[:8]],
    }


def word_count(text: str) -> int:
    """Use the established Terry rough-word metric, including references."""
    return len(WORD_RE.findall(text)) + sum(max(1, len(chunk) // 2) for chunk in KOREAN_RE.findall(text))


def visual_positions(text: str) -> Tuple[List[int], List[int]]:
    body = prose(text)
    figures = [match.start() for match in FIGURE_RE.finditer(body)]
    table_positions: List[int] = []
    lines = body.splitlines(keepends=True)
    offsets = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    separator = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
    for index in range(len(lines) - 2):
        header, divider, row = lines[index:index + 3]
        if header.count("|") >= 2 and separator.fullmatch(divider.rstrip("\r\n")) and row.count("|") >= 2:
            table_positions.append(offsets[index])
    return figures, table_positions


def markdown_table_chars(text: str) -> int:
    """Measure reader-visible table weight using the survey benchmark convention."""
    return sum(len(line.strip()) for line in prose(text).splitlines() if line.strip().startswith("|"))


def verified_status(value: Any) -> bool:
    status = str(value or "").strip().lower()
    accepted = {
        "verified", "linked_reference_verified", "metadata_verified",
        "papers_json_primary_verified", "papers_json_verified",
        "partial_verified", "primary_source_verified", "verified_arxiv_filled",
        "verified_bibliographic", "verified_id", "verified_id_no_key",
        "verified_key_only", "verified_primary_company_url",
        "verified_primary_paper_url", "verified_primary_url",
    }
    return status in accepted


def reference_identity(row: Dict[str, Any], fallback: int) -> str:
    doi = str(row.get("doi") or "").strip().lower()
    arxiv = str(row.get("arxiv_id") or "").strip().lower()
    bib = str(row.get("bibtex_key") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    if arxiv:
        return f"arxiv:{arxiv}"
    if bib:
        return f"bib:{bib}"
    title = re.sub(r"\W+", " ", str(row.get("title") or row.get("text") or "").lower()).strip()
    url = str(row.get("url") or "").strip().lower()
    return f"fallback:{title}|{url}" if title or url else f"row:{fallback}"


def prose_quality(text: str) -> Tuple[float, float, int]:
    body = prose(text)
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z0-9'_-]*|[가-힣]+", body)]
    diversity = len(set(tokens)) / max(1, len(tokens))
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    dominant = max(counts.values(), default=0) / max(1, len(tokens))
    subsections = len(re.findall(r"^##+\s+", body, flags=re.M))
    return diversity, dominant, subsections


def paragraph_quality(text: str) -> Tuple[int, List[str]]:
    lengths = []
    normalized = []
    for paragraph in re.split(r"\n\s*\n", prose(text)):
        stripped = " ".join(paragraph.split())
        if not stripped or stripped.startswith(("#", ">", "- ", "1. ", "![", "|", "<!--")):
            continue
        count = word_count(stripped)
        lengths.append(count)
        if count >= 45:
            value = re.sub(r"\[[^\]\n]{1,120},\s*(?:19|20)\d{2}[a-z]?\]", "[CIT]", stripped)
            value = re.sub(r"\b(?:19|20)\d{2}[a-z]?\b|\b\d+(?:\.\d+)?\b", "N", value)
            value = re.sub(r"\s+", " ", value).strip().casefold()
            if len(value) >= 120:
                normalized.append(value)
    ordered = sorted(lengths)
    p90 = ordered[min(len(ordered) - 1, math.ceil(0.9 * len(ordered)) - 1)] if ordered else 0
    return p90, normalized


def claim_anchor_excerpt(text: str, claim_id: str) -> Tuple[Optional[str], Optional[str]]:
    match = REFERENCE_HEADING_RE.search(text)
    body = text[:match.start()] if match else text
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    marker = f"<!-- claim:{claim_id} -->"
    if body.count(marker) != 1:
        return None, "marker must appear exactly once before references"
    tail = body.split(marker, 1)[1]
    tail = re.split(r"\n##+\s+|<!--\s*claim:", tail, maxsplit=1)[0]
    tail = re.sub(r"!\[[^\]]*\]\([^\)]*\)|\[[^\]]+\]\([^\)]*\)|[`*_>#|]", " ", tail)
    excerpt = " ".join(tail.split())[:1200]
    if word_count(excerpt) < 12:
        return None, "marker is not followed by substantive claim prose"
    return excerpt, None


def claim_anchor_digest(text: str, claim_id: str) -> Tuple[Optional[str], Optional[str]]:
    excerpt, error = claim_anchor_excerpt(text, claim_id)
    if error or excerpt is None:
        return None, error
    return hashlib.sha256(excerpt.casefold().encode("utf-8")).hexdigest(), None


def content_digest(path: Path, config_path: Optional[Path] = None, evaluator_path: Optional[Path] = None) -> str:
    hasher = hashlib.sha256()
    candidates = []
    # Bind only commit-eligible release evidence. `_refs_extracted.json` and
    # `_workspace/` are derived local score inputs and are intentionally
    # gitignored by the split content repository. Their committed counterparts
    # are the fact-check report, claim ledger, research corpus, and asset log.
    for rel in ("survey.json", "_assets_log.md", "_factcheck_report.md", "_qa_report.md", "_quality/reviewer_scores.json", "_quality/build_validation.json"):
        target = path / rel
        if target.is_file():
            candidates.append(target)
    # Figure binaries live in private R2 and are intentionally absent from the
    # split content repository. Their committed manifests bind paths and hashes.
    for directory in ("book", "_research", "_analysis"):
        base = path / directory
        if base.is_dir():
            candidates.extend(item for item in base.rglob("*") if item.is_file())
    for target in sorted(set(candidates), key=lambda item: str(item.relative_to(path))):
        rel = str(target.relative_to(path))
        hasher.update(rel.encode("utf-8") + b"\0")
        hasher.update(target.read_bytes())
        hasher.update(b"\0")
    hasher.update((config_path or CONFIG_PATH).read_bytes())
    hasher.update((evaluator_path or Path(__file__)).read_bytes())
    return hasher.hexdigest()


def max_learning_gap(text: str) -> int:
    body = prose(text)
    figures, tables = visual_positions(body)
    anchors = sorted(set([0, len(body)] + figures + tables))
    return max((word_count(body[a:b]) for a, b in zip(anchors, anchors[1:])), default=0)


def source_count_by_chapter(path: Path, chapters: Iterable[int]) -> Dict[int, int]:
    counts = {ch: set() for ch in chapters}
    refs = load_json(path / "_refs_extracted.json", [])
    if isinstance(refs, dict):
        refs = refs.get("references") or refs.get("items") or []
    if isinstance(refs, list):
        for row in refs:
            if not isinstance(row, dict):
                continue
            try:
                ch = int(str(row.get("ch") or row.get("chapter") or "0"))
            except ValueError:
                continue
            if ch not in counts:
                continue
            identity = row.get("bibtex_key") or row.get("doi") or row.get("arxiv_id") or row.get("text")
            if identity:
                counts[ch].add(str(identity).strip().lower())
    return {ch: len(values) for ch, values in counts.items()}


def valid_corpus(path: Path) -> Tuple[int, int, float]:
    papers = load_json(path / "_research/papers.json", [])
    if isinstance(papers, dict):
        papers = papers.get("papers") or papers.get("items") or []
    titles = set()
    invalid = 0
    rich = 0
    for paper in papers if isinstance(papers, list) else []:
        if not isinstance(paper, dict):
            invalid += 1
            continue
        title = re.sub(r"\W+", " ", str(paper.get("title") or "").lower()).strip()
        if len(title) < 5 or title in titles:
            invalid += 1
            continue
        titles.add(title)
        if paper.get("method_summary") and paper.get("limitations") and (paper.get("chapter_hint") or paper.get("chapter")):
            rich += 1
    return len(titles), invalid, (100.0 * rich / max(1, len(titles)))


def flatten_images(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    chapters = data.get("chapters")
    if isinstance(chapters, dict):
        return [item for items in chapters.values() if isinstance(items, list) for item in items if isinstance(item, dict)]
    return [item for item in data.get("images", []) if isinstance(item, dict)] if isinstance(data.get("images"), list) else []


def reviewer_dimensions(path: Path) -> Dict[str, float]:
    data = load_json(path / "_quality/reviewer_scores.json", {})
    source = data.get("dimensions", data) if isinstance(data, dict) else {}
    result = {}
    for key in ("evidence", "synthesis", "accuracy", "visuals", "links", "bilingual", "release"):
        value = source.get(key) if isinstance(source, dict) else None
        if isinstance(value, dict):
            value = value.get("score")
        if isinstance(value, (int, float)):
            result[key] = clamp(float(value))
    return result


def add_failure(failures: List[Dict[str, Any]], gate: str, owner: str, message: str, metric: Any = None, threshold: Any = None) -> None:
    failures.append({"id": gate, "owner": owner, "message": message, "metric": metric, "threshold": threshold})


def evaluate(root: Path, slug: str, profile_name: str = "full") -> Dict[str, Any]:
    path = survey_dir(root, slug)
    chapters = chapter_numbers(path)
    profile = load_profile(profile_name)
    failures: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {"chapter_count": len(chapters)}

    title_style = title_style_metrics(path)
    metrics["title_style"] = title_style
    for lang in ("ko", "en"):
        part_limit = int(profile[f"max_part_title_chars_{lang}"])
        chapter_limit = int(profile[f"max_chapter_title_chars_{lang}"])
        median_limit = int(profile[f"max_chapter_title_median_chars_{lang}"])
        long_parts = [row for row in title_style["part_lengths"][lang] if row["chars"] > part_limit]
        long_chapters = [row for row in title_style["chapter_lengths"][lang] if row["chars"] > chapter_limit]
        observed_median = title_style["chapter_medians"][lang]
        if long_parts:
            add_failure(failures, f"title-part-length-{lang}", "book_writer", f"{lang.upper()} part titles exceed the {part_limit}-character review limit.", long_parts, part_limit)
        if long_chapters:
            add_failure(failures, f"title-chapter-length-{lang}", "book_writer", f"{lang.upper()} chapter titles exceed the {chapter_limit}-character review limit.", long_chapters, chapter_limit)
        if observed_median > median_limit:
            add_failure(failures, f"title-chapter-median-{lang}", "book_writer", f"{lang.upper()} median chapter-title length is {observed_median:g}; maximum is {median_limit}.", observed_median, median_limit)
    if title_style["metadata_drift"]:
        add_failure(failures, "title-metadata-sync", "book_writer", "Part/chapter titles drift between survey.json, manuscript frontmatter, or visible H1 headings.", title_style["metadata_drift"][:24], 0)

    corpus_count, invalid_papers, rich_pct = valid_corpus(path)
    corpus_floor = max(int(profile["corpus_floor_base"]), int(profile["corpus_floor_per_chapter"]) * len(chapters))
    metrics.update({"research_corpus": corpus_count, "research_rich_metadata_pct": round(rich_pct, 1), "invalid_or_duplicate_papers": invalid_papers, "research_corpus_floor": corpus_floor})
    if corpus_count < corpus_floor:
        add_failure(failures, "research-corpus", "evidence_librarian", f"Research corpus has {corpus_count} unique sources; requires {corpus_floor}.", corpus_count, corpus_floor)
    if invalid_papers:
        add_failure(failures, "research-corpus-integrity", "evidence_librarian", f"Research corpus has {invalid_papers} blank or duplicate entries.", invalid_papers, 0)
    rich_floor = float(profile["min_research_rich_pct"])
    if rich_pct < rich_floor:
        add_failure(failures, "research-richness", "evidence_librarian", f"Rich research metadata covers {rich_pct:.1f}% of canonical papers; requires {rich_floor:.1f}%.", round(rich_pct, 1), rich_floor)

    sources = source_count_by_chapter(path, chapters)
    metrics["sources_per_chapter"] = sources
    min_sources = int(profile["min_sources_per_chapter"])
    for ch, count in sources.items():
        if count < min_sources:
            add_failure(failures, f"sources-ch{ch:02d}", "evidence_librarian", f"Chapter {ch} has {count} distinct cited sources; requires {min_sources}.", count, min_sources)

    min_words = int(profile["min_words_per_language_chapter"])
    word_tolerance_pct = float(profile.get("word_gate_tolerance_pct", 0))
    min_words_with_tolerance = math.ceil(min_words * (1.0 - word_tolerance_pct / 100.0))
    max_words = int(profile.get("max_words_per_language_chapter", 0))
    max_table_chars = int(profile.get("max_table_chars_per_chapter", 0))
    min_figures = int(profile["min_figures_per_chapter"])
    late_fraction = float(profile["late_visual_fraction"])
    max_gap_target = int(profile["max_learning_aid_gap_words"])
    chapter_metrics: Dict[str, Any] = {}
    all_word_ratios: List[float] = []
    figure_ratios: List[float] = []
    late_passes: List[float] = []
    gap_passes: List[float] = []
    parity_scores: List[float] = []
    table_density_scores: List[float] = []
    referenced_local_image_paths = set()
    paragraph_norms: List[Tuple[str, str]] = []
    allowed_ko_latin_tokens = survey_metadata_latin_terms(path)
    for ch in chapters:
        cm: Dict[str, Any] = {}
        lang_words = {}
        for lang in ("ko", "en"):
            chapter_file = path / "book" / lang / f"ch{ch:02d}.md"
            text = chapter_file.read_text(encoding="utf-8", errors="ignore") if chapter_file.exists() else ""
            body = prose(text)
            words = word_count(body)
            diversity, dominant_fraction, subsection_count = prose_quality(text)
            figures, table_positions = visual_positions(text)
            table_chars = markdown_table_chars(text)
            figure_targets = re.findall(r"!\[[^\]]*\]\(([^\)]+)\)", text)
            missing_figures = []
            for target in figure_targets:
                clean = target.strip().split()[0].strip("<>")
                if clean.startswith(("http://", "https://", "data:")):
                    continue
                resolved_target = (chapter_file.parent / clean).resolve()
                referenced_local_image_paths.add(resolved_target)
                if not resolved_target.exists():
                    missing_figures.append(clean)
            gap = max_learning_gap(text)
            body_length = max(1, len(prose(text)))
            last_fraction = max(figures + table_positions, default=-1) / body_length
            paragraph_p90, normalized_paragraphs = paragraph_quality(text)
            paragraph_norms.extend((value, f"{lang}-ch{ch:02d}") for value in normalized_paragraphs)
            learning_markers = ("이 장을 읽고 나면", "이 챕터를 읽고 나면", "학습 목표") if lang == "ko" else ("After reading this chapter", "By the end of this chapter", "Learning objectives")
            has_learning_outcomes = any(re.search(rf"^>\s*\*\*[^\n]*{re.escape(marker)}", body, flags=re.I | re.M) for marker in learning_markers)
            ko_language = korean_prose_language_stats(text, allowed_ko_latin_tokens) if lang == "ko" else None
            lang_words[lang] = words
            cm[lang] = {"words": words, "figures": len(figures), "tables": len(table_positions), "table_chars": table_chars, "has_learning_outcomes": has_learning_outcomes, "paragraph_p90_words": paragraph_p90, "missing_local_figures": missing_figures, "last_learning_aid_fraction": round(last_fraction, 3), "max_learning_aid_gap_words": gap, "lexical_diversity": round(diversity, 4), "dominant_token_fraction": round(dominant_fraction, 4), "subsections": subsection_count}
            if ko_language is not None:
                cm[lang]["latin_prose_tokens"] = ko_language["latin_prose_tokens"]
                cm[lang]["korean_tokens"] = ko_language["korean_tokens"]
                cm[lang]["latin_prose_fraction"] = round(ko_language["latin_prose_fraction"], 4)
                cm[lang]["top_latin_tokens"] = ko_language["top_latin_tokens"]
                cm[lang]["repeated_english_glosses"] = ko_language["repeated_english_glosses"]
                cm[lang]["top_repeated_english_glosses"] = ko_language["top_repeated_english_glosses"]
            all_word_ratios.append(min(1.0, words / min_words) if min_words else 1.0)
            figure_ratios.append(min(1.0, len(figures) / min_figures) if min_figures else 1.0)
            late_passes.append(1.0 if last_fraction >= late_fraction else 0.0)
            gap_passes.append(1.0 if gap <= max_gap_target else max(0.0, max_gap_target / max(1, gap)))
            if max_table_chars:
                table_density_scores.append(min(1.0, max_table_chars / max(1, table_chars)))
            if words < min_words_with_tolerance:
                add_failure(failures, f"depth-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} has {words} rough words; requires {min_words} with {word_tolerance_pct:g}% gate tolerance ({min_words_with_tolerance} minimum).", words, min_words_with_tolerance)
            if max_words and words > max_words:
                add_failure(failures, f"bloat-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} has {words} rough words; maximum is {max_words}. Cut, do not add. Remove audit-style checklists, role-responsibility tables, and procedural restatement before touching argument prose.", words, max_words)
            if subsection_count < int(profile["min_subsections_per_chapter"]):
                add_failure(failures, f"structure-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} has {subsection_count} substantive subsections; requires {profile['min_subsections_per_chapter']}.", subsection_count, profile["min_subsections_per_chapter"])
            if diversity < float(profile["min_lexical_diversity"]):
                add_failure(failures, f"lexical-diversity-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} lexical diversity is {diversity:.3f}; requires {profile['min_lexical_diversity']}.", round(diversity, 4), profile["min_lexical_diversity"])
            if dominant_fraction > float(profile["max_dominant_token_fraction"]):
                add_failure(failures, f"dominant-token-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} repeats one token across {dominant_fraction:.1%} of prose; maximum is {profile['max_dominant_token_fraction']:.1%}.", round(dominant_fraction, 4), profile["max_dominant_token_fraction"])
            if lang == "ko" and ko_language is not None:
                latin_limit = float(profile["max_ko_latin_prose_fraction"])
                if ko_language["latin_prose_fraction"] > latin_limit:
                    examples = ", ".join(item["token"] for item in ko_language["top_latin_tokens"][:5])
                    add_failure(
                        failures,
                        f"korean-language-ko-ch{ch:02d}",
                        "book_writer",
                        f"KO chapter {ch} uses untranslated lower-case Latin prose in {ko_language['latin_prose_fraction']:.1%} of measured prose tokens; maximum is {latin_limit:.1%}. Frequent tokens: {examples or 'none'}.",
                        round(ko_language["latin_prose_fraction"], 4),
                        latin_limit,
                    )
            if profile["require_learning_outcomes"] and not has_learning_outcomes:
                add_failure(failures, f"learning-outcomes-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} has no reader-facing learning outcomes.", False, True)
            if len(table_positions) < int(profile["min_tables_per_chapter"]):
                add_failure(failures, f"tables-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} has {len(table_positions)} markdown tables; requires {profile['min_tables_per_chapter']}.", len(table_positions), profile["min_tables_per_chapter"])
            if max_table_chars and table_chars > max_table_chars:
                add_failure(failures, f"apparatus-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} has {table_chars} table characters; maximum is {max_table_chars}. Cut, do not add. Remove audit-style checklists, role-responsibility tables, and procedural restatement; keep tables only where comparison materially helps the reader.", table_chars, max_table_chars)
            if paragraph_p90 > int(profile["max_paragraph_p90_words"]):
                add_failure(failures, f"paragraph-p90-{lang}-ch{ch:02d}", "book_writer", f"{lang.upper()} chapter {ch} paragraph p90 is {paragraph_p90} words; maximum is {profile['max_paragraph_p90_words']}.", paragraph_p90, profile["max_paragraph_p90_words"])
            if len(figures) < min_figures:
                add_failure(failures, f"figures-{lang}-ch{ch:02d}", "image_curator", f"{lang.upper()} chapter {ch} references {len(figures)} figures; requires {min_figures}.", len(figures), min_figures)
            if missing_figures:
                add_failure(failures, f"figure-files-{lang}-ch{ch:02d}", "image_curator", f"{lang.upper()} chapter {ch} references missing local figures: {missing_figures}.", len(missing_figures), 0)
            if last_fraction < late_fraction:
                add_failure(failures, f"visual-pacing-{lang}-ch{ch:02d}", "image_curator", f"{lang.upper()} chapter {ch} has no figure or table after {late_fraction:.0%} of the prose.", round(last_fraction, 3), late_fraction)
            if gap > max_gap_target:
                add_failure(failures, f"wall-text-{lang}-ch{ch:02d}", "image_curator", f"{lang.upper()} chapter {ch} has a {gap}-word learning-aid gap; maximum is {max_gap_target}.", gap, max_gap_target)
        high, low = max(lang_words.values(), default=0), min(lang_words.values(), default=0)
        parity = 100.0 if high == 0 else 100.0 * low / high
        cm["bilingual_depth_parity"] = round(parity, 1)
        parity_scores.append(parity)
        if parity < 80:
            add_failure(failures, f"bilingual-parity-ch{ch:02d}", "book_writer", f"Chapter {ch} bilingual depth parity is {parity:.1f}%; requires 80%.", parity, 80)
        chapter_metrics[f"ch{ch:02d}"] = cm
    paragraph_occurrences: Dict[str, List[str]] = {}
    for value, location in paragraph_norms:
        paragraph_occurrences.setdefault(value, []).append(location)
    repeated_paragraphs = {value: locations for value, locations in paragraph_occurrences.items() if len(locations) >= 2}
    metrics["repeated_paragraph_groups"] = len(repeated_paragraphs)
    if len(repeated_paragraphs) > int(profile["max_repeated_paragraph_groups"]):
        examples = [{"locations": locations[:6], "text": value[:180]} for value, locations in list(repeated_paragraphs.items())[:8]]
        add_failure(failures, "repeated-paragraphs", "book_writer", f"Book contains {len(repeated_paragraphs)} repeated normalized paragraph groups; maximum is {profile['max_repeated_paragraph_groups']}.", examples, profile["max_repeated_paragraph_groups"])
    metrics["chapters"] = chapter_metrics

    missing_contracts = [rel for rel in PROCESS_CONTRACTS if not (path / rel).exists()]
    missing_packets = [f"_analysis/chapter_source_packets/ch{ch:02d}.json" for ch in chapters if not (path / f"_analysis/chapter_source_packets/ch{ch:02d}.json").exists()]
    missing_contracts.extend(missing_packets)
    invalid_packets = []
    packet_schema_errors = {}
    for ch in chapters:
        packet_path = path / f"_analysis/chapter_source_packets/ch{ch:02d}.json"
        if not packet_path.exists():
            continue
        packet = load_json(packet_path, {})
        schema_errors = validate_schema(packet, "chapter-source-packet.schema.json")
        if schema_errors:
            packet_schema_errors[ch] = schema_errors
        required_packet_fields = ("chapter", "thesis", "sections", "sources", "counterevidence", "visual_candidates")
        if not isinstance(packet, dict) or any(field not in packet for field in required_packet_fields) or len(packet.get("sources", [])) < min_sources:
            invalid_packets.append(ch)
    metrics["invalid_chapter_source_packets"] = invalid_packets
    metrics["chapter_source_packet_schema_errors"] = packet_schema_errors
    for ch in invalid_packets:
        add_failure(failures, f"source-packet-ch{ch:02d}", "evidence_librarian", f"Chapter {ch} source packet is incomplete or has fewer than {min_sources} sources.")
    metrics["missing_process_contracts"] = missing_contracts
    if profile["require_process_contracts"]:
        for rel in missing_contracts:
            owner = "qa_reviewer"
            if "research" in rel or "claim_evidence" in rel or "chapter_source_packets" in rel:
                owner = "evidence_librarian"
            elif "image_plan" in rel:
                owner = "image_curator"
            add_failure(failures, f"contract-{Path(rel).stem.replace('_', '-')}", owner, f"Missing required process contract: {rel}")

    claims, claim_errors = load_jsonl(path / "_analysis/claim_evidence.jsonl")
    claim_schema_errors = {index + 1: errors for index, row in enumerate(claims) if (errors := validate_schema(row, "claim-evidence.schema.json"))}
    invalid_claim_rows = [row for index, row in enumerate(claims, 1) if index in claim_schema_errors]
    high_claims = [row for row in claims if row.get("risk") == "high"]
    verified_high = [row for row in high_claims if str(row.get("verification_status", "")).lower() in {"verified", "qualified"} and row.get("source_ids")]
    claim_coverage = 100.0 if not high_claims and not profile["require_claim_matrix"] else 100.0 * len(verified_high) / max(1, len(high_claims))
    qualified_without_caveat = [row.get("claim_id") for row in claims if row.get("verification_status") == "qualified" and not row.get("caveat")]
    invalid_claim_anchors = []
    for row in claims:
        claim_id = str(row.get("claim_id") or "")
        stored_anchors = row.get("manuscript_anchors") if isinstance(row.get("manuscript_anchors"), dict) else {}
        try:
            chapter = int(row.get("chapter", 0))
        except (TypeError, ValueError):
            chapter = 0
        for lang in ("ko", "en"):
            manuscript = path / "book" / lang / f"ch{chapter:02d}.md"
            text = manuscript.read_text(encoding="utf-8", errors="ignore") if manuscript.exists() else ""
            excerpt, error = claim_anchor_excerpt(text, claim_id)
            observed = hashlib.sha256(excerpt.casefold().encode("utf-8")).hexdigest() if excerpt is not None else None
            expected = str(stored_anchors.get(lang) or "")
            if error or not expected or observed != expected:
                invalid_claim_anchors.append({"claim_id": claim_id, "lang": lang, "chapter": chapter, "error": error or "stored excerpt digest mismatch"})
            elif lang == "en":
                normalized_claim = " ".join(str(row.get("claim") or "").split()).casefold()
                if normalized_claim not in excerpt.casefold():
                    invalid_claim_anchors.append({"claim_id": claim_id, "lang": lang, "chapter": chapter, "error": "canonical claim text is absent from the bound English excerpt"})
    metrics.update({"claim_rows": len(claims), "invalid_claim_rows": len(invalid_claim_rows), "claim_schema_errors": claim_schema_errors, "qualified_without_caveat": qualified_without_caveat, "invalid_claim_anchors": invalid_claim_anchors, "claim_jsonl_errors": claim_errors, "high_risk_claims": len(high_claims), "verified_high_risk_claims": len(verified_high), "high_risk_claim_coverage": round(claim_coverage, 1)})
    if profile["require_claim_matrix"] and not claims:
        add_failure(failures, "claim-matrix-empty", "fact_checker", "Claim-evidence matrix is empty; load-bearing claims cannot be audited.")
    if profile["require_claim_matrix"]:
        covered_claim_chapters = {int(row.get("chapter", 0)) for row in claims if str(row.get("chapter", "")).isdigit()}
        for ch in chapters:
            if ch not in covered_claim_chapters:
                add_failure(failures, f"claim-coverage-ch{ch:02d}", "fact_checker", f"Chapter {ch} has no claim-evidence rows.")
    if claim_errors:
        add_failure(failures, "claim-matrix-invalid", "fact_checker", f"Claim-evidence matrix has {len(claim_errors)} invalid JSONL rows.", len(claim_errors), 0)
    if invalid_claim_rows:
        add_failure(failures, "claim-schema-invalid", "fact_checker", f"Claim-evidence matrix has {len(invalid_claim_rows)} rows missing required fields.", len(invalid_claim_rows), 0)
    if qualified_without_caveat:
        add_failure(failures, "qualified-claim-caveats", "fact_checker", f"Qualified claims lack caveats: {qualified_without_caveat}.", len(qualified_without_caveat), 0)
    if high_claims and len(verified_high) != len(high_claims):
        add_failure(failures, "high-risk-claims", "fact_checker", f"Verified {len(verified_high)}/{len(high_claims)} high-risk claims; requires 100%.", len(verified_high), len(high_claims))
    if profile["require_claim_matrix"] and invalid_claim_anchors:
        add_failure(failures, "claim-manuscript-anchors", "fact_checker", f"{len(invalid_claim_anchors)} claim anchors are missing, non-substantive, duplicated, or do not match their stored excerpt digest.", invalid_claim_anchors[:12], 0)

    refs = load_json(path / "_refs_extracted.json", [])
    refs = refs if isinstance(refs, list) else refs.get("references", []) if isinstance(refs, dict) else []
    ref_groups: Dict[str, List[Dict[str, Any]]] = {}
    for index, row in enumerate(refs):
        if isinstance(row, dict):
            ref_groups.setdefault(reference_identity(row, index), []).append(row)
    unique_refs = list(ref_groups.values())
    verified_refs = [rows for rows in unique_refs if all(verified_status(row.get("verification_status")) for row in rows)]
    ref_verification = 100.0 * len(verified_refs) / max(1, len(unique_refs)) if unique_refs else 0.0
    academic_tokens = ("arxiv.org", "doi.org", "openaccess.thecvf.com", "proceedings.mlr.press", "roboticsproceedings.org", "ieee", "nature.com", "science.org", "cvpr", "icra", "iros", "rss", "corl", "neurips", "icml")
    academic_refs = 0
    primary_refs = 0
    for rows in unique_refs:
        blob = " ".join(str(row.get(key) or "") for row in rows for key in ("text", "url", "doi", "arxiv_id")).lower()
        doi = next((str(row.get("doi") or "").strip().lower() for row in rows if row.get("doi")), "")
        arxiv = next((str(row.get("arxiv_id") or "").strip().lower() for row in rows if row.get("arxiv_id")), "")
        is_primary = bool(re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", arxiv) or re.match(r"^10\.\d{4,9}/\S+$", doi) or "doi.org/10." in blob or re.search(r"arxiv\.org/(?:abs|pdf)/\d{4}\.\d{4,5}", blob))
        if is_primary:
            primary_refs += 1
        if is_primary or any(token in blob for token in academic_tokens):
            academic_refs += 1
    academic_floor = max(int(profile["min_academic_refs_base"]), int(profile["min_academic_refs_per_chapter"]) * len(chapters))
    primary_floor = max(int(profile["min_primary_refs_base"]), int(profile["min_primary_refs_per_chapter"]) * len(chapters))
    metrics.update({"reference_rows": len(refs), "references": len(unique_refs), "academic_references": academic_refs, "academic_reference_floor": academic_floor, "primary_id_references": primary_refs, "primary_reference_floor": primary_floor, "verified_references": len(verified_refs), "reference_verification": round(ref_verification, 1)})
    if academic_refs < academic_floor:
        add_failure(failures, "academic-references", "evidence_librarian", f"Academic references total {academic_refs}; requires {academic_floor}.", academic_refs, academic_floor)
    if primary_refs < primary_floor:
        add_failure(failures, "primary-references", "evidence_librarian", f"arXiv/DOI-backed references total {primary_refs}; requires {primary_floor}.", primary_refs, primary_floor)
    if profile_name != "legacy_baseline" and ref_verification < 90:
        add_failure(failures, "reference-verification", "fact_checker", f"Reference verification is {ref_verification:.1f}%; requires 90%.", ref_verification, 90)

    source_ledger, ledger_errors = load_jsonl(path / "_research/source_ledger.jsonl")
    ledger_schema_errors = {index + 1: errors for index, row in enumerate(source_ledger) if (errors := validate_schema(row, "source-ledger.schema.json"))}
    invalid_ledger_rows = [row for index, row in enumerate(source_ledger, 1) if index in ledger_schema_errors]
    eligible = [row for row in source_ledger if row.get("terry_link_eligible") is True]
    linked = [row for row in eligible if row.get("terry_link")]
    link_coverage = 100.0 * len(linked) / max(1, len(eligible)) if eligible else 100.0
    book_text = {lang: "\n".join(md.read_text(encoding="utf-8", errors="ignore") for md in sorted((path / "book" / lang).glob("ch*.md"))) for lang in ("ko", "en")}
    missing_rendered_links = [(row.get("source_id"), lang, row.get("terry_link")) for row in linked for lang in ("ko", "en") if str(row.get("terry_link")) not in book_text[lang]]
    ledger_ids = {str(row.get("source_id")) for row in source_ledger if row.get("source_id")}
    unknown_claim_sources = sorted({str(source_id) for row in claims for source_id in row.get("source_ids", []) if str(source_id) not in ledger_ids})
    metrics.update({"source_ledger_rows": len(source_ledger), "invalid_source_ledger_rows": len(invalid_ledger_rows), "source_ledger_schema_errors": ledger_schema_errors, "source_ledger_errors": ledger_errors, "unknown_claim_source_ids": unknown_claim_sources, "eligible_terry_links": len(eligible), "inserted_terry_links": len(linked), "terry_link_coverage": round(link_coverage, 1), "missing_rendered_terry_links": missing_rendered_links})
    if ledger_errors:
        add_failure(failures, "source-ledger-invalid", "evidence_librarian", f"Source ledger has {len(ledger_errors)} invalid JSONL rows.", len(ledger_errors), 0)
    if invalid_ledger_rows:
        add_failure(failures, "source-ledger-schema", "evidence_librarian", f"Source ledger has {len(invalid_ledger_rows)} rows missing required fields.", len(invalid_ledger_rows), 0)
    if unknown_claim_sources:
        add_failure(failures, "claim-source-integrity", "fact_checker", f"Claim ledger references unknown source IDs: {unknown_claim_sources[:12]}.", len(unknown_claim_sources), 0)
    if eligible and len(linked) != len(eligible):
        add_failure(failures, "terry-crosslinks", "evidence_librarian", f"Inserted {len(linked)}/{len(eligible)} eligible exact Terry links; requires 100%.", len(linked), len(eligible))
    if missing_rendered_links:
        add_failure(failures, "terry-crosslinks-rendered", "evidence_librarian", f"{len(missing_rendered_links)} exact Terry links are absent from a KO/EN manuscript.", len(missing_rendered_links), 0)

    image_data = load_json(path / "_workspace/image_plan.json")
    if image_data is None:
        image_data = load_json(path / "_workspace/04_image_manifest.json", {})
    image_schema_errors = validate_schema(image_data, "image-plan.schema.json") if image_data is not None and profile["require_image_plan"] else []
    all_images = flatten_images(image_data)
    images = [row for row in all_images if row.get("status") == "inserted"] if profile["require_image_plan"] else all_images
    provenance_ok = [row for row in images if row.get("source_type") and row.get("license_basis") and (row.get("insertion_anchor") or not profile["require_image_plan"])]
    missing_planned_files = [row.get("path") for row in images if row.get("path") and not (path / str(row.get("path"))).exists()]
    planned_local_image_paths = {(path / str(row.get("path"))).resolve() for row in images if row.get("path")}
    unplanned_manuscript_images = sorted(str(item) for item in referenced_local_image_paths - planned_local_image_paths)
    uninserted_planned_images = sorted(str(item) for item in planned_local_image_paths - referenced_local_image_paths)
    provenance_coverage = 100.0 * len(provenance_ok) / max(1, len(images)) if images else 0.0
    metrics.update({"image_plan_entries": len(images), "image_plan_schema_errors": image_schema_errors, "non_inserted_image_entries": len(all_images) - len(images), "image_provenance_coverage": round(provenance_coverage, 1), "missing_image_plan_files": missing_planned_files, "unplanned_manuscript_images": unplanned_manuscript_images, "uninserted_planned_images": uninserted_planned_images})
    if profile["require_image_plan"] and not images:
        add_failure(failures, "image-plan-empty", "image_curator", "Image plan has no entries.")
    if image_schema_errors:
        add_failure(failures, "image-plan-schema", "image_curator", f"Image plan fails schema validation with {len(image_schema_errors)} errors.", len(image_schema_errors), 0)
    if images and len(provenance_ok) != len(images):
        add_failure(failures, "image-provenance", "image_curator", f"Image provenance/placement is complete for {len(provenance_ok)}/{len(images)} entries; requires 100%.", len(provenance_ok), len(images))
    if missing_planned_files:
        add_failure(failures, "image-plan-files", "image_curator", f"Image plan references {len(missing_planned_files)} missing files.", len(missing_planned_files), 0)
    if profile["require_image_plan"] and unplanned_manuscript_images:
        add_failure(failures, "image-plan-coverage", "image_curator", f"{len(unplanned_manuscript_images)} manuscript images are absent from the inserted image plan.", unplanned_manuscript_images[:12], 0)
    if profile["require_image_plan"] and uninserted_planned_images:
        add_failure(failures, "image-plan-insertion", "image_curator", f"{len(uninserted_planned_images)} image-plan entries marked inserted are absent from both manuscripts.", uninserted_planned_images[:12], 0)
    source_types = {str(row.get("source_type")) for row in images}
    missing_source_groups = [group for group in profile.get("required_image_source_groups", []) if not source_types.intersection(group)]
    metrics["image_source_types"] = sorted(source_types)
    if missing_source_groups:
        add_failure(failures, "image-source-mix", "image_curator", f"Book image plan lacks required source groups: {missing_source_groups}.", sorted(source_types), missing_source_groups)

    reviewer_data = load_json(path / "_quality/reviewer_scores.json", {})
    reviewer_schema_errors = validate_schema(reviewer_data, "reviewer-scores.schema.json") if reviewer_data else []
    reviewers = reviewer_dimensions(path) if not reviewer_schema_errors else {}
    reviewer_id = str(reviewer_data.get("reviewer_id") or "") if isinstance(reviewer_data, dict) else ""
    harness_state = load_json(path / "_workspace/harness_state.json", {})
    non_qa_worker_ids = {
        str(agent_id)
        for task in harness_state.get("tasks", [])
        if isinstance(task, dict) and task.get("owner") != "qa_reviewer"
        for agent_id in task.get("agent_ids", [])
        if agent_id
    } if isinstance(harness_state, dict) else set()
    qa_worker_ids = {
        str(agent_id)
        for task in harness_state.get("tasks", [])
        if isinstance(task, dict) and task.get("owner") == "qa_reviewer"
        for agent_id in task.get("agent_ids", [])
        if agent_id
    } if isinstance(harness_state, dict) else set()
    reviewer_reused = bool(reviewer_id and reviewer_id in non_qa_worker_ids)
    reviewer_unbound = bool(harness_state and reviewer_id and reviewer_id not in qa_worker_ids)
    metrics["reviewer_dimensions"] = reviewers
    metrics["reviewer_schema_errors"] = reviewer_schema_errors
    metrics["reviewer_id"] = reviewer_id
    metrics["reviewer_reused_non_qa_worker"] = reviewer_reused
    metrics["reviewer_bound_to_qa_worker"] = bool(reviewer_id and reviewer_id in qa_worker_ids) if harness_state else None
    if profile["require_reviewer_scores"] and not reviewers:
        add_failure(failures, "reviewer-scores", "qa_reviewer", "Independent reviewer score artifact is missing or empty.")
    if reviewer_schema_errors:
        add_failure(failures, "reviewer-schema", "qa_reviewer", f"Reviewer score artifact fails schema validation with {len(reviewer_schema_errors)} errors.", len(reviewer_schema_errors), 0)
    if reviewer_reused:
        add_failure(failures, "reviewer-independence", "qa_reviewer", "The declared reviewer also performed a non-QA task in this harness run.", reviewer_id, "unique QA-only agent id")
    if reviewer_unbound:
        add_failure(failures, "reviewer-identity-binding", "qa_reviewer", "The declared reviewer ID does not match any QA task worker in this harness run.", reviewer_id, sorted(qa_worker_ids))
    build = load_json(path / "_quality/build_validation.json", {})
    build_passed = bool(isinstance(build, dict) and build.get("passed") is True)
    metrics["build_validation_passed"] = build_passed
    if profile["require_build_validation"] and not build_passed:
        add_failure(failures, "build-validation", "qa_reviewer", "Build validation has not passed.")
    qa_text = (path / "_qa_report.md").read_text(encoding="utf-8", errors="ignore") if (path / "_qa_report.md").exists() else ""
    qa_lines = [line.strip() for line in qa_text.splitlines() if line.strip()]
    qa_ready = bool(qa_lines and qa_lines[-1] == "READY FOR RELEASE")
    metrics["qa_ready"] = qa_ready
    if profile["require_qa_ready"] and not qa_ready:
        add_failure(failures, "qa-ready", "qa_reviewer", "QA report does not end in an unblocked READY FOR RELEASE verdict.")

    research_contract_ratio = 1.0 - len([rel for rel in missing_contracts if rel.startswith(("_research/", "_analysis/"))]) / 4.0
    evidence_auto = 100.0 * (0.45 * min(1.0, corpus_count / max(1, corpus_floor)) + 0.35 * (sum(min(1.0, count / max(1, min_sources)) for count in sources.values()) / max(1, len(sources))) + 0.20 * clamp(research_contract_ratio, 0, 1))
    synthesis_auto = (
        100.0 * sum(table_density_scores) / max(1, len(table_density_scores))
        if max_table_chars
        else reviewers.get("synthesis", 72.0 if profile_name == "legacy_baseline" else 0.0)
    )
    accuracy_auto = 0.55 * claim_coverage + 0.45 * ref_verification
    visual_auto = 100.0 * (0.40 * (sum(figure_ratios) / max(1, len(figure_ratios))) + 0.25 * (sum(late_passes) / max(1, len(late_passes))) + 0.20 * (sum(gap_passes) / max(1, len(gap_passes))) + 0.15 * (provenance_coverage / 100.0 if images else (1.0 if profile_name == "legacy_baseline" else 0.0)))
    links_auto = 0.6 * link_coverage + 0.4 * min(100.0, ref_verification / 0.9 if refs else 0.0)
    bilingual_auto = 0.6 * (100.0 * sum(all_word_ratios) / max(1, len(all_word_ratios))) + 0.4 * (sum(parity_scores) / max(1, len(parity_scores)))
    release_auto = 100.0 if build_passed and qa_ready else (70.0 if profile_name == "legacy_baseline" else 0.0)
    auto_scores = {"evidence": evidence_auto, "synthesis": synthesis_auto, "accuracy": accuracy_auto, "visuals": visual_auto, "links": links_auto, "bilingual": bilingual_auto, "release": release_auto}
    dimensions = {}
    for name, spec in profile["dimensions"].items():
        auto = clamp(auto_scores[name])
        reviewer = reviewers.get(name)
        score = auto if reviewer is None else 0.65 * auto + 0.35 * reviewer
        dimensions[name] = {"score": round(score, 1), "weight": spec["weight"], "owner": spec["owner"], "automatic": round(auto, 1), "reviewer": reviewer}
        if score < float(profile["dimension_floor"]):
            add_failure(failures, f"dimension-{name}", spec["owner"], f"{name} dimension is {score:.1f}; requires {profile['dimension_floor']}.", round(score, 1), profile["dimension_floor"])

    override_passed = True
    for name, floor in profile.get("required_dimension_overrides", {}).items():
        if dimensions[name]["score"] < float(floor):
            override_passed = False
            add_failure(failures, f"preference-dimension-{name}", dimensions[name]["owner"], f"Preference baseline requires {name} >= {floor}; observed {dimensions[name]['score']}.", dimensions[name]["score"], floor)

    weighted = sum(item["score"] * item["weight"] for item in dimensions.values()) / sum(item["weight"] for item in dimensions.values())
    if profile_name == "legacy_baseline":
        # Preference calibration gives depth/parity enough influence to keep
        # shallow but well-linked drafts below the S1/S4 goldens.
        weighted = 0.70 * weighted + 0.30 * dimensions["bilingual"]["score"]
    # Preserve one failure per stable id so remediation attempts are deterministic.
    unique_failures = {failure["id"]: failure for failure in failures}
    failures = list(unique_failures.values())
    enforce_blockers = bool(profile.get("enforce_hard_blockers", True))
    hard_blockers = failures if enforce_blockers else []
    passed = weighted >= float(profile["release_score"]) and override_passed and not hard_blockers
    return {
        "schema_version": "2.0",
        "slug": slug,
        "profile": profile_name,
        "score": round(weighted, 1),
        "release_score": profile["release_score"],
        "dimension_floor": profile["dimension_floor"],
        "passed": passed,
        "content_digest": content_digest(path),
        "dimensions": dimensions,
        "hard_blockers": hard_blockers,
        "diagnostics": failures if not enforce_blockers else [],
        "metrics": metrics,
    }


def write_scorecard(root: Path, slug: str, scorecard: Dict[str, Any]) -> Path:
    path = survey_dir(root, slug) / "_quality" / "scorecard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
