lm20.db : filer.csv filing.csv attachment.csv employer.csv form.csv	\
              contact.csv schedule_disbursements.csv signatures.csv	\
              disbursements.csv specific_activities.csv			\
              individual_disbursements.csv performer.csv receipts.csv
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
            --drop subLabOrg \
            --drop termDate \
            --drop amount \
            --drop empTrdName \
            --drop formLink
	sqlite-utils transform $@ attachment \
            --pk=attachment_id \
            --drop files \
            --drop file_headers
	sqlite-utils add-foreign-key $@ filing srNum filer srNum
	sqlite-utils add-foreign-key $@ attachment rptId filing rptId
	sqlite-utils add-foreign-key $@ employer rptId filing rptId

employer.csv:
	scrapy crawl employers -O $@

attachment.csv :
	scrapy crawl attachments -O $@


individual_disbursements.csv : disbursements.individual_disbursements.csv
	mv $< $@

performer.csv : specific_activities.performer.csv
	mv $< $@

%.csv : form.%.csv
	mv $< $@

form.csv form.contact.csv form.schedule_disbursements.csv		\
form.signatures.csv form.disbursements.csv				\
form.specific_activities.csv						\
form.disbursements.individual_disbursements.csv				\
form.specific_activities.performer.csv form.receipts.csv &: form.json
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

filing.csv : filing.jl
	cat $< | jq 'del(.detailed_form_data, .files, .file_headers, .file_urls) + {file_urls: .file_urls[0]}' -c | in2csv -f ndjson > $@

filing.jl :
	scrapy crawl filings -O $@

filer.csv :
	scrapy crawl filers -O $@
