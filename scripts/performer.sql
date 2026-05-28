-- performer.specific_activity_id in the CSV stores the activity_order
-- ordinal (not the actual specific_activity.id). Map it via OFFSET.
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
    (
        SELECT sa.id
        FROM specific_activity AS sa
        WHERE sa.rptId = p.rptId
        ORDER BY sa.id
        LIMIT 1
        OFFSET CAST(p.specific_activity_id AS INTEGER) - 1
    ) AS specific_activity_id,
    p.performer_order,
    p.city, p.ein, p.file_number, p.name, p.organization,
    p."po_box,_bldg,_room_no,_if_any", p.state, p.street, p.title, p.zip
FROM raw_performer p;

SELECT changes() || ' rows inserted into performer';

COMMIT;
