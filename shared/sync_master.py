#!/usr/bin/env python3
"""Regenerate per-survey references.bib and glossary.md from monorepo masters.

Two one-shot commands exposed via build.py:

  build.py --sync-bibtex    <survey-name>
  build.py --sync-glossary  <survey-name>

Both treat the master (bibtex/references.bib / glossary/master_{ko,en}.md)
as the source of truth and rewrite the survey-local file as a clean subset.
This is how "fix the master once, every survey snaps into place" works
after Phase 1 made the master a proper superset.

sync_bibtex:
  1. Extract every `[Author, Year]` / `[Author et al., Year]` / `[A & B, Year]`
     citation from the survey's chapters (ko + en).
  2. Map each (surname, year) pair to master keys. Disambiguate using the
     survey's current local .bib when multiple master entries match.
  3. Union with the current local .bib's key set (nothing is silently
     dropped; legacy keys are preserved with a warning).
  4. Rewrite book/references.bib with master's canonical entry bodies,
     grouped alphabetically, preserving a single-line provenance comment
     per entry.

sync_glossary:
  1. For each lang, read master_<lang>.md into {head: raw_line}.
  2. For each master term, scan the survey's ko or en chapters for the
     bolded primary name. Record the chapters where it appears.
  3. Regenerate book/<lang>/glossary.md as master's ordered subset
     (only terms actually cited), copying the master entry and
     appending `(Ch N, Ch M)` chapter refs.
"""

import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SURVEYS_DIR = os.path.join(ROOT, 'surveys')
MASTER_BIB = os.path.join(ROOT, 'bibtex', 'references.bib')
GLOSSARY_DIR = os.path.join(ROOT, 'glossary')


# --------------------------------------------------------------------
# Shared parsing helpers
# --------------------------------------------------------------------

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def parse_bibtex(text):
    """Return list of {key, raw, body}. Preserves entry brace content."""
    entries = []
    i = 0
    header_re = re.compile(r'@(\w+)\s*\{\s*([^\s,]+)\s*,', re.DOTALL)
    while True:
        m = header_re.search(text, i)
        if not m:
            break
        start = m.start()
        key = m.group(2)
        brace_open = text.find('{', m.start())
        depth = 0
        j = brace_open
        while j < len(text):
            if text[j] == '{':
                depth += 1
            elif text[j] == '}':
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        raw = text[start:j]
        body = text[brace_open + 1:j - 1]
        entries.append({'key': key, 'raw': raw, 'body': body})
        i = j
    return entries


def master_by_key():
    return {e['key']: e for e in parse_bibtex(read(MASTER_BIB))}


def parse_fields(body):
    """Parse a BibTeX entry body into {field_name: value}.

    Handles nested braces inside field values (LaTeX escapes like
    `{\~a}` would otherwise truncate a regex-only parse).
    Expects the body to START with the entry key followed by a comma.
    """
    fields = {}
    n = len(body)
    # Skip the leading entry key (everything up to the first comma).
    comma = body.find(',')
    i = comma + 1 if comma != -1 else 0
    while i < n:
        while i < n and body[i] in ' \n\t\r,':
            i += 1
        m = re.match(r'([A-Za-z]+)\s*=\s*', body[i:])
        if not m:
            break
        name = m.group(1).lower()
        i += m.end()
        if i >= n:
            break
        if body[i] == '{':
            depth = 1
            i += 1
            start = i
            while i < n and depth > 0:
                if body[i] == '{':
                    depth += 1
                elif body[i] == '}':
                    depth -= 1
                i += 1
            value = body[start:i - 1]
        elif body[i] == '"':
            i += 1
            start = i
            while i < n and body[i] != '"':
                i += 1
            value = body[start:i]
            i += 1 if i < n else 0
        else:
            start = i
            while i < n and body[i] not in ',\n':
                i += 1
            value = body[start:i].strip()
        fields[name] = value
    return fields


def parse_author_year(body):
    """Return (first_surname_lower, year_str) from a BibTeX entry body."""
    fields = parse_fields(body)
    author_raw = fields.get('author')
    year_raw = fields.get('year')
    if not author_raw or not year_raw:
        return None, None
    year_m = re.search(r'(\d{4})', year_raw)
    if not year_m:
        return None, None
    first = author_raw.split(' and ')[0].strip()
    # Strip LaTeX accent braces so the surname is clean ASCII.
    first = re.sub(r'\{\\?[^{}]{0,6}\}', '', first)
    if ',' in first:
        surname = first.split(',')[0].strip()
    else:
        parts = first.split()
        surname = parts[-1] if parts else first
    surname = re.sub(r'[^A-Za-z\-]', '', surname)
    return surname.lower(), year_m.group(1)


# --------------------------------------------------------------------
# sync_bibtex
# --------------------------------------------------------------------

