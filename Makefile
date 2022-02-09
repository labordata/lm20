SHELL=/bin/bash


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

filing.csv: filing.json
	cat $< | jq -r '(map(keys) | add | unique) as $$cols | map(. as $$row | $$cols | map($$row[.])) as $$rows | $$cols, $$rows[] | @csv' > $@

performer.csv : form.specific_activities.performer.csv
	cat $< | \
            sed '1s/form\.specific_activities\._key/specific_activity_id/g' | \
	    sed '1s/form\.specific_activities\.performer\._key/performer_order/g' | \
            sed '1s/form\._key/rptId/g' | \
	    sed -r '1s/[a-z0-9]+\.//g' > $@

specific_activity.csv : form.specific_activities.csv
	cat $< | \
            sed '1s/form\.specific_activities\._key/activity_order/g' | \
            sed '1s/form\._key/rptId/g' | \
	    sed -r '1s/[a-z0-9]+\.//g' > $@

signatures.csv : form.signatures.csv
	cat $< | \
            sed '1s/form\.signatures\._key/signature_number/g' | \
            sed '1s/form\._key/rptId/g' | \
	    sed -r '1s/[a-z0-9]+\.//g' > $@

receipts.csv : form.receipts.csv
	cat $< | \
            sed '1s/form\.receipts\._key/receipt_number/g' | \
            sed '1s/form\._key/rptId/g' | \
	    sed -r '1s/[a-z0-9]+\.//g' > $@

contact.csv : form.contact.csv
	cat $< | \
            sed '1s/form\.contact\._key/contact_type/g' | \
            sed '1s/form\._key/rptId/g' | \
	    sed -r '1s/[a-z0-9]+\.//g' > $@

individual_disbursements.csv : lm21_raw.individual_disbursements.csv
	cat $< | \
            sed '1s/lm21_raw\.individual_disbursements\._key/disbursement_order/g' | \
            sed '1s/lm21_raw\._key/rptId/g' | \
	    sed -r '1s/[a-z0-9_]+\.//g' > $@

%.csv : %_raw.csv
	cat $< | \
            sed '1s/.*\._key/rptId/g' | \
	    sed -r '1s/[a-z0-9_]+\.//g' > $@


form.csv form.contact.csv form.receipts.csv form.signatures.csv form.specific_activites.csv form.specific_activities.performer.csv : form.json
	json-to-multicsv.pl --file $< \
                      --path /:table:form \
                      --path /*/person_filing/:table:contact \
                      --path /*/signatures/:table:signatures \
                      --path /*/receipts/:table:receipts \
                      --path /*/specific_activities/:table:specific_activities \
                      --path /*/specific_activities/*/performers/:table:performer \
                      --path /*/direct_or_indirect/:ignore \
                      --path /*/employer/:ignore \
                      --path /*/terms_and_conditions/:ignore \
                      --path /*/disbursements/:ignore \
                      --path /*/schedule_disbursements/:ignore

lm20_raw.csv : lm20.json
	json-to-multicsv.pl --file $< \
                      --path /:table:lm20_raw \
                      --path /*/employer/:column \
                      --path /*/direct_or_indirect/:column \
                      --path /*/terms_and_conditions/:column

lm21_raw.csv lm21_raw.individual_disbursements.csv : lm21.json
	json-to-multicsv.pl --file $< \
                      --path /:table:lm21_raw \
                      --path /*/disbursements/:column \
                      --path /*/disbursements/individual_disbursements/:table:individual_disbursements \
                      --path /*/schedule_disbursements/:column


filing.json: filing.jl
	cat $< |  jq -s '.[] | del(.detailed_form_data, .file_headers, .file_urls) | .files = .files[0]' | jq -s > $@

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
