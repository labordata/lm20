BEGIN;
DROP TABLE IF EXISTS raw_individual_disbursements;
.mode csv
.import /dev/stdin raw_individual_disbursements

DELETE FROM individual_disbursements
WHERE rptId IN (SELECT DISTINCT rptId FROM raw_individual_disbursements);

INSERT INTO individual_disbursements(
    expense, name, salary, total, rptId, disbursement_order
)
SELECT
    expense, name, salary, total, rptId, disbursement_order
FROM raw_individual_disbursements;

SELECT changes() || ' rows inserted into individual_disbursements';

COMMIT;
