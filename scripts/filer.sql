BEGIN;
DROP TABLE IF EXISTS raw_filer;
.mode csv
.import /dev/stdin raw_filer

REPLACE INTO filer(srNum, companyName, companyCity, companyState)
SELECT srNum, companyName, companyCity, companyState
FROM raw_filer;

SELECT changes() || ' rows upserted into filer';

DROP TABLE raw_filer;
COMMIT;
