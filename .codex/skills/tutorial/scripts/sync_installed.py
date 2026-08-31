#!/usr/bin/env python3
"""Delegate to the canonical atomic survey/tutorial skill installer."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("TERRY_SURVEYS_ROOT", "/Users/terrytaewoongum/Codes/personal/terry-surveys")).expanduser().resolve()
script = ROOT / ".codex/skills/survey/scripts/sync_installed.py"
raise SystemExit(subprocess.call([sys.executable, str(script), "--skill", "all", *sys.argv[1:]], cwd=ROOT))
