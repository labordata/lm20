"""Merge a CSV of freshly scraped rows (stdin) into a table of lm20.db.

Rows for any rptId in the incoming batch replace that rptId's existing
rows. CSV columns are matched to table columns BY NAME, so the
batch-dependent column subsets and orderings that json-to-multicsv
emits are safe: columns missing from a batch are stored as NULL, empty
strings become NULL (matching the csvs-to-sqlite behavior of the full
build), and unknown columns are an error unless --ignore'd.

Table-specific behavior, mirroring the full build in the Makefile:

- filer: full-crawl upsert (REPLACE INTO on the srNum primary key);
  rows are never deleted, so filers absent from one crawl are kept.
- filing: the incoming batch re-crawls every filing of each affected
  filer, so child-table rows for the incoming rptIds are cleared here
  and re-inserted by the later per-table merges. Filings named by an
  incoming originalRptId are amendments' superseded originals, which
  OLMS drops from its feed; they are deleted from every table.
- specific_activity: the id primary key is reassigned on insert.
- performer: the CSV's specific_activity_id column holds the
  activity_order ordinal; it is resolved to specific_activity.id by
  (rptId, activity_order), like the full build's sqlite-utils update.

Usage: python scripts/merge_csv.py lm20.db TABLE [--replace]
       [--ignore COLUMN]... < table.csv
"""

import argparse
import csv
import sqlite3
import sys


def quoted(column):
    return '"' + column.replace('"', '""') + '"'


def table_columns(conn, table):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({quoted(table)})")]


def tables_with_rptid(conn):
    names = [
        name
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    ]
    return [name for name in names if "rptId" in table_columns(conn, name)]


def delete_by_rptid(conn, table, rpt_ids):
    if not rpt_ids:
        return 0
    placeholders = ", ".join("?" * len(rpt_ids))
    cursor = conn.execute(
        f"DELETE FROM {quoted(table)} WHERE rptId IN ({placeholders})",
        sorted(rpt_ids),
    )
    return cursor.rowcount


def incoming_rptids(rows):
    return {int(row["rptId"]) for row in rows}


def insert_rows(conn, table, columns, rows, replace=False):
    verb = "REPLACE" if replace else "INSERT"
    column_list = ", ".join(quoted(column) for column in columns)
    placeholders = ", ".join("?" * len(columns))
    conn.executemany(
        f"{verb} INTO {quoted(table)} ({column_list}) VALUES ({placeholders})",
        [tuple(row[column] for column in columns) for row in rows],
    )
    return len(rows)


def merge_filing(conn, columns, rows):
    superseded = {
        int(row["originalRptId"]) for row in rows if row["originalRptId"]
    } - incoming_rptids(rows)
    for table in tables_with_rptid(conn):
        removed = delete_by_rptid(conn, table, superseded)
        if removed:
            print(
                f"filing: removed {removed} {table} rows superseded by amendments",
                file=sys.stderr,
            )
        if table != "filing":
            # cleared here, repopulated by that table's own merge
            delete_by_rptid(conn, table, incoming_rptids(rows))
    deleted = delete_by_rptid(conn, "filing", incoming_rptids(rows))
    return deleted, insert_rows(conn, "filing", columns, rows)


def merge_performer(conn, columns, rows):
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


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("db")
    parser.add_argument("table")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="upsert on the primary key instead of deleting by rptId",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="COLUMN",
        help="CSV column to drop (a field the full build's sqlite-utils"
        " transform drops)",
    )
    args = parser.parse_args()

    reader = csv.DictReader(sys.stdin)
    raw_rows = list(reader)
    if not raw_rows or not reader.fieldnames:
        print(f"{args.table}: no rows to merge", file=sys.stderr)
        return

    header = [column for column in reader.fieldnames if column not in args.ignore]
    if len(set(header)) != len(header):
        raise SystemExit(f"{args.table}: duplicate CSV columns: {header}")

    conn = sqlite3.connect(args.db)
    columns = table_columns(conn, args.table)
    if not columns:
        raise SystemExit(f"{args.db} has no table {args.table}")
    unknown = sorted(set(header) - set(columns))
    if unknown:
        raise SystemExit(
            f"{args.table}: CSV columns {unknown} are not in the table;"
            " if the full build drops them, pass --ignore"
        )

    rows = [{column: row[column] or None for column in header} for row in raw_rows]

    with conn:
        if args.table == "filing":
            deleted, inserted = merge_filing(conn, header, rows)
        elif args.table == "performer":
            deleted, inserted = merge_performer(conn, header, rows)
        elif args.replace:
            deleted, inserted = 0, insert_rows(
                conn, args.table, header, rows, replace=True
            )
        else:
            if args.table == "specific_activity":
                # ids are reassigned on insert; drop the rows that
                # reference the old ones (re-inserted, with ids
                # re-resolved, by the performer merge)
                delete_by_rptid(conn, "performer", incoming_rptids(rows))
            deleted = delete_by_rptid(conn, args.table, incoming_rptids(rows))
            inserted = insert_rows(conn, args.table, header, rows)
    conn.close()

    print(f"{args.table}: -{deleted} +{inserted} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
