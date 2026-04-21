#!/usr/bin/env python3
"""One-shot: merge survey-local .bib files into the master bibtex/references.bib.

Phase 1 of the scale-ready pipeline plan. The master is supposed to be a
SUPERSET of every survey's local references. Until now it has been a subset
(15 entries vs. 255 across the three surveys). This script inverts that
relation without touching the survey-local files.

Behavior:
  - Parse master + each survey's book/references.bib.
  - For every survey entry:
      * key unseen in master         -> queue for append.
      * key in master, body matches  -> skip (already unioned).
      * key in master, body differs  -> record as CONFLICT (no auto-merge).
  - Append queued entries to master grouped by survey under a section
    header, preserving the per-entry comment line that appeared above
    it in the survey file (so chapter markers like "% ------ Ch01/Ch05 ------"
    are carried over).
  - Print a conflict report to stdout. Conflicts must be resolved manually.

Run from the repo root:

    python3 shared/scripts/union_bibtex.py            # dry-run (report only)
    python3 shared/scripts/union_bibtex.py --write    # commit the merge
"""

import argparse
import os
import re
import sys
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MASTER_PATH = os.path.join(ROOT, 'bibtex', 'references.bib')
SURVEYS_DIR = os.path.join(ROOT, 'surveys')

SURVEY_SHORT = {
    'robot-hand-tactile-sensor': 'rht',
    'snu-tactile-hand': 'snu',
    'vla-agentic-robotics': 'vla',
}


def parse_bibtex(text):
    """Return list of {key, type, body, raw, comment, start, end}.

    Walks the string, finding each `@type{key,` header, then counting
    balanced braces to locate the closing `}`. The preceding consecutive
    comment block (lines starting with '%') is captured as `comment`.
    """
    entries = []
    i = 0
    header_re = re.compile(r'@(\w+)\s*\{\s*([^\s,]+)\s*,', re.DOTALL)
    while True:
        m = header_re.search(text, i)
        if not m:
            break
        entry_start = m.start()
        etype = m.group(1)
        key = m.group(2)
        # Balance braces from the opening '{' after '@type'.
        brace_open = text.find('{', m.start())
        depth = 0
        j = brace_open
        while j < len(text):
            c = text[j]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        else:
            raise ValueError(f'Unbalanced braces for key {key} at offset {entry_start}')
        entry_end = j
        raw = text[entry_start:entry_end]
        body = text[brace_open + 1:entry_end - 1]
        # Grab any immediately-preceding comment lines (contiguous '%' lines).
        # Look backward from entry_start across newlines.
        k = entry_start
        # Skip a single trailing newline before entry
        while k > 0 and text[k - 1] == '\n':
            k -= 1
        # Collect comment block
        comment_lines = []
        while k > 0:
            # Find previous line start
            line_start = text.rfind('\n', 0, k - 1) + 1
            line = text[line_start:k].rstrip('\n')
            stripped = line.lstrip()
            if stripped.startswith('%') and not stripped.startswith('% ======'):
                # Stop at a section-divider line ('% =====' etc.) so we
                # don't absorb the master's top-of-file banner.
                comment_lines.insert(0, line)
                k = line_start
            else:
                break
        comment = '\n'.join(comment_lines).strip()
        entries.append({
            'key': key,
            'type': etype,
            'body': body,
            'raw': raw,
            'comment': comment,
            'start': entry_start,
            'end': entry_end,
        })
        i = entry_end
    return entries


def normalize_body(body):
    """Canonicalize a BibTeX entry body for equality checks.

    Drops whitespace runs, trailing commas, and quoting noise so that two
    entries with cosmetic-only differences compare equal.
    """
    # Remove comments inside body (unlikely but safe).
    s = re.sub(r'[\s]+', ' ', body)
    # Strip spaces around = , { } and around commas/braces.
    s = re.sub(r'\s*=\s*', '=', s)
    s = re.sub(r'\s*,\s*', ',', s)
    s = re.sub(r'\s*\{\s*', '{', s)
    s = re.sub(r'\s*\}\s*', '}', s)
    # Strip optional trailing comma.
    s = s.strip().rstrip(',')
    return s.lower()


