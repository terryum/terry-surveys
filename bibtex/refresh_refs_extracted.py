#!/usr/bin/env python3
"""Refresh _refs_extracted.json with bibtex-master-derived metadata.

Each survey's `_refs_extracted.json` should follow the rich schema defined
in CLAUDE.md § 3 (ch, num, lang, text, bibtex_key, arxiv_id, doi, nature_id,
verification_status, factcheck_notes, scholar_url, scholar_status). The
agent-driven flow has fact-checker fill in the verification fields, but the
mechanical fields (ch/num/lang/text/bibtex_key/arxiv_id/doi/nature_id) can
be derived deterministically from the chapter markdown plus the master
bibtex. This script does that derivation idempotently so that the file
gets a baseline even when fact-checker has not run yet, while preserving
any verification_status / factcheck_notes / scholar_url already set.

Usage:
    python3 bibtex/refresh_refs_extracted.py <survey-slug>
    python3 bibtex/refresh_refs_extracted.py --all

Source of truth: each chapter's `## 참고문헌` (ko) and `## References` (en)
section. Output: `surveys/<slug>/_refs_extracted.json`.
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


def parse_chapter_refs(survey_dir, lang):
    """Yield (ch, num, ref_text) tuples from chapter markdown for the given lang."""
    book_dir = survey_dir / 'book' / lang
    if not book_dir.is_dir():
        return
    for fname in sorted(os.listdir(book_dir)):
        if not (fname.startswith('ch') and fname.endswith('.md')):
            continue
        ch = fname.replace('ch', '').replace('.md', '')
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
                    yield ch, m.group(1), m.group(2).strip()
            break


def extract_metadata(ref_text):
    """Pull title / first_author / year out of a citation line."""
    year_match = re.search(r'\((\d{4})\)', ref_text)
    year = year_match.group(1) if year_match else ''
    title = ''
    title_match = re.search(r'\(\d{4}\)\.\s*(.+?)(?:\.\s*\*|\.\s*$)', ref_text)
    if title_match:
        title = title_match.group(1).strip().rstrip('.')
    author_match = re.match(r'^(.+?)\s*\(', ref_text)
    first_author = author_match.group(1).split(',')[0].strip() if author_match else ''
    return title, first_author, year


def refresh_one(slug, dry_run=False):
    survey_dir = SURVEYS_DIR / slug
    if not (survey_dir / 'survey.json').is_file():
        print(f'  ERROR: surveys/{slug}/survey.json not found')
        return False

    out_path = survey_dir / '_refs_extracted.json'
    existing = []
    if out_path.is_file():
        try:
            existing = json.loads(out_path.read_text(encoding='utf-8'))
            if not isinstance(existing, list):
                existing = []
        except json.JSONDecodeError:
            existing = []

    # Index existing entries by (ch, num, lang) so we can preserve fact-checker
    # enrichments when re-running.
    preserved = {}
    for entry in existing:
        if isinstance(entry, dict):
            key = (str(entry.get('ch', '')), str(entry.get('num', '')), entry.get('lang') or 'ko')
            preserved[key] = entry

    new_entries = []
    stats = {
        'total': 0,
        'with_arxiv': 0,
        'with_doi': 0,
        'with_bibtex_key': 0,
        'preserved_verification': 0,
    }

    for lang in ('ko', 'en'):
        for ch, num, ref_text in parse_chapter_refs(survey_dir, lang):
            stats['total'] += 1
            title, first_author, year = extract_metadata(ref_text)

            ids = extract_paper_ids(ref_text)
            ids, bibtex_key = enrich_ids_via_bibtex(
                ref_text, title, first_author, year, ids
            )

            arxiv_id = ids.get('arxiv', [None])[0] if ids.get('arxiv') else None
            doi = ids.get('doi', [None])[0] if ids.get('doi') else None
            nature_id = ids.get('nature', [None])[0] if ids.get('nature') else None

            if arxiv_id:
                stats['with_arxiv'] += 1
            if doi:
                stats['with_doi'] += 1
            if bibtex_key:
                stats['with_bibtex_key'] += 1

            prior = preserved.get((ch, num, lang)) or {}
            verification_status = prior.get('verification_status')
            factcheck_notes = prior.get('factcheck_notes')
            scholar_url = prior.get('scholar_url')
            scholar_status = prior.get('scholar_status')
            if verification_status or factcheck_notes:
                stats['preserved_verification'] += 1

            entry = {
                'ch': ch,
                'num': num,
                'lang': lang,
                'text': ref_text,
                'bibtex_key': bibtex_key,
                'arxiv_id': arxiv_id,
                'doi': doi,
                'nature_id': nature_id,
                'verification_status': verification_status,
                'factcheck_notes': factcheck_notes,
                'scholar_url': scholar_url,
                'scholar_status': scholar_status,
            }
            new_entries.append(entry)

    print(f'  {slug}:')
    print(f'    total refs: {stats["total"]}')
    print(f'    with bibtex_key: {stats["with_bibtex_key"]} ({pct(stats["with_bibtex_key"], stats["total"])}%)')
    print(f'    with arxiv_id:   {stats["with_arxiv"]} ({pct(stats["with_arxiv"], stats["total"])}%)')
    print(f'    with doi:        {stats["with_doi"]} ({pct(stats["with_doi"], stats["total"])}%)')
    print(f'    preserved verification: {stats["preserved_verification"]}')

    if dry_run:
        print(f'    (dry-run — would write {len(new_entries)} entries to {out_path.name})')
        return True

    out_path.write_text(json.dumps(new_entries, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'    → wrote {len(new_entries)} entries to {out_path.relative_to(ROOT)}')
    return True


def pct(num, denom):
    return round(100 * num / denom, 1) if denom else 0.0


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

    if '--all' in flags:
        targets = list_surveys()
    else:
        positionals = [a for a in sys.argv[1:] if not a.startswith('--')]
        if not positionals:
            print(__doc__)
            sys.exit(1)
        targets = positionals

    # Pre-warm the bibtex master cache so the first survey doesn't pay extra.
    load_bibtex_master()

    print(f'Refreshing _refs_extracted.json for {len(targets)} survey(s)' +
          (' (dry-run)' if dry_run else '') + ':')
    for slug in targets:
        refresh_one(slug, dry_run=dry_run)


if __name__ == '__main__':
    main()
