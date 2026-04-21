#!/usr/bin/env python3
"""Structural validator for terry-surveys.

Runs a set of per-survey checks that the repo-wide invariants hold:

  - survey.json has the required top-level fields
  - every chapter md (ko + en) carries the required frontmatter
  - inline `[Author et al., Year]` citations resolve to an entry in the
    chapter's own `## 참고문헌` / `## References` list
  - cross-references `(Chapter N)` point to a chapter that exists
  - figure paths resolve to an actual file under assets/figures/
  - every key in the survey's book/references.bib exists in the
    monorepo master bibtex/references.bib
  - every term in book/<lang>/glossary.md exists in glossary/master_<lang>.md
    with the same definition (chapter suffix `(Ch N)` is tolerated)
  - _refs_extracted.json has the minimum {ch, num, text} schema
  - _factcheck_report.md exposes a `## Summary` section

Severity levels:
  error   — hard breakage; build.py --validate exits non-zero
  warning — deviation that needs human judgement, does not fail the run
  info    — progress / count rollup

The check is called from build.py --validate [<name>|--all].
"""

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SURVEYS_DIR = os.path.join(ROOT, 'surveys')
MASTER_BIB = os.path.join(ROOT, 'bibtex', 'references.bib')
GLOSSARY_DIR = os.path.join(ROOT, 'glossary')


# ------------------------------------------------------------------
# Small parsers (reused across checks)
# ------------------------------------------------------------------

def parse_master_bib_keys():
    text = read(MASTER_BIB)
    return set(re.findall(r'@\w+\s*\{\s*([^\s,]+)\s*,', text))


def parse_local_bib_keys(path):
    text = read(path)
    return set(re.findall(r'@\w+\s*\{\s*([^\s,]+)\s*,', text))


def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def split_frontmatter(md_text):
    """Return (frontmatter_dict, body). frontmatter is crude YAML."""
    if not md_text.startswith('---'):
        return {}, md_text
    end = md_text.find('\n---', 3)
    if end == -1:
        return {}, md_text
    block = md_text[3:end].strip()
    body_start = md_text.find('\n', end + 3) + 1
    meta = {}
    for line in block.splitlines():
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, md_text[body_start:]


def strip_refs_section(body):
    """Return (main_body, refs_text). refs_text is '' if absent."""
    for marker in ('## 참고문헌', '## References'):
        idx = body.find(marker)
        if idx != -1:
            return body[:idx], body[idx:]
    return body, ''


def glossary_entries(md_text):
    """Return {term_key: raw_entry_line}. term_key is the bolded head
    up to the first colon or closing paren, normalized lower-case.
    """
    out = {}
    for line in md_text.splitlines():
        m = re.match(r'\s*-\s*\*\*([^*]+)\*\*\s*:\s*(.*)$', line)
        if not m:
            continue
        head = m.group(1).strip()
        # Use the full bolded head as the key (keeps parenthetical hints).
        out[head.lower()] = line.strip()
    return out


# ------------------------------------------------------------------
# Per-survey checks
# ------------------------------------------------------------------

REQUIRED_SURVEY_FIELDS = ['id', 'title', 'description', 'dates', 'features', 'parts']
REQUIRED_CHAPTER_FRONTMATTER = ['chapter', 'title', 'part', 'date', 'last_updated']

INLINE_CITE_RE = re.compile(r'\[([A-Z][^\[\]]{0,160}?,\s*(19|20|21)\d{2}[a-z]?)\]')
CROSSREF_RE = re.compile(r'\(Chapter\s+(\d+)(?:\s*[,&]\s*Chapter\s+\d+)*\)')
CROSSREF_ALL_RE = re.compile(r'Chapter\s+(\d+)')
FIGURE_RE = re.compile(r'!\[[^\]]*\]\((\.\./\.\./assets/figures/[^)\s]+)\)')
REF_LINE_RE = re.compile(r'^\s*\d+\.\s+(.+)$')


class Issues:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self):
        return not self.errors


def check_survey_json(survey_dir, iss):
    path = os.path.join(survey_dir, 'survey.json')
    if not os.path.isfile(path):
        iss.err(f'survey.json missing at {path}')
        return None
    try:
        cfg = read_json(path)
    except json.JSONDecodeError as e:
        iss.err(f'survey.json invalid: {e}')
        return None
    for field in REQUIRED_SURVEY_FIELDS:
        if field not in cfg:
            iss.err(f'survey.json missing required field: {field}')
    features = cfg.get('features', {})
    for k in ('glossary', 'pdf', 'paper'):
        if k in features and not isinstance(features[k], bool):
            iss.err(f'survey.json features.{k} is not bool')
    # parts[].chapters[].num/title/summary
    parts = cfg.get('parts', [])
    if not parts:
        iss.warn('survey.json has no parts[]')
    chapter_nums = []
    for p_idx, part in enumerate(parts):
        for c_idx, ch in enumerate(part.get('chapters', [])):
            for k in ('num', 'title', 'summary'):
                if k not in ch:
                    iss.err(
                        f'survey.json parts[{p_idx}].chapters[{c_idx}] missing {k}'
                    )
            if 'num' in ch:
                chapter_nums.append(ch['num'])
    return {'config': cfg, 'chapter_nums': chapter_nums}


