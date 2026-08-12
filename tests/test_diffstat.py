"""Tests for the diff statistics helper."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".github", "scripts"))

from diffstat import FileStat, format_diffstat, parse_diffstat  # noqa: E402

SAMPLE = """\
diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
 import os
-old_line = 1
+new_line = 1
+extra_line = 2
 tail = 3
diff --git a/README.md b/README.md
index 3333333..4444444 100644
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-# Old
+# New
"""


class TestParseDiffstat(unittest.TestCase):
    def test_counts_added_and_removed_per_file(self):
        stats = {s.path: s for s in parse_diffstat(SAMPLE)}
        self.assertEqual((stats["src/app.py"].added, stats["src/app.py"].removed), (2, 1))
        self.assertEqual((stats["README.md"].added, stats["README.md"].removed), (1, 1))

    def test_file_headers_are_not_counted_as_content(self):
        # The +++/--- lines would otherwise inflate every file by one each.
        total_added = sum(s.added for s in parse_diffstat(SAMPLE))
        self.assertEqual(total_added, 3)

    def test_ordered_by_churn_then_path(self):
        self.assertEqual([s.path for s in parse_diffstat(SAMPLE)], ["src/app.py", "README.md"])

    def test_no_newline_marker_is_ignored(self):
        diff = (
            "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n"
            "@@ -1 +1 @@\n-old\n+new\n\\ No newline at end of file\n"
        )
        stat = parse_diffstat(diff)[0]
        self.assertEqual((stat.added, stat.removed), (1, 1))

    def test_new_file_with_no_removals(self):
        diff = (
            "diff --git a/new.py b/new.py\nnew file mode 100644\n"
            "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+one\n+two\n"
        )
        self.assertEqual(parse_diffstat(diff), [FileStat("new.py", 2, 0)])

    def test_empty_and_garbage_input_yield_no_stats(self):
        for bad in ("", "not a diff at all", "@@ -1 +1 @@\n+orphan hunk\n"):
            self.assertEqual(parse_diffstat(bad), [])

    def test_churn_is_the_sum(self):
        self.assertEqual(FileStat("x", 3, 4).churn, 7)


class TestFormatDiffstat(unittest.TestCase):
    def test_renders_a_markdown_list(self):
        out = format_diffstat(parse_diffstat(SAMPLE))
        self.assertIn("- `src/app.py` +2/-1", out)
        self.assertIn("- `README.md` +1/-1", out)

    def test_truncates_and_summarizes_the_remainder(self):
        stats = [FileStat(f"f{i}.py", 2, 1) for i in range(12)]
        out = format_diffstat(stats, limit=3)
        self.assertEqual(len(out.splitlines()), 4)
        self.assertIn("9 more file(s), +18/-9", out)

    def test_empty_stats_have_a_readable_placeholder(self):
        self.assertEqual(format_diffstat([]), "(no file statistics available)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
