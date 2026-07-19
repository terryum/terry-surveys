#!/usr/bin/env python3
"""Compatibility verifier backed by the survey v2 scorecard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")
if str(DEFAULT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_ROOT))

from survey_harness.quality import evaluate  # noqa: E402
from survey_harness.state import repo_root  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--repo-root")
    parser.add_argument("--compare-baseline", action="store_true")
    parser.add_argument("--scope", choices=["full", "mini", "auto"], default="full")
    parser.add_argument("--allow-blocked", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)
    root = repo_root(args.repo_root or DEFAULT_ROOT)
    profile = "mini" if args.scope == "mini" else "full"
    result = evaluate(root, args.slug, profile)
    print(json.dumps({
        "slug": result["slug"],
        "profile": result["profile"],
        "score": result["score"],
        "passed": result["passed"],
        "hard_blockers": result["hard_blockers"],
    }, ensure_ascii=False, indent=2))
    if result["passed"]:
        return 0
    if args.allow_blocked and not args.require_ready:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
