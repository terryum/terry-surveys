#!/usr/bin/env python3
"""Build and query a lightweight reference index across all surveys.

Primary matching signal is **Tier 1 exact identifier match** (arXiv ID, DOI,
Nature article ID). When both the homepage post and the survey reference
carry the same paper identifier, the link is unambiguous — no false
positives, no dependency on a hand-curated keyword whitelist. The legacy
slug-token fuzzy matcher is kept as a low-confidence fallback that is
reported separately so callers can require human review before acting.

Usage:
    python3 bibtex/refs_index.py build          # Rebuild survey refs index
    python3 bibtex/refs_index.py build-posts    # Rebuild posts index (terryum-ai)
    python3 bibtex/refs_index.py build-all      # Both
    python3 bibtex/refs_index.py search "pi0"   # Search by keyword
    python3 bibtex/refs_index.py match <slug>   # Match a post slug to survey refs
                                                # (Tier 1 exact + Tier 3 fuzzy fallback)

All generated artifacts (refs_index.json, posts_index.json) are written
under bibtex/, alongside the master references.bib that is the canonical
home for reference-management files in this monorepo.
"""

import re
import os
import json
import sys
from urllib.parse import quote_plus

# Module-level cache for the bibtex master lookup. Populated lazily on first
# call to load_bibtex_master() so callers that only need search/match (no
# full rebuild) do not pay the parse cost.
_BIBTEX_LOOKUP_CACHE = None

# This script lives in bibtex/, the canonical home for every
# reference-management artifact (master references.bib, generated indices,
# matching tools). Paths below reflect that placement.
BIBTEX_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BIBTEX_DIR)
SURVEYS_DIR = os.path.join(ROOT, 'surveys')
INDEX_PATH = os.path.join(BIBTEX_DIR, 'refs_index.json')
POSTS_INDEX_PATH = os.path.join(BIBTEX_DIR, 'posts_index.json')
HOMEPAGE_POSTS_DIR = os.path.join(
    os.path.dirname(ROOT), 'terryum-ai', 'posts', 'papers'
)

# --------------------------------------------------------------------
# Tier 1 identifier extractors — exact-match signals
# --------------------------------------------------------------------
# arXiv IDs: "2412.14482", "2412.14482v1", with or without prefix
ARXIV_URL_RE = re.compile(
    r'arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?', re.IGNORECASE
)
ARXIV_BARE_RE = re.compile(
    r'\b(?:arXiv:)?(\d{4}\.\d{4,5})(?:v\d+)?\b', re.IGNORECASE
)
# Nature article IDs: s41467-025-57741-6, s44182-026-00079-y, etc.
NATURE_ARTICLE_RE = re.compile(
    r'nature\.com/articles/(s\d+-\d+-\d+-[\d\-a-z]+)', re.IGNORECASE
)
# Generic DOI: 10.xxxx/anything (captures until whitespace or closing bracket)
DOI_RE = re.compile(r'\b(10\.\d{4,9}/[^\s)\]]+)', re.IGNORECASE)


def extract_paper_ids(text):
    """Extract Tier 1 identifiers (arXiv/DOI/Nature) from any text blob.

    Returns a dict with three lists. All identifiers are lowercased and
    trailing punctuation trimmed so that the same paper referenced in two
    places produces identical IDs.
    """
    ids = {'arxiv': set(), 'doi': set(), 'nature': set()}
    if not text:
        return {k: [] for k in ids}

    for m in ARXIV_URL_RE.findall(text):
        ids['arxiv'].add(m.lower())
    for m in ARXIV_BARE_RE.findall(text):
        # Guard against false hits like year "2025.12345" in text.
        # arXiv IDs use YYMM.NNNNN and started at 0704 (April 2007),
        # so month part (chars 3-4) must be 01..12.
        month = int(m[2:4])
        if 1 <= month <= 12:
            ids['arxiv'].add(m.lower())
    for m in NATURE_ARTICLE_RE.findall(text):
        ids['nature'].add(m.lower().rstrip('-.,'))
    for m in DOI_RE.findall(text):
        clean = m.rstrip('.,)]').lower()
        if len(clean) < 150:
            ids['doi'].add(clean)
            # Nature DOIs (10.1038/sNNNNN-YYYY-NNNNN-N) carry the same article
            # suffix that nature.com uses; cross-populate the Nature set so
            # a reference citing the DOI URL still matches a post citing
            # the nature.com article URL (and vice versa).
            suffix = clean.split('/', 1)[-1] if '/' in clean else ''
            if re.match(r'^s\d+-\d+-\d+-[\d\-a-z]+$', suffix):
                ids['nature'].add(suffix)

    # Same bridge in the opposite direction: a nature.com ID seen on its own
    # implies the matching 10.1038/<id> DOI (Nature journals use this
    # deterministic mapping).
    for nid in list(ids['nature']):
        ids['doi'].add(f'10.1038/{nid}')

    return {k: sorted(v) for k, v in ids.items()}


