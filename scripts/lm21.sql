-- lm21 has column names with spaces/special chars produced by
-- json-to-multicsv. Column order from the incremental pipeline matches
-- the original build, so SELECT * is safe here.
BEGIN;
DROP TABLE IF EXISTS raw_lm21;
.mode csv
.import /dev/stdin raw_lm21

DELETE FROM lm21 WHERE rptId IN (SELECT DISTINCT rptId FROM raw_lm21);

INSERT INTO lm21 SELECT * FROM raw_lm21;

SELECT changes() || ' rows inserted into lm21';

COMMIT;
