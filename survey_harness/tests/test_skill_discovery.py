from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("discovery_audit", ROOT / "scripts/audit-codex-harness.py")
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


class SkillDiscoveryTests(unittest.TestCase):
    def test_alias_deduplicates_but_distinct_copies_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for root in (base / "canonical", base / "active", base / "installed"):
                root.mkdir()
            skill = base / "canonical/survey"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: survey\ndescription: Test\n---\n")
            (base / "active/survey").symlink_to(skill, target_is_directory=True)
            result = audit_module.audit([base / "canonical", base / "active"])
            self.assertTrue(result["ok"], result)
            other = base / "installed/survey"
            other.mkdir()
            (other / "SKILL.md").write_text((skill / "SKILL.md").read_text())
            result = audit_module.audit([base / "canonical", base / "active", base / "installed"])
            self.assertEqual([x["kind"] for x in result["findings"]], ["duplicate-name"])

    def test_reports_broken_paths_and_unavailable_runtime_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "legacy"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: legacy\ndescription: Test\n---\nTeamCreate(...)\nUse .Codex/agents\n[missing](references/missing.md)\n")
            (root / "gone").symlink_to(root / "missing")
            result = audit_module.audit([root])
            self.assertEqual({x["kind"] for x in result["findings"]}, {"broken-symlink", "codex-path-case", "unavailable-runtime-api", "broken-relative-link"})

    def test_non_call_historical_mentions_do_not_flag_runtime_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "survey"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: survey\ndescription: Test\n---\nDo not rely on Claude `TeamCreate`.\n[Web](https://example.com)\n")
            self.assertTrue(audit_module.audit([root])["ok"])


if __name__ == "__main__":
    unittest.main()
