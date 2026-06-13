"""lm20's table semantics for the olms merge engine.

Run as `python scripts/merge_csv.py lm20.db TABLE [--replace]
[--ignore COLUMN]... < table.csv`; see olms.merge for the engine's
behavior (name-based column matching, missing columns as NULL, loud
unknown-column errors).

Table strategies, mirroring the full build in the Makefile:

- filer: full-crawl upsert — run with --replace (REPLACE INTO on the
  srNum primary key); rows are never deleted, so filers absent from
  one crawl are kept.
- filing: the incoming batch re-crawls every filing of each affected
  filer, so child-table rows for the incoming rptIds are cleared here
  and re-inserted by the later per-table merges. Filings named by an
  incoming originalRptId are amendments' superseded originals, which
  OLMS drops from its feed; they are deleted from every table.
- specific_activity: the id primary key is reassigned on insert.
- performer: the CSV's specific_activity_id column holds the
  activity_order ordinal; it is resolved to specific_activity.id by
  (rptId, activity_order), like the full build's sqlite-utils update.
"""

import sys

from olms.merge import (
    delete_by_rptid,
    incoming_rptids,
    insert_rows,
    main,
    tables_with_rptid,
)

# Tables whose rows derive from the same crawl as the filing batch
# (filing.jl -> form.json). Clearing them for incoming rptIds is safe
# because the batch is guaranteed to carry their replacement rows.
# employer and attachment come from SEPARATE crawls, so they are not
# cleared here: if their crawl fails (e.g. OLMS starts returning 403s
# mid-run) their empty merge must not leave half-deleted tables behind.
SAME_CRAWL_TABLES = (
    "lm20",
    "lm21",
    "contact",
    "receipts",
    "signatures",
    "specific_activity",
    "performer",
    "individual_disbursements",
)


def merge_filing(conn, table, columns, rows):
    # the column is absent entirely when no filing in the batch is an
    # amendment (filing.csv carries only the keys present in the batch)
    superseded = {
        int(row["originalRptId"]) for row in rows if row.get("originalRptId")
    } - incoming_rptids(rows)
    for other in tables_with_rptid(conn):
        removed = delete_by_rptid(conn, other, superseded)
        if removed:
            print(
                f"filing: removed {removed} {other} rows superseded by amendments",
                file=sys.stderr,
            )
    for child in SAME_CRAWL_TABLES:
        # cleared here, repopulated by that table's own merge
        delete_by_rptid(conn, child, incoming_rptids(rows))
    deleted = delete_by_rptid(conn, "filing", incoming_rptids(rows))
    return deleted, insert_rows(conn, "filing", columns, rows)


def merge_specific_activity(conn, table, columns, rows):
    # ids are reassigned on insert; drop the rows that reference the
    # old ones (re-inserted, with ids re-resolved, by the performer
    # merge)
    delete_by_rptid(conn, "performer", incoming_rptids(rows))
    deleted = delete_by_rptid(conn, table, incoming_rptids(rows))
    return deleted, insert_rows(conn, table, columns, rows)


def merge_performer(conn, table, columns, rows):
    rpt_ids = incoming_rptids(rows)
    placeholders = ", ".join("?" * len(rpt_ids))
    activity_ids = {
        (rpt_id, order): activity_id
        for activity_id, rpt_id, order in conn.execute(
            "SELECT id, rptId, activity_order FROM specific_activity"
            f" WHERE rptId IN ({placeholders})",
            sorted(rpt_ids),
        )
    }
    resolved = []
    for row in rows:
        key = (int(row["rptId"]), int(row["specific_activity_id"]))
        if key not in activity_ids:
            print(
                f"performer: no specific_activity for rptId {key[0]},"
                f" activity_order {key[1]}; skipping row",
                file=sys.stderr,
            )
            continue
        resolved.append({**row, "specific_activity_id": activity_ids[key]})
    deleted = delete_by_rptid(conn, "performer", rpt_ids)
    return deleted, insert_rows(conn, "performer", columns, resolved)


STRATEGIES = {
    "filing": merge_filing,
    "specific_activity": merge_specific_activity,
    "performer": merge_performer,
}

if __name__ == "__main__":
    main(strategies=STRATEGIES, description=__doc__)
