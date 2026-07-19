#!/usr/bin/env python3
"""Benchmark Terry survey books and compare a target against existing baselines.

Default runs are read-only. Pass --write with --target to write
surveys/<target>/_quality_comparison.md.

Usage:
  python3 benchmark_surveys.py --all
  python3 benchmark_surveys.py --target <slug> [--scope full|mini|auto] [--write]
"""

import argparse
import json
import math
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_REPO_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")
if str(DEFAULT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_REPO_ROOT))

from survey_harness.config import load_profile

FULL_PROFILE = load_profile("full")
RELEASE_BASELINES = [
    "llm-wiki-to-ai-scientist",
    "microbiome-cosmetics-ai",
    "physical-ai-manufacturing",
    "humanoid-revolution",
    "robot-hand-tactile-sensor",
]


@dataclass
class Metrics:
    slug: str
    chapters: int = 0
    ko_words: int = 0
    en_words: int = 0
    refs: int = 0
    ref_link_pct: Optional[float] = None
    figure_md: int = 0
    figure_files: int = 0
    manifest_items: Optional[int] = None
    research_papers: Optional[int] = None
    research_foundations: Optional[int] = None
    research_frontier: Optional[int] = None
    rich_pct: Optional[float] = None
    refs_extracted: Optional[int] = None
    bibtex_pct: Optional[float] = None
    id_pct: Optional[float] = None
    verified_pct: Optional[float] = None
    academic_refs: Optional[int] = None
    arxiv_refs: Optional[int] = None
    doi_refs: Optional[int] = None
    nvidia_official_refs: Optional[int] = None
    validate_rc: Optional[int] = None
    validate_errors: int = 0
    validate_warnings: int = 0
    qa_final: str = ""
    body_prose_citations: int = 0
    rendered_cite_links: int = 0
    cite_targets_missing: int = 0
    cite_sup_ids_missing: int = 0
    backlink_latest: bool = False
    learning_blocks: int = 0
    table_lines: int = 0
    raw_summary_hits: int = 0
    generic_boilerplate_hits: int = 0
    referenced_figures: int = 0
    avg_para_words: Optional[float] = None
    p90_para_words: Optional[float] = None
    repeated_paragraph_groups: int = 0
    visual_pacing_failures: int = 0
    min_last_visual_pct: Optional[float] = None
    max_words_after_last_figure: Optional[int] = None
    max_words_between_visuals: Optional[int] = None
    research_blank_titles: int = 0
    research_duplicate_titles: int = 0
    research_stale_hints: int = 0

    @property
    def ko_words_per_chapter(self):
        return self.ko_words / self.chapters if self.chapters else 0

    @property
    def en_words_per_chapter(self):
        return self.en_words / self.chapters if self.chapters else 0

    @property
    def figures_per_chapter(self):
        return self.figure_files / self.chapters if self.chapters else 0


def repo_root(explicit=None):
    root = Path(explicit).expanduser().resolve() if explicit else DEFAULT_REPO_ROOT
    if not (root / "build.py").exists() or not (root / "surveys").is_dir():
        raise SystemExit(f"ERROR: repo root is not terry-surveys: {root}")
    return root


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def survey_slugs(root):
    return sorted(
        p.name for p in (root / "surveys").iterdir()
        if p.is_dir() and (p / "survey.json").exists()
    )


def chapter_nums(cfg):
    nums = []
    for part in cfg.get("parts", []):
        for ch in part.get("chapters", []):
            if ch.get("num") is not None:
                nums.append(int(ch.get("num")))
    return nums


