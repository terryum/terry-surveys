#!/usr/bin/env python3
"""Run the repository-owned survey harness from canonical or installed skill."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")


def resolve_root() -> Path:
    configured = os.environ.get("TERRY_SURVEYS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if (DEFAULT_ROOT / "survey_harness/__init__.py").is_file():
        return DEFAULT_ROOT.resolve()
    for candidate in (Path.cwd(), *Path.cwd().parents):
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

raise SystemExit(main())
