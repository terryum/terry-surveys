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
  - _refs_extracted.json has the minimum {ch, num, text} schema and
    bibtex_key / arxiv_id / doi coverage targets are met
  - _factcheck_report.md exposes a `## Summary` section
  - _research/papers.json exists and is non-empty (warn if 100% bibtex_backfill)

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
FIGURE_RE = re.compile(r'!\[[^\]]*\]\(((?:\.\./)+assets/figures/[^)\s]+)\)')
SUBFOLDER_FIGURE_RE = re.compile(r'assets/figures/ch\d+/')
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

    # Hero description length (KO ≤ 90 chars, EN ≤ 140 chars).
    # The long chapter list already renders below as Chapter Grid, so the
    # description should stay a single hook. See 2026-04 humanoid-revolution
    # incident: the original description listed all four catalysts + all
    # five companies + three diffusion stages, running 243 KO / 444 EN.
    desc = cfg.get('description', {}) or {}
    desc_ko = desc.get('ko', '') if isinstance(desc, dict) else ''
    desc_en = desc.get('en', '') if isinstance(desc, dict) else ''
    if len(desc_ko) > 90:
        iss.warn(
            f'survey.json description.ko is {len(desc_ko)} chars (> 90) — '
            f'home hero looks cluttered. Aim for a one-line hook; the '
            f'Chapter Grid below already lists parts/chapters.'
        )
    if len(desc_en) > 140:
        iss.warn(
            f'survey.json description.en is {len(desc_en)} chars (> 140) — '
            f'home hero looks cluttered. Aim for a one-line hook; the '
            f'Chapter Grid below already lists parts/chapters.'
        )

    # Cover image (optional but recommended for home hero above <h1>).
    cover = cfg.get('cover_image', '')
    if cover:
        # Resolve "../assets/cover.jpg" relative to book/ko/ perspective —
        # actual file lives at surveys/<slug>/assets/cover.<ext>.
        cover_basename = os.path.basename(cover)
        cover_path = os.path.join(survey_dir, 'assets', cover_basename)
        if not os.path.isfile(cover_path):
            iss.warn(
                f'survey.json cover_image "{cover}" points to '
                f'{cover_path} which does not exist.'
            )
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
    else:
        check_unlinked_refs(refs_text, rel, iss)

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

    # Forbid ch{N}/ subfolder paths under assets/figures — flat naming is
    # canonical (CLAUDE.md "금지 사항"). 2026-04 KAIST IP retry storm:
    # standalone-era ch10.html referenced /assets/figures/ch10/fig_10_X_*.png
    # after files were moved to flat (ch10_*.png), generating 404 storms that
    # an external automated client looped on for 4 days.
    for line_no, line in enumerate(body.splitlines(), start=1):
        if SUBFOLDER_FIGURE_RE.search(line):
            iss.err(
                f'{rel}:{line_no}: figure path uses forbidden ch{{N}}/ subfolder — '
                f'flat naming is canonical. Use chNN_<slug>_figN.<ext> directly '
                f'under assets/figures/.'
            )

    # Reader-facing content must NOT reference monorepo-internal paths.
    # Maintainer workflow notes (how to add terms, sync bibtex, etc.) belong
    # in CLAUDE.md / glossary/README.md / _workspace/, never in book/**.md.
    # See 2026-04 humanoid-revolution incident: scaffold blockquote
    # "> **신규 용어 추가 시**: 먼저 `glossary/master_ko.md`를 grep …"
    # rendered as visible instruction text on the public glossary page.
    INTERNAL_PATHS = [
        r'glossary/master_(ko|en)\.md',
        r'bibtex/references\.bib',
        r'\.claude/',
        r'_workspace/',
        r'shared/(build_site|validate|scaffold)\.py',
    ]
    for pat_s in INTERNAL_PATHS:
        pat = re.compile(pat_s)
        for line_no, line in enumerate(body.splitlines(), start=1):
            if pat.search(line):
                iss.warn(
                    f'{rel}:{line_no}: reader-facing content references '
                    f'internal path "{pat_s}" — move maintainer notes to '
                    f'CLAUDE.md / _workspace/ / glossary/README.md.'
                )
                break  # one warning per pattern per file

    # Figure alt-text must NOT contain [Author, Year] citation brackets.
    # Rationale: build_site.py's citation linkifier converts [Author, Year]
    # into <sup><a>[N]</a></sup> HTML; if this happens inside a markdown
    # image's alt attribute, the attribute's closing quote is tripped by
    # the generated HTML and downstream attributes (loading="lazy",
    # onerror=..., style=...) leak into the visible figcaption.
    # See humanoid-revolution 2026-04 incident — Kajita caption leaked
    # `loading="lazy" onerror="..." style="cursor:zoom-in">` to the page.
    # Fix is to write figure captions as `Author et al. Year` (no brackets).
    for line in body.splitlines():
        if not line.lstrip().startswith('!['):
            continue
        # Extract alt text: everything between the first `![` and the
        # matching `](` that precedes `../../assets/figures/`.
        close = line.find('](../../assets/figures/')
        if close == -1:
            close = line.find('](../../../../assets/figures/')
        if close == -1:
            continue
        alt = line[line.index('![') + 2:close]
        cm = INLINE_CITE_RE.search(alt)
        if cm:
            iss.err(
                f'{rel}: figure alt text contains citation brackets "[{cm.group(1)}]" — '
                f'build_site linkifier will corrupt alt attribute and leak HTML into figcaption. '
                f'Use "Author et al. Year" (no square brackets) in figure captions.'
            )

    # Inline citation resolution — strict cite_map check.
    # The build_site.py linkifier silently drops un-mappable citations,
    # leaving them as plain `[Author, Year]` text in the rendered HTML
    # (no clickable superscript, no scroll-to-ref, no back-button).
    # Replay build_citation_map() and require every body-text citation
    # to resolve. See the 2026-04-28 sweep that fixed S5 (claude-to-codex)
    # and S6 (physical-ai-manufacturing); plan in
    # ~/.claude/plans/s5-stateless-lollipop.md.
    check_unresolved_citations(path, body, main_body, rel, iss)