def rough_word_count(text):
    englishish = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*", text)
    korean_chunks = re.findall(r"[가-힣]+", text)
    return len(englishish) + sum(max(1, len(chunk) // 2) for chunk in korean_chunks)


def reference_entries(markdown):
    in_refs = False
    count = 0
    linked = 0
    for raw in markdown.splitlines():
        line = raw.strip()
        if re.match(r"^##\s*(참고문헌|References)\s*$", line):
            in_refs = True
            continue
        if in_refs and line.startswith("## "):
            in_refs = False
        if in_refs and re.match(r"^\d+\.\s+", line):
            count += 1
            if re.search(r"\[[^\]]+\]\(https?://", line):
                linked += 1
    return count, linked


def manifest_count(manifest):
    if isinstance(manifest, list):
        return len(manifest)
    if not isinstance(manifest, dict):
        return None
    if isinstance(manifest.get("figures"), list):
        return len(manifest["figures"])
    if isinstance(manifest.get("images"), list):
        return len(manifest["images"])
    if isinstance(manifest.get("chapters"), dict):
        return sum(len(v) for v in manifest["chapters"].values() if isinstance(v, list))
    for key in ("total_images", "total_figures"):
        if isinstance(manifest.get(key), int):
            return manifest[key]
    return None


def chapter_hint_numbers(value):
    if isinstance(value, list):
        blob = " ".join(str(item) for item in value)
    else:
        blob = str(value or "")
    return [int(match.group(1)) for match in re.finditer(r"\bCh(?:apter)?\.?\s*(\d+)\b", blob, flags=re.I)]


def research_metadata_counts(survey_dir, chapter_count):
    counts = {"blank_titles": 0, "duplicate_titles": 0, "stale_hints": 0}
    for rel in (
        "_research/papers_foundations.json",
        "_research/papers_frontier.json",
        "_research/papers.json",
    ):
        data = load_json(survey_dir / rel)
        if isinstance(data, dict):
            data = data.get("papers") or data.get("items")
        if not isinstance(data, list):
            continue
        seen = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip()
            if not title:
                counts["blank_titles"] += 1
            else:
                key = title.casefold()
                if key in seen:
                    counts["duplicate_titles"] += 1
                else:
                    seen.add(key)
            hints = item.get("chapter_hint", item.get("chapter"))
            for num in chapter_hint_numbers(hints):
                if num < 1 or num > chapter_count:
                    counts["stale_hints"] += 1
    return counts


def verified_percentage(refs):
    if not refs:
        return None
    good = 0
    for item in refs:
        status = str(item.get("verification_status") or "").lower()
        if any(token in status for token in ("verified", "primary", "papers_json")):
            good += 1
    return round(100 * good / len(refs), 1)


def reference_text_and_urls(item):
    text = str(item.get("text") or "")
    urls = []
    if item.get("url"):
        urls.append(str(item.get("url")))
    urls.extend(re.findall(r"https?://[^\s)\]>\"]+", text))
    return (text + " " + " ".join(urls)).lower(), urls


def ref_source_mix(refs):
    counts = {
        "academic": 0,
        "arxiv": 0,
        "doi": 0,
        "nvidia_official": 0,
    }
    academic_tokens = [
        "arxiv.org",
        "doi.org",
        "openaccess.thecvf.com",
        "proceedings.mlr.press",
        "roboticsproceedings.org",
        "science.org",
        "nature.com",
        "ieee",
        "cvpr",
        "icra",
        "iros",
        "rss",
        "corl",
        "neurips",
        "icml",
    ]
    nvidia_tokens = [
        "developer.nvidia.com",
        "nvidianews.nvidia.com",
        "research.nvidia.com",
        "blogs.nvidia.com",
        "investor.nvidia.com",
        "nvidia.com",
    ]
    for item in refs:
        blob, _urls = reference_text_and_urls(item)
        if "arxiv.org" in blob or item.get("arxiv_id"):
            counts["arxiv"] += 1
        if "doi.org" in blob or item.get("doi"):
            counts["doi"] += 1
        if any(token in blob for token in academic_tokens) or item.get("arxiv_id") or item.get("doi"):
            counts["academic"] += 1
        if any(token in blob for token in nvidia_tokens):
            counts["nvidia_official"] += 1
    return counts


def split_body_refs(markdown):
    match = re.search(r"^##\s*(?:참고문헌|References)\s*$", markdown, flags=re.M)
    if not match:
        return markdown, ""
    return markdown[:match.start()], markdown[match.start():]


def reference_author_year_pairs(markdown):
    _body, refs = split_body_refs(markdown)
    pairs = set()
    for raw in refs.splitlines():
        line = raw.strip()
        match = re.match(r"^\d+\.\s+(.+?)\s+\((\d{4}[a-z]?)\)", line)
        if not match:
            continue
        author = re.sub(r"\s+", " ", match.group(1).strip().strip("*"))
        year = match.group(2)
        if author:
            pairs.add((author, year))
            if author.endswith("."):
                pairs.add((author.rstrip("."), year))
    return sorted(pairs, key=lambda item: len(item[0]), reverse=True)


def count_body_prose_author_year(survey_dir):
    count = 0
    for md in list((survey_dir / "book" / "ko").glob("ch*.md")) + list((survey_dir / "book" / "en").glob("ch*.md")):
        text = md.read_text(encoding="utf-8", errors="ignore")
        body, _refs = split_body_refs(text)
        pairs = reference_author_year_pairs(text)
        for line in body.splitlines():
            if line.lstrip().startswith("!["):
                continue
            for author, year in pairs:
                if re.search(rf"(?<!\[){re.escape(author)}\s+\({re.escape(year)}\)", line):
                    count += 1
                    break
    return count


def rendered_citation_ux(root, survey_dir):
    status = {
        "cite_links": 0,
        "missing_targets": 0,
        "missing_sup_ids": 0,
        "backlink_latest": False,
    }
    html_files = list((survey_dir / "docs" / "ko").glob("ch*.html")) + list((survey_dir / "docs" / "en").glob("ch*.html"))
    for html_path in html_files:
        html = html_path.read_text(encoding="utf-8", errors="ignore")
        ids = set(re.findall(r'id="([^"]+)"', html))
        for match in re.finditer(r'(<sup\b[^>]*>).*?<a class="cite-link" href="#([^"]+)"', html, flags=re.S):
            status["cite_links"] += 1
            sup_tag, target = match.group(1), match.group(2)
            if target not in ids:
                status["missing_targets"] += 1
            if not re.search(r'id="ch\d{2}-cite-\d+"', sup_tag):
                status["missing_sup_ids"] += 1
    js_path = root / "shared" / "js" / "chapter.js"
    if js_path.exists():
        js = js_path.read_text(encoding="utf-8", errors="ignore")
        status["backlink_latest"] = "backLink.href = '#' + backId" in js and "backLink.onclick" in js
    return status


RAW_SUMMARY_RE = re.compile(
    r"(이 자료는|이 항목은|S9에서 중요한 점|This paper\b|This work\b|This entry\b|"
    r"It uses\b|Training uses\b|The system is trained\b|Reports \d|Shows large gains)",
    re.I,
)

GENERIC_BOILERPLATE_RE = re.compile(
    r"(공개 benchmark와 실제 제조 현장 사이에는 여전히 세 가지 간극|"
    r"첫 실험 셀을 고른 뒤, 사람 작업자의 동작 영상|"
    r"same SKU, same fixture, same lighting|"
    r"first experimental cell.*same task id|"
    r"공정 변수를 학습 가능한 형태로 남기는 것이다|"
    r"라는 구체 시나리오를 보면|"
    r"learned policy가 모든 것을 결정하지 않는다|"
    r"실패가 replay set으로 들어가고|"
    r"모델 이름이 아니라 관측 단위다|"
    r"VLA 하나를 고르는 문제가 아니다|"
    r"The point is not the model name but the unit of observation|"
    r"Large-data driven manipulation is not just choosing a VLA)",
    re.I,
)


def normalize_paragraph(text):
    text = re.sub(r"\[[^\]\n]{1,120},\s*(?:19|20)\d{2}[a-z]?\]", "[CIT]", text)
    text = re.sub(r"https?://\S+", "URL", text)
    text = re.sub(r"\b(?:19|20)\d{2}[a-z]?\b", "YEAR", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "N", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def repeated_paragraph_hits(chapter_bodies):
    hits = []
    seen = {}
    for rel, body in chapter_bodies:
        for para in re.split(r"\n\s*\n", body):
            stripped = " ".join(para.split())
            if rough_word_count(stripped) < 45:
                continue
            if stripped.startswith(("#", ">", "- ", "1. ", "![", "|")):
                continue
            norm = normalize_paragraph(stripped)
            if len(norm) < 120:
                continue
            seen.setdefault(norm, []).append(rel)
    for norm, rels in seen.items():
        unique_rels = sorted(set(str(r) for r in rels))
        if len(rels) >= 3 or len(unique_rels) >= 2:
            hits.append((len(rels), unique_rels[:6], norm[:180]))
    hits.sort(reverse=True, key=lambda item: item[0])
    return hits


def visual_pacing(body):
    lines = body.splitlines()
    visual_lines = []
    figure_lines = []
    table_active = False
    for idx, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("!["):
            visual_lines.append(idx)
            figure_lines.append(idx)
        if stripped.startswith("|"):
            if not table_active:
                visual_lines.append(idx)
                table_active = True
        else:
            table_active = False

    def segment_words(start, end):
        segment = "\n".join(
            line for line in lines[start:end]
            if not line.lstrip().startswith(("![", "|", "*그림", "*Figure"))
        )
        return rough_word_count(segment)

    total_lines = max(1, len(lines))
    total_words = segment_words(0, len(lines))
    last_visual = visual_lines[-1] if visual_lines else 0
    last_figure = figure_lines[-1] if figure_lines else 0
    cutpoints = [0] + visual_lines + [len(lines)]
    gaps = [segment_words(a, b) for a, b in zip(cutpoints, cutpoints[1:])]
    return {
        "total_words": total_words,
        "last_visual_pct": round(100 * last_visual / total_lines) if last_visual else 0,
        "last_figure_pct": round(100 * last_figure / total_lines) if last_figure else 0,
        "words_after_last_visual": segment_words(last_visual, len(lines)) if last_visual else total_words,
        "words_after_last_figure": segment_words(last_figure, len(lines)) if last_figure else total_words,
        "max_words_between_visuals": max(gaps) if gaps else total_words,
    }


def paragraph_lengths(body):
    values = []
    for para in re.split(r"\n\s*\n", body):
        stripped = para.strip()
        if not stripped:
            continue
        if stripped.startswith(("---", "#", ">", "- ", "1. ", "![", "|")):
            continue
        values.append(rough_word_count(stripped))
    return values


def referenced_local_figure_count(body):
    return len(re.findall(r"!\[[^\]]*\]\(\.\./\.\./assets/figures/[^)]+\)", body))


def update_visual_metrics(metrics, pacing):
    last_visual_pct = pacing["last_visual_pct"]
    words_after_last_figure = pacing["words_after_last_figure"]
    max_words_between_visuals = pacing["max_words_between_visuals"]
    metrics.min_last_visual_pct = (
        last_visual_pct
        if metrics.min_last_visual_pct is None
        else min(metrics.min_last_visual_pct, last_visual_pct)
    )
    metrics.max_words_after_last_figure = (
        words_after_last_figure
        if metrics.max_words_after_last_figure is None
        else max(metrics.max_words_after_last_figure, words_after_last_figure)
    )
    metrics.max_words_between_visuals = (
        max_words_between_visuals
        if metrics.max_words_between_visuals is None
        else max(metrics.max_words_between_visuals, max_words_between_visuals)
    )
    if (
        last_visual_pct < 100 * FULL_PROFILE["late_visual_fraction"]
        or words_after_last_figure > FULL_PROFILE["max_learning_aid_gap_words"]
        or max_words_between_visuals > FULL_PROFILE["max_learning_aid_gap_words"]
    ):
        metrics.visual_pacing_failures += 1

def collect_metrics(root, slug, run_validate=True):
    survey_dir = root / "surveys" / slug
    cfg = load_json(survey_dir / "survey.json") or {}
    metrics = Metrics(slug=slug, chapters=len(chapter_nums(cfg)))
    research_meta = research_metadata_counts(survey_dir, metrics.chapters)
    metrics.research_blank_titles = research_meta["blank_titles"]
    metrics.research_duplicate_titles = research_meta["duplicate_titles"]
    metrics.research_stale_hints = research_meta["stale_hints"]

    ref_count = 0
    linked_count = 0
    chapter_bodies = []
    for lang in ("ko", "en"):
        for md_path in sorted((survey_dir / "book" / lang).glob("ch*.md")):
            text = md_path.read_text(encoding="utf-8", errors="ignore")
            body, _refs_body = split_body_refs(text)
            words = rough_word_count(body)
            if lang == "ko":
                metrics.ko_words += words
            else:
                metrics.en_words += words
            chapter_bodies.append((md_path.relative_to(survey_dir), body))
            refs, linked = reference_entries(text)
            ref_count += refs
            linked_count += linked
            metrics.figure_md += len(re.findall(r"^!\[", text, flags=re.M))
            metrics.learning_blocks += int(
                "이 장을 읽고 나면" in body
                or "이 챕터를 읽고 나면" in body
                or "학습 목표" in body
                or "After reading this chapter" in body
                or "By the end of this chapter" in body
                or "Learning objectives" in body
            )
            metrics.table_lines += len(re.findall(r"^\|.*\|$", body, flags=re.M))
            metrics.raw_summary_hits += len(RAW_SUMMARY_RE.findall(body))
            metrics.generic_boilerplate_hits += len(GENERIC_BOILERPLATE_RE.findall(body))
            metrics.referenced_figures += referenced_local_figure_count(body)
            update_visual_metrics(metrics, visual_pacing(body))
            para_values = paragraph_lengths(body)
            if para_values:
                existing = getattr(metrics, "_para_values", [])
                existing.extend(para_values)
                setattr(metrics, "_para_values", existing)
    para_values = getattr(metrics, "_para_values", [])
    if para_values:
        metrics.avg_para_words = round(sum(para_values) / len(para_values), 1)
        metrics.p90_para_words = sorted(para_values)[int(0.9 * (len(para_values) - 1))]
        delattr(metrics, "_para_values")
    metrics.repeated_paragraph_groups = len(repeated_paragraph_hits(chapter_bodies))

    metrics.refs = ref_count
    metrics.ref_link_pct = round(100 * linked_count / ref_count, 1) if ref_count else None

    metrics.body_prose_citations = count_body_prose_author_year(survey_dir)
    citation_ux = rendered_citation_ux(root, survey_dir)
    metrics.rendered_cite_links = citation_ux["cite_links"]
    metrics.cite_targets_missing = citation_ux["missing_targets"]
    metrics.cite_sup_ids_missing = citation_ux["missing_sup_ids"]
    metrics.backlink_latest = citation_ux["backlink_latest"]

    fig_dir = survey_dir / "assets" / "figures"
    metrics.figure_files = len([p for p in fig_dir.glob("*") if p.is_file()]) if fig_dir.exists() else 0
    metrics.manifest_items = manifest_count(load_json(survey_dir / "_workspace" / "04_image_manifest.json"))

    papers = load_json(survey_dir / "_research" / "papers.json")
    if isinstance(papers, list):
        metrics.research_papers = len(papers)
        rich = [
            p for p in papers
            if p.get("method_summary") and str(p.get("method_summary")).strip()
            and p.get("provenance") != "bibtex_backfill"
        ]
        metrics.rich_pct = round(100 * len(rich) / len(papers), 1) if papers else 0.0

    for role, attr in (("foundations", "research_foundations"), ("frontier", "research_frontier")):
        shard = load_json(survey_dir / "_research" / f"papers_{role}.json")
        if isinstance(shard, dict):
            shard = shard.get("papers") or shard.get("items")
        if isinstance(shard, list):
            setattr(metrics, attr, len(shard))

    refs = load_json(survey_dir / "_refs_extracted.json")
    if isinstance(refs, list):
        metrics.refs_extracted = len(refs)
        metrics.bibtex_pct = round(100 * sum(1 for x in refs if x.get("bibtex_key")) / len(refs), 1) if refs else 0.0
        metrics.id_pct = round(100 * sum(1 for x in refs if x.get("arxiv_id") or x.get("doi") or x.get("nature_id")) / len(refs), 1) if refs else 0.0
        metrics.verified_pct = verified_percentage(refs)
        mix = ref_source_mix(refs)
        metrics.academic_refs = mix["academic"]
        metrics.arxiv_refs = mix["arxiv"]
        metrics.doi_refs = mix["doi"]
        metrics.nvidia_official_refs = mix["nvidia_official"]

    qa_path = survey_dir / "_qa_report.md"
    if qa_path.exists():
        lines = [line.strip() for line in qa_path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
        metrics.qa_final = lines[-1] if lines else ""

    if run_validate:
        proc = subprocess.run(
            ["python3", "build.py", "--validate", slug],
            cwd=root,
            text=True,
            capture_output=True,
        )
        text = proc.stdout + proc.stderr
        metrics.validate_rc = proc.returncode
        metrics.validate_errors = len(re.findall(r"ERRORS \(|\bERROR:", text))
        warning_match = re.search(r"WARNINGS \((\d+)\)", text)
        metrics.validate_warnings = int(warning_match.group(1)) if warning_match else 0

    return metrics


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def build_baseline(metrics_list):
    return {
        "ko_words_per_chapter_median": median([m.ko_words_per_chapter for m in metrics_list if m.chapters]),
        "en_words_per_chapter_median": median([m.en_words_per_chapter for m in metrics_list if m.chapters]),
        "figures_per_chapter_median": median([m.figures_per_chapter for m in metrics_list if m.chapters]),
        "ref_link_pct_best_practice": 100.0,
        "rich_pct_best_practice": 90.0,
        "id_pct_median": median([m.id_pct for m in metrics_list]),
        "verified_pct_median": median([m.verified_pct for m in metrics_list]),
    }


def fmt(value, digits=1):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def markdown_table(metrics_list):
    lines = [
        "| Survey | Ch | KO/ch | EN/ch | Refs | Academic refs | arXiv | DOI | Ref links | Fig/ch | Papers | Rich | IDs | Verified | Validate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for m in metrics_list:
        validate = f"rc={m.validate_rc}, warn={m.validate_warnings}"
        lines.append(
            f"| `{m.slug}` | {m.chapters} | {fmt(m.ko_words_per_chapter,0)} | "
            f"{fmt(m.en_words_per_chapter,0)} | {m.refs} | {fmt(m.academic_refs,0)} | "
            f"{fmt(m.arxiv_refs,0)} | {fmt(m.doi_refs,0)} | {fmt(m.ref_link_pct)}% | "
            f"{fmt(m.figures_per_chapter)} | {fmt(m.research_papers,0)} | {fmt(m.rich_pct)}% | "
            f"{fmt(m.id_pct)}% | {fmt(m.verified_pct)}% | {validate} |"
        )
    return "\n".join(lines)


def compare_target(target, baseline, scope):
    if scope == "auto":
        scope = "mini" if target.chapters and target.chapters <= 6 else "full"
    profile = load_profile(scope)
    min_words = profile["min_words_per_language_chapter"]
    target_corpus = max(profile["corpus_floor_base"], profile["corpus_floor_per_chapter"] * target.chapters)
    min_foundations = profile["min_research_shard_entries"]
    min_frontier = profile["min_research_shard_entries"]
    checks = []

    def add(name, value, threshold, passed, note=""):
        checks.append({
            "name": name,
            "value": value,
            "threshold": threshold,
            "passed": bool(passed),
            "note": note,
        })

    add("KO structured-depth words/chapter", target.ko_words_per_chapter, min_words, target.ko_words_per_chapter >= min_words,
        f"scope={scope}; threshold from quality_profiles.yaml")
    add("EN structured-depth words/chapter", target.en_words_per_chapter, min_words, target.en_words_per_chapter >= min_words,
        f"scope={scope}; threshold from quality_profiles.yaml")
    add("Reference hyperlink coverage", target.ref_link_pct, 100.0, target.ref_link_pct == 100.0)
    add("Body prose author-year citations", target.body_prose_citations, 0, target.body_prose_citations == 0)
    add("Rendered citation links", target.rendered_cite_links, ">0", target.rendered_cite_links > 0)
    add("Citation href target misses", target.cite_targets_missing, 0, target.cite_targets_missing == 0)
    add("Citation sup id misses", target.cite_sup_ids_missing, 0, target.cite_sup_ids_missing == 0)
    add("Reference backlink retargets latest citation", str(target.backlink_latest), "True", target.backlink_latest)
    min_figures = float(profile["min_figures_per_chapter"])
    add("Figure files/chapter", target.figures_per_chapter, min_figures, target.figures_per_chapter >= min_figures)
    if target.rich_pct is not None:
        rich_floor = float(profile["min_research_rich_pct"])
        add("Research rich metadata", target.rich_pct, rich_floor, target.rich_pct >= rich_floor)
    else:
        add("Research rich metadata", None, profile["min_research_rich_pct"], False, "_research/papers.json missing or invalid")
    add("Research blank titles", target.research_blank_titles, 0, target.research_blank_titles == 0)
    add("Research duplicate exact titles", target.research_duplicate_titles, 0, target.research_duplicate_titles == 0)
    add("Research stale chapter hints", target.research_stale_hints, 0, target.research_stale_hints == 0,
        "chapter_hint values must match the current survey chapter count before writing starts")
    if scope == "full":
        add("Research corpus size", target.research_papers, target_corpus,
            target.research_papers is not None and target.research_papers >= target_corpus,
            "threshold from quality_profiles.yaml; search saturation still required")
        academic_floor = max(profile["min_academic_refs_base"], profile["min_academic_refs_per_chapter"] * target.chapters)
        add("Academic reference count", target.academic_refs, academic_floor,
            target.academic_refs is not None and target.academic_refs >= academic_floor,
            "counts arXiv/DOI/conference/journal links inside reference text")
        primary_floor = max(profile["min_primary_refs_base"], profile["min_primary_refs_per_chapter"] * target.chapters)
        add("arXiv or DOI reference count",
            (target.arxiv_refs or 0) + (target.doi_refs or 0)
            if target.arxiv_refs is not None and target.doi_refs is not None else None,
            primary_floor,
            target.arxiv_refs is not None and target.doi_refs is not None
            and (target.arxiv_refs + target.doi_refs) >= primary_floor,
            "full paper-heavy survey should be grounded in many primary papers, not only blogs")
        add("Foundations shard size", target.research_foundations, min_foundations,
            target.research_foundations is not None and target.research_foundations >= min_foundations,
            "requires a non-empty foundations shard; topic balance comes from search_protocol.md")
        add("Frontier shard size", target.research_frontier, min_frontier,
            target.research_frontier is not None and target.research_frontier >= min_frontier,
            "requires a non-empty frontier shard; topic balance comes from search_protocol.md")
    required_learning = target.chapters * 2
    add("Learning blocks", target.learning_blocks, required_learning,
        target.learning_blocks >= required_learning,
        "KO and EN chapter each need reader-facing learning outcomes")
    add("Markdown tables", target.table_lines, required_learning * 2,
        target.table_lines >= required_learning * 2,
        "at least one real markdown table per KO/EN chapter")
    add("Raw research-summary leakage", target.raw_summary_hits, 0,
        target.raw_summary_hits == 0,
        "writer must rewrite method_summary text into narrative prose")
    add("Repeated generic boilerplate", target.generic_boilerplate_hits, 0,
        target.generic_boilerplate_hits == 0,
        "chapter-specific prose required")
    add("Repeated normalized paragraph groups", target.repeated_paragraph_groups, 0,
        target.repeated_paragraph_groups == 0,
        "same paragraph structure across chapters indicates generated filler, even if citations differ")
    add("Referenced figures/chapter/lang", target.referenced_figures / required_learning if required_learning else 0,
        3.0,
        required_learning > 0 and target.referenced_figures / required_learning >= 3.0,
        "counts figures actually referenced in markdown, not unused assets")
    add("Visual pacing failures", target.visual_pacing_failures, 0,
        target.visual_pacing_failures == 0,
        "thresholds from quality_profiles.yaml")
    visual_pct = round(100 * profile["late_visual_fraction"])
    visual_gap = profile["max_learning_aid_gap_words"]
    add("Minimum last visual position", target.min_last_visual_pct, f">={visual_pct}%",
        target.min_last_visual_pct is not None and target.min_last_visual_pct >= visual_pct,
        "prevents first-half image clustering followed by wall text")
    add("Max words after last figure", target.max_words_after_last_figure, f"<={visual_gap}",
        target.max_words_after_last_figure is not None and target.max_words_after_last_figure <= visual_gap,
        "late chapter sections need figure/table support, not only prose")
    add("Max words between visuals", target.max_words_between_visuals, f"<={visual_gap}",
        target.max_words_between_visuals is not None and target.max_words_between_visuals <= visual_gap,
        "tables count as visual aids for pacing; unused assets do not")
    add("Paragraph reading hygiene p90", target.p90_para_words, 150,
        target.p90_para_words is not None and target.p90_para_words <= 150,
        "long paragraph walls fail readability even when word count passes")

    if target.validate_rc is not None:
        add("Validator", target.validate_rc, 0, target.validate_rc == 0,
            f"warnings={target.validate_warnings}, error_markers={target.validate_errors}")
    if target.verified_pct is not None:
        add("Verification coverage", target.verified_pct, 90.0, target.verified_pct >= 90.0,
            "below 90 requires source-type ceiling explanation in QA")
    if baseline.get("figures_per_chapter_median") is not None:
        threshold = min(3.0, baseline["figures_per_chapter_median"])
        add("Figure density vs baseline floor", target.figures_per_chapter, threshold, target.figures_per_chapter >= threshold)

    return checks


def comparison_markdown(target, baselines, baseline_stats, checks):
    verdict = "PASS" if all(c["passed"] for c in checks) else "BLOCKED"
    lines = [
        f"# Survey Quality Comparison — {target.slug}",
        "",
        f"## Verdict: {verdict}",
        "",
        "This report compares the target survey against Terry's existing survey corpus and the current `$survey` quality gates.",
        "",
        "## Target Metrics",
        "",
        markdown_table([target]),
        "",
        "## Research Metadata Hygiene",
        "",
        f"- Blank research titles: {target.research_blank_titles}",
        f"- Duplicate exact research titles: {target.research_duplicate_titles}",
        f"- Stale out-of-range chapter hints: {target.research_stale_hints}",
        "",
        "## Citation UX",
        "",
        f"- Body prose author-year citations: {target.body_prose_citations}",
        f"- Rendered cite links: {target.rendered_cite_links}",
        f"- Missing citation href targets: {target.cite_targets_missing}",
        f"- Citation sup elements without stable ids: {target.cite_sup_ids_missing}",
        f"- Backlink retargets latest clicked citation: {target.backlink_latest}",
        "",
        "## Reader-Learning Hygiene",
        "",
        f"- Learning blocks: {target.learning_blocks}",
        f"- Markdown table lines: {target.table_lines}",
        f"- Raw research-summary leakage hits: {target.raw_summary_hits}",
        f"- Repeated generic boilerplate hits: {target.generic_boilerplate_hits}",
        f"- Repeated normalized paragraph groups: {target.repeated_paragraph_groups}",
        f"- Referenced local figures: {target.referenced_figures}",
        f"- Visual pacing failures: {target.visual_pacing_failures}",
        f"- Min last visual position: {fmt(target.min_last_visual_pct,0)}%",
        f"- Max words after last figure: {fmt(target.max_words_after_last_figure,0)}",
        f"- Max words between visuals: {fmt(target.max_words_between_visuals,0)}",
        f"- Paragraph words avg/p90: {fmt(target.avg_para_words)} / {fmt(target.p90_para_words,0)}",
        "",
        "## Baseline Corpus",
        "",
        markdown_table(baselines),
        "",
        "## Baseline Summary",
        "",
        f"- Median KO structured-depth words/chapter: {fmt(baseline_stats.get('ko_words_per_chapter_median'),0)}",
        f"- Median EN structured-depth words/chapter: {fmt(baseline_stats.get('en_words_per_chapter_median'),0)}",
        f"- Median figure files/chapter: {fmt(baseline_stats.get('figures_per_chapter_median'))}",
        f"- Median ID coverage: {fmt(baseline_stats.get('id_pct_median'))}%",
        f"- Median verification coverage: {fmt(baseline_stats.get('verified_pct_median'))}%",
        "",
        "## Parity Checks",
        "",
        "| Check | Target | Required | Result | Note |",
        "|---|---:|---:|---|---|",
    ]
    for c in checks:
        result = "PASS" if c["passed"] else "FAIL"
        lines.append(f"| {c['name']} | {fmt(c['value'])} | {fmt(c['threshold'])} | {result} | {c['note']} |")
    lines.extend([
        "",
        "## Rule",
        "",
        "A new Codex-generated survey should be equal to or better than the existing corpus after normalizing by chapter count. If a metric is below baseline, `_qa_report.md` must explain the exception and list remediation before release.",
    ])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root")
    parser.add_argument("--all", action="store_true", help="print benchmark table for every survey")
    parser.add_argument("--target", help="survey slug to compare against baselines")
    parser.add_argument("--baseline", action="append", help="baseline slug; repeatable. Defaults to release baseline set")
    parser.add_argument("--scope", choices=["auto", "full", "mini"], default="auto")
    parser.add_argument("--exhaustive", action="store_true", help="explicitly request Claude-parity exhaustive full-survey gates; currently identical to --scope full")
    parser.add_argument("--write", action="store_true", help="write _quality_comparison.md for --target")
    parser.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    args = parser.parse_args(argv)

    root = repo_root(args.repo_root)
    slugs = survey_slugs(root)

    if args.all:
        metrics = [collect_metrics(root, slug) for slug in slugs]
        if args.json:
            print(json.dumps([m.__dict__ for m in metrics], indent=2, ensure_ascii=False))
        else:
            print(markdown_table(metrics))
        return 0

    if not args.target:
        parser.error("pass --all or --target <slug>")
    if args.target not in slugs:
        raise SystemExit(f"ERROR: target survey not found: {args.target}")

    baseline_slugs = args.baseline or [slug for slug in RELEASE_BASELINES if slug in slugs and slug != args.target]
    if not baseline_slugs:
        baseline_slugs = [slug for slug in slugs if slug != args.target]
    baselines = [collect_metrics(root, slug) for slug in baseline_slugs]
    target = collect_metrics(root, args.target)
    baseline_stats = build_baseline(baselines)
    checks = compare_target(target, baseline_stats, args.scope)

    if args.json:
        payload = {
            "target": target.__dict__,
            "baselines": [m.__dict__ for m in baselines],
            "baseline_stats": baseline_stats,
            "checks": checks,
            "passed": all(c["passed"] for c in checks),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        report = comparison_markdown(target, baselines, baseline_stats, checks)
        print(report, end="")
        if args.write:
            out = root / "surveys" / args.target / "_quality_comparison.md"
            out.write_text(report, encoding="utf-8")
            print(f"\nWROTE {out}")

    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
