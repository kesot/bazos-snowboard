"""HTTP client for Bazos."""

import logging
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import USER_AGENT, absolute_url
from performance import PerformanceTracker


class RateLimited(SystemExit):
    pass


class BazosClient:
    def __init__(self, perf_tracker: PerformanceTracker, max_workers: int):
        self.perf_tracker = perf_tracker
        self.logger = logging.getLogger("BazosClient")

        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        adapter = HTTPAdapter(
            pool_connections=5,
            pool_maxsize=max(max_workers * 2, 10),
            max_retries=Retry(total=3, backoff_factor=0.5,
                              status_forcelist=[500, 502, 503, 504]),
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def fetch_url(self, url: str) -> Optional[bytes]:
        """Fetch a URL. Returns None on 404."""
        self.logger.info("requesting %s", url)
        self.perf_tracker.record_request()
        start = time.time()
        response = self.session.get(url, timeout=30)
        self.perf_tracker.record_fetch_time(time.time() - start)

        if response.status_code == 404:
            self.logger.info("404 for %s", url)
            return None
        if response.status_code == 429:
            raise RateLimited("Rate limited by Bazos (HTTP 429) - wait a few minutes "
                              "and retry, or use fewer --threads.")
        if response.status_code != 200:
            raise RuntimeError(f"GET {url} failed with HTTP {response.status_code}")
        return response.content

    def fetch_ad_text(self, relative_url: str) -> str:
        """Fetch the full description of an ad."""
        content = self.fetch_url(absolute_url(relative_url))
        if content is None:
            return ""
        soup = BeautifulSoup(content, "html.parser")
        element = soup.find("div", class_="popisdetail")
        return element.get_text("\n") if element else ""
