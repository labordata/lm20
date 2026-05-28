BEGIN;
DROP TABLE IF EXISTS raw_lm20;
.mode csv
.import /dev/stdin raw_lm20

DELETE FROM lm20 WHERE rptId IN (SELECT DISTINCT rptId FROM raw_lm20);

INSERT INTO lm20(
    rptId, amended, date_fiscal_year_ends, direct, indirect,
    city, date_entered_into, ein, name, organization,
    "po_box,_bldg,_room_no,_if_any", state, street, zip_code,
    notes, written_agreement, type_of_person
)
SELECT
    rptId, amended, date_fiscal_year_ends, direct, indirect,
    city, date_entered_into, ein, name, organization,
    "po_box,_bldg,_room_no,_if_any", state, street, zip_code,
    notes, written_agreement, type_of_person
FROM raw_lm20;

SELECT changes() || ' rows inserted into lm20';

COMMIT;