def normalize_title(title):
    """Lowercase, alphanumeric-only, whitespace-collapsed title for matching."""
    if not title:
        return ''
    t = title.lower()
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# --------------------------------------------------------------------
# Bibtex master enrichment — recover IDs when ref text omits them
# --------------------------------------------------------------------
# Lightweight bibtex parser. Captures the fields we use for ID enrichment:
# title, author, year, url, note, doi, journal, booktitle. Sufficient for
# our purposes; not a full bibtex grammar.
_BIBTEX_ENTRY_RE = re.compile(r'@(\w+)\s*\{\s*([^,\s]+)\s*,([\s\S]*?)\n\}', re.MULTILINE)
_BIBTEX_FIELD_RE = re.compile(r'(\w+)\s*=\s*[{"]([\s\S]*?)["}]\s*,?\s*\n', re.MULTILINE)


def parse_bibtex_master(bibtex_path):
    """Parse master references.bib into a list of entry dicts.

    Each entry: {key, type, title, year, author, url, note, doi, journal,
    booktitle, ...}. Custom fields preserved verbatim for downstream tools.
    """
    if not os.path.isfile(bibtex_path):
        return []
    with open(bibtex_path, 'r', encoding='utf-8') as f:
        text = f.read()

    entries = []
    for m in _BIBTEX_ENTRY_RE.finditer(text):
        entry_type, key, body = m.group(1), m.group(2), m.group(3) + '\n'
        fields = {'key': key.strip(), 'type': entry_type.lower()}
        for fm in _BIBTEX_FIELD_RE.finditer(body):
            fields[fm.group(1).lower()] = re.sub(r'\s+', ' ', fm.group(2)).strip()
        entries.append(fields)
    return entries


def _bibtex_first_author_lastname(author_field):
    """Return lowercase last name of the first author from a bibtex author field.

    Handles both "Last, First and Last2, First2" and "First Last and First2 Last2".
    """
    if not author_field:
        return ''
    first = author_field.split(' and ')[0].strip()
    if ',' in first:
        return first.split(',', 1)[0].strip().lower()
    parts = first.split()
    return parts[-1].strip().lower() if parts else ''


def _bibtex_extract_ids(entry):
    """Pull arxiv/doi/nature IDs out of a bibtex entry's url/note/doi fields."""
    blob_parts = [entry.get('url', ''), entry.get('note', ''), entry.get('doi', ''),
                  entry.get('eprint', ''), entry.get('archiveprefix', '')]
    return extract_paper_ids(' '.join(p for p in blob_parts if p))


