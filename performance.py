"""Simple thread-safe performance counters."""

import threading
import time


class PerformanceTracker:
    def __init__(self):
        self.start_time = None
        self.page_times = []
        self.request_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.fetch_times = []
        self.lock = threading.Lock()

    def start(self):
        self.start_time = time.time()

    def record_page(self, page_num, duration):
        with self.lock:
            self.page_times.append((page_num, duration))

    def record_request(self):
        with self.lock:
            self.request_count += 1

    def record_cache_hit(self):
        with self.lock:
            self.cache_hits += 1

    def record_cache_miss(self):
        with self.lock:
            self.cache_misses += 1

    def record_fetch_time(self, duration):
        with self.lock:
            self.fetch_times.append(duration)

    def get_stats(self) -> str:
        if not self.start_time:
            return "No timing data available"
        with self.lock:
            total = max(time.time() - self.start_time, 1e-9)
            lookups = self.cache_hits + self.cache_misses
            hit_rate = self.cache_hits / lookups * 100 if lookups else 0
            avg_fetch = sum(self.fetch_times) / len(self.fetch_times) if self.fetch_times else 0
            return (
                "\nStats:\n"
                f"  Total time:       {total:.2f}s\n"
                f"  Pages:            {len(self.page_times)}\n"
                f"  HTTP requests:    {self.request_count} (avg {avg_fetch:.3f}s)\n"
                f"  Cache hit rate:   {hit_rate:.1f}% ({self.cache_hits} hits, {self.cache_misses} misses)\n"
            )
