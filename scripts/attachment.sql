BEGIN;
DROP TABLE IF EXISTS raw_attachment;
.mode csv
.import /dev/stdin raw_attachment

DELETE FROM attachment WHERE rptId IN (SELECT DISTINCT rptId FROM raw_attachment);

INSERT INTO attachment(rptId, attachment_id, filename, file_description)
SELECT rptId, attachment_id, filename, file_description
FROM raw_attachment;

SELECT changes() || ' rows inserted into attachment';

COMMIT;
