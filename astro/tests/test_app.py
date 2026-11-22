"""Tests for the AP reports pages.  Run:  .venv/bin/python -m unittest -v tests.test_app"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as webapp  # noqa: E402

REPORT = """# Andhra Pradesh investment report

_15 Nov 2026 to 22 Nov 2026_

## 2. New investments
| Date | Company | Amount |
|---|---|---|
| 18 Nov | Example Ltd | 1,200 |

- [Source](https://example.com/news)
- [Bad link](javascript:alert(1))

<script>alert('x')</script>
<img src=x onerror=alert(1)>
"""


class TestApReports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "2026-11-22.md").write_text(REPORT)
        (d / "2026-11-15.md").write_text("# Andhra Pradesh investment report\n\n_8 Nov 2026 to 15 Nov 2026_\n\nOlder.\n")
        (d / "notes.txt").write_text("ignored")
        self.old = webapp.AP_REPORT_DIR
        webapp.AP_REPORT_DIR = d
        self.client = webapp.app.test_client()

    def tearDown(self):
        webapp.AP_REPORT_DIR = self.old
        self.tmp.cleanup()

    def test_list_is_newest_first_and_skips_other_files(self):
        self.assertEqual([r["date"] for r in webapp.list_reports()], ["2026-11-22", "2026-11-15"])
        self.assertEqual(webapp.list_reports()[0]["period"], "15 Nov 2026 to 22 Nov 2026")

    def test_index_shows_latest(self):
        html = self.client.get("/ap-reports").get_data(as_text=True)
        self.assertIn("Example Ltd", html)
        self.assertIn("<table>", html)
        self.assertIn("Week ending 15 Nov 2026", html)

    def test_specific_week(self):
        r = self.client.get("/ap-reports/2026-11-15")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Older.", r.get_data(as_text=True))

    def test_unsafe_content_is_removed(self):
        html = self.client.get("/ap-reports/2026-11-22").get_data(as_text=True)
        article = html.split("<article>")[1].split("</article>")[0]
        self.assertNotIn("<script", article)
        self.assertNotIn("onerror", article)
        self.assertNotIn("javascript:", article)
        self.assertIn('href="https://example.com/news"', article)

    def test_missing_and_bad_paths_are_404(self):
        for path in ("/ap-reports/2020-01-01", "/ap-reports/..%2F..%2Fetc%2Fpasswd",
                     "/ap-reports/notes"):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_empty_folder(self):
        webapp.AP_REPORT_DIR = Path(self.tmp.name) / "missing"
        r = self.client.get("/ap-reports")
        self.assertEqual(r.status_code, 200)
        self.assertIn("No reports found", r.get_data(as_text=True))

    def test_chart_page_links_to_reports(self):
        self.assertIn('href="/ap-reports"', self.client.get("/").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
