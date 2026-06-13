"""Load lm20's JSON documents straight into lm20.db.

Replaces the json-to-multicsv + sed + per-table CSV merge chain: each
source document is flattened to its tables (olms.flatten) and merged
in ONE transaction (olms.merge.load_tables), so a failure can't leave
the database mid-cascade.

Sources (see update.mk / Makefile for how the documents are derived
from filing.jl):

    python scripts/load_json.py lm20.db filing  filing.json
    python scripts/load_json.py lm20.db form    form.json
    python scripts/load_json.py lm20.db lm20    lm20.json
    python scripts/load_json.py lm20.db lm21    lm21.json

Column names and ordinals reproduce the published schema exactly: the
old perl json-to-multicsv counted list ordinals from 1 (list_base=1),
and the rename maps encode what the sed header rewrites used to do.
Table strategies (amendment eviction, same-crawl clearing,
specific_activity id reassignment, performer ordinal resolution) are
shared with scripts/merge_csv.py.
"""

import argparse
import json
import sqlite3
import sys

from olms.flatten import COLUMN, IGNORE, Table, flatten
from olms.merge import load_tables

from merge_csv import STRATEGIES

FILING_SPEC = [
    (
        "",
        Table(
            "filing",
            keys=(None,),
            # fields the full build's sqlite-utils transform dropped
            drop=frozenset(
                {"subLabOrg", "termDate", "amount", "empTrdName", "formLink"}
            ),
        ),
    ),
]

FORM_SPEC = [
    ("", Table("form", keys=("rptId",), emit=False)),
    ("*/person_filing", Table("contact", keys=("rptId", "contact_type"))),
    ("*/signatures", Table("signatures", keys=("rptId", "signature_number"))),
    (
        "*/receipts",
        Table("receipts", keys=("rptId", "receipt_number"), list_base=1),
    ),
    (
        "*/specific_activities",
        Table(
            "specific_activity",
            keys=("rptId", "activity_order"),
            list_base=1,
            renames={
                "nature_of_activity": "specific_nature_of_activity",
                "period_of_performance": "specific_period_of_performance",
                "extent_of_performance": "specific_extent_of_performance",
                "subject_employees": "specific_subject_employees",
                "subject_labor_orgs": "specific_subject_labor_orgs",
            },
        ),
    ),
    (
        "*/specific_activities/*/performers",
        Table(
            "performer",
            keys=("rptId", "specific_activity_id", "performer_order"),
            list_base=1,
        ),
    ),
    ("*/direct_or_indirect", IGNORE),
    ("*/employer", IGNORE),
    ("*/terms_and_conditions", IGNORE),
    ("*/disbursements", IGNORE),
    ("*/schedule_disbursements", IGNORE),
]

LM20_SPEC = [
    (
        "",
        Table(
            "lm20",
            keys=("rptId",),
            # the full build's transform dropped employer.title
            drop=frozenset({"title"}),
        ),
    ),
    ("*/employer", COLUMN),
    ("*/direct_or_indirect", COLUMN),
    ("*/terms_and_conditions", COLUMN),
]

LM21_SPEC = [
    (
        "",
        Table(
            "lm21",
            keys=("rptId",),
            # the schedule_disbursements leaf names, as the old sed
            # header rewrite mangled them into the published schema
            renames={
                "15.a. Employer Name": " Employer Name",
                "15.b. Trade Name, If any": " Trade Name, If any",
                "15.d.Amount": "Amount",
                "15.e.Purpose": "Purpose",
                "P.O. Box., Bldg., Room No., if any": "P.O. B, B, Room N, if any",
            },
        ),
    ),
    ("*/disbursements", COLUMN),
    ("*/schedule_disbursements", COLUMN),
    (
        "*/disbursements/individual_disbursements",
        Table(
            "individual_disbursements",
            keys=("rptId", "disbursement_order"),
            list_base=1,
        ),
    ),
]

SOURCES = {
    "filing": (FILING_SPEC, ["filing"]),
    "form": (
        FORM_SPEC,
        ["contact", "signatures", "receipts", "specific_activity", "performer"],
    ),
    "lm20": (LM20_SPEC, ["lm20"]),
    "lm21": (LM21_SPEC, ["lm21", "individual_disbursements"]),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db")
    parser.add_argument("source", choices=sorted(SOURCES))
    parser.add_argument("json_file")
    args = parser.parse_args()

    spec, order = SOURCES[args.source]
    with open(args.json_file) as f:
        tables = flatten(json.load(f), spec)

    conn = sqlite3.connect(args.db)
    reports = load_tables(conn, args.db, tables, order, strategies=STRATEGIES)
    conn.close()
    for report in reports:
        print(report, file=sys.stderr)


if __name__ == "__main__":
    main()