def load_bibtex_master(force_reload=False):
    """Load + index the master bibtex. Cached after first call.

    Returns dict with:
      - by_title: normalized_title -> entry
      - by_author_year: (lastname_lc, year_str) -> [entries]
      - by_arxiv: arxiv_id -> entry
      - by_doi: doi -> entry
      - by_key: bibtex_key -> entry
    """
    global _BIBTEX_LOOKUP_CACHE
    if _BIBTEX_LOOKUP_CACHE is not None and not force_reload:
        return _BIBTEX_LOOKUP_CACHE

    bibtex_path = os.path.join(BIBTEX_DIR, 'references.bib')
    entries = parse_bibtex_master(bibtex_path)

    by_title = {}
    by_author_year = {}
    by_arxiv = {}
    by_doi = {}
    by_key = {}

    # First pass: parse IDs for every entry.
    for e in entries:
        e['_ids'] = _bibtex_extract_ids(e)
        by_key[e['key']] = e

    # Second pass: union IDs across duplicate-titled entries. The master
    # bibtex sometimes carries two keys for the same paper (e.g.
    # xu2025dexumi without url + xu2025dexumib with arxiv url). Without
    # this union, refs that match by title to the lighter entry would
    # never recover the IDs the heavier sibling holds.
    title_to_entries = {}
    for e in entries:
        nt = normalize_title(e.get('title', ''))
        if nt:
            title_to_entries.setdefault(nt, []).append(e)

    for nt, group in title_to_entries.items():
        # Union all IDs across entries sharing this normalized title and
        # write the union back onto each member, so any later by_title /
        # by_author_year hit retrieves the full ID set.
        union_ids = {'arxiv': set(), 'doi': set(), 'nature': set()}
        for e in group:
            for k in union_ids:
                union_ids[k].update(e['_ids'].get(k, []))
        union_ids = {k: sorted(v) for k, v in union_ids.items()}
        for e in group:
            e['_ids'] = union_ids
        # Heaviest entry (most ID coverage, then with url) becomes the
        # by_title canonical so consumers reading entry.url get a usable link.
        def weight(e):
            return (
                len(e['_ids'].get('arxiv', [])) + len(e['_ids'].get('doi', [])),
                1 if e.get('url') else 0,
                len(e.get('note', '')),
            )
        by_title[nt] = max(group, key=weight)

    # Cross-key fuzzy merge: same first author + year + ≥50% title token
    # overlap → very likely the same paper under two bibtex keys (the
    # DexUMI failure mode: xu2025dexumi has no url, xu2025dexumib has the
    # arxiv url, both for arxiv:2505.21864). Union the IDs across such
    # clusters so the lighter sibling can heal via the heavier one.
    BIBTEX_TITLE_STOP = frozenset({
        'the', 'a', 'an', 'of', 'for', 'in', 'on', 'to', 'and', 'or', 'with',
        'via', 'from', 'by', 'is', 'as', 'at', 'we', 'our', 'be', 'are', 'can',
        'this', 'that', 'these', 'those', 'their', 'using', 'use', 'used',
    })

    def _significant_tokens(nt_str):
        return {t for t in nt_str.split() if len(t) >= 4 and t not in BIBTEX_TITLE_STOP}

    by_first_author_year = {}
    for e in entries:
        last = _bibtex_first_author_lastname(e.get('author', ''))
        year = e.get('year', '').strip()
        if last and year:
            by_first_author_year.setdefault((last, year), []).append(e)

    fuzzy_merges = 0
    for (last, year), group in by_first_author_year.items():
        if len(group) < 2:
            continue
        # Pairwise Jaccard on significant title tokens, union-find across the group.
        n = len(group)
        parent_idx = list(range(n))

        def fp(x):
            while parent_idx[x] != x:
                parent_idx[x] = parent_idx[parent_idx[x]]
                x = parent_idx[x]
            return x

        token_sets = [_significant_tokens(normalize_title(e.get('title', ''))) for e in group]
        for i in range(n):
            for j in range(i + 1, n):
                a, b = token_sets[i], token_sets[j]
                if not a or not b:
                    continue
                inter = len(a & b)
                union = len(a | b)
                if union and inter / union >= 0.5:
                    ri, rj = fp(i), fp(j)
                    if ri != rj:
                        parent_idx[rj] = ri

        clusters = {}
        for i in range(n):
            clusters.setdefault(fp(i), []).append(group[i])

        for cluster in clusters.values():
            if len(cluster) < 2:
                continue
            union_ids = {'arxiv': set(), 'doi': set(), 'nature': set()}
            for e in cluster:
                for k in union_ids:
                    union_ids[k].update(e['_ids'].get(k, []))
            union_ids = {k: sorted(v) for k, v in union_ids.items()}
            # Only count as a real merge if the union actually adds IDs to
            # some member that previously had none.
            added = False
            for e in cluster:
                before = sum(len(e['_ids'].get(k, [])) for k in union_ids)
                e['_ids'] = union_ids
                if before == 0 and any(union_ids[k] for k in union_ids):
                    added = True
            if added:
                fuzzy_merges += 1

    if fuzzy_merges:
        print(f"  bibtex fuzzy ID merge: healed {fuzzy_merges} same-paper cluster(s)")

    # Third pass: build the secondary lookups using the unioned IDs.
    for e in entries:
        last = _bibtex_first_author_lastname(e.get('author', ''))
        year = e.get('year', '').strip()
        if last and year:
            by_author_year.setdefault((last, year), []).append(e)

        for ax in e['_ids'].get('arxiv', []):
            by_arxiv.setdefault(ax, e)
        for doi in e['_ids'].get('doi', []):
            by_doi.setdefault(doi, e)

    _BIBTEX_LOOKUP_CACHE = {
        'by_title': by_title,
        'by_author_year': by_author_year,
        'by_arxiv': by_arxiv,
        'by_doi': by_doi,
        'by_key': by_key,
    }
    return _BIBTEX_LOOKUP_CACHE


