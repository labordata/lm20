old_lm20.db : filer.csv filing.csv attachment.csv employer.csv
	csvs-to-sqlite $^ $@
	sqlite-utils transform $@ filer \
            --pk=srNum \
            --drop filerType \
            --column-order srNum \
            --column-order companyName \
            --column-order companyCity \
            --column-order companyState
	sqlite-utils transform $@ filing \
            --pk=rptId \
            --drop files \
            --drop subLabOrg \
            --drop termDate \
            --drop amount \
            --drop empTrdName \
            --drop file_headers \
            --drop formLink
	sqlite-utils transform $@ attachment \
            --pk=attachment_id \
            --drop files \
            --drop file_headers
	sqlite-utils add-foreign-key $@ filing srNum filer srNum
	sqlite-utils add-foreign-key $@ attachment rptId filing rptId
	sqlite-utils add-foreign-key $@ employer rptId filing rptId

lm20.db : form.csv
	csvs-to-sqlite form*.csv $@

employer.csv:
	scrapy crawl employers -O $@

attachment.csv :
	scrapy crawl attachments -O $@

form.csv : form.json
	json-to-multicsv.pl \
            --path /:table:form \
            --path /*/person_filing/:table:contact \
            --path /*/signatures/:table:signatures \
            --path /*/receipts/:table:receipts \
            --path /*/schedule_disbursements/:table:schedule_disbursements \
            --path /*/specific_activities/:table:specific_activities \
            --path /*/specific_activities/*/performers/:table:performer \
            --path /*/*/individual_disbursements/:table:individual_disbursements \
            --path /*/disbursements/:table:disbursements \
            --path /*/direct_or_indirect/:column \
            --path /*/employer/:column \
            --path /*/terms_and_conditions/:column \
            --file $< 

form.json : filing.jl
	cat $< |  jq -s '.[] | .detailed_form_data + {rptId, formFiled} | select(.file_number)' | jq -s > $@

filing.jl :
	scrapy crawl filings -O $@

filer.csv :
	scrapy crawl filers -O $@
