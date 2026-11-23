#!/usr/bin/env python3
"""Run the repository-owned survey harness from canonical or installed skill."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_ROOT = Path.home() / "Codes/terry/terryum-ai/surveys/framework"


def resolve_root() -> Path:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--repo-root", type=Path)
    args, _ = parser.parse_known_args()
    if args.repo_root:
        explicit = args.repo_root.expanduser().resolve()
        if (explicit / "survey_harness/__init__.py").is_file():
            return explicit
    configured = os.environ.get("TERRY_SURVEYS_ROOT")
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if (candidate / "survey_harness/__init__.py").is_file():
            return candidate
        if not args.repo_root:
            raise SystemExit(f"ERROR: TERRY_SURVEYS_ROOT is not a framework checkout: {candidate}")
    cwd = Path.cwd()
    canonical = Path(__file__).resolve().parents[4]
    for candidate in (canonical, cwd, *cwd.parents, cwd / "surveys/framework", DEFAULT_ROOT):
        if (candidate / "survey_harness/__init__.py").is_file():
            return candidate.resolve()
    raise SystemExit(
        "ERROR: cannot locate terry-surveys; set TERRY_SURVEYS_ROOT to the framework checkout"
    )


ROOT = resolve_root()
# The wrapper itself is also named survey_harness.py. Put the repository first
# even when it already appears later in sys.path so Python imports the package.
sys.path[:] = [entry for entry in sys.path if entry != str(ROOT)]
sys.path.insert(0, str(ROOT))

from survey_harness.cli import main  # noqa: E402

raise SystemExit(main(default_root=ROOT))
