"""Search logic: walk Bazos result pages and match ads against a regex."""

import datetime
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterator, List, Optional

from bs4 import BeautifulSoup

from client import BazosClient
from config import absolute_url
from database import DatabaseManager
from performance import PerformanceTracker

DATE_RE = re.compile(r"\[(\d{1,2}\.\d{1,2}\.\s?\d{4})\]")


@dataclass
class Ad:
    url: str          # relative, e.g. /inzerat/123/slug.php
    title: str
    summary: str      # short description shown in the list
    price: str
    location: str
    date: str

    @property
    def full_url(self) -> str:
        return absolute_url(self.url)


def _text(node, sep=" ") -> str:
    return " ".join(node.get_text(sep).split()) if node else ""


def parse_list_page(content: bytes) -> tuple[List[Ad], Optional[str]]:
    """Parse a results page. Returns (ads, absolute URL of next page or None)."""
    soup = BeautifulSoup(content, "html.parser")
    ads = []
    for div in soup.select("div.inzeraty.inzeratyflex"):
        link = div.select_one("h2.nadpis a") or div.select_one("div.inzeratynadpis a")
        if not link or not link.get("href"):
            continue
        header = div.select_one("div.inzeratynadpis")
        date = DATE_RE.search(header.get_text(" ") if header else "")
        ads.append(Ad(
            url=link["href"],
            title=_text(link),
            summary=_text(div.select_one("div.popis")),
            price=_text(div.select_one("div.inzeratycena")),
            location=_text(div.select_one("div.inzeratylok")),
            date=date.group(1).replace(" ", "") if date else "",
        ))

    next_url = None
    pager = soup.select_one("div.strankovani")
    if pager:
        for a in pager.find_all("a"):
            if a.get_text(strip=True) == "Další" and a.get("href"):
                next_url = absolute_url(a["href"])
                break
    return ads, next_url


class BazosSearcher:
    def __init__(self, db: DatabaseManager, client: BazosClient, perf: PerformanceTracker,
                 max_workers: int, cache_days: int):
        self.db = db
        self.client = client
        self.perf = perf
        self.max_workers = max_workers
        self.cache_age = datetime.timedelta(days=cache_days)
        self.logger = logging.getLogger("BazosSearcher")

    def get_ad_text(self, relative_url: str) -> str:
        """Full ad description, from cache if fresh enough."""
        cached, refreshed = self.db.get_ad_content(relative_url)
        if cached is not None and refreshed and datetime.datetime.now() - refreshed < self.cache_age:
            self.perf.record_cache_hit()
            return cached
        self.perf.record_cache_miss()
        text = self.client.fetch_ad_text(relative_url)
        self.db.save_content(relative_url, text)
        return text

    def matches(self, ad: Ad, regex: re.Pattern) -> bool:
        # Cheap check on list-page text first; only open the ad if needed.
        if regex.search(ad.title) or regex.search(ad.summary):
            return True
        return regex.search(self.get_ad_text(ad.url)) is not None

    def _check(self, ad: Ad, regex: re.Pattern) -> bool:
        try:
            return self.matches(ad, regex)
        except SystemExit:
            raise
        except Exception as e:  # one broken ad shouldn't stop the search
            self.logger.error("error processing %s: %s", ad.url, e)
            return False

    def search(self, pattern: str, start_url: str, max_pages: Optional[int] = None) -> Iterator[Ad]:
        """Yield matching ads, page by page, in site order."""
        regex = re.compile(pattern, re.IGNORECASE)
        seen = set()
        url, page = start_url, 0
        self.perf.start()
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            while url and (max_pages is None or page < max_pages):
                page_start = time.time()
                content = self.client.fetch_url(url)
                if content is None:
                    break
                ads, url = parse_list_page(content)
                ads = [a for a in ads if a.url not in seen]
                seen.update(a.url for a in ads)
                for ad, ok in zip(ads, pool.map(lambda a: self._check(a, regex), ads)):
                    if ok:
                        yield ad
                self.perf.record_page(page, time.time() - page_start)
                self.logger.info("page %d: %d ads", page, len(ads))
                page += 1