def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def build_union(write=False):
    master_text = read_file(MASTER_PATH)
    master_entries = parse_bibtex(master_text)
    master_by_key = {e['key']: e for e in master_entries}

    results = {
        'master_count_before': len(master_entries),
        'surveys': {},
        'conflicts': [],
        'new_per_survey': {},
    }

    for survey_name, short in SURVEY_SHORT.items():
        bib_path = os.path.join(SURVEYS_DIR, survey_name, 'book', 'references.bib')
        if not os.path.exists(bib_path):
            continue
        survey_text = read_file(bib_path)
        survey_entries = parse_bibtex(survey_text)
        results['surveys'][survey_name] = len(survey_entries)

        new_entries = []
        for e in survey_entries:
            existing = master_by_key.get(e['key'])
            if existing is None:
                new_entries.append(e)
                # Reserve the key so later surveys in this run don't
                # re-append the same paper; they'll match against this
                # freshly-queued entry instead.
                master_by_key[e['key']] = e
            else:
                if normalize_body(existing['body']) != normalize_body(e['body']):
                    results['conflicts'].append({
                        'key': e['key'],
                        'survey': survey_name,
                        'short': short,
                        'master_body': existing['body'],
                        'survey_body': e['body'],
                    })
                # else: identical, already unioned -> skip silently.
        results['new_per_survey'][survey_name] = new_entries

    if not write:
        return results

    # Compose appended text, grouped by survey.
    appended = []
    today = date.today().isoformat()
    for survey_name, short in SURVEY_SHORT.items():
        new_entries = results['new_per_survey'].get(survey_name, [])
        if not new_entries:
            continue
        appended.append(
            '\n% ============================================================\n'
            f'% {short}: imported from surveys/{survey_name}/book/references.bib\n'
            f'% Union merge: {today} ({len(new_entries)} entries)\n'
            '% ============================================================\n'
        )
        for e in new_entries:
            # Preserve the per-entry comment if present; otherwise add a
            # minimal marker so future readers know the provenance.
            if e['comment']:
                appended.append(e['comment'] + '\n')
            else:
                appended.append(f'% ------ {short}:imported ------\n')
            appended.append(e['raw'] + '\n\n')
            # Register in master index for cross-survey dedupe within this run.
            master_by_key[e['key']] = e

    # Ensure master ends with a single newline before appending.
    if not master_text.endswith('\n'):
        master_text += '\n'
    new_master = master_text + ''.join(appended)
    with open(MASTER_PATH, 'w', encoding='utf-8') as f:
        f.write(new_master)

    results['master_count_after'] = results['master_count_before'] + sum(
        len(v) for v in results['new_per_survey'].values()
    )
    return results


def print_report(results, write):
    print('=' * 60)
    print('BibTeX master union report')
    print('=' * 60)
    print(f"master entries before: {results['master_count_before']}")
    for survey, count in results['surveys'].items():
        short = SURVEY_SHORT[survey]
        new = len(results['new_per_survey'].get(survey, []))
        print(f"  {short:4s} {survey:30s} local={count:4d}  new={new:4d}")
    if 'master_count_after' in results:
        print(f"master entries after:  {results['master_count_after']}")
    else:
        projected = results['master_count_before'] + sum(
            len(v) for v in results['new_per_survey'].values()
        )
        print(f"master entries after (projected): {projected}")

    print('-' * 60)
    if results['conflicts']:
        print(f"CONFLICTS: {len(results['conflicts'])} key(s) share a key but differ")
        for c in results['conflicts']:
            print(f"  [{c['short']}] {c['key']}")
            print(f"    master : {c['master_body'][:160].strip()!r}")
            print(f"    survey : {c['survey_body'][:160].strip()!r}")
        print('')
        print('Conflicts are NOT auto-merged. Resolve manually in the master,')
        print('then re-run. Surveys citing a conflicting key continue to use')
        print("the master's definition.")
    else:
        print('CONFLICTS: none')

    if not write:
        print('')
        print('(dry-run; re-run with --write to commit the merge)')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true', help='Commit merge to master')
    args = ap.parse_args()
    results = build_union(write=args.write)
    print_report(results, write=args.write)
    # Exit non-zero if conflicts exist so CI callers can gate on this.
    if results['conflicts']:
        sys.exit(2)


if __name__ == '__main__':
    main()