def enrich_ids_via_bibtex(ref_text, title, first_author, year, ids):
    """Fill in missing arxiv/doi/nature IDs by matching the ref against bibtex master.

    Returns (enriched_ids_dict, matched_bibtex_key_or_None).
    """
    has_any = any(ids[k] for k in ('arxiv', 'doi', 'nature'))
    lookup = load_bibtex_master()
    candidate_entry = None

    # First — if the ref already extracted an arxiv/doi/nature ID, try to
    # find the matching bibtex entry directly. This is the strongest signal
    # and works even when the ref line uses an exotic citation format that
    # defeats title/author parsing (e.g. IEEE-style "Author, "Title," arXiv:X, YYYY.").
    if has_any:
        for ax in ids.get('arxiv', []):
            if ax in lookup['by_arxiv']:
                candidate_entry = lookup['by_arxiv'][ax]
                break
        if candidate_entry is None:
            for doi in ids.get('doi', []):
                if doi in lookup['by_doi']:
                    candidate_entry = lookup['by_doi'][doi]
                    break

    nt = normalize_title(title)
    if candidate_entry is None and nt and nt in lookup['by_title']:
        candidate_entry = lookup['by_title'][nt]

    if candidate_entry is None and first_author and year:
        last_lc = first_author.split(',')[0].strip().split()[-1].lower() if first_author else ''
        if last_lc:
            cands = lookup['by_author_year'].get((last_lc, year), [])
            # If unique author+year, accept it. If multiple, require title token overlap.
            if len(cands) == 1:
                candidate_entry = cands[0]
            elif len(cands) > 1 and nt:
                ref_tokens = set(nt.split())
                best = None
                best_overlap = 0
                for c in cands:
                    c_tokens = set(normalize_title(c.get('title', '')).split())
                    overlap = len(ref_tokens & c_tokens)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best = c
                if best_overlap >= 3:
                    candidate_entry = best

    if candidate_entry is None:
        return ids, None

    matched_key = candidate_entry['key']
    bib_ids = candidate_entry.get('_ids') or _bibtex_extract_ids(candidate_entry)

    if has_any:
        # Already have IDs from ref text; just record bibtex_key for downstream.
        return ids, matched_key

    enriched = {k: list(ids.get(k, [])) for k in ('arxiv', 'doi', 'nature')}
    for k in enriched:
        for v in bib_ids.get(k, []):
            if v not in enriched[k]:
                enriched[k].append(v)
        enriched[k].sort()
    return enriched, matched_key


def extract_refs_from_survey(survey_dir, survey_id):
    """Extract all references from a survey's chapters.

    For each ref line we now also (a) normalize the title for downstream
    canonical-ID merging, (b) try to enrich missing arxiv/doi via the
    master bibtex when the ref text alone is too thin (e.g. lacks an
    arxiv URL because the author wrote `arXiv` without the ID, or just
    cites a post backlink).
    """
    refs = []
    book_ko = os.path.join(survey_dir, 'book', 'ko')
    if not os.path.isdir(book_ko):
        return refs

    for fname in sorted(os.listdir(book_ko)):
        if not fname.endswith('.md') or not fname.startswith('ch'):
            continue
        ch_num = fname.replace('ch', '').replace('.md', '')

        with open(os.path.join(book_ko, fname), 'r', encoding='utf-8') as f:
            content = f.read()

        for marker in ['## 참고문헌', '## References']:
            idx = content.find(marker)
            if idx != -1:
                ref_section = content[idx:]
                for line in ref_section.split('\n'):
                    m = re.match(r'^(\d+)\.\s+(.+)', line.strip())
                    if m:
                        ref_text = m.group(2)
                        # Extract key info
                        year_match = re.search(r'\((\d{4})\)', ref_text)
                        year = year_match.group(1) if year_match else ''

                        # Extract title (between Year). and next period/asterisk)
                        title = ''
                        title_match = re.search(r'\(\d{4}\)\.\s*(.+?)(?:\.\s*\*|\.\s*$)', ref_text)
                        if title_match:
                            title = title_match.group(1).strip().rstrip('.')

                        # Extract first author
                        author_match = re.match(r'^(.+?)\s*\(', ref_text)
                        first_author = author_match.group(1).split(',')[0].strip() if author_match else ''

                        # Extract keywords for matching
                        keywords = extract_keywords(ref_text)

                        # Tier 1 identifiers (arxiv / doi / nature) — first
                        # from the ref text itself, then enriched via the
                        # master bibtex if still empty.
                        ids = extract_paper_ids(ref_text)
                        ids, bibtex_key = enrich_ids_via_bibtex(
                            ref_text, title, first_author, year, ids
                        )

                        refs.append({
                            'survey': survey_id,
                            'chapter': ch_num,
                            'ref_num': m.group(1),
                            'text': ref_text,
                            'title': title,
                            'title_norm': normalize_title(title),
                            'year': year,
                            'first_author': first_author,
                            'keywords': keywords,
                            'ids': ids,
                            'bibtex_key': bibtex_key,
                        })
                break
    return refs


