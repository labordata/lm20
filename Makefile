lm20.db : filer.csv filing.csv attachment.csv employer.csv		\
          detailed_form.csv contact.csv schedule_disbursements.csv	\
          signatures.csv disbursements.csv specific_activities.csv	\
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
	sqlite-utils transform $@ detailed_form \
            --rename "form._key" id \
            --pk id
	sqlite-utils transform $@ disbursements \
            --rename "form._key" form_id \
            --rename "form.disbursements._key" type \
            --rename disbursements dollar_value
	sqlite-utils convert $@ disbursements type 'value.replace("_", " ")'
	sqlite3 $@ "delete from disbursements where type = 'individual disbursements'"
	sqlite-utils transform $@ individual_disbursements \
            --drop "form.disbursements._key" \
            --rename "form._key" form_id  \
            --rename "form.disbursements.individual_disbursements._key" ordering \
            --pk form_id \
            --pk ordering
	sqlite-utils convert $@ specific_activities rowid "{'id': value}" --multi
	sqlite-utils transform $@ specific_activities \
            --rename "form._key" form_id \
            --rename "form.specific_activities._key" ordering \
            --column-order id \
            --pk id
	sqlite3 $@ 'update performer set "form.specific_activities._key" = (SELECT id from specific_activities where form_id = "form._key" and ordering = "form.specific_activities._key")'
	sqlite-utils transform $@ performer \
            --rename "form.specific_activities._key" specific_activities_id \
            --rename "form.specific_activities.performer._key" ordering
	sqlite-utils add-foreign-key $@ filing srNum filer srNum
	sqlite-utils add-foreign-key $@ attachment rptId filing rptId
	sqlite-utils add-foreign-key $@ employer rptId filing rptId
	sqlite-utils add-foreign-key $@ detailed_form rptId filing rptId
	sqlite-utils add-foreign-key $@ disbursements form_id detailed_form id
	sqlite-utils add-foreign-key $@ individual_disbursements form_id detailed_form id
	sqlite-utils add-foreign-key $@ specific_activities form_id detailed_form id
	sqlite-utils add-foreign-key $@ performer specific_activities_id specific_activities id


employer.csv:
	scrapy crawl employers -O $@

attachment.csv :
	scrapy crawl attachments -O $@


individual_disbursements.csv : disbursements.individual_disbursements.csv
	cat $< | python scripts/tail_header.py > $@

performer.csv : specific_activities.performer.csv
	cat $< | python scripts/tail_header.py > $@

detailed_form.csv : form.csv
	cat $< | python scripts/tail_header.py > $@

%.csv : form.%.csv
	cat $< | python scripts/tail_header.py > $@

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
