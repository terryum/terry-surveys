#!/usr/bin/env python3
"""Backfill _research/papers.json from chapter refs + master bibtex.

Surveys that pre-date the multi-agent orchestration flow do not yet have
`_research/papers.json` — the rich JSON file produced by deep-researcher
agents. The downstream candidate-pool builder
(terry-papers/scripts/sync-survey-candidates.mjs) leans on this file for
method_summary, limitations, tags, group, chapter_hint. Without it, every
candidate from those surveys ends up empty-shelled and ranks near zero in
graph_proximity.

This script reconstructs a best-effort `_research/papers.json` from data
already in the repo:

  - chapter `## 참고문헌` / `## References` lines  → title/year/first_author
  - master `bibtex/references.bib`                  → bibtex_key, venue, url,
                                                       arxiv_id, doi, authors
  - existing `_refs_extracted.json`                 → chapter_hint (which
                                                       chapter cites it)

Fields that genuinely require reading the paper PDF — method_summary,
limitations, experiments, quantitative_results, group, tags — are left
null/empty and the entry is stamped with `provenance: "bibtex_backfill"`
so future deep-researcher passes know to enrich them.

Usage:
    python3 bibtex/backfill_research_metadata.py <survey-slug>
    python3 bibtex/backfill_research_metadata.py --all [--dry-run] [--force]

Idempotent. Re-running preserves any non-backfill entries already present
(deep-researcher entries take precedence; only `provenance:bibtex_backfill`
entries get refreshed).
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURVEYS_DIR = ROOT / 'surveys'
sys.path.insert(0, str(ROOT))

from bibtex.refs_index import (  # noqa: E402
    extract_paper_ids,
    enrich_ids_via_bibtex,
    load_bibtex_master,
    normalize_title,
)


def parse_authors(author_field):
    """Split a bibtex author field into a list of normalized author strings."""
    if not author_field:
        return []
    parts = [p.strip() for p in re.split(r'\s+and\s+', author_field) if p.strip()]
    out = []
    for p in parts:
        if ',' in p:
            last, first = [s.strip() for s in p.split(',', 1)]
            out.append(f'{first} {last}'.strip())
        else:
            out.append(p)
    return out


def derive_venue(bib_entry):
    """Best-effort venue/journal from bibtex entry."""
    if not bib_entry:
        return None
    for k in ('journal', 'booktitle', 'note', 'publisher'):
        v = bib_entry.get(k)
        if v:
            return v
    return None


def parse_chapter_refs(survey_dir):
    """Yield (ch_int, num, ref_text, lang) tuples from the KO+EN chapters."""
    for lang in ('ko', 'en'):
        book_dir = survey_dir / 'book' / lang
        if not book_dir.is_dir():
            continue
        for fname in sorted(os.listdir(book_dir)):
            if not (fname.startswith('ch') and fname.endswith('.md')):
                continue
            ch_str = fname.replace('ch', '').replace('.md', '')
            try:
                ch_int = int(ch_str)
            except ValueError:
                continue
            with open(book_dir / fname, encoding='utf-8') as f:
                content = f.read()
            for marker in ('## 참고문헌', '## References'):
                idx = content.find(marker)
                if idx == -1:
                    continue
                section = content[idx:]
                for line in section.split('\n'):
                    m = re.match(r'^(\d+)\.\s+(.+)', line.strip())
                    if m:
                        yield ch_int, m.group(1), m.group(2).strip(), lang
                break


def extract_metadata(ref_text):
    year_match = re.search(r'\((\d{4})\)', ref_text)
    year = int(year_match.group(1)) if year_match else None
    title = ''
    title_match = re.search(r'\(\d{4}\)\.\s*(.+?)(?:\.\s*\*|\.\s*$)', ref_text)
    if title_match:
        title = title_match.group(1).strip().rstrip('.')
    first_author = ''
    author_match = re.match(r'^(.+?)\s*\(', ref_text)
    if author_match:
        first_author = author_match.group(1).split(',')[0].strip()
    return title, first_author, year


def backfill_one(slug, force=False, dry_run=False):
    survey_dir = SURVEYS_DIR / slug
    if not (survey_dir / 'survey.json').is_file():
        print(f'  ERROR: surveys/{slug}/survey.json not found')
        return False

    research_dir = survey_dir / '_research'
    research_dir.mkdir(exist_ok=True)
    papers_path = research_dir / 'papers.json'

    existing_entries = []
    deep_researcher_entries = []
    if papers_path.is_file():
        try:
            existing_entries = json.loads(papers_path.read_text(encoding='utf-8'))
            if not isinstance(existing_entries, list):
                existing_entries = []
        except json.JSONDecodeError:
            existing_entries = []

        # Always preserve deep-researcher entries, regardless of --force.
        # `--force` only means "refresh existing bibtex_backfill entries" —
        # it must never destroy entries that an agent (deep-researcher)
        # populated with method_summary, limitations, tags, etc.
        for e in existing_entries:
            if isinstance(e, dict) and e.get('provenance') != 'bibtex_backfill':
                deep_researcher_entries.append(e)

        all_deep = (len(deep_researcher_entries) == len(existing_entries)
                    and len(existing_entries) > 0)
        if not force and all_deep:
            print(f'  {slug}: papers.json already populated by deep-researcher '
                  f'({len(existing_entries)} entries) — skipping backfill '
                  f'(use --force to refresh bibtex_backfill entries)')
            return True

    bib_lookup = load_bibtex_master()

    # Group refs by canonical_id (arxiv > doi > bibtex_key > normalized_title)
    # so the same paper cited across N chapters becomes one papers.json entry
    # whose chapter_hint accumulates all N chapters.
    grouped = {}
    occurrence_order = []
    for ch_int, num, ref_text, lang in parse_chapter_refs(survey_dir):
        title, first_author, year = extract_metadata(ref_text)
        ids = extract_paper_ids(ref_text)
        ids, bibtex_key = enrich_ids_via_bibtex(
            ref_text, title, first_author, str(year) if year else '', ids
        )

        arxiv_id = ids.get('arxiv', [None])[0] if ids.get('arxiv') else None
        doi = ids.get('doi', [None])[0] if ids.get('doi') else None
        nature_id = ids.get('nature', [None])[0] if ids.get('nature') else None

        if arxiv_id:
            canon = f'arxiv:{arxiv_id}'
        elif doi:
            canon = f'doi:{doi}'
        elif nature_id:
            canon = f'nature:{nature_id}'
        elif bibtex_key:
            canon = f'bib:{bibtex_key}'
        else:
            canon = f'title:{normalize_title(title)}'
            if canon == 'title:':
                canon = f'raw:{ref_text[:80]}'

        if canon not in grouped:
            occurrence_order.append(canon)
            bib_entry = bib_lookup['by_key'].get(bibtex_key) if bibtex_key else None
            authors = parse_authors(bib_entry.get('author', '')) if bib_entry else []
            url = bib_entry.get('url') if bib_entry else None
            venue = derive_venue(bib_entry)

            grouped[canon] = {
                'bibtex_key': bibtex_key,
                'title': (bib_entry.get('title') if bib_entry else None) or title or None,
                'authors': authors,
                'year': (int(bib_entry['year']) if (bib_entry and bib_entry.get('year', '').isdigit())
                         else year),
                'venue': venue,
                'arxiv_id': arxiv_id,
                'doi': doi,
                'nature_id': nature_id,
                'url': url,
                'method_summary': None,
                'experiments': None,
                'quantitative_results': None,
                'limitations': [],
                'group': None,
                'tags': [],
                '_chapters_set': set(),
                '_first_author': first_author,
                'provenance': 'bibtex_backfill',
            }
        grouped[canon]['_chapters_set'].add(ch_int)

    # Materialize chapter_hint as a deterministic string (e.g. "Ch3, Ch7, Ch11").
    final_entries = []
    for canon in occurrence_order:
        entry = grouped[canon]
        chs = sorted(entry.pop('_chapters_set'))
        first_author = entry.pop('_first_author')
        entry['chapter_hint'] = ', '.join(f'Ch{c}' for c in chs) if chs else None
        # If we never matched a bibtex entry, surface first_author for ranker
        # token overlap; harmless when authors[] is non-empty too.
        if not entry['authors'] and first_author:
            entry['authors'] = [first_author]
        final_entries.append(entry)

    # Merge with preserved deep-researcher entries (those win on bibtex_key
    # collision; backfill skipped for any paper deep-researcher already covered).
    if deep_researcher_entries:
        preserved_keys = {
            e.get('bibtex_key') for e in deep_researcher_entries
            if isinstance(e, dict) and e.get('bibtex_key')
        }
        preserved_arxiv = {
            e.get('arxiv_id') for e in deep_researcher_entries
            if isinstance(e, dict) and e.get('arxiv_id')
        }
        preserved_doi = {
            e.get('doi') for e in deep_researcher_entries
            if isinstance(e, dict) and e.get('doi')
        }
        filtered = []
        for e in final_entries:
            if e.get('bibtex_key') and e['bibtex_key'] in preserved_keys:
                continue
            if e.get('arxiv_id') and e['arxiv_id'] in preserved_arxiv:
                continue
            if e.get('doi') and e['doi'] in preserved_doi:
                continue
            filtered.append(e)
        merged = list(deep_researcher_entries) + filtered
    else:
        merged = final_entries

    stats = {
        'total': len(merged),
        'backfilled': len(final_entries),
        'preserved': len(deep_researcher_entries),
        'with_bibtex_key': sum(1 for e in merged if e.get('bibtex_key')),
        'with_arxiv': sum(1 for e in merged if e.get('arxiv_id')),
        'with_doi': sum(1 for e in merged if e.get('doi')),
        'with_method_summary': sum(1 for e in merged if e.get('method_summary')),
    }

    print(f'  {slug}:')
    print(f'    total entries:        {stats["total"]} '
          f'(backfilled {stats["backfilled"]}, preserved deep-researcher {stats["preserved"]})')
    print(f'    with bibtex_key:      {stats["with_bibtex_key"]}')
    print(f'    with arxiv_id:        {stats["with_arxiv"]}')
    print(f'    with doi:             {stats["with_doi"]}')
    print(f'    with method_summary:  {stats["with_method_summary"]} '
          f'({stats["with_method_summary"]}/{stats["total"]} → '
          f'{round(100 * stats["with_method_summary"] / max(stats["total"], 1), 1)}%)')

    if dry_run:
        print(f'    (dry-run — would write {stats["total"]} entries to _research/papers.json)')
        return True

    papers_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8')
    print(f'    → wrote {papers_path.relative_to(ROOT)}')
    return True


def list_surveys():
    return sorted(
        d for d in os.listdir(SURVEYS_DIR)
        if (SURVEYS_DIR / d / 'survey.json').is_file()
    )


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    flags = [a for a in sys.argv[1:] if a.startswith('--')]
    dry_run = '--dry-run' in flags
    force = '--force' in flags

    if '--all' in flags:
        targets = list_surveys()
    else:
        positionals = [a for a in sys.argv[1:] if not a.startswith('--')]
        if not positionals:
            print(__doc__)
            sys.exit(1)
        targets = positionals

    load_bibtex_master()  # warm cache

    print(f'Backfilling _research/papers.json for {len(targets)} survey(s)' +
          (' (dry-run)' if dry_run else '') +
          (' [--force will overwrite bibtex_backfill entries]' if force else '') + ':')
    for slug in targets:
        backfill_one(slug, force=force, dry_run=dry_run)


if __name__ == '__main__':
    main()
