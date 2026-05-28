-- performer.specific_activity_id in the CSV stores the activity_order
-- ordinal from the JSON path key. Resolve it to specific_activity.id by
-- joining on (rptId, activity_order) — the same logic as the main Makefile's
-- sqlite-utils update step.
BEGIN;
DROP TABLE IF EXISTS raw_performer;
.mode csv
.import /dev/stdin raw_performer

INSERT INTO performer(
    rptId, specific_activity_id, performer_order,
    city, ein, file_number, name, organization,
    "po_box,_bldg,_room_no,_if_any", state, street, title, zip
)
SELECT
    p.rptId,
    sa.id,
    p.performer_order,
    p.city, p.ein, p.file_number, p.name, p.organization,
    p."po_box,_bldg,_room_no,_if_any", p.state, p.street, p.title, p.zip
FROM raw_performer p
JOIN specific_activity sa
    ON CAST(sa.rptId AS INTEGER) = CAST(p.rptId AS INTEGER)
    AND CAST(sa.activity_order AS INTEGER) = CAST(p.specific_activity_id AS INTEGER);

SELECT changes() || ' rows inserted into performer';

COMMIT;
