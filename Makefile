SHELL=/bin/bash

define assert_not_empty
(test -s $(1) || (echo "ERROR: $(1) is empty" && exit 1))
endef


lm20.db : lm20.csv lm21.csv filer.csv filing.csv employer.csv attachment.csv contact.csv receipts.csv signatures.csv specific_activity.csv performer.csv individual_disbursements.csv
	csvs-to-sqlite $^ $@
	sqlite-utils transform $@ filer \
            --pk srNum \
            --drop filerType \
            --column-order srNum \
            --column-order companyName \
            --column-order companyCity \
            --column-order companyState
	sqlite-utils transform $@ filing \
            --pk rptId \
            --drop files \
            --drop subLabOrg \
            --drop termDate \
            --drop amount \
            --drop empTrdName \
            --drop formLink
	sqlite-utils transform $@ lm20 \
            --rename "form._key" rptId \
            --drop title
	sqlite-utils transform $@ attachment \
            --pk attachment_id \
            --drop files \
            --drop file_headers
	sqlite-utils $@ "update lm20 set date_fiscal_year_ends = replace(date_fiscal_year_ends, ' / ', ' ')"
	sqlite-utils convert $@ lm20 date_entered_into 'r.parsedate(value)'
	sqlite-utils convert $@ lm21 period_begin 'r.parsedate(value)'
	sqlite-utils convert $@ lm21 period_through 'r.parsedate(value)'
	sqlite-utils transform $@ specific_activity \
            --pk id
	sqlite-utils $@ "update performer set specific_activity_id = (select id from specific_activity where rptId = performer.rptId and activity_order = performer.specific_activity_id)"
	sqlite-utils vacuum $@
	sqlite-utils add-foreign-keys $@ \
               filing srNum filer srNum \
               contact rptId filing rptId \
               employer rptId filing rptId \
               lm20 rptId filing rptId \
               lm21 rptId filing rptId \
               performer rptId filing rptId \
               receipts rptId filing rptId \
               signatures rptId filing rptId \
               specific_activity rptId filing rptId \
               attachment rptId filing rptId \
               performer specific_activity_id specific_activity id \
               individual_disbursements rptId filing rptId

attachment.csv :
	scrapy crawl attachments -L 'INFO' -O $@ && $(call assert_not_empty,$@)

employer.csv :
	scrapy crawl employers -L 'INFO' -O $@ && $(call assert_not_empty,$@)

filing.jl :
	scrapy crawl filings -L 'INFO' -O $@ && $(call assert_not_empty,$@)

filer.csv :
	scrapy crawl filers -L 'INFO' -O $@ && $(call assert_not_empty,$@)

include common.mk
