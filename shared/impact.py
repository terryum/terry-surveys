#!/usr/bin/env python3
"""Paper-impact analyzer.

Given a post slug (from terryum-ai homepage), report which survey
chapters are candidates for an update. Two tiers:

  Tier 1 (exact ID match)
    Look up the post's arXiv / DOI / Nature IDs in refs_index.json's
    reverse_index. Any chapter already citing the paper is reported
    as "already citing, suggest inserting [#NN] post link".

  Tier 2 (keyword / topic)
    Tokenize the post's tags, subfields, key_concepts, and methodology
    into word atoms. Tokenize each chapter's summary + title in the
    same way. Compute a Jaccard-ish overlap score and rank the top
    N per survey.

Wired via build.py --impact <slug>. Consumed by the
link-post-to-surveys skill for the Tier 1 auto-insert + Tier 2 manual
review pass.
"""

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SURVEYS_DIR = os.path.join(ROOT, 'surveys')
BIBTEX_DIR = os.path.join(ROOT, 'bibtex')
REFS_INDEX = os.path.join(BIBTEX_DIR, 'refs_index.json')
POSTS_INDEX = os.path.join(BIBTEX_DIR, 'posts_index.json')
HOMEPAGE_POSTS = os.path.abspath(os.path.join(ROOT, '..', 'terryum-ai', 'posts', 'papers'))
MASTER_BIB = os.path.join(BIBTEX_DIR, 'references.bib')

# Tier 2 ranking thresholds.
TIER2_MIN_OVERLAP = 2         # at least N shared word atoms
TIER2_TOP_PER_SURVEY = 5      # emit only the top-K chapters per survey


def read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_post(slug):
    """Return (post_from_index, meta_from_file). Either can be None."""
    post = None
    meta = None
    if os.path.isfile(POSTS_INDEX):
        idx = read_json(POSTS_INDEX)
        for p in idx.get('posts', []):
            if p.get('slug') == slug:
                post = p
                break
    meta_path = os.path.join(HOMEPAGE_POSTS, slug, 'meta.json')
    if os.path.isfile(meta_path):
        meta = read_json(meta_path)
    return post, meta


def tokenize(text):
    """Lower-case word atoms from a string; splits on hyphen/space/punct."""
    return set(re.findall(r'[a-z0-9]+', (text or '').lower()))


STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'to', 'for', 'in', 'on', 'with',
    'is', 'are', 'be', 'as', 'by', 'from', 'into', 'via', 'at', 'but',
    'this', 'that', 'papers', 'robotics', 'paper', 'part', 'chapter',
    'book', 'model', 'models', 'method', 'methods', 'approach', 'learning',
    'how', 'what', 'why',
}


def paper_atoms(meta):
    """Build the paper's concept set from tags/subfields/key_concepts/methodology."""
    atoms = set()
    for key in ('tags', 'display_tags', 'subfields', 'key_concepts', 'methodology'):
        for v in meta.get(key, []) or []:
            atoms |= tokenize(v)
    # Also include source_title tokens for extra coverage.
    atoms |= tokenize(meta.get('source_title', ''))
    return {a for a in atoms if len(a) >= 3 and a not in STOPWORDS}


def chapter_atoms(chapter):
    atoms = set()
    for k in ('summary', 'title'):
        v = chapter.get(k)
        if isinstance(v, dict):
            for lang_val in v.values():
                atoms |= tokenize(lang_val)
        elif isinstance(v, str):
            atoms |= tokenize(v)
    return {a for a in atoms if len(a) >= 3 and a not in STOPWORDS}


def enrich_ids_from_master(id_set):
    """Expand an (kind, id) set via the master bibtex/references.bib.

    The master is our richest cross-identifier source: a single
    @article can carry arXiv, DOI, Nature ID, and URL in one entry.
    When the post only supplies an arXiv ID but the RHT ref line only
    quotes the Nature DOI, the master entry is what links them.
    """
    if not os.path.isfile(MASTER_BIB):
        return id_set
    with open(MASTER_BIB, 'r', encoding='utf-8') as f:
        master = f.read()

    arxiv_re = re.compile(r'(?:arxiv\.org/(?:abs|pdf|html)/|arXiv:)(\d{4}\.\d{4,5})', re.I)
    doi_re = re.compile(r'\b(10\.\d{4,9}/[^\s"}\]]+)', re.I)
    nature_re = re.compile(r'nature\.com/articles/(s\d+-\d+-\d+-[\d\-a-z]+)', re.I)
    entry_re = re.compile(r'@\w+\s*\{[^@]+?\n\}', re.DOTALL)

    out = set(id_set)
    for em in entry_re.finditer(master):
        body = em.group(0)
        entry_ids = set()
        for m in arxiv_re.finditer(body):
            entry_ids.add(('arxiv', m.group(1).lower()))
        for m in doi_re.finditer(body):
            entry_ids.add(('doi', m.group(1).lower().rstrip('.,)]}')))
        for m in nature_re.finditer(body):
            entry_ids.add(('nature', m.group(1).lower()))
        # Nature DOI ↔ article ID bridge (same suffix).
        for kind, ident in list(entry_ids):
            if kind == 'doi' and ident.startswith('10.1038/s'):
                entry_ids.add(('nature', ident.split('/', 1)[-1]))
            if kind == 'nature':
                entry_ids.add(('doi', f'10.1038/{ident}'))
        if entry_ids & out:
            out |= entry_ids
    return out


