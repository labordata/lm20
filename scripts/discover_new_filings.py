"""Discover filers (srNums) with new LM-20 or LM-21 activity since
lm20.db's max rptId.

rptIds in OLMS are monotonically increasing with receiveDate across all
form types. Bisect `orgReport.do` to find the current max-assigned
rptId, forward-scan the new window for LM-20/LM-21 hits, then parse
each hit's HTML for the filer's srNum. srNums go to stdout, one per
line.

Paper filings come back as PDFs we can't trivially parse; we skip them
and let the periodic full backfill pick them up.

Usage: python scripts/discover_new_filings.py lm20.db
"""

import argparse
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3
from parsel import Selector

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REPORT_URL = "https://olmsapps.dol.gov/query/orgReport.do?rptId={}&rptForm={}"
PROBE_FORMS = ("LM2Form", "LM10Form", "LM20Form", "LM30Form", "S1Form")
SCAN_FORMS = ("LM20Form", "LM21Form")
SCAN_CONCURRENCY = 1
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def _session():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    s.verify = False
    return s


def fetch_assigned(session, rpt_id, form):
    """True if `rpt_id` is assigned to `form`.

    Real form pages embed an Angular app (`ng-app="LM20App"` etc.) and
    fetch their data asynchronously. The OLMS "not found" page is a
    plain HTML stub without ng-app.
    """
    r = session.get(REPORT_URL.format(rpt_id, form), timeout=30)
    ct = r.headers.get("Content-Type", "").split(";")[0].strip()
    if ct == "application/pdf":
        return True
    return ct == "text/html" and b"ng-app=" in r.content


def is_assigned(session, rpt_id):
    with ThreadPoolExecutor(max_workers=len(PROBE_FORMS)) as ex:
        return any(ex.map(lambda f: fetch_assigned(session, rpt_id, f), PROBE_FORMS))


def fetch_lm2021_html(session, rpt_id):
    """Return (html_bytes, form_name) if rpt_id is an electronic LM-20 or
    LM-21, else None."""
    for form in SCAN_FORMS:
        r = session.get(REPORT_URL.format(rpt_id, form), timeout=30)
        ct = r.headers.get("Content-Type", "").split(";")[0].strip()
        if ct == "text/html" and b"Signature" in r.content:
            return r.content, form
    return None, None


def bisect_max_assigned(session, low, initial_step=10_000, max_probes=40):
    """Largest assigned rptId > `low` via geometric expansion + binary search."""
    lo = low
    step = initial_step
    probe = low + step
    while True:
        if is_assigned(session, probe):
            lo = probe
            step *= 2
            probe = low + step
            if step > 10_000_000:
                raise RuntimeError("runaway expansion — check OLMS connectivity")
        else:
            hi = probe
            break
    for _ in range(max_probes):
        if hi - lo <= 1:
            break
        mid = (lo + hi) // 2
        if is_assigned(session, mid):
            lo = mid
        else:
            hi = mid
    return lo


def extract_sr_num(html_bytes):
    sel = Selector(text=html_bytes.decode("utf-8", errors="replace"))
    # LM-20: "1.a. File Number: C-"
    val = sel.xpath(
        "//span[@class='i-label' and "
        "normalize-space(text())='1.a. File Number: C-']"
        "/following-sibling::span[@class='i-value'][1]/text()"
    ).get()
    if not val:
        # LM-21: "1. File Number: C-"
        val = sel.xpath(
            "//span[@class='i-label' and "
            "normalize-space(text())='1. File Number: C-']"
            "/following-sibling::span[@class='i-value'][1]/text()"
        ).get()
    return int(val.strip()) if val else None


def max_known_lm2021(db_path):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT max(rptId) FROM filing"
        ).fetchone()
    return row[0] or 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", help="lm20.db (reads max rptId)")
    args = ap.parse_args()

    sess = _session()
    max_known = max_known_lm2021(args.db)
    print(f"# max known rptId: {max_known}", file=sys.stderr)

    max_assigned = bisect_max_assigned(sess, max_known)
    window = range(max_known + 1, max_assigned + 1)
    print(
        f"# scanning rptId window {max_known + 1}..{max_assigned} "
        f"({len(window)} ids)",
        file=sys.stderr,
    )

    sr_nums = set()

    def scan_one(rpt_id):
        time.sleep(2)
        body, _ = fetch_lm2021_html(sess, rpt_id)
        if body is None:
            return None
        return extract_sr_num(body)

    with ThreadPoolExecutor(max_workers=SCAN_CONCURRENCY) as ex:
        for sr in ex.map(scan_one, window):
            if sr is not None:
                sr_nums.add(sr)

    print(
        f"# {len(sr_nums)} filers with new activity in "
        f"window {max_known + 1}..{max_assigned}",
        file=sys.stderr,
    )
    for sr in sorted(sr_nums):
        print(sr)


if __name__ == "__main__":
    main()
