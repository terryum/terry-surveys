#!/usr/bin/env python3
"""Assemble the weekly refresh report (staleness + fresh-paper impact).

Called from the GitHub Actions workflow at
`.github/workflows/weekly-refresh.yml`. Standalone runnable:

    python3 shared/weekly_report.py                # prints to stdout
    python3 shared/weekly_report.py > report.md    # capture to file

The report combines two signals that Phase 4 and Phase 3 already
produce independently:

  1. Top-N oldest chapters with the most new papers available
     (via shared/staleness.py).
  2. Most recently published posts (by source_date in posts_index.json)
     and, for each, which chapters they affect (via shared/impact.py).

The goal is to hand a human a single punch-list of "what to refresh
this week" without any LLM involvement — deterministic, reproducible,
cheap enough to run every Monday.
"""

import datetime as dt
import io
import os
import sys
import contextlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
POSTS_INDEX = os.path.join(ROOT, 'bibtex', 'posts_index.json')

# How far back "recent posts" stretches. A weekly cadence + a 14-day
# window ensures no post is missed when the workflow runs late or
# fails once.
LOOKBACK_DAYS = 14
TOP_STALENESS = 10
TOP_IMPACT_POSTS = 10


def capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit:
            pass
    return buf.getvalue()


def recent_posts(cutoff):
    import json
    if not os.path.isfile(POSTS_INDEX):
        return []
    with open(POSTS_INDEX, 'r', encoding='utf-8') as f:
        idx = json.load(f)
    out = []
    for p in idx.get('posts', []):
        d = p.get('source_date', '')[:10]
        try:
            date = dt.date.fromisoformat(d)
        except ValueError:
            continue
        if date >= cutoff:
            out.append((date, p))
    out.sort(key=lambda t: -t[0].toordinal())
    return out[:TOP_IMPACT_POSTS]


def build_report():
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=LOOKBACK_DAYS)

    sys.path.insert(0, ROOT)
    from shared import staleness, impact

    parts = []
    parts.append(f'# Weekly refresh — {today.isoformat()}')
    parts.append('')
    parts.append(f'Window: posts with `source_date >= {cutoff.isoformat()}`  '
                 f'(last {LOOKBACK_DAYS} days).')
    parts.append('')

    # Staleness
    parts.append('## Top stale chapters')
    parts.append('')
    parts.append('```text')
    parts.append(capture(staleness.main, '--all'))
    parts.append('```')
    parts.append('')

    # Fresh paper impact
    parts.append('## Fresh paper impact')
    parts.append('')
    posts = recent_posts(cutoff)
    if not posts:
        parts.append('_No new posts in the lookback window._')
    else:
        for date, post in posts:
            slug = post['slug']
            parts.append(f'### [{date.isoformat()}] {slug}')
            parts.append(f'*{post.get("source_title", "")}*')
            parts.append('')
            parts.append('```text')
            parts.append(capture(impact.main, slug))
            parts.append('```')
            parts.append('')

    return '\n'.join(parts)


def main():
    print(build_report())


if __name__ == '__main__':
    main()
