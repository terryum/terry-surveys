from __future__ import annotations

import unittest

from shared.build_site import md_to_html_content


class BuildSiteTests(unittest.TestCase):
    def test_claim_anchor_is_not_rendered(self):
        markdown = """# Chapter

## Evidence

<!-- claim:ch01-c01 -->

        Supported reader-facing prose. <!-- claim:ch01-c02 -->
"""

        rendered = md_to_html_content(markdown, 1, "en")

        self.assertNotIn("claim:ch01-c01", rendered)
        self.assertNotIn("claim:ch01-c02", rendered)
        self.assertNotIn("<p></p>", rendered)
        self.assertIn("<p>Supported reader-facing prose.</p>", rendered)


if __name__ == "__main__":
    unittest.main()
