"""OLMS rate-limits aggressive clients with HTTP 403s.

Treat those as "slow down", not as content: back off the download slot,
retry the request a few times, and if the server keeps blocking anyway,
close the spider so the run ends with an obviously short output (which
the Makefile guards turn into a failure) instead of quietly merging
partial data.
"""

import logging

from scrapy.downloadermiddlewares.retry import get_retry_request

logger = logging.getLogger(__name__)


class BlockingBackoffMiddleware:
    BLOCK_CODES = (403, 429)
    MAX_RETRIES = 4
    MAX_CONSECUTIVE_BLOCKS = 50
    INITIAL_BACKOFF = 5.0
    MAX_BACKOFF = 300.0

    def __init__(self, crawler):
        self.crawler = crawler
        self.consecutive_blocks = 0
        self.closing = False

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_response(self, request, response, spider):
        if response.status not in self.BLOCK_CODES:
            self.consecutive_blocks = 0
            return response

        self.consecutive_blocks += 1
        if self.consecutive_blocks >= self.MAX_CONSECUTIVE_BLOCKS:
            if not self.closing:
                self.closing = True
                logger.error(
                    "%d consecutive %s responses; OLMS has blocked us — "
                    "closing %s",
                    self.consecutive_blocks,
                    response.status,
                    spider.name,
                )
                self.crawler.engine.close_spider(spider, "blocked_by_server")
            return response

        self._back_off(request, response)
        retry = get_retry_request(
            request,
            spider=spider,
            reason=f"HTTP {response.status} (rate limited)",
            max_retry_times=self.MAX_RETRIES,
            stats_base_key="block_backoff",
        )
        if retry is None:
            return response
        return retry

    def _back_off(self, request, response):
        key = request.meta.get("download_slot")
        slot = self.crawler.engine.downloader.slots.get(key) if key else None
        if slot is None:
            return
        new_delay = min(max(slot.delay * 2, self.INITIAL_BACKOFF), self.MAX_BACKOFF)
        if new_delay > slot.delay:
            logger.warning(
                "HTTP %s from %s; backing off download slot to %.0fs",
                response.status,
                request.url,
                new_delay,
            )
            slot.delay = new_delay
