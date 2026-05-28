-- receipts has column names with special chars. Column order matches
-- original build pipeline, so SELECT * is safe.
BEGIN;
DROP TABLE IF EXISTS raw_receipts;
.mode csv
.import /dev/stdin raw_receipts

DELETE FROM receipts WHERE rptId IN (SELECT DISTINCT rptId FROM raw_receipts);

INSERT INTO receipts SELECT * FROM raw_receipts;

SELECT changes() || ' rows inserted into receipts';

COMMIT;
