BEGIN;
DROP TABLE IF EXISTS raw_contact;
.mode csv
.import /dev/stdin raw_contact

DELETE FROM contact WHERE rptId IN (SELECT DISTINCT rptId FROM raw_contact);

INSERT INTO contact(
    city, ein, name, organization,
    "po_box,_bldg,_room_no,_if_any", state, street,
    title, zip_code, rptId, contact_type
)
SELECT
    city, ein, name, organization,
    "po_box,_bldg,_room_no,_if_any", state, street,
    title, zip_code, rptId, contact_type
FROM raw_contact;

SELECT changes() || ' rows inserted into contact';

COMMIT;
