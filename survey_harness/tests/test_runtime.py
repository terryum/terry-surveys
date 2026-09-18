from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness_runtime import ownership_conflicts, refresh_owned_inputs, revalidate_inputs, snapshot_inputs


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.roots = {"content": self.root, "repo": self.root}

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rel, value):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def test_fingerprints_track_consumed_sources_and_instructions(self):
        self.write("source.md", "source one")
        self.write("SKILL.md", "contract one")
        source = snapshot_inputs(self.roots, [{"root": "content", "path": "source.md"}])
        skill = snapshot_inputs(self.roots, [{"root": "repo", "path": "SKILL.md"}])
        self.assertEqual(revalidate_inputs(self.roots, source), [])
        self.write("SKILL.md", "contract two")
        self.assertEqual(revalidate_inputs(self.roots, source), [])
        self.assertEqual(revalidate_inputs(self.roots, skill), ["repo:SKILL.md"])
        self.write("source.md", "source two")
        self.assertEqual(revalidate_inputs(self.roots, source), ["content:source.md"])

    def test_chapter_record_changes_do_not_invalidate_other_chapters(self):
        rows = [{"ch": "01", "claim": "first"}, {"chapter_hints": [2], "claim": "second"}]
        self.write("claims.jsonl", "\n".join(json.dumps(row) for row in rows))
        snapshot = snapshot_inputs(self.roots, [{"root": "content", "path": "claims.jsonl", "chapter": 1}])
        rows[1]["claim"] = "changed second"
        self.write("claims.jsonl", "\n".join(json.dumps(row) for row in rows))
        self.assertEqual(revalidate_inputs(self.roots, snapshot), [])
        rows[0]["claim"] = "changed first"
        self.write("claims.jsonl", "\n".join(json.dumps(row) for row in rows))
        self.assertEqual(revalidate_inputs(self.roots, snapshot), ["content:claims.jsonl#ch01"])

    def test_chapter_maps_and_status_changes(self):
        data = {"chapters": {"ch01": {"status": "planned", "text": "first"}, "ch02": {"text": "second"}}}
        self.write("plan.json", json.dumps(data))
        snapshot = snapshot_inputs(self.roots, [{"root": "content", "path": "plan.json", "chapter": 1, "ignore_keys": ["status"]}])
        data["chapters"]["ch02"]["text"] = "updated"
        data["chapters"]["ch01"]["status"] = "ready"
        self.write("plan.json", json.dumps(data))
        self.assertEqual(revalidate_inputs(self.roots, snapshot), [])

    def test_directory_snapshots_exclude_caches_but_track_added_source(self):
        self.write("skill/SKILL.md", "contract")
        snapshot = snapshot_inputs(self.roots, [{"root": "repo", "path": "skill"}])
        self.write("skill/__pycache__/module.pyc", "cache")
        self.write("skill/.DS_Store", "finder")
        self.assertEqual(revalidate_inputs(self.roots, snapshot), [])
        self.write("skill/reference.md", "instructions")
        self.assertEqual(revalidate_inputs(self.roots, snapshot), ["repo:skill"])

    def test_ownership_overlap_and_owned_refresh_do_not_bless_neighbors(self):
        self.assertTrue(ownership_conflicts(["book/ko"], ["book/ko/ch01.md"]))
        self.assertFalse(ownership_conflicts(["book/ko/ch01.md"], ["book/ko/ch02.md"]))
        self.assertFalse(ownership_conflicts(["book/ko"], ["book/korean"]))
        self.write("inputs/source.md", "original")
        self.write("inputs/manifest.md", "original")
        snapshot = snapshot_inputs(self.roots, [
            {"root": "content", "path": "inputs", "exclude_paths": ["manifest.md"]},
            {"root": "content", "path": "inputs/manifest.md"},
        ])
        self.write("inputs/manifest.md", "authorized")
        self.assertEqual(revalidate_inputs(self.roots, snapshot, ["inputs/manifest.md"]), [])
        self.write("inputs/source.md", "unauthorized")
        refreshed = refresh_owned_inputs(self.roots, snapshot, ["inputs/manifest.md"])
        self.assertEqual(revalidate_inputs(self.roots, refreshed), ["content:inputs"])

    def test_legacy_snapshot_and_escaping_paths_are_rejected(self):
        self.assertEqual(revalidate_inputs(self.roots, None), ["unverified input snapshot"])
        with self.assertRaisesRegex(ValueError, "within its root"):
            snapshot_inputs(self.roots, [{"root": "content", "path": "../outside"}])


if __name__ == "__main__":
    unittest.main()
