from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from survey_harness.state import new_state, save_state
from survey_harness.tests.helpers import make_repo

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".codex/skills/survey/scripts/sync_installed.py"


class InstallerTests(unittest.TestCase):
    def test_staged_install_to_isolated_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CODEX_HOME=str(Path(tmp) / "codex-home"))
            project = Path(tmp) / "project"
            result = subprocess.run(["python3", str(SCRIPT), "--apply", "--project-root", str(project)], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = Path(env["CODEX_HOME"]) / "skills/survey"
            tutorial = Path(env["CODEX_HOME"]) / "skills/tutorial"
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "scripts/survey_harness.py").is_file())
            self.assertTrue((tutorial / "SKILL.md").is_file())
            self.assertTrue((tutorial / "scripts/tutorial_harness.py").is_file())
            self.assertIn("SYNCED", result.stdout)
            self.assertEqual((project / ".agents/skills/survey").resolve(), ROOT / ".codex/skills/survey")
            checked = subprocess.run(["python3", str(SCRIPT), "--check", "--project-root", str(project)], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            wrapper_env = dict(env)
            wrapper_env.pop("TERRY_SURVEYS_ROOT", None)
            wrapper = subprocess.run(["python3", str(installed / "scripts/survey_harness.py"), "--help"], cwd=ROOT, env=wrapper_env, capture_output=True, text=True)
            self.assertEqual(wrapper.returncode, 0, wrapper.stderr)
            self.assertIn("survey v2 harness", wrapper.stdout)
            framework = project / "surveys/framework"
            framework.mkdir(parents=True)
            make_repo(framework, "default-survey")
            save_state(framework, new_state(framework, "default-survey", "mini"))
            shutil.copytree(ROOT / "survey_harness", framework / "survey_harness",
                            ignore=shutil.ignore_patterns("__pycache__", "tests"))
            shutil.copyfile(ROOT / "harness_runtime.py", framework / "harness_runtime.py")
            args = ["python3", str(installed / "scripts/survey_harness.py")]
            default = subprocess.check_output(args + ["next", "default-survey"], cwd=project, env=wrapper_env)
            self.assertEqual(json.loads(default)["tasks"][0]["id"], "kg-seed")
            other = Path(tmp) / "explicit"
            other.mkdir()
            make_repo(other, "explicit-survey")
            save_state(other, new_state(other, "explicit-survey", "mini"))
            explicit = subprocess.check_output(
                args + ["--repo-root", str(other), "next", "explicit-survey"], cwd=project, env=wrapper_env,
            )
            self.assertEqual(json.loads(explicit)["slug"], "explicit-survey")
            tutorial_wrapper = subprocess.run(["python3", str(tutorial / "scripts/tutorial_harness.py"), "--help"], cwd=ROOT, env=wrapper_env, capture_output=True, text=True)
            self.assertEqual(tutorial_wrapper.returncode, 0, tutorial_wrapper.stderr)
            self.assertIn("action-first tutorial harness", tutorial_wrapper.stdout)

    def test_discovery_archive_is_opt_in_and_preserves_material(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            skills = project / ".agents/skills"
            for name in ("survey", "survey-lite", "other-custom-skill"):
                (skills / name).mkdir(parents=True)
                (skills / name / "SKILL.md").write_text(f"original {name}")
            env = dict(os.environ, CODEX_HOME=str(Path(tmp) / "home"))
            args = ["python3", str(SCRIPT), "--project-root", str(project)]
            dry = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertFalse((skills / "survey").is_symlink())
            applied = subprocess.run(args + ["--apply", "--archive-legacy"], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            backup = Path(next(line.removeprefix("DISCOVERY BACKUP ") for line in applied.stdout.splitlines() if line.startswith("DISCOVERY BACKUP ")))
            self.assertEqual((backup / "survey/SKILL.md").read_text(), "original survey")
            self.assertEqual((backup / "survey-lite/SKILL.md").read_text(), "original survey-lite")
            self.assertTrue((backup / "manifest.json").is_file())
            self.assertFalse((skills / "survey-lite").exists())
            self.assertEqual((skills / "other-custom-skill/SKILL.md").read_text(), "original other-custom-skill")

    def test_check_detects_installed_drift_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            env = dict(os.environ, CODEX_HOME=str(Path(tmp) / "home"))
            args = ["python3", str(SCRIPT), "--project-root", str(project)]
            subprocess.run(args + ["--apply"], cwd=ROOT, env=env, check=True, capture_output=True)
            installed = Path(env["CODEX_HOME"]) / "skills/survey/SKILL.md"
            installed.write_text("changed locally")
            checked = subprocess.run(args + ["--check"], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(checked.returncode, 1)
            self.assertEqual(installed.read_text(), "changed locally")


if __name__ == "__main__":
    unittest.main()
