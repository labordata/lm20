# common.mk — CSV/JSON transform rules shared by the full build
# (Makefile) and the incremental update (update.mk). The spider targets
# that produce filing.jl, filer.csv, employer.csv, and attachment.csv
# live in the including makefile.

FORM_CSVS := form.csv form.contact.csv form.receipts.csv form.signatures.csv \
    form.specific_activities.csv form.specific_activities.performer.csv

filing.csv: filing.json
	if [ "$$(jq 'length' $<)" -gt 0 ]; then \
	    cat $< | jq -r '(map(keys) | add | unique) as $$cols | map(. as $$row | $$cols | map($$row[.])) as $$rows | $$cols, $$rows[] | @csv' > $@; \
	else \
	    : > $@; \
	fi

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

# json-to-multicsv only writes files for tables that received at least
# one row, so touch the declared outputs: a batch with, say, no LM-21
# receipts then yields an empty CSV downstream ("no rows to merge")
# instead of a missing prerequisite.
$(FORM_CSVS) &: form.json
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
	touch $(FORM_CSVS)

lm20_raw.csv : lm20.json
	json-to-multicsv.pl --file $< \
	                  --path /:table:lm20_raw \
	                  --path /*/employer/:column \
	                  --path /*/direct_or_indirect/:column \
	                  --path /*/terms_and_conditions/:column
	touch $@

lm21_raw.csv lm21_raw.individual_disbursements.csv &: lm21.json
	json-to-multicsv.pl --file $< \
	                  --path /:table:lm21_raw \
	                  --path /*/disbursements/:column \
	                  --path /*/disbursements/individual_disbursements/:table:individual_disbursements \
	                  --path /*/schedule_disbursements/:column
	touch lm21_raw.csv lm21_raw.individual_disbursements.csv

filing.json: filing.jl
	cat $< | jq -s '.[] | del(.detailed_form_data, .file_headers, .file_urls) | .files = .files[0] | .file_path = .files.path | .file_checksum = .files.checksum | .file_status = .files.status | del(.files)' | jq -s > $@

lm20.json : form.json
	cat $< | jq 'with_entries( select(.value.formFiled == "LM-20")| del(.value.file_number, .value.person_filing, .value.signatures, .value.specific_activities, .value.formFiled))' > $@

lm21.json : form.json
	cat $< | jq 'with_entries( select(.value.formFiled == "LM-21") | del(.value.file_number, .value.person_filing, .value.signatures, .value.receipts, .value.formFiled))' > $@

form.json : filing.jl
	cat $< | jq -s '.[] | .detailed_form_data + {rptId, formFiled} | select(.file_number)' | jq -s | jq 'INDEX(.rptId) | with_entries(.value |= del(.rptId))' > $@
