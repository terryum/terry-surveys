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
    python3 bibtex/refs_index.py build-posts    # Rebuild posts index (terry-artlab-homepage)
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

# This script lives in bibtex/, the canonical home for every
# reference-management artifact (master references.bib, generated indices,
# matching tools). Paths below reflect that placement.
BIBTEX_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BIBTEX_DIR)
SURVEYS_DIR = os.path.join(ROOT, 'surveys')
INDEX_PATH = os.path.join(BIBTEX_DIR, 'refs_index.json')
POSTS_INDEX_PATH = os.path.join(BIBTEX_DIR, 'posts_index.json')
HOMEPAGE_POSTS_DIR = os.path.join(
    os.path.dirname(ROOT), 'terry-artlab-homepage', 'posts', 'papers'
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


def extract_refs_from_survey(survey_dir, survey_id):
    """Extract all references from a survey's chapters."""
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

                        # Tier 1 identifiers (arxiv / doi / nature)
                        ids = extract_paper_ids(ref_text)

                        refs.append({
                            'survey': survey_id,
                            'chapter': ch_num,
                            'ref_num': m.group(1),
                            'text': ref_text,
                            'title': title,
                            'year': year,
                            'first_author': first_author,
                            'keywords': keywords,
                            'ids': ids,
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

    # Deduplicate by title (keep all locations)
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
                'locations': [],
            }
        else:
            # Merge keywords
            existing_kw = set(title_map[key]['keywords'])
            existing_kw.update(ref['keywords'])
            title_map[key]['keywords'] = list(existing_kw)

        # Merge Tier 1 IDs across all ref copies for the same paper
        for kind in ('arxiv', 'doi', 'nature'):
            existing = set(title_map[key]['ids'][kind])
            existing.update(ref['ids'].get(kind, []))
            title_map[key]['ids'][kind] = sorted(existing)

        title_map[key]['locations'].append({
            'survey': ref['survey'],
            'chapter': ref['chapter'],
            'ref_num': ref['ref_num'],
        })

    index = {
        'version': 1,
        'total_refs': len(all_refs),
        'unique_papers': len(title_map),
        'papers': title_map,
    }

    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\nIndex built: {len(all_refs)} total refs, {len(title_map)} unique papers")
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
    """Scan terry-artlab-homepage posts and extract Tier 1 identifiers.

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


def match_post_slug(slug):
    """Match a homepage post slug to survey references.

    Two-tier strategy:
      Tier 1 — arXiv/DOI/Nature ID exact match   (confidence=exact)
      Tier 3 — slug-token fuzzy fallback         (confidence=low, needs review)

    Tier 1 is the primary signal. When any Tier 1 hit exists, Tier 3 matches
    are reported separately and callers should NOT auto-link them without
    human review. When no Tier 1 hit exists, Tier 3 matches are still
    returned as suggestions but always need review.
    """
    if not os.path.isfile(INDEX_PATH):
        print("Refs index not found. Run: python3 shared/refs_index.py build")
        return {'tier1': [], 'tier3': []}

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

    # --- Tier 3: legacy slug-token fuzzy fallback -------------------------
    parts = slug.split('-')
    if parts and re.match(r'^\d{4}$', parts[0]):
        parts = parts[1:]

    tier3 = []
    # Title/location keys already hit via Tier 1 — exclude from fuzzy output.
    tier1_titles = {m['paper']['title'].lower().strip() for m in tier1}

    for key, paper in index['papers'].items():
        if paper['title'].lower().strip() in tier1_titles:
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
    if not tier1 and not tier3:
        print(f"No matches for post slug '{slug}'")
        return {'tier1': [], 'tier3': []}

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

    if tier3:
        header = (
            "⚠️  Tier 3 (slug-token fuzzy — REQUIRES HUMAN REVIEW)"
            if tier1 else
            "⚠️  Tier 3 only (no Tier 1 hit — REQUIRES HUMAN REVIEW)"
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