def check_chapters(survey_dir, chapter_nums, iss):
    """Check both ko/ and en/ chapters for frontmatter, citations,
    cross-refs, figures, and that numbers align with survey.json."""
    max_ch = max(chapter_nums) if chapter_nums else 0
    for lang in ('ko', 'en'):
        book_lang = os.path.join(survey_dir, 'book', lang)
        if not os.path.isdir(book_lang):
            iss.err(f'book/{lang}/ missing')
            continue
        expected = {f'ch{n:02d}.md' for n in chapter_nums}
        found = {f for f in os.listdir(book_lang) if re.match(r'ch\d+\.md$', f)}
        missing = expected - found
        extra = found - expected
        for m in sorted(missing):
            iss.err(f'book/{lang}/{m} missing (listed in survey.json)')
        for x in sorted(extra):
            iss.warn(f'book/{lang}/{x} present but not in survey.json')

        for fname in sorted(found):
            path = os.path.join(book_lang, fname)
            check_one_chapter(path, lang, max_ch, survey_dir, iss)


def check_one_chapter(path, lang, max_ch, survey_dir, iss):
    text = read(path)
    meta, body = split_frontmatter(text)
    rel = os.path.relpath(path, survey_dir)

    for k in REQUIRED_CHAPTER_FRONTMATTER:
        if k not in meta:
            iss.err(f'{rel}: frontmatter missing {k}')

    main_body, refs_text = strip_refs_section(body)
    if not refs_text:
        iss.warn(f'{rel}: no "## 참고문헌" or "## References" section')

    # Cross-references
    for m in CROSSREF_ALL_RE.finditer(main_body):
        n = int(m.group(1))
        if max_ch and n > max_ch:
            iss.err(f'{rel}: cross-ref (Chapter {n}) exceeds max chapter {max_ch}')

    # Figure existence
    for m in FIGURE_RE.finditer(body):
        rel_fig = m.group(1)
        abs_fig = os.path.normpath(os.path.join(os.path.dirname(path), rel_fig))
        if not os.path.isfile(abs_fig):
            iss.err(f'{rel}: figure not found: {rel_fig}')

    # Inline citation resolution
    ref_lines = []
    for line in refs_text.splitlines():
        m = REF_LINE_RE.match(line)
        if m:
            ref_lines.append(m.group(1))
    # Build a quick lookup: lowercase concatenation for substring matches.
    refs_blob = ' || '.join(ref_lines).lower()

    unresolved = set()
    for cm in INLINE_CITE_RE.finditer(main_body):
        cite = cm.group(1)
        if not ref_lines:
            # No references section → already warned; skip further.
            break
        # Extract year and primary surname(s) from the citation.
        year_m = re.search(r'(19|20|21)\d{2}', cite)
        if not year_m:
            continue
        year = year_m.group(0)
        # Primary surname: first capitalised token before ',' or 'et al.'
        surname_m = re.match(
            r"\s*([A-Z][\w\-']+)", cite.replace('&', ',').split(',')[0].strip()
        )
        if not surname_m:
            continue
        surname = surname_m.group(1).lower()
        if year not in refs_blob or surname not in refs_blob:
            unresolved.add(cite)
    if unresolved:
        sample = sorted(unresolved)[:5]
        iss.warn(
            f'{rel}: {len(unresolved)} inline citation(s) not resolved '
            f'in references section (sample: {sample})'
        )


def check_bib_subset(survey_dir, iss):
    local_bib = os.path.join(survey_dir, 'book', 'references.bib')
    if not os.path.isfile(local_bib):
        iss.err('book/references.bib missing')
        return
    master_keys = parse_master_bib_keys()
    local_keys = parse_local_bib_keys(local_bib)
    missing = local_keys - master_keys
    if missing:
        sample = sorted(missing)[:10]
        iss.err(
            f'{len(missing)} local .bib key(s) missing from master '
            f'(sample: {sample})'
        )


