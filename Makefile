SHELL=/bin/bash

.DELETE_ON_ERROR:

define assert_not_empty
(test -s $(1) || (echo "ERROR: $(1) is empty" && exit 1))
endef


# Full from-scratch build: the schema is the checked-in schema.sql (the
# published shape, formerly inferred by csvs-to-sqlite from CSV
# contents), and the rows go in through the same olms merge engine the
# incremental update uses.
lm20.db : schema.sql filing.json form.json lm20.json lm21.json filer.csv employer.csv attachment.csv
	rm -f $@
	sqlite3 $@ < schema.sql
	python scripts/merge_csv.py $@ filer --replace --ignore filerType < filer.csv
	python scripts/load_json.py $@ filing filing.json
	python scripts/load_json.py $@ form form.json
	python scripts/load_json.py $@ lm20 lm20.json
	python scripts/load_json.py $@ lm21 lm21.json
	python scripts/merge_csv.py $@ employer < employer.csv
	python scripts/merge_csv.py $@ attachment --ignore files --ignore file_headers < attachment.csv
	sqlite-utils $@ "update lm20 set date_fiscal_year_ends = replace(date_fiscal_year_ends, ' / ', ' ')"
	sqlite-utils convert $@ lm20 date_entered_into 'r.parsedate(value)'
	sqlite-utils convert $@ lm21 period_begin 'r.parsedate(value)'
	sqlite-utils convert $@ lm21 period_through 'r.parsedate(value)'
	sqlite-utils vacuum $@
	@test -z "$$(sqlite3 $@ 'PRAGMA foreign_key_check;')" && echo "fk-check: $@ is clean"

attachment.csv :
	scrapy crawl attachments -L 'INFO' -O $@ && $(call assert_not_empty,$@)

employer.csv :
	scrapy crawl employers -L 'INFO' -O $@ && $(call assert_not_empty,$@)

filing.jl :
	scrapy crawl filings -L 'INFO' -O $@ && $(call assert_not_empty,$@)

filer.csv :
	scrapy crawl filers -L 'INFO' -O $@ && $(call assert_not_empty,$@)

include common.mk
