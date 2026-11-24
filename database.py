"""SQLite cache of ad descriptions, so repeated searches don't re-download every ad."""

import datetime
import sqlite3
import threading
from contextlib import closing
from typing import Optional, Tuple


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        self.lock = threading.Lock()

    def init_db(self):
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS ads (urlId TEXT, lastRefreshed TEXT, content TEXT)")
        self.connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS url_key ON ads (urlId)")
        self.connection.commit()

    def save_content(self, relative_url: str, content: str):
        now = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
        with self.lock, closing(self.connection.cursor()) as cur:
            cur.execute(
                "INSERT OR REPLACE INTO ads(urlId, content, lastRefreshed) VALUES (?, ?, ?)",
                (relative_url, content, now))
            self.connection.commit()

    def get_ad_content(self, relative_url: str) -> Tuple[Optional[str], Optional[datetime.datetime]]:
        """Return (content, last_refreshed) or (None, None) if not cached."""
        with self.lock, closing(self.connection.cursor()) as cur:
            cur.execute("SELECT content, lastRefreshed FROM ads WHERE urlId=?", (relative_url,))
            row = cur.fetchone()
        if row is None:
            return None, None
        try:
            refreshed = datetime.datetime.fromisoformat(str(row[1]))
        except ValueError:
            refreshed = None
        return row[0], refreshed

    def close(self):
        if self.connection:
            self.connection.close()