CITE_BLOCK_RE = re.compile(
    # Short bracket of citation-legal chars ending in a year. Figure
    # captions and image tags contain ':' or '/' and so never match.
    r"\[([A-Z][A-Za-z\s.&,;'\-]{0,80}(?:19|20|21)\d{2}[a-z]?)\]"
)
CITE_INNER_SPLIT_RE = re.compile(r'\s*;\s*')


def extract_citations(chapter_md):
    """Yield (surname_primary_lower, year) for each inline citation."""
    results = []
    for m in CITE_BLOCK_RE.finditer(chapter_md):
        inner = m.group(1)
        for piece in CITE_INNER_SPLIT_RE.split(inner):
            piece = piece.strip()
            year_m = re.search(r'(19|20|21)\d{2}', piece)
            if not year_m:
                continue
            year = year_m.group(0)
            # Strip 'et al.' and '&' so the leading surname is easy.
            head = piece.split(',')[0]
            head = head.replace('&', ' ').replace(' et al.', '').replace(' et al', '')
            head = head.strip()
            surname_m = re.match(r"([A-Z][\w\-']+)", head)
            if not surname_m:
                continue
            results.append((surname_m.group(1).lower(), year))
    return results


def build_master_index():
    """master_keys_by_author_year: (surname, year) -> [keys...]"""
    idx = defaultdict(list)
    entries = master_by_key()
    for key, entry in entries.items():
        surname, year = parse_author_year(entry['body'])
        if surname and year:
            idx[(surname, year)].append(key)
    return idx, entries


def sync_bibtex(name):
    survey_dir = os.path.join(SURVEYS_DIR, name)
    if not os.path.isdir(survey_dir):
        print(f'ERROR: surveys/{name}/ does not exist')
        sys.exit(1)

    local_bib_path = os.path.join(survey_dir, 'book', 'references.bib')
    local_entries = parse_bibtex(read(local_bib_path)) if os.path.isfile(local_bib_path) else []
    local_keys = {e['key'] for e in local_entries}

    master_index, master_entries = build_master_index()

    # Pass 1: gather cites from all chapters.
    cite_hits = []
    for lang in ('ko', 'en'):
        book_lang = os.path.join(survey_dir, 'book', lang)
        if not os.path.isdir(book_lang):
            continue
        for fname in sorted(os.listdir(book_lang)):
            if not re.match(r'ch\d+\.md$', fname):
                continue
            cite_hits.extend(extract_citations(read(os.path.join(book_lang, fname))))

    derived_keys = set()
    unresolved = []
    ambiguous = []
    for surname, year in cite_hits:
        candidates = master_index.get((surname, year), [])
        if not candidates:
            unresolved.append(f'{surname},{year}')
            continue
        if len(candidates) == 1:
            derived_keys.add(candidates[0])
            continue
        # Disambiguate by existing local selection.
        overlap = [k for k in candidates if k in local_keys]
        if len(overlap) == 1:
            derived_keys.add(overlap[0])
        else:
            ambiguous.append((surname, year, candidates))

    # Keys to write: union of derived + existing local (never silently drop).
    final_keys = (derived_keys | local_keys) & set(master_entries.keys())
    dropped_local = local_keys - set(master_entries.keys())

    # Compose new local .bib.
    header = (
        f'% {name}/book/references.bib — subset of bibtex/references.bib\n'
        f'% Regenerated by build.py --sync-bibtex.\n'
        f'% Total entries: {len(final_keys)}\n'
        f'% Source of truth: bibtex/references.bib (monorepo master)\n'
        '\n'
    )
    parts = [header]
    for key in sorted(final_keys):
        parts.append(master_entries[key]['raw'] + '\n\n')
    write(local_bib_path, ''.join(parts).rstrip() + '\n')

    # Report.
    print(f'sync-bibtex: {name}')
    print(f'  local .bib entries (before): {len(local_keys)}')
    print(f'  local .bib entries (after):  {len(final_keys)}')
    print(f'  cites extracted from chapters: {len(cite_hits)}')
    print(f'  cites resolved to 1 master key: {len(derived_keys)}')
    print(f'  cites unresolved (no author+year match): {len(set(unresolved))}')
    if unresolved:
        print(f"    sample: {sorted(set(unresolved))[:10]}")
    print(f'  cites ambiguous (multi master match): {len(ambiguous)}')
    if ambiguous:
        for s, y, cands in ambiguous[:5]:
            print(f"    ({s},{y}) → {cands}")
    if dropped_local:
        print(f'  WARNING: {len(dropped_local)} local keys not in master (dropped): '
              f'{sorted(dropped_local)[:10]}')


# --------------------------------------------------------------------
# sync_glossary
# --------------------------------------------------------------------

GLOSSARY_ENTRY_RE = re.compile(r'^\s*-\s*\*\*([^*]+)\*\*\s*:\s*(.*)$')
GLOSSARY_SECTION_RE = re.compile(r'^##\s+(.+)$')


