BEGIN;
DROP TABLE IF EXISTS raw_signatures;
.mode csv
.import /dev/stdin raw_signatures

DELETE FROM signatures WHERE rptId IN (SELECT DISTINCT rptId FROM raw_signatures);

INSERT INTO signatures(
    rptId, signature_number, date, signed,
    telephone, telephone_number, title
)
SELECT
    rptId, signature_number, date, signed,
    telephone, telephone_number, title
FROM raw_signatures;

SELECT changes() || ' rows inserted into signatures';

COMMIT;
