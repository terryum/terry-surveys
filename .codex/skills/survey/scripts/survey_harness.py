#!/usr/bin/env python3
"""Run the repository-owned survey harness from canonical or installed skill."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_ROOT = Path("/Users/terrytaewoongum/Codes/personal/terry-surveys")
ROOT = Path(os.environ.get("TERRY_SURVEYS_ROOT", DEFAULT_ROOT)).expanduser().resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from survey_harness.cli import main  # noqa: E402

raise SystemExit(main())
