from pathlib import Path

from scrapy.extensions.httpcache import FilesystemCacheStorage


class SharedFilesystemCacheStorage(FilesystemCacheStorage):
    """Cache responses in one namespace instead of per-spider.

    The stock FilesystemCacheStorage keys paths by spider.name, so the
    three *_incremental spiders would each re-fetch the same filer
    detail-servlet responses. Sharing the namespace lets one update run
    fetch each response once.
    """

    def _get_request_path(self, spider, request):
        key = self._fingerprinter.fingerprint(request).hex()
        return str(Path(self.cachedir, "shared", key[0:2], key))
