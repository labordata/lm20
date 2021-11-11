lm20.db : filing.csv filer.csv
	csvs-to-sqlite $^ $@
	sqlite-utils transform $@ filer \
            --pk=srNum \
            --drop filerType \
            --column-order srNum \
            --column-order companyName \
            --column-order companyCity \
            --column-order companyState
	sqlite-utils transform $@ filing --pk=rptId --drop files
	sqlite-utils add-foreign-key $@ filing srNum filer srNum


filing.csv :
	scrapy crawl filings -O $@

filer.csv :
	scrapy crawl filers -O $@
