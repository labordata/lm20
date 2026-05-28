BEGIN;
DROP TABLE IF EXISTS raw_employer;
.mode csv
.import /dev/stdin raw_employer

DELETE FROM employer WHERE rptId IN (SELECT DISTINCT rptId FROM raw_employer);

INSERT INTO employer(rptId, empLabOrg, empTrdName, city, state, termDate, amount)
SELECT rptId, empLabOrg, empTrdName, city, state, termDate, amount
FROM raw_employer;

SELECT changes() || ' rows inserted into employer';

COMMIT;
