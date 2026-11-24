"""Offline tests for page parsing and matching (no network)."""

import datetime
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import build_search_query, first_page_url  # noqa: E402
from database import DatabaseManager  # noqa: E402
from performance import PerformanceTracker  # noqa: E402
from searcher import Ad, BazosSearcher, parse_list_page  # noqa: E402

LIST_PAGE = """
<html><body>
<div class="inzeraty inzeratyflex">
<div class="inzeratynadpis"><a href="/inzerat/1/board-a.php"><img src="x.jpg"></a>
<h2 class=nadpis><a href="/inzerat/1/board-a.php">Snowboard Burton 158</a></h2><span class=velikost10> - [24.11. 2026]</span><br>
<div class=popis>Prodam <b>snowboard</b>, delka 158 cm.</div>
</div>
<div class="inzeratycena"><b><span translate="no">  2 690 Kč</span></b></div>
<div class="inzeratylok">Praha 7<br>170 00</div>
</div>
<div class="inzeraty inzeratyflex">
<div class="inzeratynadpis"><a href="/inzerat/2/board-b.php"><img src="x.jpg"></a>
<h2 class=nadpis><a href="/inzerat/2/board-b.php">Snowboard Nitro</a></h2><span class=velikost10> - [3.1. 2026]</span><br>
<div class=popis>Malo jety.</div>
</div>
<div class="inzeratycena"><b><span translate="no">Dohodou</span></b></div>
<div class="inzeratylok">Brno<br>602 00</div>
</div>
<div class="strankovani">Stránka: <b>1</b> <a href="/snowboard/40/?hledat=snowboard">2</a>
<a href="/snowboard/40/?hledat=snowboard"><b>Další</b></a></div>
</body></html>
""".encode("utf-8")


class FakeClient:
    def __init__(self, texts):
        self.texts = texts
        self.fetched = []

    def fetch_ad_text(self, url):
        self.fetched.append(url)
        return self.texts.get(url, "")


class ParseTests(unittest.TestCase):
    def test_parse_list_page(self):
        ads, next_url = parse_list_page(LIST_PAGE)
        self.assertEqual(len(ads), 2)
        a = ads[0]
        self.assertEqual(a.url, "/inzerat/1/board-a.php")
        self.assertEqual(a.title, "Snowboard Burton 158")
        self.assertEqual(a.price, "2 690 Kč")
        self.assertEqual(a.location, "Praha 7 170 00")
        self.assertEqual(a.date, "24.11.2026")
        self.assertIn("158 cm", a.summary)
        self.assertEqual(a.full_url, "https://sport.bazos.cz/inzerat/1/board-a.php")
        self.assertEqual(next_url, "https://sport.bazos.cz/snowboard/40/?hledat=snowboard")

    def test_last_page_has_no_next(self):
        page = LIST_PAGE.replace("Další".encode("utf-8"), b"x")
        _, next_url = parse_list_page(page)
        self.assertIsNone(next_url)

    def test_urls(self):
        q = build_search_query("snowboard", "11000", 50, "1000", "6000")
        self.assertEqual(q, "?hledat=snowboard&hlokalita=11000&humkreis=50&cenaod=1000&cenado=6000&order=")
        self.assertEqual(first_page_url(q), "https://sport.bazos.cz/snowboard/" + q)
        self.assertEqual(first_page_url("https://sport.bazos.cz/snowboard/?x=1"),
                         "https://sport.bazos.cz/snowboard/?x=1")


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(os.path.join(self.tmp.name, "t.db"))
        self.db.init_db()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def make(self, texts, cache_days=7):
        client = FakeClient(texts)
        return BazosSearcher(self.db, client, PerformanceTracker(), 2, cache_days), client

    def test_list_text_match_skips_detail_fetch(self):
        s, client = self.make({})
        ad = Ad("/inzerat/1/a.php", "Burton 158", "", "", "", "")
        self.assertTrue(s.matches(ad, re.compile("15[5-9]")))
        self.assertEqual(client.fetched, [])

    def test_detail_match_and_cache(self):
        s, client = self.make({"/inzerat/2/b.php": "Delka 163 cm, wide"})
        ad = Ad("/inzerat/2/b.php", "Nitro", "Malo jety", "", "", "")
        rx = re.compile(r"(?<!\d)16[0-9](?!\d)")
        self.assertTrue(s.matches(ad, rx))
        self.assertTrue(s.matches(ad, rx))
        self.assertEqual(client.fetched, ["/inzerat/2/b.php"])  # second time from cache

    def test_stale_cache_is_refreshed(self):
        s, client = self.make({"/inzerat/3/c.php": "new text 160"}, cache_days=0)
        self.db.save_content("/inzerat/3/c.php", "old text")
        ad = Ad("/inzerat/3/c.php", "x", "", "", "", "")
        self.assertTrue(s.matches(ad, re.compile("160")))
        self.assertEqual(client.fetched, ["/inzerat/3/c.php"])

    def test_db_roundtrip(self):
        self.db.save_content("/u", "hello")
        content, ts = self.db.get_ad_content("/u")
        self.assertEqual(content, "hello")
        self.assertIsInstance(ts, datetime.datetime)
        self.assertEqual(self.db.get_ad_content("/missing"), (None, None))


if __name__ == "__main__":
    unittest.main()
