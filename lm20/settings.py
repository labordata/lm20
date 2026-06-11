# Scrapy settings for lm20 project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "lm20"

SPIDER_MODULES = ["lm20.spiders"]
NEWSPIDER_MODULE = "lm20.spiders"

SPIDER_CONTRACTS = {
    "lm20.contracts.FilersFormContract": 10,
    "lm20.contracts.FilingsFormContract": 11,
    "lm20.contracts.EmployersFormContract": 12,
}

# Crawl responsibly by identifying yourself (and your website) on the user-agent
from olms import USER_AGENT  # noqa: E402, F401

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

FILES_STORE = "./reports"
# Report documents already in ./reports (the tracked files restored by
# checkout) are not re-downloaded within the default FILES_EXPIRES
# window — skipping them is most of the traffic reduction that keeps
# OLMS from 403-blocking the incremental crawls.

# OLMS 403-blocks heavy traffic, so crawl lightly: cap per-domain
# concurrency and let AutoThrottle pace requests by observed latency.
# BlockingBackoffMiddleware handles any 403/429 that still gets
# through (exponential backoff + retry, abort when persistently
# blocked).
CONCURRENT_REQUESTS_PER_DOMAIN = 4

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# Disable cookies (enabled by default)
# COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
# DEFAULT_REQUEST_HEADERS = {
#   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#   'Accept-Language': 'en',
# }

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    "olms.middleware.BlockingBackoffMiddleware": 560,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
# EXTENSIONS = {
#    'scrapy.extensions.telnet.TelnetConsole': None,
# }