REF_MD_LINK_RE = re.compile(r'\[[^\]]+\]\((https?://[^)\s]+)\)')


def check_unlinked_refs(refs_text, rel, iss):
    """Every numbered entry under ## 참고문헌 / ## References must contain at
    least one markdown hyperlink [text](http://…) — build_site.py renders it
    as a clickable <a target="_blank">. Without it the entry ships as plain
    text and the reader can't reach the source. See 2026-05-05
    claude-to-codex incident: 12 chapters published with text-only refs.
    """
    line_no = 0
    for raw in refs_text.splitlines():
        line_no += 1
        m = REF_LINE_RE.match(raw)
        if not m:
            continue
        entry = m.group(1)
        if REF_MD_LINK_RE.search(entry):
            continue
        snippet = entry[:60] + ('…' if len(entry) > 60 else '')
        iss.err(
            f'{rel}: reference entry has no hyperlink — every ref under '
            f'## 참고문헌 / ## References must contain a markdown link '
            f'[text](url) so build_site.py renders it as <a target="_blank">. '
            f'Pull the URL from book/references.bib (url field). Entry: "{snippet}"'
        )


def check_unresolved_citations(path, body, main_body, rel, iss):
    """Error on any inline [Author, Year] that build_site.py would NOT
    convert into a <sup><a class="cite-link"> superscript.

    Mirrors the lookup logic of build_site.replace_citations_with_links
    so we surface the exact same set of failures the build will produce
    (no false positives: if the build will linkify it, we accept it).
    """
    # Local import — keeps validate.py importable even if build_site.py
    # later grows reverse-imports from validate.
    from shared.build_site import build_citation_map

    cite_map, refs = build_citation_map(body)
    if not refs:
        # No references section — already warned upstream; skip.
        return

    unresolved = []
    for line_no, line in enumerate(main_body.splitlines(), start=1):
        for cm in INLINE_CITE_RE.finditer(line):
            inner = cm.group(1).strip()
            if inner in cite_map:
                continue
            # Mirror replace_citations_with_links's fuzzy fallback:
            # match by year-substring + author-substring.
            yr_m = re.search(r'\d{4}[a-z]?', inner)
            if not yr_m:
                continue
            yr = yr_m.group()
            inner_lower = inner.lower()
            inner_author = inner_lower.replace(yr, '').strip(' ,[]()')
            matched = False
            for key in cite_map:
                key_yr_m = re.search(r'\d{4}[a-z]?', key)
                if not key_yr_m or key_yr_m.group() != yr:
                    continue
                key_author = key.lower().replace(yr, '').strip(' ,[]()')
                if not key_author:
                    continue
                if key_author in inner_lower or (inner_author and inner_author in key_author):
                    matched = True
                    break
            if matched:
                continue
            unresolved.append((line_no, inner))

    for line_no, cite in unresolved:
        iss.err(
            f'{rel}:{line_no}: inline citation [{cite}] does not resolve to '
            f'any reference — linkifier will leave it as plain text. Add the '
            f'cite to the chapter\'s ## References section, or fix the year '
            f'format so build_site._extract_year_info can parse it: '
            f'(YYYY) | (YYYYa) | YYYY-MM-DD | trailing [Author, YYYY] tag.'
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
    recommended = ('bibtex_key', 'arxiv_id', 'doi', 'verification_status')
    bad = 0
    coverage = {k: 0 for k in recommended}
    for entry in data:
        if not isinstance(entry, dict):
            bad += 1
            continue
        for k in required:
            if k not in entry:
                bad += 1
                break
        for k in recommended:
            if entry.get(k):
                coverage[k] += 1
    if bad:
        iss.err(f'_refs_extracted.json: {bad} entry(ies) missing required fields {required}')

    total = len(data)
    if total:
        # The schema target — set to baseline 50% so deterministic backfill
        # passes the bar; fact-checker should drive arxiv/doi to ≥ 90% later.
        # bibtex_key alone is the most stable mechanical signal; if it is
        # below 50% the survey almost certainly has not been run through
        # `python3 build.py --refresh-refs <slug>`.
        bk_pct = round(100 * coverage['bibtex_key'] / total, 1)
        id_pct = round(100 * (coverage['arxiv_id'] + coverage['doi']) / (2 * total), 1)
        if bk_pct < 50:
            iss.warn(
                f'_refs_extracted.json: bibtex_key coverage {bk_pct}% (<50%) — '
                f'run `python3 build.py --refresh-refs {os.path.basename(survey_dir)}`'
            )
        if id_pct < 30:
            iss.warn(
                f'_refs_extracted.json: arxiv/doi coverage {id_pct}% (<30%) — '
                f'fact-checker should enrich identifiers'
            )


def check_research_papers(survey_dir, iss):
    path = os.path.join(survey_dir, '_research', 'papers.json')
    if not os.path.isfile(path):
        iss.warn(
            '_research/papers.json missing — run `python3 build.py --backfill-research '
            f'{os.path.basename(survey_dir)}` (mechanical) or '
            '`/survey --orchestrate <slug>` (deep-researcher pass)'
        )
        return
    try:
        data = read_json(path)
    except json.JSONDecodeError as e:
        iss.err(f'_research/papers.json invalid JSON: {e}')
        return
    if not isinstance(data, list):
        iss.err('_research/papers.json is not a list')
        return
    if not data:
        iss.warn('_research/papers.json is empty')
        return
    backfill_count = sum(
        1 for e in data if isinstance(e, dict) and e.get('provenance') == 'bibtex_backfill'
    )
    rich_count = sum(
        1 for e in data if isinstance(e, dict) and e.get('method_summary')
    )
    rich_pct = round(100 * rich_count / len(data), 1)
    if rich_pct < 25 and backfill_count == len(data):
        iss.warn(
            f'_research/papers.json is 100% bibtex_backfill (no method_summary) — '
            f'deep-researcher pass needed for ranker quality'
        )
    elif rich_pct < 25:
        iss.warn(
            f'_research/papers.json: only {rich_pct}% have method_summary — '
            f'deep-researcher should enrich'
        )


def check_factcheck_report(survey_dir, iss):
    path = os.path.join(survey_dir, '_factcheck_report.md')
    if not os.path.isfile(path):
        iss.warn('_factcheck_report.md missing')
        return
    text = read(path)
    if '## Summary' not in text:
        iss.warn('_factcheck_report.md missing "## Summary" section')


def check_research_shards(survey_dir, iss):
    """For each researcher role (foundations, frontier): if any of the 3 mandated
    outputs exists, ALL 3 must exist. Catches the 2026-04-29 silent-failure pattern
    where deep-researcher-frontier produced papers/groups but skipped timeline."""
    research = os.path.join(survey_dir, '_research')
    if not os.path.isdir(research):
        return
    for role in ('foundations', 'frontier'):
        artifacts = {
            'papers': os.path.join(research, f'papers_{role}.json'),
            'groups': os.path.join(research, f'groups_{role}.md'),
            'timeline': os.path.join(research, f'timeline_{role}.md'),
        }
        present = {k: os.path.isfile(p) for k, p in artifacts.items()}
        if not any(present.values()):
            continue  # role didn't run — that's fine
        missing = [k for k, ok in present.items() if not ok]
        if missing:
            iss.err(
                f'_research/ {role} shard partial output: missing '
                + ', '.join(f'{k}_{role}.{"json" if k == "papers" else "md"}' for k in missing)
                + f' (deep-researcher-{role} silent-failure pattern — see 2026-04-29)'
            )


def check_analysis_outputs(survey_dir, iss):
    """critical-analyst mandates 3 outputs in _analysis/. If the directory exists OR
    any output exists, all 3 must exist. Same silent-failure class as check_research_shards."""
    analysis = os.path.join(survey_dir, '_analysis')
    required = ['gaps.md', 'novelty_matrix.md', 'positioning.md']
    present = {f: os.path.isfile(os.path.join(analysis, f)) for f in required}
    has_dir = os.path.isdir(analysis)
    has_any_file = any(present.values())
    if not has_dir and not has_any_file:
        iss.warn('_analysis/ missing entirely — critical-analyst phase has not run')
        return
    missing = [f for f, ok in present.items() if not ok]
    if missing:
        iss.err(
            '_analysis/ partial output: missing ' + ', '.join(missing)
            + ' (critical-analyst silent-failure pattern — see 2026-04-29)'
        )


def check_visibility_consistency(survey_dir, iss):
    """Require the centralized private source repository for every survey."""
    survey_json = os.path.join(survey_dir, 'survey.json')
    if not os.path.isfile(survey_json):
        return  # check_survey_json이 별도로 처리
    try:
        with open(survey_json, encoding='utf-8') as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    if cfg.get('github_repo') != 'terryum/terry-surveys-contents':
        iss.err(
            'github_repo must be terryum/terry-surveys-contents; '
            'standalone survey repositories are no longer source targets'
        )
    if cfg.get('github_repo_visibility') != 'private':
        iss.err('github_repo_visibility must be private for every survey')


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
    check_research_papers(survey_dir, iss)
    check_research_shards(survey_dir, iss)
    check_analysis_outputs(survey_dir, iss)
    check_visibility_consistency(survey_dir, iss)

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
