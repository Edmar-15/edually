from pathlib import Path

from django.test import TestCase


class ForumResponsiveLayoutTests(TestCase):
    def test_feed_css_avoids_hardcoded_desktop_left_margin(self):
        css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "feed.css"
        css = css_path.read_text(encoding="utf-8")

        self.assertNotIn("margin: 0 auto 0 133px;", css)
        self.assertNotIn("margin-left: 133px;", css)
