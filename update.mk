# update.mk — incremental update of lm20.db.
#
# Each table has a `scripts/<table>.sql` script that imports its CSV
# into a temp table and merges into the real table. `update_<table>`
# phony targets express the FK order. Filer refresh and discovery are
# always-fresh (depend on FORCE). Intermediate files land in the
# working dir (all gitignored).
#
# Usage: make -f update.mk

PRIOR_DB_URL ?= https://github.com/labordata/lm20/releases/download/nightly/lm20.db.zip

.DELETE_ON_ERROR:

FORM_CSVS := form.csv form.contact.csv form.receipts.csv form.signatures.csv \
    form.specific_activities.csv form.specific_activities.performer.csv

.PHONY: update polish_db fk-check FORCE \
        update_filer update_filing \
        update_lm20 update_lm21 \
        update_contact update_employer update_attachment \
        update_receipts update_signatures \
        update_specific_activity update_performer \
        update_individual_disbursements

# ============================================================================
# Entry
# ============================================================================

update: lm20.db update_filer sr_nums.txt
	@if [ -s sr_nums.txt ]; then \
	    $(MAKE) -o sr_nums.txt -o update_filer \
	        -f update.mk \
	        update_filing update_lm20 update_lm21 \
	        update_contact update_employer update_attachment \
	        update_receipts update_signatures \
	        update_specific_activity update_performer \
	        update_individual_disbursements polish_db; \
	fi
	@$(MAKE) -f update.mk fk-check

# ============================================================================
# Validation
# ============================================================================

fk-check:
	@violations=$$(sqlite3 lm20.db "PRAGMA foreign_key_check;" 2>&1); \
	if [ -n "$$violations" ]; then \
	    echo "fk-check: violations in lm20.db:" >&2; \
	    echo "$$violations" >&2; \
	    echo "" >&2; \
	    echo "Detailed violations by table:" >&2; \
	    sqlite3 lm20.db "SELECT \"table\", COUNT(*) as violation_count FROM pragma_foreign_key_check() GROUP BY \"table\";" >&2; \
	    exit 1; \
	fi
	@echo "fk-check: lm20.db has no FK violations"

polish_db:
	sqlite-utils convert lm20.db lm20 date_entered_into 'r.parsedate(value)'
	sqlite-utils convert lm20.db lm21 period_begin 'r.parsedate(value)'
	sqlite-utils convert lm20.db lm21 period_through 'r.parsedate(value)'

# ============================================================================
# Per-table merges (topological — leaves before roots)
# ============================================================================

# performer depends on specific_activity (specific_activity.sql cascade-deletes
# performer rows, then performer.sql re-inserts with id resolution).
update_performer: performer.csv update_specific_activity
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/performer.sql -bail; \
	else \
	    echo "update_performer: $< empty; no performers to merge" >&2; \
	fi

update_specific_activity: specific_activity.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/specific_activity.sql -bail; \
	else \
	    echo "update_specific_activity: $< empty; no specific activities to merge" >&2; \
	fi

update_lm20: lm20.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/lm20.sql -bail; \
	else \
	    echo "update_lm20: $< empty; no LM-20 forms to merge" >&2; \
	fi

update_lm21: lm21.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/lm21.sql -bail; \
	else \
	    echo "update_lm21: $< empty; no LM-21 forms to merge" >&2; \
	fi

update_contact: contact.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/contact.sql -bail; \
	else \
	    echo "update_contact: $< empty; no contacts to merge" >&2; \
	fi

update_employer: employer.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/employer.sql -bail; \
	else \
	    echo "update_employer: $< empty; no employers to merge" >&2; \
	fi

update_attachment: attachment.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/attachment.sql -bail; \
	else \
	    echo "update_attachment: $< empty; no attachments to merge" >&2; \
	fi

update_receipts: receipts.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/receipts.sql -bail; \
	else \
	    echo "update_receipts: $< empty; no receipts to merge" >&2; \
	fi

update_signatures: signatures.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/signatures.sql -bail; \
	else \
	    echo "update_signatures: $< empty; no signatures to merge" >&2; \
	fi

update_individual_disbursements: individual_disbursements.csv update_filing
	@if [ "$$(wc -l < $<)" -gt 0 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/individual_disbursements.sql -bail; \
	else \
	    echo "update_individual_disbursements: $< empty; no disbursements to merge" >&2; \
	fi

update_filing: filing.csv update_filer
	cat $< | sqlite3 lm20.db -init scripts/filing.sql -bail

update_filer: filer.csv | lm20.db
	@if [ "$$(wc -l < $<)" -gt 1 ]; then \
	    cat $< | sqlite3 lm20.db -init scripts/filer.sql -bail; \
	else \
	    echo "update_filer: $< empty (spider produced no rows); keeping existing filer table" >&2; \
	fi

# ============================================================================
# CSV pipeline (same transformations as the main Makefile)
# ============================================================================

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
	cat $< | jq -s '.[] | del(.detailed_form_data, .file_headers, .file_urls) | .files = .files[0] | .file_path = .files.path | .file_checksum = .files.checksum | .file_status = .files.status | del(.files)' | jq -s > $@

lm20.json : form.json
	cat $< | jq 'with_entries( select(.value.formFiled == "LM-20")| del(.value.file_number, .value.person_filing, .value.signatures, .value.specific_activities, .value.formFiled))' > $@

lm21.json : form.json
	cat $< | jq 'with_entries( select(.value.formFiled == "LM-21") | del(.value.file_number, .value.person_filing, .value.signatures, .value.receipts, .value.formFiled))' > $@

form.json : filing.jl
	cat $< | jq -s '.[] | .detailed_form_data + {rptId, formFiled} | select(.file_number)' | jq -s | jq 'INDEX(.rptId) | with_entries(.value |= del(.rptId))' > $@

# ============================================================================
# Spider outputs (only invoked when sr_nums.txt is non-empty)
# ============================================================================

filing.jl: sr_nums.txt
	scrapy crawl filings_incremental -L WARNING -a sr_nums_file=$< -O $@

employer.csv: sr_nums.txt
	scrapy crawl employers_incremental -L WARNING -a sr_nums_file=$< -O $@

attachment.csv: sr_nums.txt
	scrapy crawl attachments_incremental -L WARNING -a sr_nums_file=$< -O $@

# ============================================================================
# Always-fresh inputs
# ============================================================================

sr_nums.txt: FORCE lm20.db
	python scripts/discover_new_filings.py lm20.db > $@

filer.csv: FORCE
	scrapy crawl filers -L INFO -O $@

# Bootstrap: fetch the prior nightly release if no local lm20.db.
lm20.db:
	curl -fsSL -o prev.zip $(PRIOR_DB_URL)
	unzip -o prev.zip lm20.db
	rm -f prev.zip

FORCE:
