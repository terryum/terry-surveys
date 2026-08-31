from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".codex/skills/survey/scripts/sync_installed.py"


class InstallerTests(unittest.TestCase):
    def test_staged_install_to_isolated_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CODEX_HOME=str(Path(tmp) / "codex-home"))
            result = subprocess.run(["python3", str(SCRIPT), "--apply"], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = Path(env["CODEX_HOME"]) / "skills/survey"
            tutorial = Path(env["CODEX_HOME"]) / "skills/tutorial"
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "scripts/survey_harness.py").is_file())
            self.assertTrue((tutorial / "SKILL.md").is_file())
            self.assertTrue((tutorial / "scripts/tutorial_harness.py").is_file())
            self.assertIn("SYNCED", result.stdout)
            wrapper_env = dict(env)
            wrapper_env.pop("TERRY_SURVEYS_ROOT", None)
            wrapper = subprocess.run(["python3", str(installed / "scripts/survey_harness.py"), "--help"], cwd=ROOT, env=wrapper_env, capture_output=True, text=True)
            self.assertEqual(wrapper.returncode, 0, wrapper.stderr)
            self.assertIn("survey v2 harness", wrapper.stdout)
            tutorial_wrapper = subprocess.run(["python3", str(tutorial / "scripts/tutorial_harness.py"), "--help"], cwd=ROOT, env=wrapper_env, capture_output=True, text=True)
            self.assertEqual(tutorial_wrapper.returncode, 0, tutorial_wrapper.stderr)
            self.assertIn("action-first tutorial harness", tutorial_wrapper.stdout)


if __name__ == "__main__":
    unittest.main()
