from __future__ import annotations

import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from survey_harness.quality import evaluate


ROOT = Path(__file__).resolve().parents[2]


class PreferenceRegressionTests(unittest.TestCase):
    def setUp(self):
        if not (ROOT / "surveys/robot-hand-tactile-sensor/survey.json").is_file():
            self.skipTest("private survey contents repository is not linked")

    def test_goldens_rank_above_shallow_s9(self):
        results = {slug: evaluate(ROOT, slug, "legacy_baseline") for slug in ("robot-hand-tactile-sensor", "humanoid-revolution", "large-data-manipulation", "nvidia-physical-ai-robotics")}
        self.assertTrue(results["robot-hand-tactile-sensor"]["passed"])
        self.assertTrue(results["humanoid-revolution"]["passed"])
        self.assertTrue(results["large-data-manipulation"]["passed"])
        self.assertFalse(results["nvidia-physical-ai-robotics"]["passed"])
        self.assertGreater(results["robot-hand-tactile-sensor"]["score"], results["nvidia-physical-ai-robotics"]["score"])
        self.assertGreater(results["humanoid-revolution"]["score"], results["nvidia-physical-ai-robotics"]["score"])

    def test_initial_s10_is_negative_fixture(self):
        commit = "00fc5fe"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "fixture.tar"
            result = subprocess.run(["git", "archive", "--format=tar", f"--output={archive}", commit, "build.py", "surveys/large-data-manipulation"], cwd=ROOT, capture_output=True, text=True)
            if result.returncode != 0:
                self.skipTest(f"historical fixture unavailable: {result.stderr.strip()}")
            with tarfile.open(archive) as tf:
                tf.extractall(tmp_path / "repo")
            score = evaluate(tmp_path / "repo", "large-data-manipulation", "legacy_baseline")
            self.assertFalse(score["passed"])
            self.assertLess(score["score"], 72)


if __name__ == "__main__":
    unittest.main()
