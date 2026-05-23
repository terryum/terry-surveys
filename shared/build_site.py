#!/usr/bin/env python3
"""Unified build system for terry-surveys monorepo.

Converts Markdown chapters → static HTML site with citation linking,
sidebar navigation, KaTeX math, and bilingual (ko/en) support.

Usage:
    # Called from build.py, not directly
    from shared.build_site import build_survey
    build_survey(config, survey_dir, shared_dir)
"""

import re
import os
import json
import shutil


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(survey_dir):
    """Load survey.json and derive chapter metadata."""
    config_path = os.path.join(survey_dir, 'survey.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Derive CHAPTERS_KO, CHAPTERS_EN, NUM_CHAPTERS from parts
    chapters_ko = {}
    chapters_en = {}
    for part_idx, part in enumerate(config['parts'], 1):
        part_num = part.get('part_num_override', part_idx)
        for ch in part['chapters']:
            chapters_ko[ch['num']] = {
                'title': ch['title']['ko'],
                'part': part['name']['ko'],
                'part_num': part_num
            }
            chapters_en[ch['num']] = {
                'title': ch['title']['en'],
                'part': part['name']['en'],
                'part_num': part_num
            }

    num_chapters = max(chapters_ko.keys()) if chapters_ko else 0
    return config, chapters_ko, chapters_en, num_chapters


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

def parse_frontmatter(md):
    """Extract YAML frontmatter and body."""
    meta = {}
    body = md
    if md.startswith('---'):
        parts = md.split('---', 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2]
            for line in fm.strip().split('\n'):
                if ':' in line and not line.strip().startswith('-'):
                    key, val = line.split(':', 1)
                    meta[key.strip().strip('"')] = val.strip().strip('"')
    return meta, body


def _extract_year_info(ref_text):
    """Return (year, suffix, author_span) from a reference entry, or
    (None, None, None) if no year-like pattern is found.

    Priority ladder (deterministic — first hit wins):
      1. (YYYY) or (YYYYa) — parenthesized year with optional letter suffix
      2. YYYY-MM-DD — ISO date (handles non-academic posts)
      3. Trailing [Author, YYYY] / [Author, YYYYa] tag at end of ref
      4. Bare 4-digit year — last resort
    """
    m = re.search(r'\((\d{4})([a-z])?\)', ref_text)
    if m:
        return m.group(1), m.group(2) or '', m.start()
    m_iso = re.search(r'\b(\d{4})-\d{2}-\d{2}\b', ref_text)
    if m_iso:
        return m_iso.group(1), '', m_iso.start()
    m_tag = re.search(r'\[([^\[\]]+?),\s*(\d{4})([a-z])?\]\s*\.?\s*$', ref_text)
    if m_tag:
        return m_tag.group(2), m_tag.group(3) or '', m_tag.start()
    # Bare year — take the RIGHTMOST 4-digit match (with optional letter
    # suffix `2025a`). Reasoning: academic refs commonly carry an arXiv ID
    # like `arXiv:2307.15818, 2023.` where 2307 is an arXiv-month encoding,
    # not a publication year. The publication year is reliably the trailing
    # token. Range 1900–2099 to skip stray 4-digit numbers (page counts,
    # dataset sizes, etc.). Suffix capture handles industry refs that use
    # `Cosmax, 2025a.` style for same-author same-year disambiguation.
    bare_matches = [m for m in re.finditer(r'\b(\d{4})([a-z])?\b', ref_text)
                    if 1900 <= int(m.group(1)) <= 2099]
    if bare_matches:
        last = bare_matches[-1]
        return last.group(1), last.group(2) or '', last.start()
    return None, None, None


def _extract_trailing_tag(ref_text):
    """Return (author, year, suffix) from a trailing [Author, YYYY] tag, or None."""
    m = re.search(r'\[([^\[\]]+?),\s*(\d{4})([a-z])?\]\s*\.?\s*$', ref_text)
    if m:
        return m.group(1).strip(), m.group(2), m.group(3) or ''
    return None


def build_citation_map(md_text):
    """Build a mapping from Author-Year citations to sequential numbers."""
    ref_section = None
    for marker in ['## 참고문헌', '## References']:
        idx = md_text.find(marker)
        if idx != -1:
            ref_section = md_text[idx:]
            break

    if not ref_section:
        return {}, []

    refs = []
    for line in ref_section.split('\n'):
        line = line.strip()
        match = re.match(r'^\d+\.\s+(.+)', line)
        if match:
            ref_text = match.group(1)
            refs.append(ref_text)

    cite_map = {}
    for i, ref_text in enumerate(refs, 1):
        # Trailing [Author, YYYY] tag is the canonical inline-citation form
        # for non-academic refs (blog posts, GitHub READMEs). Register it
        # directly so e.g. `[Um, 2026]` resolves even when the ref's only
        # year-like pattern is an ISO date earlier in the line.
        tag = _extract_trailing_tag(ref_text)
        if tag:
            tag_author, tag_year, tag_suffix = tag
            cite_map[f'{tag_author}, {tag_year}{tag_suffix}'] = i
            cite_map[f'{tag_author} ({tag_year}{tag_suffix})'] = i

        year, suffix, span = _extract_year_info(ref_text)
        if year is None:
            continue

        author_part = ref_text[:span].strip().rstrip(',').rstrip('.').strip()
        first_author = author_part.split(',')[0].strip()
        yrkey = f'{year}{suffix}'

        cite_map[f'{first_author}, {yrkey}'] = i
        cite_map[f'{first_author} ({yrkey})'] = i
        cite_map[f'{first_author} et al., {yrkey}'] = i
        cite_map[f'{first_author} et al. ({yrkey})'] = i
        # When the ref carries a letter suffix (2025a, 2025b, …), also
        # register an unsuffixed alias so a body citation like `[Org, 2025]`
        # (omitting the suffix) still resolves. setdefault → first
        # suffix-bearing ref wins the ambiguous lookup.
        if suffix:
            cite_map.setdefault(f'{first_author}, {year}', i)
            cite_map.setdefault(f'{first_author} ({year})', i)
            cite_map.setdefault(f'{first_author} et al., {year}', i)
            cite_map.setdefault(f'{first_author} et al. ({year})', i)

        authors_list = [a.strip() for a in author_part.split(',')]
        last_names = [a for a in authors_list if len(a) > 2 and not re.match(r'^[A-Z]\.\s*$', a.strip())]
        if len(last_names) == 2:
            cite_map[f'{last_names[0]} & {last_names[1]}, {yrkey}'] = i
            cite_map[f'{last_names[0]} and {last_names[1]}, {yrkey}'] = i
            if suffix:
                cite_map.setdefault(f'{last_names[0]} & {last_names[1]}, {year}', i)
                cite_map.setdefault(f'{last_names[0]} and {last_names[1]}, {year}', i)

        first_author_clean = first_author.replace('**', '').strip()
        if first_author_clean != first_author:
            cite_map[f'{first_author_clean}, {yrkey}'] = i
            cite_map[f'{first_author_clean} et al., {yrkey}'] = i
            if suffix:
                cite_map.setdefault(f'{first_author_clean}, {year}', i)
                cite_map.setdefault(f'{first_author_clean} et al., {year}', i)

        org_part = author_part.replace('**', '').strip().rstrip('.')
        if org_part:
            cite_map[f'{org_part}, {yrkey}'] = i
            cite_map[f'{org_part} ({yrkey})'] = i
            cite_map[f'{org_part} [{yrkey}]'] = i
            if suffix:
                cite_map.setdefault(f'{org_part}, {year}', i)
                cite_map.setdefault(f'{org_part} ({year})', i)
                cite_map.setdefault(f'{org_part} [{year}]', i)

        # Keyword-based matching for known project/paper names
        for keyword in re.findall(
            r'(?:TacScale|TacPlay|EgoScale|AoE|AirExo|DEXOP|DexCap|DexUMI|'
            r'ExoStart|ImMimic|ForceMimic|DexForce|ForceVLA|Tactile-VLA|'
            r'UniTacHand|DOGlove|AnySkin|AnyTouch|Bunny-VisionPro|AnyTeleop|'
            r'DexPilot|DexH2R|pi0|RT-1|RT-2|Octo|OpenVLA|GR00T|Helix|'
            r'DIGIT|GelSight|LEAP|MANO|ALOHA|Mobile ALOHA|Sparsh|UniTouch|'
            r'OSMO|NeuralFeels|DiffTactile|Diffusion Policy|ACT|Flow Matching|'
            r'Gemini Robotics|X-Embodiment|Isaac|MuJoCo|X-Sim|RoboPaint|FARM|'
            r'VTDexManip|ReSkin|Robot Synesthesia|PP-Tac|RGMC|'
            r'SayCan|SayPlan|PaLM-E|CaP|CaP-X|AutoTAMP|HAMSTER|RT-H|'
            r'DROID|KARMA|Embodied-RAG|REFLECT|BUMBLE|AutoRT|PragmaBot|SIMPLER)',
            ref_text, re.IGNORECASE
        ):
            kw_lower = keyword.lower()
            cite_map[f'{keyword} [{yrkey}]'] = i
            cite_map[f'{keyword}, {yrkey}'] = i
            cite_map[f'{keyword} ({yrkey})'] = i
            cite_map[f'_kw_{kw_lower}_{yrkey}'] = i
            if suffix:
                cite_map.setdefault(f'{keyword} [{year}]', i)
                cite_map.setdefault(f'{keyword}, {year}', i)
                cite_map.setdefault(f'{keyword} ({year})', i)
                cite_map.setdefault(f'_kw_{kw_lower}_{year}', i)

    # Unique year+suffix mapping (suffix-aware)
    year_count = {}
    for ref_text in refs:
        y, s, _ = _extract_year_info(ref_text)
        if y:
            yr = f'{y}{s}'
            year_count[yr] = year_count.get(yr, 0) + 1
    for i, ref_text in enumerate(refs, 1):
        y, s, _ = _extract_year_info(ref_text)
        if y:
            yr = f'{y}{s}'
            if year_count[yr] == 1 and yr not in cite_map:
                cite_map[yr] = i

    return cite_map, refs


def replace_citations_with_links(html_text, cite_map, ch_num, ref_list=None):
    """Replace [Author, Year] citations in HTML with superscript links."""
    if not cite_map:
        return html_text
    if ref_list is None:
        ref_list = []

    year_refs = {}
    for key, num in cite_map.items():
        year_match = re.search(r'\d{4}[a-z]?', key)
        if year_match:
            yr = year_match.group()
            author = key.replace(yr, '').strip(' ,[]()').lower()
            if yr not in year_refs:
                year_refs[yr] = []
            year_refs[yr].append((author, num))

    def make_link(num, title):
        return f'<sup><a class="cite-link" href="#ch{ch_num}-ref-{num}" title="{title}">[{num}]</a></sup>'

    def citation_replacer(match):
        full_match = match.group(0)
        inner = match.group(1)

        end_pos = match.end()
        if end_pos < len(html_text) and html_text[end_pos] == '(':
            return full_match

        if not re.search(r'\d{4}[a-z]?', inner):
            return full_match

        inner_clean = inner.strip()

        if inner_clean in cite_map:
            return make_link(cite_map[inner_clean], inner_clean)

        inner_year = re.search(r'\d{4}[a-z]?', inner_clean)
        if inner_year:
            yr = inner_year.group()
            inner_lower = inner_clean.lower()

            for key, num in cite_map.items():
                key_year = re.search(r'\d{4}[a-z]?', key)
                if key_year and key_year.group() == yr:
                    key_author = key.replace(yr, '').strip(' ,[]()').lower()
                    if key_author and key_author in inner_lower:
                        return make_link(num, inner_clean)
                    if inner_lower.replace(yr, '').strip(' ,[]()') in key_author and len(inner_lower) > 4:
                        return make_link(num, inner_clean)

            if inner_clean == yr and yr in cite_map:
                return make_link(cite_map[yr], inner_clean)

        return full_match

    result = re.sub(r'\[([^\]]+)\](?!\()', citation_replacer, html_text)

    def contextual_replacer(match):
        prefix = match.group(1)
        year = match.group(2)

        if 'cite-link' in prefix:
            return match.group(0)

        prefix_clean = re.sub(r'<[^>]+>', '', prefix).strip()
        prefix_lower = prefix_clean.lower()

        kw_key = f'_kw_{prefix_lower}_{year}'
        if kw_key in cite_map:
            return f'{prefix}{make_link(cite_map[kw_key], prefix_clean + " " + year)}'

        for pattern in [f'{prefix_clean} [{year}]', f'{prefix_clean}, {year}', f'{prefix_clean} ({year})']:
            if pattern in cite_map:
                return f'{prefix}{make_link(cite_map[pattern], prefix_clean + " " + year)}'

        for key, num in cite_map.items():
            if key.startswith('_kw_'):
                continue
            key_year = re.search(r'\d{4}[a-z]?', key)
            if key_year and key_year.group() == year:
                key_lower = key.lower()
                if prefix_lower and len(prefix_lower) > 2 and prefix_lower in key_lower:
                    return f'{prefix}{make_link(num, prefix_clean + " " + year)}'

        if ref_list:
            for idx, ref_text in enumerate(ref_list, 1):
                ref_year = re.search(r'\((\d{4})\)', ref_text)
                if ref_year and ref_year.group(1) == year:
                    ref_lower = ref_text.lower()
                    if prefix_lower and len(prefix_lower) > 2:
                        if prefix_lower in ref_lower:
                            return f'{prefix}{make_link(idx, prefix_clean + " " + year)}'
                        prefix_base = re.sub(r'[\d.]+$', '', prefix_lower)
                        if prefix_base and len(prefix_base) > 1 and prefix_base in ref_lower:
                            return f'{prefix}{make_link(idx, prefix_clean + " " + year)}'

        if year in cite_map:
            return f'{prefix}{make_link(cite_map[year], year)}'

        return match.group(0)

    result = re.sub(r'(\S+)\s*\[(\d{4})\](?!\()', contextual_replacer, result)

    return result


def build_references_list_html(refs, ch_num):
    """Build the chapter-level reference list."""
    if not refs:
        return ''
    items = []
    for i, ref_text in enumerate(refs, 1):
        ref_html = ref_text
        ref_html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', ref_html)
        ref_html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', ref_html)
        # Convert markdown links [text](url) to HTML <a> tags
        ref_html = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<a href="\2" target="_blank" rel="noopener">\1</a>',
            ref_html
        )
        items.append(f'  <li id="ch{ch_num}-ref-{i}" value="{i}">{ref_html}</li>')
    return '<ol class="references-list">\n' + '\n'.join(items) + '\n</ol>'


