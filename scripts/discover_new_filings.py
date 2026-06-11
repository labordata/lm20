"""Discover filers (srNums) with new LM-20 or LM-21 activity since
lm20.db's max rptId.

rptIds in OLMS are monotonically increasing with receiveDate across all
form types. Bisect `orgReport.do` to find the current max-assigned
rptId, forward-scan the new window for LM-20/LM-21 hits, then parse
each hit's HTML for the filer's srNum. srNums go to stdout, one per
line.

Paper filings come back as PDFs we can't trivially parse; we skip them
here and rely on the scheduled full rebuild
(.github/workflows/full-build.yml) to pick them up.

Usage: python scripts/discover_new_filings.py lm20.db
"""

import argparse
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import urllib3
from parsel import Selector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lm20.settings import USER_AGENT  # noqa: E402

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REPORT_URL = "https://olmsapps.dol.gov/query/orgReport.do?rptId={}&rptForm={}"
PROBE_FORMS = ("LM2Form", "LM10Form", "LM20Form", "LM30Form", "S1Form")
SCAN_FORMS = ("LM20Form", "LM21Form")
SCAN_CONCURRENCY = 4


def _session():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    s.verify = False
    return s


BLOCK_CODES = (403, 429)


def fetch(session, rpt_id, form):
    """Return (content_type, body); the body is read only for HTML
    responses, so probing a multi-megabyte PDF costs only its headers.

    OLMS rate-limits with 403s; those are NOT "not found" — back off
    and retry, and abort discovery if the block persists, since a
    blocked scan is indistinguishable from "no new filings".
    """
    url = REPORT_URL.format(rpt_id, form)
    delay = 5
    for _ in range(6):
        with session.get(url, timeout=30, stream=True) as response:
            if response.status_code in BLOCK_CODES:
                print(
                    f"# OLMS returned {response.status_code} for {url};"
                    f" backing off {delay}s",
                    file=sys.stderr,
                )
                time.sleep(delay)
                delay *= 2
                continue
            content_type = (
                response.headers.get("Content-Type", "").split(";")[0].strip()
            )
            if content_type != "text/html":
                return content_type, b""
            return content_type, response.content
    raise RuntimeError(
        f"OLMS kept returning {'/'.join(map(str, BLOCK_CODES))} for {url};"
        " we are blocked — aborting discovery rather than reporting"
        " 'no new filings'"
    )


def fetch_assigned(session, rpt_id, form):
    """True if `rpt_id` is assigned to `form`.

    Real form pages embed an Angular app (`ng-app="LM20App"` etc.) and
    fetch their data asynchronously. The OLMS "not found" page is a
    plain HTML stub without ng-app.
    """
    content_type, body = fetch(session, rpt_id, form)
    if content_type == "application/pdf":
        return True
    return content_type == "text/html" and b"ng-app=" in body


def is_assigned(session, rpt_id):
    # any() short-circuits, and an assigned rptId renders under
    # whichever form is asked first, so this usually costs one request.
    return any(fetch_assigned(session, rpt_id, form) for form in PROBE_FORMS)


def fetch_lm2021_html(session, rpt_id):
    """Return html_bytes if rpt_id is an electronic LM-20 or LM-21,
    else None."""
    for form in SCAN_FORMS:
        content_type, body = fetch(session, rpt_id, form)
        if content_type == "text/html" and b"Signature" in body:
            return body
    return None


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

    # Canary: max_known is assigned by definition (it's in our DB), so
    # if the probe can't see it, the markup heuristics have broken and
    # an empty scan would mean "discovery is blind", not "nothing new".
    if max_known and not is_assigned(sess, max_known):
        raise RuntimeError(
            f"rptId {max_known} is in {args.db} but the OLMS probe reports"
            " it unassigned; the ng-app/content-type heuristics are broken"
        )

    max_assigned = bisect_max_assigned(sess, max_known)
    window = range(max_known + 1, max_assigned + 1)
    print(
        f"# scanning rptId window {max_known + 1}..{max_assigned} "
        f"({len(window)} ids)",
        file=sys.stderr,
    )

    sr_nums = set()

    def scan_one(rpt_id):
        body = fetch_lm2021_html(sess, rpt_id)
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
