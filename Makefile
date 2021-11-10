
lm20.db : filing.csv filer.csv
	csvs-to-sqlite $^ $@
	sqlite-utils transform $@ filer --pk=srNum
	sqlite-utils transform $@ filing --pk=rptId --drop files
	sqlite-utils add-foreign-key $@ filing srNum filer srNum

filing.csv :
	scrapy crawl filings -O $@

filer.csv :
	scrapy crawl filers -O $@
