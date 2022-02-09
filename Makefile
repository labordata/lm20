SHELL=/bin/bash

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

lm20.db : form.csv lm20.csv lm21.csv filer.csv filing.csv employer.csv attachment.csv
	sed -i.bak '1s/form\._key/rptId/g' *.csv
	sed -i.bak '1s/[a-z0-9]+\.//g' form*.csv lm20.csv lm21.csv
	for f in form.*.csv; do mv "$$f" "$${f/form./}"; done
	mv specific_activities.performer.csv performer.csv
	csvs-to-sqlite *.csv $@
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
	sqlite-utils transform $@ form \
            --drop amended \
            --drop date_fiscal_year_ends \
            --drop period_begin \
            --drop period_through \
            --drop total_disbursements \
            --drop type_of_person
	sqlite-utils transform $@ lm20 \
            --drop title
	sqlite-utils transform $@ attachment \
            --pk attachment_id \
            --drop files \
            --drop file_headers
	sqlite-utils $@ "update lm20 set date_fiscal_year_ends = replace(date_fiscal_year_ends, ' / ', ' ')"
	sqlite-utils convert $@ lm20 date_entered_into 'r.parsedate(value)'
	sqlite-utils convert $@ lm21 period_begin 'r.parsedate(value)'
	sqlite-utils convert $@ lm21 period_through 'r.parsedate(value)'
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
               specific_activities rptId filing rptId \
               attachment rptId filing rptId

filing.csv: filing.json
	cat $< | jq -r '(map(keys) | add | unique) as $$cols | map(. as $$row | $$cols | map($$row[.])) as $$rows | $$cols, $$rows[] | @csv' > $@

form.csv : form.json
	json-to-multicsv.pl --file $< \
                      --path /:table:form \
                      --path /*/person_filing/:table:contact \
                      --path /*/signatures/:table:signatures \
                      --path /*/receipts/:table:receipts \
                      --path /*/specific_activities/:table:specific_activities \
                      --path /*/specific_activities/*/performers/:table:performer \
                      --path /*/*/individual_disbursements/:table:individual_disbursements \
                      --path /*/direct_or_indirect/:ignore \
                      --path /*/employer/:ignore \
                      --path /*/terms_and_conditions/:ignore \
                      --path /*/disbursements/:ignore \
                      --path /*/schedule_disbursements/:ignore
	sed -i.bak '1s/form\.contact\._key/contact_type/g' form.contact.csv
	sed -i.bak '1s/form\.receipts\._key/receipt_number/g' form.receipts.csv
	sed -i.bak '1s/form\.signatures\._key/signature_number/g' form.signatures.csv
	sed -i.bak '1s/form\.specific_activities\._key/activity_number/g' form.specific_activities.csv form.specific_activities.performer.csv
	sed -i.bak '1s/form\.specific_activities\.performer\._key/performer_number/g' form.specific_activities.performer.csv

lm20.csv : lm20.json
	json-to-multicsv.pl --file $< \
                      --path /:table:lm20 \
                      --path /*/employer/:column \
                      --path /*/direct_or_indirect/:column \
                      --path /*/terms_and_conditions/:column
	sed -i.bak '1s/lm20\._key/rptId/g' lm20.csv

lm21.csv : lm21.json
	json-to-multicsv.pl --file $< \
                      --path /:table:lm21 \
                      --path /*/disbursements/:column \
                      --path /*/disbursements/individual_disbursements/:ignore \
                      --path /*/schedule_disbursements/:column
	sed -i.bak '1s/lm21\._key/rptId/g' lm21.csv

filing.json: filing.jl
	cat $< |  jq -s '.[] | del(.detailed_form_data, .file_headers) | .file_urls = .file_urls[0] | .files = .files[0]' | jq -s > $@

lm20.json : form.json
	cat $< | jq 'with_entries( select(.value.formFiled == "LM-20")| del(.value.file_number, .value.person_filing, .value.signatures, .value.specific_activities, .value.formFiled))' > $@

lm21.json : form.json
	cat $< | jq 'with_entries( select(.value.formFiled == "LM-21") | del(.value.file_number, .value.person_filing, .value.signatures, .value.receipts, .value.formFiled))' > $@

form.json : filing.jl
	cat $< |  jq -s '.[] | .detailed_form_data + {rptId, formFiled} | select(.file_number)' | jq -s | jq 'INDEX(.rptId) | with_entries(.value |= del(.rptId))' > $@


attachment.csv :
	scrapy crawl attachments -L 'WARNING' -O $@

employer.csv :
	scrapy crawl employers -L 'WARNING' -O $@

filing.jl :
	scrapy crawl filings -L 'WARNING' -O $@

filer.csv :
	scrapy crawl filers -L 'WARNING' -O $@