def extract_keywords(text):
    """Extract searchable keywords from reference text."""
    # Known project/paper names
    known = re.findall(
        r'(?:pi0|RT-1|RT-2|PaLM-E|SayCan|OpenVLA|DROID|ALOHA|Mobile ALOHA|'
        r'GelSight|DIGIT|MANO|Diffusion Policy|ACT|Flow Matching|'
        r'DexUMI|DEXOP|ExoStart|ForceVLA|DexForce|PP-Tac|OSMO|UniTacHand|'
        r'EquiTac|GEN-0|GEN-1|Habilis|RoboPaint|CaP-X|RoboClaw|'
        r'UMI|UMI-FT|EgoScale|HumanPlus|Bunny-VisionPro|AnyTeleop|'
        r'TacScale|TacPlay|AutoRT|BUMBLE|REFLECT|PragmaBot|SIMPLER|'
        r'KARMA|Embodied-RAG|AutoTAMP|HAMSTER|3D Diffuser Actor|'
        r'DexH2R|ManipTrans|X-Sim|FARM|AnySkin|AnyTouch|DOGlove|'
        r'ACT-1|Stretchable Glove|Tactile Skin|3DTactile|'
        r'Sparsh|UniTouch|NeuralFeels|DiffTactile|ReSkin|Robot Synesthesia|'
        r'VTDexManip|RGMC|Gemini Robotics|X-Embodiment)',
        text, re.IGNORECASE
    )
    return list(set(kw.lower() for kw in known))


def build_index():
    """Build the complete reference index."""
    all_refs = []

    for survey_name in sorted(os.listdir(SURVEYS_DIR)):
        survey_dir = os.path.join(SURVEYS_DIR, survey_name)
        config_path = os.path.join(survey_dir, 'survey.json')
        if not os.path.isfile(config_path):
            continue

        refs = extract_refs_from_survey(survey_dir, survey_name)
        all_refs.extend(refs)
        print(f"  {survey_name}: {len(refs)} refs")

    # Pass 1 — title-keyed dedup. Same title across surveys collapses; title
    # variants (e.g. "DexUMI: Universal Manipulation Interface" vs "...for
    # Dexterous Hands") still split here. Pass 2 fixes that.
    title_map = {}
    for ref in all_refs:
        key = ref['title'].lower().strip()
        if not key:
            key = f"{ref['first_author']}_{ref['year']}"
        if key not in title_map:
            title_map[key] = {
                'title': ref['title'],
                'year': ref['year'],
                'first_author': ref['first_author'],
                'keywords': ref['keywords'],
                'ids': {'arxiv': [], 'doi': [], 'nature': []},
                'bibtex_keys': [],
                'locations': [],
            }
        else:
            existing_kw = set(title_map[key]['keywords'])
            existing_kw.update(ref['keywords'])
            title_map[key]['keywords'] = list(existing_kw)

        for kind in ('arxiv', 'doi', 'nature'):
            existing = set(title_map[key]['ids'][kind])
            existing.update(ref['ids'].get(kind, []))
            title_map[key]['ids'][kind] = sorted(existing)

        if ref.get('bibtex_key'):
            if ref['bibtex_key'] not in title_map[key]['bibtex_keys']:
                title_map[key]['bibtex_keys'].append(ref['bibtex_key'])

        title_map[key]['locations'].append({
            'survey': ref['survey'],
            'chapter': ref['chapter'],
            'ref_num': ref['ref_num'],
        })

    # Pass 2 — canonical-ID merge. Build clusters of title_keys that share an
    # arxiv_id, doi, or nature ID. Within each cluster, pick the longest
    # title as the canonical key and absorb the others (locations, keywords,
    # IDs, bibtex_keys all union'd). This fixes the DexUMI failure mode
    # where three title variants of the same arxiv:2505.21864 stayed split.
    parent = {k: k for k in title_map}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # Prefer the title-key with the longer title as the cluster root —
        # downstream consumers see the more descriptive title.
        if len(title_map[ra]['title']) >= len(title_map[rb]['title']):
            parent[rb] = ra
        else:
            parent[ra] = rb

    for kind in ('arxiv', 'doi', 'nature'):
        id_to_keys = {}
        for k, p in title_map.items():
            for ident in p['ids'].get(kind, []):
                id_to_keys.setdefault(ident, []).append(k)
        for keys_sharing_id in id_to_keys.values():
            if len(keys_sharing_id) < 2:
                continue
            anchor = keys_sharing_id[0]
            for other in keys_sharing_id[1:]:
                union(anchor, other)

    merge_count = 0
    if any(find(k) != k for k in title_map):
        merged = {}
        for k, paper in title_map.items():
            root = find(k)
            if root not in merged:
                merged[root] = {
                    'title': title_map[root]['title'],
                    'year': title_map[root]['year'],
                    'first_author': title_map[root]['first_author'],
                    'keywords': [],
                    'ids': {'arxiv': set(), 'doi': set(), 'nature': set()},
                    'bibtex_keys': [],
                    'locations': [],
                    'aliases': [],
                }
            target = merged[root]
            for kind in target['ids']:
                target['ids'][kind].update(paper['ids'].get(kind, []))
            target['keywords'] = list(set(target['keywords']) | set(paper['keywords']))
            for bk in paper.get('bibtex_keys', []):
                if bk not in target['bibtex_keys']:
                    target['bibtex_keys'].append(bk)
            target['locations'].extend(paper['locations'])
            if k != root:
                target['aliases'].append({
                    'title': paper['title'],
                    'year': paper['year'],
                })
                merge_count += 1
            # Prefer the year from any non-empty entry (most variants share year)
            if not target['year'] and paper['year']:
                target['year'] = paper['year']
            if not target['first_author'] and paper['first_author']:
                target['first_author'] = paper['first_author']
        for root_paper in merged.values():
            for kind in root_paper['ids']:
                root_paper['ids'][kind] = sorted(root_paper['ids'][kind])
        title_map = merged

    if merge_count:
        print(f"  canonical-ID merge: collapsed {merge_count} title variant(s)")

    # Reverse index: paper ID → list of locations.
    # Consumers (e.g. build.py --impact) look up a post's arXiv/DOI/Nature
    # ID here to find every survey+chapter that already cites that paper.
    reverse_index = {'arxiv': {}, 'doi': {}, 'nature': {}}
    for title_key, paper in title_map.items():
        for kind in reverse_index:
            for ident in paper['ids'].get(kind, []):
                reverse_index[kind].setdefault(ident, []).extend(paper['locations'])

    index = {
        'version': 3,
        'total_refs': len(all_refs),
        'unique_papers': len(title_map),
        'papers': title_map,
        'reverse_index': reverse_index,
    }

    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\nIndex built: {len(all_refs)} total refs, {len(title_map)} unique papers")
    print(f"Reverse index: {sum(len(v) for v in reverse_index.values())} ID entries")
    print(f"Saved to: {INDEX_PATH}")
    return index


