from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".codex/skills/survey/scripts/import_chatgpt_share.py"


def flatten(value):
    values = []

    def add(item):
        index = len(values)
        values.append(None)
        if isinstance(item, dict):
            values[index] = {f"_{add(key)}": add(child) for key, child in item.items()}
        elif isinstance(item, list):
            values[index] = [add(child) for child in item]
        else:
            values[index] = item
        return index

    add(value)
    return values


class ChatGPTShareImportTests(unittest.TestCase):
    def test_converts_active_user_assistant_branch_to_markdown(self):
        mapping = {
            "root": {"parent": None, "message": None},
            "user": {
                "parent": "root",
                "message": {"author": {"role": "user"}, "content": {"parts": ["Find papers"]}},
            },
            "tool": {
                "parent": "user",
                "message": {"author": {"role": "tool"}, "content": {"parts": ["hidden result"]}},
            },
            "assistant": {
                "parent": "tool",
                "message": {
                    "author": {"role": "assistant"},
                    "content": {"parts": ["Answer \ue200cite\ue202turn1search0\ue201"]},
                },
            },
        }
        root = {
            "loaderData": {
                "routes/share.$shareId.($action)": {
                    "serverResponse": {
                        "data": {
                            "title": "Demo research",
                            "conversation_id": "demo-id",
                            "mapping": mapping,
                            "current_node": "assistant",
                        }
                    }
                }
            }
        }
        payload = json.dumps(flatten(root), ensure_ascii=False, separators=(",", ":"))
        html = (
            "<html><script>window.__reactRouterContext.streamController.enqueue("
            + json.dumps(payload, ensure_ascii=False)
            + ")</script></html>"
        )

        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "share.html"
            output_path = Path(tmp) / "share.md"
            html_path.write_text(html, encoding="utf-8")
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "https://chatgpt.com/share/demo-id",
                    "--html",
                    str(html_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            markdown = output_path.read_text(encoding="utf-8")
            self.assertIn("# Demo research", markdown)
            self.assertIn("## User 1\n\nFind papers", markdown)
            self.assertIn("## Assistant 1", markdown)
            self.assertIn("Opaque ChatGPT citation omitted", markdown)
            self.assertNotIn("hidden result", markdown)
            self.assertIn("trust: briefing_only", markdown)

    def test_rejects_non_share_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["python3", str(SCRIPT), "https://example.com/share/nope", "--output", str(Path(tmp) / "x.md")],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("expected an https://chatgpt.com/share", result.stderr)


if __name__ == "__main__":
    unittest.main()
