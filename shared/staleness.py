#!/usr/bin/env python3
"""Chapter-level staleness tracker.

For every chapter in every survey, compute:
  - days_since_update:  days between today and the chapter's last_updated
  - related_new_papers: count of posts in bibtex/posts_index.json whose
    source paper was published AFTER the chapter's last_updated date
  - refresh_priority:   related_new_papers * (days_since_update / 30.0)

This rough signal answers "which chapters should I look at next week?"
Phase 3's impact analyzer (Tier 2 keyword/topic match) will later refine
the related_new_papers number to only count topically-relevant papers.

Exposed via:
    python3 build.py --staleness              # all surveys
    python3 build.py --staleness <survey>     # single survey
"""

import datetime as dt
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SURVEYS_DIR = os.path.join(ROOT, 'surveys')
POSTS_INDEX = os.path.join(ROOT, 'bibtex', 'posts_index.json')


def parse_date(s):
    if not s:
        return None
    s = str(s)
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def load_posts():
    if not os.path.isfile(POSTS_INDEX):
        return []
    with open(POSTS_INDEX, 'r', encoding='utf-8') as f:
        return json.load(f).get('posts', [])


def collect_chapter_rows(survey_name, posts, today):
    cfg_path = os.path.join(SURVEYS_DIR, survey_name, 'survey.json')
    if not os.path.isfile(cfg_path):
        return []
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    rows = []
    fallback = cfg.get('dates', {}).get('last_updated', '2026-01-01')
    for part in cfg.get('parts', []):
        for ch in part.get('chapters', []):
            last_updated_str = ch.get('last_updated', fallback)
            last_updated = parse_date(last_updated_str)
            if not last_updated:
                continue
            days_since = (today - last_updated).days
            new_papers = [
                p for p in posts
                if (d := parse_date(p.get('source_date'))) and d > last_updated
            ]
            priority = len(new_papers) * max(days_since, 0) / 30.0
            title = ch.get('title', {})
            title_en = title.get('en') if isinstance(title, dict) else str(title)
            rows.append({
                'survey': survey_name,
                'num': ch['num'],
                'title': title_en,
                'last_updated': last_updated_str,
                'days_since_update': days_since,
                'related_new_papers': len(new_papers),
                'refresh_priority': round(priority, 2),
            })
    return rows


def format_report(rows):
    rows = sorted(rows, key=lambda r: -r['refresh_priority'])
    out = []
    out.append(f"{'survey':<28} {'ch':>3} {'last_upd':<11} {'age':>4} "
               f"{'new':>4} {'prio':>7}  title")
    out.append('-' * 100)
    for r in rows:
        title = (r['title'] or '')[:40]
        out.append(
            f"{r['survey']:<28} {r['num']:>3} {r['last_updated']:<11} "
            f"{r['days_since_update']:>4} {r['related_new_papers']:>4} "
            f"{r['refresh_priority']:>7.2f}  {title}"
        )
    return '\n'.join(out)


def main(target=None):
    today = dt.date.today()
    posts = load_posts()

    if target and target != '--all':
        rows = collect_chapter_rows(target, posts, today)
        if not rows:
            print(f'ERROR: no chapters found for {target}')
            sys.exit(1)
    else:
        rows = []
        for name in sorted(os.listdir(SURVEYS_DIR)):
            if not os.path.isfile(os.path.join(SURVEYS_DIR, name, 'survey.json')):
                continue
            rows.extend(collect_chapter_rows(name, posts, today))

    print(f'today: {today.isoformat()}  |  posts tracked: {len(posts)}')
    print()
    print(format_report(rows))
    print()
    print('Top 5 refresh candidates:')
    for r in sorted(rows, key=lambda r: -r['refresh_priority'])[:5]:
        print(f"  [{r['survey']} ch{r['num']:02d}] priority={r['refresh_priority']} "
              f"(age={r['days_since_update']}d, new_papers={r['related_new_papers']})")


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else '--all'
    main(arg)
