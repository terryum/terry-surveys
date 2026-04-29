#!/usr/bin/env python3
"""Merge deep-researcher shard files into canonical papers.json.

Supports N shards (2-way foundations/frontier OR 3-way foundations/frontier/video,
or any other combination). Shard files are auto-discovered as papers_*.json in
_research/. The old hardcoded 2-shard interface is preserved as a fallback.

Usage:
  python3 merge_research_shards.py <survey-slug>

Reads (auto-discovered):
  surveys/<slug>/_research/papers_foundations.json
  surveys/<slug>/_research/papers_frontier.json
  surveys/<slug>/_research/papers_video.json        (if present — 3-way)
  … any other papers_*.json files
  EXCLUDED: papers_ch<N>.json (chapter-view artifacts produced downstream by
  book-writer / chapter-extractor — these are per-chapter subsets of the
  canonical corpus, not researcher shards, and merging them would double-count.)

Writes:
  surveys/<slug>/_research/papers.json          (canonical — deduped + merged)
  surveys/<slug>/_research/groups.md            (concatenated shard groups)
  surveys/<slug>/_research/timeline.md          (concatenated shard timelines)
  surveys/<slug>/_research/_merge_report.md     (dedup stats + conflict log)

Dedup order of precedence:
  1. arxiv_id (exact match, lowercase, versionless: 2412.00123 == 2412.00123v2)
  2. doi (exact match, lowercase)
  3. normalized_title (lowercase, alphanumeric-only, whitespace-collapsed)

On collision:
  - tags + chapter_hint: UNION
  - primary_verified: OR
  - method_summary: longer wins; shorter preserved as method_summary_alt
  - first encountered owner wins for `owner` field (tie-break: alphabetical)
  - quantitative_results: longer wins; alt stored as quantitative_results_alt

Exit non-zero if all shards are missing or JSON-invalid.
"""

import json
import re
import sys
from pathlib import Path


MONOREPO = Path(__file__).resolve().parents[4]  # .claude/skills/survey/scripts/ → repo root


def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_arxiv(arxiv_id):
    if not arxiv_id:
        return None
    s = str(arxiv_id).lower().strip()
    # Strip version suffix: 2412.00123v2 → 2412.00123
    s = re.sub(r"v\d+$", "", s)
    return s or None


def normalize_doi(doi):
    if not doi:
        return None
    s = str(doi).lower().strip()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    return s or None


def dedup_key(entry):
    """Return (key_type, key_value) preferring arxiv_id > doi > title."""
    ax = normalize_arxiv(entry.get("arxiv_id"))
    if ax:
        return ("arxiv", ax)
    doi = normalize_doi(entry.get("doi"))
    if doi:
        return ("doi", doi)
    nt = normalize_title(entry.get("title", ""))
    if nt:
        return ("title", nt)
    # Last-resort fallback: bibtex_key itself (should never happen if entry is valid)
    return ("bibtex", entry.get("bibtex_key", ""))


def union_list(a, b):
    """Union of two list-likes, preserving order of first occurrence."""
    out = []
    seen = set()
    for src in (a or [], b or []):
        items = src if isinstance(src, list) else [src]
        for item in items:
            key = json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def merge_entries(existing, incoming, conflicts):
    """Merge incoming into existing in-place. Returns updated existing."""
    bibtex = existing.get("bibtex_key", "?")

    # tags + chapter_hint: UNION
    if incoming.get("tags"):
        existing["tags"] = union_list(existing.get("tags"), incoming.get("tags"))
    if incoming.get("chapter_hint"):
        existing["chapter_hint"] = union_list(existing.get("chapter_hint"), incoming.get("chapter_hint"))

    # primary_verified: OR
    existing["primary_verified"] = bool(existing.get("primary_verified")) or bool(incoming.get("primary_verified"))

    # method_summary: longer wins; shorter → alt
    es = existing.get("method_summary") or ""
    ins = incoming.get("method_summary") or ""
    if ins and ins != es:
        if len(ins) > len(es):
            if es:
                existing["method_summary_alt"] = es
            existing["method_summary"] = ins
        else:
            existing["method_summary_alt"] = ins

    # quantitative_results: longer wins; shorter → alt
    eq = existing.get("quantitative_results") or ""
    inq = incoming.get("quantitative_results") or ""
    if inq and inq != eq:
        if len(inq) > len(eq):
            if eq:
                existing["quantitative_results_alt"] = eq
            existing["quantitative_results"] = inq
        else:
            existing["quantitative_results_alt"] = inq

    # Conflict detection on id/doi/bibtex_key mismatch
    for field in ("arxiv_id", "doi", "bibtex_key"):
        ev = (existing.get(field) or "").strip() if existing.get(field) else None
        iv = (incoming.get(field) or "").strip() if incoming.get(field) else None
        if ev and iv and ev.lower() != iv.lower():
            conflicts.append({
                "bibtex_key": bibtex,
                "field": field,
                "existing_owner": existing.get("owner", "?"),
                "existing_value": ev,
                "incoming_value": iv,
            })

    # Fill any blank fields from incoming (non-destructive)
    for field in ("arxiv_id", "doi", "url", "venue", "authors", "year", "group", "source_type"):
        if incoming.get(field) and not existing.get(field):
            existing[field] = incoming[field]

    return existing


def load_shard(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: {path} is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)