def parse_master_glossary(path):
    """Parse master_<lang>.md. Return list of (section, head, raw_line).

    Order is preserved so the regenerated local file reuses the master's
    alphabetical layout.
    """
    entries = []
    section = ''
    for line in read(path).splitlines():
        sec = GLOSSARY_SECTION_RE.match(line)
        if sec:
            section = sec.group(1).strip()
            continue
        m = GLOSSARY_ENTRY_RE.match(line)
        if m:
            head = m.group(1).strip()
            entries.append((section, head, line.rstrip()))
    return entries


def primary_term(head):
    """Strip parenthetical qualifiers: 'Capacitive sensor (정전용량식 센서)' → 'capacitive sensor'."""
    base = re.sub(r'\s*\([^)]*\)', '', head).strip()
    return base.lower()


def chapters_using_term(survey_dir, lang, head):
    """Return sorted list of chapter numbers (ints) where `head` appears in the chapter body.

    Matches the primary term (before any parenthetical hint) as a word-ish
    substring, case-insensitive. Skips frontmatter.
    """
    term = primary_term(head)
    if not term:
        return []
    book_lang = os.path.join(survey_dir, 'book', lang)
    if not os.path.isdir(book_lang):
        return []
    pattern = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(term) + r'(?![A-Za-z0-9_])', re.IGNORECASE)
    hits = []
    for fname in sorted(os.listdir(book_lang)):
        m = re.match(r'ch(\d+)\.md$', fname)
        if not m:
            continue
        ch_num = int(m.group(1))
        body = read(os.path.join(book_lang, fname))
        # Strip frontmatter to avoid bogus matches in YAML.
        if body.startswith('---'):
            end = body.find('\n---', 3)
            if end != -1:
                body = body[body.find('\n', end + 3) + 1:]
        if pattern.search(body):
            hits.append(ch_num)
    return hits


def sync_glossary(name):
    survey_dir = os.path.join(SURVEYS_DIR, name)
    if not os.path.isdir(survey_dir):
        print(f'ERROR: surveys/{name}/ does not exist')
        sys.exit(1)

    for lang in ('ko', 'en'):
        master_path = os.path.join(GLOSSARY_DIR, f'master_{lang}.md')
        if not os.path.isfile(master_path):
            print(f'skip {lang}: master missing')
            continue
        local_path = os.path.join(survey_dir, 'book', lang, 'glossary.md')
        if not os.path.isdir(os.path.dirname(local_path)):
            continue

        master_entries = parse_master_glossary(master_path)

        # Read the local file's frontmatter + intro to preserve it.
        old_text = read(local_path) if os.path.isfile(local_path) else ''
        front, intro = split_glossary_prelude(old_text)

        # Walk master in order; for each entry, check chapter usage.
        out_sections = defaultdict(list)
        section_order = []
        matched = 0
        for section, head, raw in master_entries:
            chs = chapters_using_term(survey_dir, lang, head)
            if not chs:
                continue
            matched += 1
            if section not in out_sections:
                section_order.append(section)
            # Append chapter ref.
            ch_suffix = ' (' + ', '.join(f'Ch{n}' for n in chs) + ')'
            # If master line already has its own trailing period, keep it.
            out_sections[section].append(raw + ch_suffix)

        new_text_parts = []
        if front:
            new_text_parts.append(front + '\n')
        if intro:
            new_text_parts.append(intro + '\n')
        elif not front:
            # Minimal header if neither existed before.
            title = {'ko': '용어집 (Glossary)', 'en': 'Glossary'}[lang]
            new_text_parts.append(f'# {title}\n\n')
        for section in section_order:
            new_text_parts.append(f'\n## {section}\n\n')
            for line in out_sections[section]:
                new_text_parts.append(line + '\n')

        write(local_path, ''.join(new_text_parts).rstrip() + '\n')
        print(f'sync-glossary: {name}/{lang} — {matched} term(s) matched '
              f'in {len(section_order)} section(s)')


def split_glossary_prelude(text):
    """Return (frontmatter_block_or_empty, intro_paragraph_before_first_##).

    We keep the user's existing frontmatter and the prose introduction
    intact, then overwrite the A-Z sections.
    """
    if not text:
        return '', ''
    front = ''
    body = text
    if text.startswith('---'):
        end = text.find('\n---', 3)
        if end != -1:
            front = text[:end + 4]
            body = text[end + 4:]
            # Strip leading newline after frontmatter for clean rejoin.
            body = body.lstrip('\n')
    # Intro is everything up to the first "## " section header.
    m = re.search(r'(?m)^##\s+', body)
    if m:
        intro = body[:m.start()].rstrip()
    else:
        intro = body.rstrip()
    return front.rstrip(), intro


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: sync_master.py {bibtex|glossary} <survey-name>')
        sys.exit(1)
    mode, target = sys.argv[1], sys.argv[2]
    if mode == 'bibtex':
        sync_bibtex(target)
    elif mode == 'glossary':
        sync_glossary(target)
    else:
        print(f'unknown mode: {mode}')
        sys.exit(1)
