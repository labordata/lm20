# common.mk — the jq fan-out from filing.jl, shared by the full build
# (Makefile) and the incremental update (update.mk). The spider targets
# that produce filing.jl, filer.csv, employer.csv, and attachment.csv
# live in the including makefile; the JSON documents here are loaded
# straight into the database by scripts/load_json.py.

filing.json: filing.jl
	cat $< | jq -s '.[] | del(.detailed_form_data, .file_headers, .file_urls) | .files = .files[0] | .file_path = .files.path | .file_checksum = .files.checksum | .file_status = .files.status | del(.files)' | jq -s > $@

lm20.json : form.json
	cat $< | jq 'with_entries( select(.value.formFiled == "LM-20")| del(.value.file_number, .value.person_filing, .value.signatures, .value.specific_activities, .value.formFiled))' > $@

lm21.json : form.json
	cat $< | jq 'with_entries( select(.value.formFiled == "LM-21") | del(.value.file_number, .value.person_filing, .value.signatures, .value.receipts, .value.formFiled))' > $@

form.json : filing.jl
	cat $< | jq -s '.[] | .detailed_form_data + {rptId, formFiled} | select(.file_number)' | jq -s | jq 'INDEX(.rptId) | with_entries(.value |= del(.rptId))' > $@