def search_index(query):
    """Search the index by keyword."""
    if not os.path.isfile(INDEX_PATH):
        print("Index not found. Run: python3 shared/refs_index.py build")
        return

    with open(INDEX_PATH) as f:
        index = json.load(f)

    query_lower = query.lower()
    results = []
    for key, paper in index['papers'].items():
        if (query_lower in key or
            query_lower in paper.get('first_author', '').lower() or
            any(query_lower in kw for kw in paper.get('keywords', []))):
            results.append(paper)

    if not results:
        print(f"No matches for '{query}'")
        return

    print(f"\n{len(results)} matches for '{query}':\n")
    for paper in results[:20]:
        locs = ', '.join(f"{l['survey']} ch{l['chapter']}[{l['ref_num']}]" for l in paper['locations'])
        print(f"  {paper['first_author']} ({paper['year']}). {paper['title'][:80]}")
        print(f"    -> {locs}")
        if paper['keywords']:
            print(f"    keywords: {', '.join(paper['keywords'])}")
        print()


def build_posts_index():
    """Scan terryum-ai posts and extract Tier 1 identifiers.

    Produces posts_index.json with one entry per post containing slug,
    post_number, source_title, source_author, source_date, and the set
    of paper identifiers (arxiv / doi / nature) derived from source_url.
    """
    if not os.path.isdir(HOMEPAGE_POSTS_DIR):
        print(f"Homepage posts dir not found: {HOMEPAGE_POSTS_DIR}")
        return None

    entries = []
    for slug in sorted(os.listdir(HOMEPAGE_POSTS_DIR)):
        meta_path = os.path.join(HOMEPAGE_POSTS_DIR, slug, 'meta.json')
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        source_url = meta.get('source_url', '') or ''
        ids = extract_paper_ids(source_url)
        # Also scan source_title + authors — in case URL is broken but
        # the title contains an arXiv ID as a fallback.
        secondary_ids = extract_paper_ids(
            f"{meta.get('source_title','')} {meta.get('source_author','')}"
        )
        for kind in ids:
            ids[kind] = sorted(set(ids[kind]) | set(secondary_ids[kind]))

        entries.append({
            'slug': slug,
            'post_number': meta.get('postNumber') or meta.get('post_number'),
            'source_title': meta.get('source_title', ''),
            'source_author': meta.get('source_author', ''),
            'source_date': meta.get('source_date', ''),
            'source_url': source_url,
            'visibility': meta.get('visibility', 'public'),
            'ids': ids,
        })

    index = {
        'version': 1,
        'total_posts': len(entries),
        'posts': entries,
    }
    with open(POSTS_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"Posts index: {len(entries)} posts → {POSTS_INDEX_PATH}")
    return index


