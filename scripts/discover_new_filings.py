"""Discover filers (srNums) with new LM-20 or LM-21 activity since
lm20.db's max rptId.

Paper filings come back as PDFs we can't trivially parse; we skip them
here and rely on the scheduled full rebuild
(.github/workflows/full-build.yml) to pick them up.

Usage: python scripts/discover_new_filings.py lm20.db
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

from olms.discover import (
    DiscoveryConfig,
    _session,
    bisect_max_assigned,
    extract_sr_num,
    fetch_hit_html,
    is_assigned,
    watermark,
)

CONFIG = DiscoveryConfig(
    watermark_sql="SELECT max(rptId) FROM filing",
    scan_forms=("LM20Form", "LM21Form"),
    # LM-20 labels its file number "1.a.", LM-21 plain "1."
    sr_num_labels=("1.a. File Number: C-", "1. File Number: C-"),
    description=__doc__,
)

# OLMS has been observed to un-assign LM-20/21 rptIds after they're
# published (reports get pulled), which trips olms.discover's canary
# check and requires manually deleting the row from lm20.db to
# unblock scrapes. We tolerate that here rather than upstream, since
# other form types haven't shown this behavior: if the DB's max
# rptId is unassigned, walk backward a bounded number of ids looking
# for one that IS assigned. Finding one confirms the probe heuristics
# still work and the original id was simply pulled; the scan window
# then starts just above the DB's max, so we intentionally never
# re-scan the pulled ids (they're gone, not "new"). If nothing nearby
# is assigned, we still raise: that's the "heuristics are broken"
# case the canary exists to catch.
MAX_BACKWARD_PROBES = 25


def find_canary(sess, max_known):
    for rpt_id in range(max_known, max_known - MAX_BACKWARD_PROBES, -1):
        if rpt_id <= 0:
            break
        if is_assigned(sess, rpt_id):
            print(f"# max assigned rptId: {rpt_id}", file=sys.stderr)
            return rpt_id
    return None


def discover(config, db):
    sess = _session(config.user_agent)
    max_known = watermark(db, config.watermark_sql)
    print(f"# max known rptId: {max_known}", file=sys.stderr)

    if max_known and find_canary(sess, max_known) is None:
        raise RuntimeError(
            f"rptId {max_known} and the {MAX_BACKWARD_PROBES} ids below it"
            f" are all unassigned in {db}; the ng-app/content-type"
            " heuristics are broken"
        )

    max_assigned = bisect_max_assigned(sess, max_known)
    window = range(max_known + 1, max_assigned + 1)
    print(
        f"# scanning rptId window {max_known + 1}..{max_assigned} "
        f"({len(window)} ids)",
        file=sys.stderr,
    )

    sr_nums = set()
    extractor = config.extractor or (
        lambda body: extract_sr_num(body, config.sr_num_labels)
    )

    def scan_one(rpt_id):
        body = fetch_hit_html(sess, rpt_id, config.scan_forms)
        if body is None:
            return None
        return extractor(body)

    with ThreadPoolExecutor(max_workers=config.scan_concurrency) as ex:
        for sr in ex.map(scan_one, window):
            if sr is not None:
                sr_nums.add(sr)

    print(
        f"# {len(sr_nums)} filers with new activity in "
        f"window {max_known + 1}..{max_assigned}",
        file=sys.stderr,
    )
    return sr_nums


def main(config):
    ap = argparse.ArgumentParser(description=config.description or __doc__)
    ap.add_argument("db", help="database holding the max known rptId")
    args = ap.parse_args()

    for sr in sorted(discover(config, args.db)):
        print(sr)


if __name__ == "__main__":
    main(CONFIG)