def check_glossary_subset(survey_dir, iss):
    for lang in ('ko', 'en'):
        master_path = os.path.join(GLOSSARY_DIR, f'master_{lang}.md')
        local_path = os.path.join(survey_dir, 'book', lang, 'glossary.md')
        if not os.path.isfile(master_path):
            iss.warn(f'glossary master for {lang} missing; skipping subset check')
            continue
        if not os.path.isfile(local_path):
            # OK only if features.glossary is false
            continue
        master_entries = glossary_entries(read(master_path))
        local_entries = glossary_entries(read(local_path))

        unknown = []
        definition_drift = []
        for key, local_line in local_entries.items():
            if key not in master_entries:
                unknown.append(key)
                continue
            # Compare definition strings modulo the "(Ch N)" suffix that
            # local entries append for traceability.
            m_line = master_entries[key]
            # Strip trailing chapter-reference suffix like " (Ch6, Ch7, Ch9)"
            # or " (Ch6)" or " (Ch6, 7, 9)".
            local_stripped = re.sub(
                r'\s*\(\s*(?:[Cc]h\s*\d+|\d+)(?:\s*,\s*(?:[Cc]h\s*\d+|\d+))*\s*\)\s*$',
                '',
                local_line,
            ).strip()
            if normalize_glossary(local_stripped) != normalize_glossary(m_line):
                definition_drift.append(key)
        if unknown:
            iss.warn(
                f'book/{lang}/glossary.md: {len(unknown)} term(s) not in master '
                f'(sample: {sorted(unknown)[:5]})'
            )
        if definition_drift:
            iss.warn(
                f'book/{lang}/glossary.md: {len(definition_drift)} definition(s) '
                f'drift from master (sample: {sorted(definition_drift)[:5]})'
            )


def normalize_glossary(line):
    # Normalise for definition comparison: collapse whitespace, drop
    # trailing punctuation, lowercase.
    s = re.sub(r'\s+', ' ', line).strip().rstrip('.').lower()
    return s


def check_refs_extracted(survey_dir, iss):
    path = os.path.join(survey_dir, '_refs_extracted.json')
    if not os.path.isfile(path):
        iss.warn('_refs_extracted.json missing')
        return
    try:
        data = read_json(path)
    except json.JSONDecodeError as e:
        iss.err(f'_refs_extracted.json invalid JSON: {e}')
        return
    if not isinstance(data, list):
        iss.err('_refs_extracted.json is not a list')
        return
    required = ('ch', 'num', 'text')
    bad = 0
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            bad += 1
            continue
        for k in required:
            if k not in entry:
                bad += 1
                break
    if bad:
        iss.err(f'_refs_extracted.json: {bad} entry(ies) missing required fields {required}')


def check_factcheck_report(survey_dir, iss):
    path = os.path.join(survey_dir, '_factcheck_report.md')
    if not os.path.isfile(path):
        iss.warn('_factcheck_report.md missing')
        return
    text = read(path)
    if '## Summary' not in text:
        iss.warn('_factcheck_report.md missing "## Summary" section')


# ------------------------------------------------------------------
# Orchestration
# ------------------------------------------------------------------

def validate_one(name, verbose=True):
    survey_dir = os.path.join(SURVEYS_DIR, name)
    if not os.path.isdir(survey_dir):
        print(f'ERROR: surveys/{name}/ does not exist')
        return False
    iss = Issues()

    survey_meta = check_survey_json(survey_dir, iss)
    if survey_meta is not None:
        chapter_nums = survey_meta['chapter_nums']
        check_chapters(survey_dir, chapter_nums, iss)
    check_bib_subset(survey_dir, iss)
    check_glossary_subset(survey_dir, iss)
    check_refs_extracted(survey_dir, iss)
    check_factcheck_report(survey_dir, iss)

    if verbose:
        print(f"\n[{name}]")
        if iss.errors:
            print(f"  ERRORS ({len(iss.errors)}):")
            for e in iss.errors:
                print(f"    - {e}")
        if iss.warnings:
            print(f"  WARNINGS ({len(iss.warnings)}):")
            for w in iss.warnings:
                print(f"    - {w}")
        if not iss.errors and not iss.warnings:
            print("  OK — no issues")
    return iss


def validate_all(verbose=True):
    all_issues = {}
    for name in sorted(os.listdir(SURVEYS_DIR)):
        if not os.path.isdir(os.path.join(SURVEYS_DIR, name)):
            continue
        if not os.path.isfile(os.path.join(SURVEYS_DIR, name, 'survey.json')):
            continue
        all_issues[name] = validate_one(name, verbose=verbose)
    return all_issues


def main(target=None):
    if target and target != '--all':
        iss = validate_one(target, verbose=True)
        sys.exit(1 if iss.errors else 0)
    all_issues = validate_all(verbose=True)
    total_err = sum(len(i.errors) for i in all_issues.values())
    total_warn = sum(len(i.warnings) for i in all_issues.values())
    print('')
    print('=' * 60)
    print(f'validate summary: {total_err} error(s), {total_warn} warning(s) across {len(all_issues)} surveys')
    sys.exit(1 if total_err else 0)


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else '--all'
    main(arg)