def tier1_matches(post, refs_index):
    """Return a list of {survey, chapter, ref_num, id_kind, id}.

    Any survey citing the same paper by ANY identifier counts as a Tier
    1 hit, even if the post only knows one ID and the survey ref line
    only carries a different one. We walk a transitive closure across
    the papers[] index: start from the post's IDs, find paper entries
    holding any of them, absorb those papers' IDs, iterate until the
    ID set stops growing. This unions ID sets across sibling survey
    entries that happened to title the same paper slightly differently
    (e.g. one appends "(F-TAC Hand)" to the master title).
    """
    rev = refs_index.get('reverse_index', {})
    papers = refs_index.get('papers', {})
    if post is None:
        return []

    # Normalised (kind, id) set; seed from the post, then bridge via
    # the master bib so DOI/arXiv cross-references are unioned even
    # when individual survey ref lines only quote one of them.
    frontier = set()
    for kind in ('arxiv', 'doi', 'nature'):
        for ident in post.get('ids', {}).get(kind, []):
            frontier.add((kind, ident.lower()))
    frontier = enrich_ids_from_master(frontier)

    known = set()
    while frontier:
        known |= frontier
        new_frontier = set()
        for paper in papers.values():
            paper_ids = set()
            for kind in ('arxiv', 'doi', 'nature'):
                for ident in paper.get('ids', {}).get(kind, []):
                    paper_ids.add((kind, ident.lower()))
            if paper_ids & known:
                # This paper shares an ID with what we know; absorb the rest.
                new_frontier |= (paper_ids - known)
        frontier = new_frontier

    # Look up every ID we ended up with.
    seen = set()
    out = []
    for kind, ident in sorted(known):
        for loc in rev.get(kind, {}).get(ident, []):
            sig = (loc['survey'], str(loc['chapter']), str(loc['ref_num']))
            if sig in seen:
                continue
            seen.add(sig)
            entry = dict(loc)
            entry['id_kind'] = kind
            entry['id'] = ident
            out.append(entry)
    return out


def tier2_matches(paper_set, skip_locations):
    """Score every chapter; drop those already in Tier 1."""
    results_by_survey = {}
    skip = {(l['survey'], str(int(l['chapter']))) for l in skip_locations}
    for name in sorted(os.listdir(SURVEYS_DIR)):
        cfg_path = os.path.join(SURVEYS_DIR, name, 'survey.json')
        if not os.path.isfile(cfg_path):
            continue
        cfg = read_json(cfg_path)
        rows = []
        for part in cfg.get('parts', []):
            for ch in part.get('chapters', []):
                ch_atoms = chapter_atoms(ch)
                shared = paper_set & ch_atoms
                if len(shared) < TIER2_MIN_OVERLAP:
                    continue
                key = (name, str(ch['num']))
                if key in skip:
                    continue
                union = paper_set | ch_atoms
                score = len(shared) / max(len(union), 1)
                rows.append({
                    'survey': name,
                    'chapter': ch['num'],
                    'title': ch.get('title', {}).get('en', ''),
                    'shared': sorted(shared),
                    'score': round(score, 3),
                })
        rows.sort(key=lambda r: -r['score'])
        rows = rows[:TIER2_TOP_PER_SURVEY]
        if rows:
            results_by_survey[name] = rows
    return results_by_survey


def run_impact(slug):
    post, meta = load_post(slug)
    if post is None and meta is None:
        print(f'ERROR: no post or meta found for slug {slug!r}')
        sys.exit(1)

    if not os.path.isfile(REFS_INDEX):
        print('ERROR: refs_index.json not found. Run: python3 build.py --index')
        sys.exit(1)
    refs_index = read_json(REFS_INDEX)

    print(f'# Impact: {slug}')
    print()
    title = (meta or {}).get('source_title') or (post or {}).get('source_title', '')
    if title:
        print(f'- source: {title}')
    ids = (post or {}).get('ids', {})
    pid_summary = ', '.join(
        f'{k}={v[0]}' for k, v in ids.items() if v
    ) or '(no IDs)'
    print(f'- ids: {pid_summary}')
    post_num = (post or meta or {}).get('post_number') or (meta or {}).get('postNumber')
    if post_num:
        print(f'- post_number: [#{post_num}]')
    print()

    # Tier 1
    t1 = tier1_matches(post, refs_index)
    print('## Tier 1 — already citing (exact ID match)')
    if not t1:
        print('_none_')
    else:
        for loc in t1:
            print(
                f"- {loc['survey']} ch{loc['chapter']} ref [{loc['ref_num']}] "
                f"(via {loc['id_kind']}={loc['id']})"
            )
    print()

    # Tier 2
    print('## Tier 2 — related chapters (keyword / topic)')
    if meta is None:
        print('_meta.json not available; skipping Tier 2_')
        return
    atoms = paper_atoms(meta)
    if not atoms:
        print('_paper has no tags/subfields/keywords; skipping_')
        return
    t2 = tier2_matches(atoms, t1)
    if not t2:
        print('_no related chapters above threshold_')
        return
    for survey, rows in t2.items():
        print(f'\n### {survey}')
        for r in rows:
            tags = ', '.join(r['shared'][:8])
            print(
                f"- ch{r['chapter']:02d} (score={r['score']}) — {r['title']}\n"
                f"  shared: [{tags}]"
            )


def main(slug):
    run_impact(slug)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: impact.py <post-slug>')
        sys.exit(1)
    main(sys.argv[1])
