BEGIN;
DROP TABLE IF EXISTS raw_filing;
.mode csv
.import /dev/stdin raw_filing

DELETE FROM filing WHERE rptId IN (SELECT DISTINCT rptId FROM raw_filing);

-- Explicit column list excludes fields dropped by sqlite-utils transform:
-- subLabOrg, termDate, amount, empTrdName, formLink
INSERT INTO filing(
  address1, address2, amended, amendment, beginDate, city,
  empLabOrg, endDate, file_checksum, file_path, file_status,
  filing_url, formFiled, originalRptId, paperOrElect,
  receiveDate, registerDate, repOrgsCnt, rptId,
  srFilerId, srNum, state, yrCovered, zip
)
SELECT
  address1, address2, amended, amendment, beginDate, city,
  empLabOrg, endDate, file_checksum, file_path, file_status,
  filing_url, formFiled, originalRptId, paperOrElect,
  receiveDate, registerDate, repOrgsCnt, rptId,
  srFilerId, srNum, state, yrCovered, zip
FROM raw_filing;

SELECT changes() || ' rows inserted into filing';

COMMIT;
