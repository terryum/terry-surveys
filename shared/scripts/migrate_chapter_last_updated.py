#!/usr/bin/env python3
"""One-shot: add per-chapter `last_updated` to survey.json.

Reads each survey's `book/ko/chNN.md` frontmatter to pick up the
canonical last_updated for that chapter. Falls back to the survey-
level `dates.last_updated` when the chapter frontmatter is missing.

Run from the repo root:

    python3 shared/scripts/migrate_chapter_last_updated.py            # dry-run
    python3 shared/scripts/migrate_chapter_last_updated.py --write    # commit
"""

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SURVEYS_DIR = os.path.join(ROOT, 'surveys')


def chapter_date(survey_dir, ch_num, fallback):
    """Return the `last_updated` stamp from ch<num>.md frontmatter, or fallback."""
    candidate = os.path.join(survey_dir, 'book', 'ko', f'ch{ch_num:02d}.md')
    if not os.path.isfile(candidate):
        candidate = os.path.join(survey_dir, 'book', 'en', f'ch{ch_num:02d}.md')
    if not os.path.isfile(candidate):
        return fallback
    with open(candidate, 'r', encoding='utf-8') as f:
        text = f.read()
    if not text.startswith('---'):
        return fallback
    end = text.find('\n---', 3)
    if end == -1:
        return fallback
    for line in text[3:end].splitlines():
        m = re.match(r'\s*last_updated\s*:\s*["\']?(\d{4}-\d{2}-\d{2})', line)
        if m:
            return m.group(1)
    return fallback


def migrate(survey_dir, write=False):
    cfg_path = os.path.join(survey_dir, 'survey.json')
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    fallback = cfg.get('dates', {}).get('last_updated', '2026-01-01')
    changes = 0
    for part in cfg.get('parts', []):
        for ch in part.get('chapters', []):
            if 'last_updated' in ch:
                continue
            ch['last_updated'] = chapter_date(survey_dir, ch['num'], fallback)
            changes += 1
    if write and changes:
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.write('\n')
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    total = 0
    for name in sorted(os.listdir(SURVEYS_DIR)):
        sd = os.path.join(SURVEYS_DIR, name)
        if not os.path.isfile(os.path.join(sd, 'survey.json')):
            continue
        changes = migrate(sd, write=args.write)
        print(f'{name}: {changes} chapter(s) annotated')
        total += changes
    print(f'total: {total}')
    if not args.write:
        print('(dry-run; pass --write to commit)')


if __name__ == '__main__':
    main()
