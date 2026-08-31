#!/usr/bin/env python3
"""Run the repository-owned tutorial harness from canonical or installed skill."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")


def resolve_root() -> Path:
    configured = os.environ.get("TERRY_SURVEYS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if (DEFAULT_ROOT / "tutorial_harness/__init__.py").is_file():
        return DEFAULT_ROOT.resolve()
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "tutorial_harness/__init__.py").is_file():
            return candidate.resolve()
    raise SystemExit("ERROR: cannot locate terry-surveys; set TERRY_SURVEYS_ROOT")


ROOT = resolve_root()
sys.path[:] = [entry for entry in sys.path if entry != str(ROOT)]
sys.path.insert(0, str(ROOT))

from tutorial_harness.cli import main  # noqa: E402

raise SystemExit(main())
