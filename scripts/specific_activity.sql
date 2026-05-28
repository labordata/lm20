-- specific_activity has an auto-generated `id` PK not present in the CSV.
-- Cascade-delete performers before replacing activities so that recycled
-- ids don't create ghost FK references.
BEGIN;
DROP TABLE IF EXISTS raw_specific_activity;
.mode csv
.import /dev/stdin raw_specific_activity

DELETE FROM performer
WHERE specific_activity_id IN (
    SELECT id
    FROM specific_activity
    WHERE rptId IN (SELECT DISTINCT rptId FROM raw_specific_activity)
);

DELETE FROM specific_activity
WHERE rptId IN (SELECT DISTINCT rptId FROM raw_specific_activity);

-- Insert in deterministic (rptId, activity_order) order so performer.sql
-- can recover the new id via OFFSET.
-- `id` is omitted — SQLite assigns it automatically (INTEGER PRIMARY KEY).
INSERT INTO specific_activity(
    rptId, activity_order,
    specific_nature_of_activity, specific_period_of_performance,
    specific_extent_of_performance, specific_subject_employees,
    specific_subject_labor_orgs
)
SELECT
    rptId, activity_order,
    specific_nature_of_activity, specific_period_of_performance,
    specific_extent_of_performance, specific_subject_employees,
    specific_subject_labor_orgs
FROM raw_specific_activity
ORDER BY CAST(rptId AS INTEGER), CAST(activity_order AS INTEGER);

SELECT changes() || ' rows inserted into specific_activity';

COMMIT;