def concat_md(shard_names, research_dir, md_prefix, heading, output):
    """Concatenate per-shard markdown files (groups_*.md or timeline_*.md).

    Returns list of missing shard filenames so the caller can surface them in the merge report.
    """
    lines = [f"# {heading}\n"]
    missing = []
    for name in shard_names:
        path = research_dir / f"{md_prefix}_{name}.md"
        if path.exists():
            lines.append(f"\n## {name}\n")
            lines.append(path.read_text())
        else:
            missing.append(path.name)
            print(f"WARN: missing {path.name} — concat will skip this shard", file=sys.stderr)
    output.write_text("\n".join(lines))
    return missing


def main():
    if len(sys.argv) != 2:
        print("Usage: merge_research_shards.py <survey-slug>", file=sys.stderr)
        sys.exit(1)

    slug = sys.argv[1]
    research_dir = MONOREPO / "surveys" / slug / "_research"
    if not research_dir.is_dir():
        print(f"ERROR: {research_dir} not found", file=sys.stderr)
        sys.exit(1)

    # Auto-discover all shard files: papers_*.json (sorted for determinism).
    # Exclude chapter-view artifacts (papers_ch<N>.json) — those are per-chapter
    # subsets produced downstream (book-writer / chapter-extractor), not researcher shards.
    chapter_view_pat = re.compile(r"^papers_ch\d+\.json$")
    shard_paths = sorted(p for p in research_dir.glob("papers_*.json") if not chapter_view_pat.match(p.name))
    if not shard_paths:
        print(f"ERROR: no papers_*.json shards found at {research_dir}", file=sys.stderr)
        sys.exit(1)

    shard_names = [p.stem[len("papers_"):] for p in shard_paths]  # e.g. ["foundations","frontier","video"]

    canonical = {}  # dedup_key → merged entry
    key_origin = {}  # dedup_key → shard_name
    conflicts = []
    dedup_stats = {"shard_entries": 0, "duplicates": 0, "unique_entries": 0}
    per_shard_counts = {}

    all_empty = True
    for shard_label, shard_path in zip(shard_names, shard_paths):
        shard = load_shard(shard_path) or []
        if shard:
            all_empty = False
        per_shard_counts[shard_label] = 0
        for entry in shard:
            dedup_stats["shard_entries"] += 1
            entry.setdefault("owner", shard_label)
            key = dedup_key(entry)
            if key in canonical:
                dedup_stats["duplicates"] += 1
                merge_entries(canonical[key], entry, conflicts)
            else:
                canonical[key] = dict(entry)
                key_origin[key] = shard_label
                per_shard_counts[shard_label] = per_shard_counts.get(shard_label, 0) + 1

    if all_empty:
        print(f"ERROR: all shards are empty at {research_dir}", file=sys.stderr)
        sys.exit(1)

    dedup_stats["unique_entries"] = len(canonical)

    # Sort: year desc, then bibtex_key asc for stability
    merged_list = sorted(
        canonical.values(),
        key=lambda e: (-(int(e.get("year") or 0)), (e.get("bibtex_key") or "").lower()),
    )

    # Write canonical papers.json
    out_path = research_dir / "papers.json"
    out_path.write_text(json.dumps(merged_list, indent=2, ensure_ascii=False))

    # Concatenate groups + timeline markdown (N-way)
    missing_groups = concat_md(shard_names, research_dir, "groups",
              f"Research Groups — {slug}", research_dir / "groups.md")
    missing_timeline = concat_md(shard_names, research_dir, "timeline",
              f"Timeline — {slug}", research_dir / "timeline.md")
    missing_md = missing_groups + missing_timeline

    # Merge report
    report = [f"# Merge Report — {slug}\n"]
    report.append(f"- Shards merged:       {len(shard_names)} ({', '.join(shard_names)})")
    report.append(f"- Shard entries (sum): {dedup_stats['shard_entries']}")
    report.append(f"- Duplicates merged:   {dedup_stats['duplicates']}")
    report.append(f"- Unique canonical:    {dedup_stats['unique_entries']}")
    for name in shard_names:
        count = sum(1 for v in key_origin.values() if v == name)
        report.append(f"- {name} entries:    {count}")
    report.append("")

    if conflicts:
        report.append(f"## Conflicts detected ({len(conflicts)})\n")
        report.append("| bibtex_key | field | existing (owner) | incoming value |")
        report.append("|---|---|---|---|")
        for c in conflicts:
            report.append(f"| {c['bibtex_key']} | {c['field']} | {c['existing_value']} ({c['existing_owner']}) | {c['incoming_value']} |")
        report.append("")
        report.append("**Action**: qa-reviewer should verify conflicting entries against primary sources.")
    else:
        report.append("## Conflicts\n\nNone detected.")

    if missing_md:
        report.append("")
        report.append(f"## Missing Shard Artifacts ({len(missing_md)})\n")
        for fname in missing_md:
            report.append(f"- `{fname}` not found — concat skipped this shard")
        report.append("")
        report.append("**Action**: the responsible deep-researcher agent must produce these files; rerun merge afterwards.")

    (research_dir / "_merge_report.md").write_text("\n".join(report))

    # Stdout summary
    print(f"Merged: {dedup_stats['shard_entries']} shard entries → {dedup_stats['unique_entries']} canonical "
          f"({dedup_stats['duplicates']} duplicates)")
    print(f"Canonical papers.json: {out_path}")
    print(f"Merge report: {research_dir / '_merge_report.md'}")
    if conflicts:
        print(f"WARNING: {len(conflicts)} conflicts — see merge report", file=sys.stderr)
    if missing_md:
        print(f"WARNING: {len(missing_md)} missing shard md files — see merge report", file=sys.stderr)


if __name__ == "__main__":
    main()
