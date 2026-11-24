#!/usr/bin/env python3
"""Search snowboard ads on sport.bazos.cz and filter them with a regex.

The regex is matched against the ad title, the list-page summary and, if
needed, the full ad text (cached locally in SQLite).
"""

import argparse
import csv
import logging
import sys

from client import BazosClient
from config import (DEFAULT_CACHE_DAYS, DEFAULT_DB_PATH, DEFAULT_THREADS,
                    build_search_query, first_page_url)
from database import DatabaseManager
from performance import PerformanceTracker
from searcher import BazosSearcher

EPILOG = r"""
examples:
  # every snowboard ad in the category
  python scraper.py

  # 160-175 cm boards, 1000-6000 CZK, within 50 km of Praha 1
  python scraper.py "(?<!\d)(16[0-9]|17[0-5])(?!\d)" --location 11000 --radius 50 --price-from 1000 --price-to 6000

  # Burton boards around 160 cm, save to CSV
  python scraper.py "16[0-2]" --query burton --csv burton.csv

  # raw Bazos query string (copy everything from '?' in the browser URL)
  python scraper.py "15[5-9]" --search-url "?hledat=snowboard&hlokalita=&humkreis=25&cenaod=&cenado=5000&order="
"""


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, epilog=EPILOG,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pattern", nargs="?", default=".*",
                   help='regex matched (case-insensitive) in title/description (default: ".*")')
    s = p.add_argument_group("search filters (ignored if --search-url is given)")
    s.add_argument("--query", default="snowboard", help='Bazos keyword search (default: "snowboard")')
    s.add_argument("--location", default="", help="Czech postal code to search around, e.g. 11000")
    s.add_argument("--radius", type=int, default=25, help="radius in km around --location (default: 25)")
    s.add_argument("--price-from", default="", help="minimum price in CZK")
    s.add_argument("--price-to", default="", help="maximum price in CZK")
    p.add_argument("--search-url", help="raw Bazos query string or full results URL")
    o = p.add_argument_group("output / tuning")
    o.add_argument("--csv", metavar="FILE", help="also write matches to a CSV file")
    o.add_argument("--max-pages", type=int, help="stop after N result pages")
    o.add_argument("--threads", type=int, default=DEFAULT_THREADS,
                   help=f"parallel ad downloads (default: {DEFAULT_THREADS})")
    o.add_argument("--cache-days", type=int, default=DEFAULT_CACHE_DAYS,
                   help=f"re-download cached ad text older than N days (default: {DEFAULT_CACHE_DAYS})")
    o.add_argument("--db", default=DEFAULT_DB_PATH, help=f"cache file (default: {DEFAULT_DB_PATH})")
    o.add_argument("--stats", action="store_true", help="print timing/cache statistics")
    o.add_argument("-v", "--verbose", action="store_true", help="log progress to stderr")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    query = args.search_url or build_search_query(args.query, args.location, args.radius,
                                                  args.price_from, args.price_to)
    start_url = first_page_url(query)
    print(f"Searching {start_url}\nPattern: {args.pattern}\n")

    perf = PerformanceTracker()
    db = DatabaseManager(args.db)
    db.init_db()
    client = BazosClient(perf, max_workers=args.threads)
    searcher = BazosSearcher(db, client, perf, max_workers=args.threads, cache_days=args.cache_days)

    csv_file = open(args.csv, "w", newline="", encoding="utf-8-sig") if args.csv else None
    writer = csv.writer(csv_file) if csv_file else None
    if writer:
        writer.writerow(["price", "location", "date", "title", "url"])

    count = 0
    try:
        for ad in searcher.search(args.pattern, start_url, args.max_pages):
            count += 1
            print(f"{count:3}. {ad.price:>10} | {ad.location:<20} | {ad.date:<10} | {ad.title}")
            print(f"     {ad.full_url}")
            if writer:
                writer.writerow([ad.price, ad.location, ad.date, ad.title, ad.full_url])
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        db.close()
        if csv_file:
            csv_file.close()

    print(f"\nFound {count} matching ads.")
    if args.csv:
        print(f"Saved to {args.csv}")
    if args.stats:
        print(perf.get_stats())
    return 0


if __name__ == "__main__":
    sys.exit(main())