# ---------------------------------------------------------------------------
# Markdown → HTML conversion
# ---------------------------------------------------------------------------

def md_to_html_content(md_text, ch_num, lang):
    """Convert markdown body to HTML sections."""
    lines = md_text.strip().split('\n')
    html_parts = []
    in_table = False
    in_code = False
    in_list = False
    in_blockquote = False
    list_type = None
    current_section_id = None
    bq_lines = []

    def flush_blockquote():
        nonlocal bq_lines, in_blockquote
        if bq_lines:
            content = '\n'.join(bq_lines)
            css_class = 'key-paper' if any(k in content for k in ['핵심 논문', 'Key Paper', '핵심 연구']) else ''
            html_parts.append(f'<blockquote class="{css_class}">{process_inline(content)}</blockquote>')
            bq_lines = []
            in_blockquote = False

    def flush_list():
        nonlocal in_list, list_type
        if in_list:
            tag = 'ol' if list_type == 'ol' else 'ul'
            html_parts.append(f'</{tag}>')
            in_list = False
            list_type = None

    def process_inline(text):
        math_placeholders = []

        def save_math(m):
            inner = m.group(1)
            if inner and inner[0].isdigit():
                return m.group(0)
            math_placeholders.append(m.group(0))
            return f'\x00MATH{len(math_placeholders)-1}\x00'
        text = re.sub(r'\$([^\$]+?)\$', save_math, text)

        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

        def inline_img(m):
            alt = m.group(1)
            src = m.group(2)
            # Survey-local (../../) or shared-registry (../../../../) paths
            # all land at the same docs/assets/figures/ output root.
            src = src.replace('../../../../assets/figures/', '../assets/figures/')
            src = src.replace('../../assets/figures/', '../assets/figures/')
            return f'<a href="{src}" target="_blank"><img src="{src}" alt="{alt}" loading="lazy" style="max-height:160px;width:auto;border-radius:8px;cursor:zoom-in"></a>'
        # Image alt text may contain `[Author, Year]` citations — allow inner `]`
        # so long as it is not followed by `(` (which would start the URL group).
        text = re.sub(r'!\[((?:[^\]]|\](?!\())*)\]\(([^)]+)\)', inline_img, text)

        text = re.sub(r'\[(#\d+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" class="post-link">[\1]</a>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

        def single_chapter_ref(m):
            ref_text = m.group(0)
            ch_match = re.search(r'Chapter\s+(\d+)', ref_text)
            if ch_match:
                ch = ch_match.group(1).zfill(2)
                return f'<a href="ch{ch}.html">{ref_text}</a>'
            return ref_text

        def chapter_ref_group(m):
            inner = m.group(1)
            result = re.sub(r'Chapter\s+\d+(?:\.\d+)?(?:\s*[^,)]*)?', single_chapter_ref, inner)
            return f'({result})'
        text = re.sub(r'\(([^)]*Chapter\s+\d[^)]*)\)', chapter_ref_group, text)

        def restore_math(m):
            idx = int(m.group(1))
            original = math_placeholders[idx]
            inner = original[1:-1]
            return f'<span class="math-inline">{inner}</span>'
        text = re.sub(r'\x00MATH(\d+)\x00', restore_math, text)
        return text

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith('$$') and stripped.endswith('$$') and len(stripped) > 4:
            flush_blockquote()
            flush_list()
            inner = stripped[2:-2]
            html_parts.append(f'<div class="math-block">{inner}</div>')
            continue

        if stripped.startswith('```'):
            if in_code:
                html_parts.append('</code></pre>')
                in_code = False
            else:
                flush_blockquote()
                flush_list()
                lang_match = re.match(r'```(\w+)', stripped)
                code_lang = lang_match.group(1) if lang_match else ''
                html_parts.append(f'<pre><code class="language-{code_lang}">')
                in_code = True
            continue

        if in_code:
            html_parts.append(line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
            continue

        if stripped.startswith('---') and not in_table:
            flush_blockquote()
            flush_list()
            html_parts.append('<hr>')
            continue

        if stripped.startswith('>'):
            flush_list()
            if in_table:
                html_parts.append('</tbody></table></div>')
                in_table = False
            content = stripped.lstrip('>').strip()
            if not in_blockquote:
                in_blockquote = True
                bq_lines = [content]
            else:
                bq_lines.append(content)
            continue
        elif in_blockquote:
            flush_blockquote()

        if not stripped:
            flush_list()
            if in_table:
                html_parts.append('</tbody></table></div>')
                in_table = False
            continue

        if stripped.startswith('# ') and not stripped.startswith('## '):
            continue

        if stripped.startswith('## '):
            flush_list()
            if in_table:
                html_parts.append('</tbody></table></div>')
                in_table = False
            title = stripped[3:].strip()
            sec_match = re.match(r'(\d+\.\d+)', title)
            if sec_match:
                sec_id = f'sec-{sec_match.group(1).replace(".", "-")}'
            else:
                sec_id = f'sec-{title.lower().replace(" ", "-")[:30]}'

            if current_section_id is not None:
                html_parts.append('</section>')

            current_section_id = sec_id
            html_parts.append(f'<section id="{sec_id}" class="content-section">')
            html_parts.append(f'<h2>{process_inline(title)}</h2>')
            continue

        if stripped.startswith('### '):
            flush_list()
            if in_table:
                html_parts.append('</tbody></table></div>')
                in_table = False
            title = stripped[4:].strip()
            html_parts.append(f'<h3>{process_inline(title)}</h3>')
            continue

        if stripped.startswith('#### '):
            flush_list()
            if in_table:
                html_parts.append('</tbody></table></div>')
                in_table = False
            title = stripped[5:].strip()
            html_parts.append(f'<h4>{process_inline(title)}</h4>')
            continue

        # Block-level image: allow inner `]` not followed by `(` so alt text can
        # contain `[Author, Year]` citations (inline_img at process_inline uses
        # the same widened pattern for the paragraph-level case).
        img_match = re.match(r'!\[((?:[^\]]|\](?!\())*)\]\(([^)]+)\)', stripped)
        if img_match:
            flush_list()
            caption = img_match.group(1)
            src = img_match.group(2)
            # Survey-local (../../) or shared-registry (../../../../) paths
            # all land at the same docs/assets/figures/ output root.
            src = src.replace('../../../../assets/figures/', '../assets/figures/')
            src = src.replace('../../assets/figures/', '../assets/figures/')
            src_dark = src.replace('_technical.png', '_darkmode.png')
            html_parts.append(f'<figure>')
            html_parts.append(f'  <a href="{src}" target="_blank"><img src="{src_dark}" alt="{caption}" loading="lazy" onerror="this.onerror=null;this.src=\'{src}\'" style="cursor:zoom-in"></a>')
            html_parts.append(f'  <figcaption>{process_inline(caption)}</figcaption>')
            html_parts.append(f'</figure>')
            continue

        if '|' in stripped and stripped.startswith('|'):
            if not in_table:
                flush_list()
                in_table = True
                # Wrap the table so .table-wrap can carry overflow-x:auto on
                # narrow viewports without forcing display:block on the table
                # itself (which would break table-layout:auto column sizing —
                # short-content columns dominated by their long headers).
                html_parts.append('<div class="table-wrap"><table class="styled-table">')
                cells = [c.strip() for c in stripped.split('|')[1:-1]]
                html_parts.append('<thead><tr>')
                for c in cells:
                    html_parts.append(f'<th>{process_inline(c)}</th>')
                html_parts.append('</tr></thead><tbody>')
            elif re.match(r'\|[\s\-:|]+\|', stripped):
                continue
            else:
                cells = [c.strip() for c in stripped.split('|')[1:-1]]
                html_parts.append('<tr>')
                for c in cells:
                    html_parts.append(f'<td>{process_inline(c)}</td>')
                html_parts.append('</tr>')
            continue
        elif in_table:
            html_parts.append('</tbody></table></div>')
            in_table = False

        if re.match(r'^[-*]\s', stripped):
            content = re.sub(r'^[-*]\s+', '', stripped)
            if not in_list or list_type != 'ul':
                flush_list()
                html_parts.append('<ul>')
                in_list = True
                list_type = 'ul'
            html_parts.append(f'<li>{process_inline(content)}</li>')
            continue

        ol_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
        if ol_match:
            content = ol_match.group(2)
            if not in_list or list_type != 'ol':
                flush_list()
                html_parts.append('<ol>')
                in_list = True
                list_type = 'ol'
            html_parts.append(f'<li>{process_inline(content)}</li>')
            continue

        flush_list()
        html_parts.append(f'<p>{process_inline(stripped)}</p>')

    flush_blockquote()
    flush_list()
    if in_table:
        html_parts.append('</tbody></table></div>')
    if in_code:
        html_parts.append('</code></pre>')
    if current_section_id is not None:
        html_parts.append('</section>')

    return '\n'.join(html_parts)


def extract_sections(md_text, ch_num):
    """Extract section titles for sidebar navigation."""
    sections = []
    for line in md_text.split('\n'):
        line = line.strip()
        if line.startswith('## ') and not line.startswith('### '):
            title = line[3:].strip()
            sec_match = re.match(r'(\d+\.\d+)', title)
            if sec_match:
                sec_id = f'sec-{sec_match.group(1).replace(".", "-")}'
            else:
                sec_id = f'sec-{title.lower().replace(" ", "-")[:30]}'
            sections.append({"id": sec_id, "title": title})
    return sections


def build_sidebar(sections, part_num):
    """Build sidebar navigation HTML."""
    if not sections:
        return ''
    dots = []
    for i, sec in enumerate(sections):
        active = ' active' if i == 0 else ''
        label = sec['title']
        if len(label) > 35:
            label = label[:35] + '...'
        dots.append(f'    <a class="nav-dot{active}" data-section="{sec["id"]}">\n'
                     f'      <span class="dot"></span>\n'
                     f'      <span class="label">{label}</span>\n'
                     f'    </a>')
    return f'  <nav class="sidebar-nav part-{part_num}">\n' + '\n'.join(dots) + '\n  </nav>'


# ---------------------------------------------------------------------------
# Chapter HTML builder
# ---------------------------------------------------------------------------

def build_chapter_html(ch_num, lang, chapters_meta, book_dir, lang_code, num_chapters):
    """Build a complete chapter HTML page."""
    md_path = os.path.join(book_dir, f'ch{ch_num:02d}.md')
    if not os.path.exists(md_path):
        print(f"  WARNING: {md_path} not found, skipping")
        return None

    with open(md_path, 'r', encoding='utf-8') as f:
        md = f.read()

    meta, body = parse_frontmatter(md)
    ch_meta = chapters_meta[ch_num]
    part_num = ch_meta['part_num']
    part_label = ch_meta['part']
    title = ch_meta['title']

    date = meta.get('date', '2026-04-07')
    last_updated = meta.get('last_updated', '2026-04-07')

    if lang_code == 'ko':
        date_label = '집필일'
        updated_label = '최종수정일'
        toc_label = '목록'
    else:
        date_label = 'Written'
        updated_label = 'Last updated'
        toc_label = 'Index'

    if ch_num > 1:
        prev_link = f'<a href="ch{ch_num-1:02d}.html" class="prev">&larr; Ch.{ch_num-1}</a>'
    else:
        prev_link = '<span class="placeholder"></span>'

    toc_link = f'<a href="./" class="toc-link">{toc_label}</a>'

    if ch_num < num_chapters:
        next_link = f'<a href="ch{ch_num+1:02d}.html" class="next">Ch.{ch_num+1} &rarr;</a>'
    else:
        next_link = '<span class="placeholder"></span>'

    chapter_nav_html = f'''      <nav class="chapter-nav">
        {prev_link}
        {toc_link}
        {next_link}
      </nav>'''

    cite_map, ref_list = build_citation_map(body)

    body_content = body
    for marker in ['## 참고문헌', '## References']:
        idx = body.find(marker)
        if idx != -1:
            body_content = body[:idx]
            break

    content_html = md_to_html_content(body_content, ch_num, lang)
    content_html = replace_citations_with_links(content_html, cite_map, ch_num, ref_list)

    ref_section_title = '참고문헌' if lang == 'ko' else 'References'
    ref_html = ''
    if ref_list:
        ref_html = f'<section id="sec-references" class="content-section">\n'
        ref_html += f'<h2>{ref_section_title}</h2>\n'
        ref_html += build_references_list_html(ref_list, ch_num)
        ref_html += '\n</section>'

    content_html = content_html + '\n' + chapter_nav_html + '\n' + ref_html

    sections = extract_sections(body, ch_num)
    sidebar_html = build_sidebar(sections, part_num)

    html = f'''<!DOCTYPE html>
<html lang="{lang_code}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chapter {ch_num}: {title}</title>
  <link rel="stylesheet" href="../css/style.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
</head>
<body{' class="lang-en"' if lang_code == 'en' else ''}>
  <canvas id="particle-canvas"></canvas>

  <header id="site-header"></header>
  <script src="../js/header.js"></script>

  <main class="chapter-page part-{part_num}">
{sidebar_html}

    <article class="chapter-content">
      <header class="chapter-header">
        <span class="part-label">{part_label}</span>
        <h1>Chapter {ch_num}: {title}</h1>
        <div class="chapter-meta">
          <span>{date_label}: {date}</span>
          <span>{updated_label}: {last_updated}</span>
        </div>
      </header>

{content_html}

{chapter_nav_html}
    </article>
  </main>

  <footer id="site-footer"></footer>
  <script src="../js/footer.js"></script>

  <script src="../js/main.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
  <script src="../js/chapter.js"></script>
  <script>
    document.addEventListener("DOMContentLoaded", function() {{
      if (typeof katex !== 'undefined') {{
        document.querySelectorAll('.math-inline').forEach(function(el) {{
          katex.render(el.textContent, el, {{ throwOnError: false, displayMode: false }});
        }});
        document.querySelectorAll('.math-block').forEach(function(el) {{
          katex.render(el.textContent, el, {{ throwOnError: false, displayMode: true }});
        }});
      }}
    }});
  </script>
</body>
</html>'''

    return html


# ---------------------------------------------------------------------------
# BibTeX & References page
# ---------------------------------------------------------------------------

def parse_bib(bib_path):
    """Parse BibTeX file into list of references."""
    refs = []
    with open(bib_path, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = re.findall(r'@\w+\{([^,]+),([^@]+)', content)
    for key, body in entries:
        ref = {'key': key.strip()}
        for field in ['title', 'author', 'year', 'journal', 'booktitle', 'url']:
            match = re.search(rf'{field}\s*=\s*\{{(.+?)\}}', body)
            if match:
                ref[field] = match.group(1).strip()
        if 'title' in ref:
            refs.append(ref)
    return refs


def collect_all_chapter_refs(book_dir):
    """Collect all references from all chapters, deduplicated."""
    all_refs = []
    seen_keys = set()

    for fname in sorted(os.listdir(book_dir)):
        if not fname.startswith('ch') or not fname.endswith('.md'):
            continue
        with open(os.path.join(book_dir, fname), 'r', encoding='utf-8') as f:
            content = f.read()

        ref_section = None
        for marker in ['## 참고문헌', '## References']:
            idx = content.find(marker)
            if idx != -1:
                ref_section = content[idx:]
                break
        if not ref_section:
            continue

        for line in ref_section.split('\n'):
            m = re.match(r'^\d+\.\s+(.+)', line.strip())
            if m:
                ref_text = m.group(1).strip()
                # Dedup key: first 80 chars lowercase (catches same paper across chapters)
                key = re.sub(r'\s+', ' ', ref_text[:80]).lower()
                if key not in seen_keys:
                    seen_keys.add(key)
                    all_refs.append(ref_text)

    return all_refs


def build_references_html(config, lang_code, bib_path, book_dir=None):
    """Build consolidated references page from all chapter references."""
    # Collect refs from all chapters (primary source)
    chapter_refs = []
    if book_dir and os.path.isdir(book_dir):
        chapter_refs = collect_all_chapter_refs(book_dir)

    # Also parse BibTeX for any additional refs not in chapters
    bib_refs = []
    if os.path.exists(bib_path):
        bib_refs = parse_bib(bib_path)

    if lang_code == 'ko':
        page_title = '통합 참고문헌 (References)'
    else:
        page_title = 'Consolidated References'

    ref_items = []

    if chapter_refs:
        # Use chapter refs as primary (they include [scholar] links etc.)
        for i, ref_text in enumerate(chapter_refs, 1):
            ref_html = ref_text
            ref_html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', ref_html)
            ref_html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', ref_html)
            # Convert markdown links to HTML
            ref_html = re.sub(
                r'\[([^\]]+)\]\(([^)]+)\)',
                r'<a href="\2" target="_blank" rel="noopener">\1</a>',
                ref_html
            )
            ref_items.append(
                f'<div class="ref-item" id="consolidated-ref-{i}">'
                f'<span class="ref-id">[{i}]</span> '
                f'{ref_html}'
                f'</div>'
            )
    else:
        # Fallback to BibTeX
        for i, ref in enumerate(bib_refs, 1):
            authors = ref.get('author', 'Unknown')
            year = ref.get('year', '')
            title = ref.get('title', '')
            venue = ref.get('journal', ref.get('booktitle', ''))
            url = ref.get('url', '')
            url_html = f' <a href="{url}" target="_blank" rel="noopener">[Link]</a>' if url else ''
            ref_items.append(
                f'<div class="ref-item" id="ref-{ref["key"]}">'
                f'<span class="ref-id">[{i}]</span> '
                f'{authors} ({year}). <strong>{title}</strong>. <em>{venue}</em>.{url_html}'
                f'</div>'
            )

    total_refs = len(ref_items)
    content = '\n'.join(ref_items)

    # Acknowledgment from config
    ack_key = 'ko' if lang_code == 'ko' else 'en'
    ack_lines = config.get('acknowledgment', {}).get(ack_key, [])
    ack_html = ''
    if ack_lines:
        ack_title = '감사의 글' if lang_code == 'ko' else 'Acknowledgment'
        ack_paragraphs = '\n'.join(f'        <p>{line}</p>' for line in ack_lines)
        harness_line = ('이 프로젝트는 황민호님의 <a href="https://github.com/revfactory/harness">Harness</a> 스킬을 이용하여 제작되었습니다.'
                        if lang_code == 'ko'
                        else 'This project was built using the <a href="https://github.com/revfactory/harness">Harness</a> skill by Minho Hwang.')
        ai_line = ('이 저작물의 제작에 AI 도구가 활용되었습니다. 문헌 조사, 콘텐츠 생성, 원고 작성에 Claude(Opus 4.6)를 사용하였습니다.'
                   if lang_code == 'ko'
                   else 'AI tools were used in the production of this work: Claude (Opus 4.6) for literature survey, content generation, and manuscript preparation.')
        ack_html = f'''
      <section class="acknowledgment-section">
        <h2>{ack_title}</h2>
{ack_paragraphs}
        <p>{harness_line}</p>
        <p>{ai_line}</p>
      </section>'''

    html = f'''<!DOCTYPE html>
<html lang="{lang_code}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <link rel="stylesheet" href="../css/style.css">
</head>
<body{' class="lang-en"' if lang_code == 'en' else ''}>
  <canvas id="particle-canvas"></canvas>

  <header id="site-header"></header>
  <script src="../js/header.js"></script>

  <main>
    <div class="references-section">
      <header class="chapter-header">
        <h1>{page_title}</h1>
        <p class="chapter-summary">{total_refs} references</p>
      </header>
{content}
{ack_html}
    </div>
  </main>

  <footer id="site-footer"></footer>
  <script src="../js/footer.js"></script>

  <script src="../js/main.js"></script>
</body>
</html>'''

    return html


# ---------------------------------------------------------------------------
# Glossary page (optional, enabled by features.glossary)
# ---------------------------------------------------------------------------

def build_glossary_html(lang_code, book_dir):
    """Build glossary page."""
    md_path = os.path.join(book_dir, 'glossary.md')
    if not os.path.exists(md_path):
        return None

    with open(md_path, 'r', encoding='utf-8') as f:
        md = f.read()

    meta, body = parse_frontmatter(md)

    if lang_code == 'ko':
        page_title = '용어집 (Glossary)'
    else:
        page_title = 'Glossary'

    content_lines = []
    for line in body.strip().split('\n'):
        stripped = line.strip()
        if stripped.startswith('# '):
            continue
        if stripped.startswith('## '):
            letter = stripped[3:].strip()
            content_lines.append(f'<h2 class="glossary-letter">{letter}</h2>')
        elif stripped.startswith('- **'):
            text = stripped[2:]
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            content_lines.append(f'<div class="glossary-item">{text}</div>')
        elif stripped:
            content_lines.append(f'<p>{stripped}</p>')

    content = '\n'.join(content_lines)

    toc_label = '← 목차로' if lang_code == 'ko' else '← Back to contents'
    back_nav = f'''      <nav class="chapter-nav">
        <a href="./" class="toc-link">{toc_label}</a>
      </nav>'''

    html = f'''<!DOCTYPE html>
<html lang="{lang_code}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <link rel="stylesheet" href="../css/style.css">
</head>
<body{' class="lang-en"' if lang_code == 'en' else ''}>
  <canvas id="particle-canvas"></canvas>

  <header id="site-header"></header>
  <script src="../js/header.js"></script>

  <main>
    <div class="glossary-section">
      <header class="chapter-header">
        <h1>{page_title}</h1>
      </header>
{content}
{back_nav}
    </div>
  </main>

  <footer id="site-footer"></footer>
  <script src="../js/footer.js"></script>

  <script src="../js/main.js"></script>
</body>
</html>'''

    return html


# ---------------------------------------------------------------------------
# Index & TOC pages (data-driven from config)
# ---------------------------------------------------------------------------

def build_index_html(config):
    """Build root index.html with language auto-detection."""
    title = config['short_title']['en']
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="css/style.css">
  <script>
    (function() {{
      var lang = localStorage.getItem('preferred-lang');
      if (lang === 'en') {{ window.location.replace('en/'); return; }}
      if (lang === 'ko') {{ window.location.replace('ko/'); return; }}
      var browserLang = (navigator.language || navigator.userLanguage || '').toLowerCase();
      if (browserLang.startsWith('ko')) {{
        localStorage.setItem('preferred-lang', 'ko');
        window.location.replace('ko/');
      }} else {{
        localStorage.setItem('preferred-lang', 'en');
        window.location.replace('en/');
      }}
    }})();
  </script>
</head>
<body>
  <canvas id="particle-canvas"></canvas>

  <main class="lang-landing">
    <h1 class="gradient-text">{title}</h1>
    <p style="color: var(--text-secondary); font-size: 1.1rem; max-width: 600px; text-align: center; line-height: 1.8;">
      {config['subtitle']['en']}
    </p>

    <div class="lang-options">
      <a href="ko/" class="lang-option">
        <span class="lang-flag">&#x1F1F0;&#x1F1F7;</span>
        <span class="lang-name">&#xD55C;&#xAD6D;&#xC5B4;</span>
        <span class="lang-sub">Korean</span>
      </a>
      <a href="en/" class="lang-option">
        <span class="lang-flag">&#x1F1FA;&#x1F1F8;</span>
        <span class="lang-name">English</span>
        <span class="lang-sub">English</span>
      </a>
    </div>
  </main>

  <script src="js/main.js"></script>
</body>
</html>
'''


def build_toc_html(config, lang_code):
    """Build table of contents page from config data."""
    lang = 'ko' if lang_code == 'ko' else 'en'
    title = config['title'][lang]
    subtitle = config['subtitle'][lang]
    description = config['description'][lang]
    dates = config.get('dates', {})
    first_pub = dates.get('first_published', '')
    last_upd = dates.get('last_updated', '')

    # Optional cover image above the title. Path is relative to docs/{lang}/,
    # so for a file at surveys/<slug>/assets/cover.jpg we use ../assets/cover.jpg.
    cover_path = config.get('cover_image', '').strip()
    cover_html = ''
    if cover_path:
        cover_alt = title
        cover_html = (
            f'      <div class="hero-cover">\n'
            f'        <img src="{cover_path}" alt="{cover_alt}" loading="eager">\n'
            f'      </div>\n'
        )

    start_text = '읽기 시작' if lang_code == 'ko' else 'Start Reading'

    # Highlights
    highlights = config.get('highlights', {}).get(lang, [])
    highlight_items = ''
    for h in highlights:
        highlight_items += f'''        <div class="intro-item">
          <span class="item-icon">{h['icon']}</span>
          <div class="intro-item-content">
            <h4>{h['title']}</h4>
            <p>{h['desc']}</p>
          </div>
        </div>
'''

    # Chapter grid
    parts_html = ''
    for part_idx, part in enumerate(config['parts'], 1):
        part_num = part.get('part_num_override', part_idx)
        part_name = part['name'][lang]
        chapters_html = ''
        for ch in part['chapters']:
            num_str = f'{ch["num"]:02d}'
            ch_title = ch['title'][lang]
            ch_summary = ch.get('summary', {}).get(lang, '')
            chapters_html += f'''          <a href="ch{num_str}.html" class="chapter-card fade-in">
            <span class="ch-num">{num_str}</span>
            <h3>{ch_title}</h3>
            <p>{ch_summary}</p>
            <span class="arrow">&rarr;</span>
          </a>
'''

        parts_html += f'''      <div class="part-group part-{part_num}">
        <h2 class="part-title">{part_name}</h2>
        <div class="chapter-grid">
{chapters_html}        </div>
      </div>

'''

    # Appendix: references link (+ glossary link if enabled)
    ref_label = '통합 참고문헌 (References)' if lang_code == 'ko' else 'Consolidated References'
    ref_summary = '전체 참고문헌 목록' if lang_code == 'ko' else 'Full bibliography'
    appendix_label = '부록 (Appendices)' if lang_code == 'ko' else 'Appendices'

    glossary_card = ''
    if config.get('features', {}).get('glossary', False):
        gl_label = '용어집 (Glossary)' if lang_code == 'ko' else 'Glossary'
        gl_summary = '핵심 용어 정의' if lang_code == 'ko' else 'Key term definitions'
        glossary_card = f'''          <a href="glossary.html" class="chapter-card fade-in">
            <span class="ch-num">G</span>
            <h3>{gl_label}</h3>
            <p>{gl_summary}</p>
            <span class="arrow">&rarr;</span>
          </a>
'''

    parts_html += f'''      <div class="part-group part-2">
        <h2 class="part-title">{appendix_label}</h2>
        <div class="chapter-grid">
{glossary_card}          <a href="references.html" class="chapter-card fade-in">
            <span class="ch-num">A</span>
            <h3>{ref_label}</h3>
            <p>{ref_summary}</p>
            <span class="arrow">&rarr;</span>
          </a>
        </div>
      </div>
'''

    html = f'''<!DOCTYPE html>
<html lang="{lang_code}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="../css/style.css">
</head>
<body{' class="lang-en"' if lang_code == 'en' else ''}>
  <canvas id="particle-canvas"></canvas>

  <header id="site-header"></header>
  <script src="../js/header.js"></script>

  <main>
    <!-- Hero -->
    <section class="hero">
{cover_html}      <h1 class="gradient-text">{config['short_title'][lang]}</h1>
      <p class="subtitle">{subtitle}</p>
      <p class="description">{description}</p>
      <p class="hero-dates" style="color: var(--text-muted); font-size: 0.9rem; margin-top: 0.5rem;">
        <span>First published: {first_pub}</span>
        <span style="margin: 0 0.5rem;">|</span>
        <span>Last updated: {last_upd}</span>
      </p>
      <div class="hero-cta">
        <a href="ch01.html" class="btn-primary">{start_text}</a>
      </div>
    </section>

    <!-- Intro Cards -->
    <section class="intro-section">
      <div class="intro-list">
{highlight_items}      </div>
    </section>

    <!-- Chapter Grid -->
    <section class="chapters-section">
{parts_html}
    </section>
  </main>

  <footer id="site-footer"></footer>
  <script src="../js/footer.js"></script>

  <script src="../js/main.js"></script>
</body>
</html>
'''

    return html


# ---------------------------------------------------------------------------
# CSS/JS copy with placeholder replacement
# ---------------------------------------------------------------------------

def write_headers(docs_dir):
    """Write Cloudflare Pages _headers for static-asset caching.

    HTML stays no-cache so chapter edits ship instantly. CSS/JS file names
    are not content-hashed, so cap at 1h. /assets/* covers figures and
    cover images — 24h is conservative enough that figure swaps appear
    within a day, while removing per-request revalidate roundtrips.
    """
    content = (
        "/*.html\n"
        "  Cache-Control: public, max-age=0, must-revalidate\n"
        "\n"
        "/css/*\n"
        "  Cache-Control: public, max-age=3600\n"
        "\n"
        "/js/*\n"
        "  Cache-Control: public, max-age=3600\n"
        "\n"
        "/assets/*\n"
        "  Cache-Control: public, max-age=86400\n"
    )
    out_path = os.path.join(docs_dir, '_headers')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Created: _headers")


def copy_shared_assets(config, shared_dir, docs_dir):
    """Copy shared CSS/JS to survey docs, replacing placeholders in header.js."""
    css_src = os.path.join(shared_dir, 'css')
    css_dst = os.path.join(docs_dir, 'css')
    if os.path.exists(css_dst):
        shutil.rmtree(css_dst)
    shutil.copytree(css_src, css_dst)

    js_src = os.path.join(shared_dir, 'js')
    js_dst = os.path.join(docs_dir, 'js')
    if os.path.exists(js_dst):
        shutil.rmtree(js_dst)
    os.makedirs(js_dst, exist_ok=True)

    github_url = f'https://github.com/{config["github_repo"]}'
    site_title = config['short_title']['en']

    for fname in os.listdir(js_src):
        src_path = os.path.join(js_src, fname)
        dst_path = os.path.join(js_dst, fname)
        with open(src_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace('{{GITHUB_URL}}', github_url)
        content = content.replace('{{SITE_TITLE}}', site_title)
        with open(dst_path, 'w', encoding='utf-8') as f:
            f.write(content)


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def build_survey(config, survey_dir, shared_dir):
    """Build a complete survey site from config and content."""
    config, chapters_ko, chapters_en, num_chapters = load_config(survey_dir)

    docs_dir = os.path.join(survey_dir, 'docs')
    book_ko = os.path.join(survey_dir, 'book', 'ko')
    book_en = os.path.join(survey_dir, 'book', 'en')
    bib_path = os.path.join(survey_dir, 'book', 'references.bib')

    # Ensure output directories
    for d in ['ko', 'en', 'css', 'js', os.path.join('assets', 'figures')]:
        os.makedirs(os.path.join(docs_dir, d), exist_ok=True)

    # Copy shared CSS/JS
    print("Copying shared assets...")
    copy_shared_assets(config, shared_dir, docs_dir)

    glossary_enabled = config.get('features', {}).get('glossary', False)

    # Build KO chapters
    print("Building Korean chapters...")
    for ch in sorted(chapters_ko.keys()):
        html = build_chapter_html(ch, 'ko', chapters_ko, book_ko, 'ko', num_chapters)
        if html:
            out_path = os.path.join(docs_dir, 'ko', f'ch{ch:02d}.html')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"  Created: ko/ch{ch:02d}.html")

    # Build EN chapters
    print("Building English chapters...")
    for ch in sorted(chapters_en.keys()):
        html = build_chapter_html(ch, 'en', chapters_en, book_en, 'en', num_chapters)
        if html:
            out_path = os.path.join(docs_dir, 'en', f'ch{ch:02d}.html')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"  Created: en/ch{ch:02d}.html")

    # Build References (consolidated from all chapters)
    print("Building references...")
    for lang_code in ['ko', 'en']:
        lang_book_dir = book_ko if lang_code == 'ko' else book_en
        html = build_references_html(config, lang_code, bib_path, book_dir=lang_book_dir)
        out_path = os.path.join(docs_dir, lang_code, 'references.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  Created: {lang_code}/references.html")
    if not os.path.exists(bib_path):
        print("  WARNING: references.bib not found, skipping references page")

    # Build Glossary (if enabled)
    if config.get('features', {}).get('glossary', False):
        print("Building glossary...")
        for lang_code in ['ko', 'en']:
            book_dir = book_ko if lang_code == 'ko' else book_en
            html = build_glossary_html(lang_code, book_dir)
            if html:
                out_path = os.path.join(docs_dir, lang_code, 'glossary.html')
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"  Created: {lang_code}/glossary.html")

    # Build index pages
    print("Building index pages...")
    with open(os.path.join(docs_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build_index_html(config))
    print("  Created: index.html")

    with open(os.path.join(docs_dir, 'ko', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build_toc_html(config, 'ko'))
    print("  Created: ko/index.html")

    with open(os.path.join(docs_dir, 'en', 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build_toc_html(config, 'en'))
    print("  Created: en/index.html")

    # Copy cover image (if present) from assets/cover.* → docs/assets/.
    # Referenced from index.html as ../assets/cover.<ext>. Skipped silently
    # when absent so existing surveys without a cover build unaffected.
    src_assets = os.path.join(survey_dir, 'assets')
    dst_assets = os.path.join(docs_dir, 'assets')
    os.makedirs(dst_assets, exist_ok=True)
    if os.path.isdir(src_assets):
        for fname in os.listdir(src_assets):
            if fname.startswith('cover.') and fname.lower().endswith(
                ('.png', '.jpg', '.jpeg', '.webp', '.svg')
            ):
                shutil.copy2(
                    os.path.join(src_assets, fname),
                    os.path.join(dst_assets, fname),
                )
                print(f"  Copied cover: {fname}")

    # Copy figures: survey-local first, then overlay shared registry.
    # Shared figures (<sourceSlug>_figN.<ext>, no chapter prefix) live at
    # <monorepo-root>/assets/figures/ and are reused by any survey whose
    # chapters reference them via the relative path
    # ../../../../assets/figures/<file>. The output path in docs/ stays
    # the same (docs/assets/figures/<file>) so build chapter links
    # resolve regardless of source.
    print("Copying figures...")
    src_figures = os.path.join(survey_dir, 'assets', 'figures')
    dst_figures = os.path.join(docs_dir, 'assets', 'figures')
    if os.path.exists(src_figures):
        if os.path.exists(dst_figures):
            shutil.rmtree(dst_figures)
        shutil.copytree(src_figures, dst_figures)
        print(f"  Copied survey figures to docs/assets/figures/")
    monorepo_root = os.path.dirname(os.path.dirname(os.path.abspath(survey_dir)))
    shared_figures = os.path.join(monorepo_root, 'assets', 'figures')
    if os.path.isdir(shared_figures):
        os.makedirs(dst_figures, exist_ok=True)
        copied = 0
        allowed_ext = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.pdf')
        for fname in os.listdir(shared_figures):
            src = os.path.join(shared_figures, fname)
            if not os.path.isfile(src):
                continue
            if not fname.lower().endswith(allowed_ext):
                continue
            shutil.copy2(src, os.path.join(dst_figures, fname))
            copied += 1
        if copied:
            print(f"  Overlaid {copied} shared figure(s) from monorepo assets/figures/")

    # Cloudflare Pages cache headers (additive — does not affect _redirects)
    print("Writing _headers...")
    write_headers(docs_dir)

    print("\nBuild complete!")
    total = 0
    for root, dirs, files in os.walk(docs_dir):
        total += len([f for f in files if f.endswith('.html')])
    print(f"Total HTML files: {total}")
