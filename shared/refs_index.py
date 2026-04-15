#!/usr/bin/env python3
"""Build and query a lightweight reference index across all surveys.

This index enables fast cross-referencing between:
- Survey references → Homepage posts
- New homepage posts → Survey references that mention the same paper

Usage:
    python3 shared/refs_index.py build          # Rebuild index
    python3 shared/refs_index.py search "pi0"   # Search by keyword
    python3 shared/refs_index.py match <slug>   # Match a post slug to survey refs
"""

import re
import os
import json
import sys
from urllib.parse import quote_plus

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURVEYS_DIR = os.path.join(ROOT, 'surveys')
INDEX_PATH = os.path.join(ROOT, 'refs_index.json')


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

                        refs.append({
                            'survey': survey_id,
                            'chapter': ch_num,
                            'ref_num': m.group(1),
                            'text': ref_text,
                            'title': title,
                            'year': year,
                            'first_author': first_author,
                            'keywords': keywords,
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
                'locations': [],
            }
        else:
            # Merge keywords
            existing_kw = set(title_map[key]['keywords'])
            existing_kw.update(ref['keywords'])
            title_map[key]['keywords'] = list(existing_kw)

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


def match_post_slug(slug):
    """Match a homepage post slug to survey references.

    This is the fast-path for the /post skill: given a new post slug,
    find all survey references that might be about the same paper.
    """
    if not os.path.isfile(INDEX_PATH):
        print("Index not found. Run: python3 shared/refs_index.py build")
        return []

    with open(INDEX_PATH) as f:
        index = json.load(f)

    # Extract searchable parts from slug
    # e.g. "2505-dexumi" -> ["dexumi"], "2410-pi0-vla-flow-model" -> ["pi0", "vla", "flow"]
    parts = slug.split('-')
    # Remove leading date part (YYMM)
    if parts and re.match(r'^\d{4}$', parts[0]):
        parts = parts[1:]

    matches = []
    for key, paper in index['papers'].items():
        score = 0
        # Check keywords
        for kw in paper.get('keywords', []):
            for part in parts:
                if part.lower() in kw or kw in part.lower():
                    score += 3

        # Check title
        title_lower = key
        for part in parts:
            if len(part) > 2 and part.lower() in title_lower:
                score += 1

        if score > 0:
            matches.append((score, paper))

    matches.sort(key=lambda x: -x[0])

    if not matches:
        print(f"No survey references match post slug '{slug}'")
        return []

    print(f"\n{len(matches)} potential matches for post '{slug}':\n")
    for score, paper in matches[:10]:
        locs = ', '.join(f"{l['survey']} ch{l['chapter']}[{l['ref_num']}]" for l in paper['locations'])
        print(f"  [score={score}] {paper['first_author']} ({paper['year']}). {paper['title'][:80]}")
        print(f"    -> {locs}")
        print()

    return [(s, p) for s, p in matches]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    if cmd == 'build':
        build_index()
    elif cmd == 'search' and len(sys.argv) >= 3:
        search_index(sys.argv[2])
    elif cmd == 'match' and len(sys.argv) >= 3:
        match_post_slug(sys.argv[2])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