def _load_post_entry(slug):
    """Read one post's metadata and identifiers without loading the full index."""
    meta_path = os.path.join(HOMEPAGE_POSTS_DIR, slug, 'meta.json')
    if not os.path.isfile(meta_path):
        return None
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    source_url = meta.get('source_url', '') or ''
    ids = extract_paper_ids(source_url)
    secondary_ids = extract_paper_ids(
        f"{meta.get('source_title','')} {meta.get('source_author','')}"
    )
    for kind in ids:
        ids[kind] = sorted(set(ids[kind]) | set(secondary_ids[kind]))
    return {
        'slug': slug,
        'post_number': meta.get('postNumber') or meta.get('post_number'),
        'source_title': meta.get('source_title', ''),
        'source_author': meta.get('source_author', ''),
        'source_url': source_url,
        'ids': ids,
    }


# --------------------------------------------------------------------
# Tier 2 helpers — title Jaccard similarity over meaningful tokens
# --------------------------------------------------------------------
# Stopwords that inflate Jaccard scores without adding signal.
_TITLE_STOP = frozenset({
    'the', 'a', 'an', 'of', 'for', 'in', 'on', 'to', 'and', 'or', 'with',
    'via', 'from', 'by', 'is', 'as', 'at', 'we', 'our', 'be', 'are', 'can',
    'this', 'that', 'these', 'those', 'their', 'paper', 'learning',
    'toward', 'towards',
})
# Tier 2 similarity threshold — set empirically. Jaccard on 5+ char tokens
# rarely crosses 0.55 unless titles share most meaningful words.
TIER2_THRESHOLD = 0.55


def _title_tokens(title):
    """Return lower-case word tokens of length ≥ 5 minus a short stopword set.

    Length filter drops "hand", "tac", "the", etc. — the same failure mode
    that produced F-TAC → Sparsh-skin false positives in the legacy matcher.
    """
    if not title:
        return set()
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]+", title.lower())
    return {w for w in words if len(w) >= 5 and w not in _TITLE_STOP}


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = a & b
    union = a | b
    return len(inter) / len(union) if union else 0.0


