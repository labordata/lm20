"""Discover filers (srNums) with new LM-20 or LM-21 activity since
lm20.db's max rptId.

Paper filings come back as PDFs we can't trivially parse; we skip them
here and rely on the scheduled full rebuild
(.github/workflows/full-build.yml) to pick them up.

Usage: python scripts/discover_new_filings.py lm20.db
"""

from olms.discover import DiscoveryConfig, main

CONFIG = DiscoveryConfig(
    watermark_sql="SELECT max(rptId) FROM filing",
    scan_forms=("LM20Form", "LM21Form"),
    # LM-20 labels its file number "1.a.", LM-21 plain "1."
    sr_num_labels=("1.a. File Number: C-", "1. File Number: C-"),
    description=__doc__,
)

if __name__ == "__main__":
    main(CONFIG)