def match_post_slug(slug):
    """Match a homepage post slug to survey references.

    Three-tier strategy:
      Tier 1 — arXiv/DOI/Nature ID exact match     (confidence=exact)
      Tier 2 — Title-token Jaccard ≥ TIER2_THRESHOLD (confidence=medium)
      Tier 3 — slug-token fuzzy fallback            (confidence=low, review)

    Tier 1 is always preferred. Tier 2 covers the gap when a paper has no
    arXiv/DOI/Nature identifier but the post title matches the survey ref
    title closely enough that false positives are unlikely. Tier 3 is a
    last-resort suggestion surface — it is reported but never auto-linked.
    """
    if not os.path.isfile(INDEX_PATH):
        print("Refs index not found. Run: python3 bibtex/refs_index.py build")
        return {'tier1': [], 'tier2': [], 'tier3': []}

    with open(INDEX_PATH) as f:
        index = json.load(f)

    # --- Tier 1: pull post identifiers and exact-match against refs -------
    post = _load_post_entry(slug)
    tier1 = []
    if post:
        post_ids = post['ids']
        post_id_set = {
            ('arxiv', x) for x in post_ids['arxiv']
        } | {
            ('doi', x) for x in post_ids['doi']
        } | {
            ('nature', x) for x in post_ids['nature']
        }
        if post_id_set:
            for key, paper in index['papers'].items():
                ref_ids = paper.get('ids') or {}
                ref_id_set = {
                    ('arxiv', x) for x in ref_ids.get('arxiv', [])
                } | {
                    ('doi', x) for x in ref_ids.get('doi', [])
                } | {
                    ('nature', x) for x in ref_ids.get('nature', [])
                }
                overlap = post_id_set & ref_id_set
                if overlap:
                    tier1.append({
                        'paper': paper,
                        'matched_ids': sorted(overlap),
                    })

    # --- Tier 2: title Jaccard similarity ---------------------------------
    tier1_titles = {m['paper']['title'].lower().strip() for m in tier1}
    tier2 = []
    if post and post.get('source_title'):
        post_tokens = _title_tokens(post['source_title'])
        if post_tokens:
            for key, paper in index['papers'].items():
                if paper['title'].lower().strip() in tier1_titles:
                    continue
                ref_tokens = _title_tokens(paper.get('title', ''))
                sim = _jaccard(post_tokens, ref_tokens)
                if sim >= TIER2_THRESHOLD:
                    tier2.append({'paper': paper, 'similarity': round(sim, 3)})
            tier2.sort(key=lambda m: -m['similarity'])

    tier2_titles = {m['paper']['title'].lower().strip() for m in tier2}

    # --- Tier 3: legacy slug-token fuzzy fallback -------------------------
    parts = slug.split('-')
    if parts and re.match(r'^\d{4}$', parts[0]):
        parts = parts[1:]

    tier3 = []
    for key, paper in index['papers'].items():
        title_lc = paper['title'].lower().strip()
        if title_lc in tier1_titles or title_lc in tier2_titles:
            continue
        score = 0
        for kw in paper.get('keywords', []):
            for part in parts:
                if len(part) < 4:
                    continue
                if part.lower() in kw or kw in part.lower():
                    score += 3
        title_lower = key
        for part in parts:
            if len(part) >= 5 and part.lower() in title_lower:
                score += 1
        if score >= 3:
            tier3.append((score, paper))

    tier3.sort(key=lambda x: -x[0])

    # --- Report ------------------------------------------------------------
    if not tier1 and not tier2 and not tier3:
        print(f"No matches for post slug '{slug}'")
        return {'tier1': [], 'tier2': [], 'tier3': []}

    if post and not post.get('ids', {}).get('arxiv') \
            and not post.get('ids', {}).get('doi') \
            and not post.get('ids', {}).get('nature'):
        print(f"⚠️  Post '{slug}' has no arXiv/DOI/Nature identifier — "
              f"Tier 1 exact matching disabled for this post.")

    if tier1:
        print(f"\n✅ Tier 1 (exact ID match) — {len(tier1)} paper(s):\n")
        for hit in tier1:
            p = hit['paper']
            locs = ', '.join(
                f"{l['survey']} ch{l['chapter']}[{l['ref_num']}]"
                for l in p['locations']
            )
            ids_str = ', '.join(f"{k}:{v}" for k, v in hit['matched_ids'])
            print(f"  • {p['first_author']} ({p['year']}). {p['title'][:80]}")
            print(f"    matched: {ids_str}")
            print(f"    -> {locs}")
            print()

    if tier2:
        header = (
            f"📗 Tier 2 (title-Jaccard ≥ {TIER2_THRESHOLD}) — {len(tier2)} paper(s)"
            if tier1 else
            f"📗 Tier 2 (title-Jaccard ≥ {TIER2_THRESHOLD}) — {len(tier2)} paper(s) (no Tier 1 hit)"
        )
        print(f"\n{header}:\n")
        for hit in tier2:
            p = hit['paper']
            locs = ', '.join(
                f"{l['survey']} ch{l['chapter']}[{l['ref_num']}]"
                for l in p['locations']
            )
            print(f"  • [sim={hit['similarity']}] {p['first_author']} ({p['year']}). {p['title'][:80]}")
            print(f"    -> {locs}")
            print()

    if tier3:
        header = (
            "⚠️  Tier 3 (slug-token fuzzy — REQUIRES HUMAN REVIEW)"
            if tier1 or tier2 else
            "⚠️  Tier 3 only (no Tier 1/2 hit — REQUIRES HUMAN REVIEW)"
        )
        print(f"\n{header} — top {min(len(tier3), 5)} of {len(tier3)}:\n")
        for score, paper in tier3[:5]:
            locs = ', '.join(
                f"{l['survey']} ch{l['chapter']}[{l['ref_num']}]"
                for l in paper['locations']
            )
            print(f"  [score={score}] {paper['first_author']} ({paper['year']}). {paper['title'][:80]}")
            print(f"    -> {locs}")
            print()

    return {
        'tier1': tier1,
        'tier2': tier2,
        'tier3': [{'score': s, 'paper': p} for s, p in tier3],
    }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    if cmd == 'build':
        build_index()
    elif cmd == 'build-posts':
        build_posts_index()
    elif cmd == 'build-all':
        build_index()
        build_posts_index()
    elif cmd == 'search' and len(sys.argv) >= 3:
        search_index(sys.argv[2])
    elif cmd == 'match' and len(sys.argv) >= 3:
        match_post_slug(sys.argv[2])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
