# update.mk — incremental update of lm20.db.
#
# Discover filers with new LM-20/LM-21 activity
# (scripts/discover_new_filings.py), crawl just those filers with the
# *_incremental spiders, fan filing.jl out into JSON documents
# (common.mk), and load them into the previously released database —
# each document's tables in one transaction (scripts/load_json.py),
# the flat spider feeds via scripts/merge_csv.py. The filer table is
# refreshed on every run. Paper filings and upstream deletions this
# path can't see are reconciled by the scheduled full rebuild
# (.github/workflows/full-build.yml).
#
# Usage: make -f update.mk update

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c

PRIOR_DB_URL ?= https://github.com/labordata/lm20/releases/download/nightly/lm20.db.zip

# Cache responses for the length of the run so the three incremental
# spiders fetch each filer's detail page once instead of three times.
# The shared storage class de-namespaces the cache (stock scrapy keys
# it by spider name); error responses are not cached so a transient
# block doesn't poison the later spiders.
CACHE_FLAGS := -s HTTPCACHE_ENABLED=True -s HTTPCACHE_EXPIRATION_SECS=0 \
    -s HTTPCACHE_STORAGE=olms.cache.SharedFilesystemCacheStorage \
    -s HTTPCACHE_IGNORE_HTTP_CODES=400,403,404,429,500,502,503,504

.DELETE_ON_ERROR:

LOAD_TARGETS := update_filing update_forms update_lm20 update_lm21
CSV_TARGETS := update_employer update_attachment

.PHONY: update polish_db fk-check update_filer $(LOAD_TARGETS) $(CSV_TARGETS)

# ============================================================================
# Entry
# ============================================================================

# Discovery and the filer refresh must be fresh every run, so rebuild
# them once here, explicitly, rather than marking them FORCE — which
# would make any direct sub-target invocation re-crawl them mid-pipeline.
update: lm20.db
	rm -f filer.csv sr_nums.txt
	$(MAKE) -f update.mk -j2 sr_nums.txt filer.csv
	$(MAKE) -f update.mk update_filer
	@if [ -s sr_nums.txt ]; then \
	    $(MAKE) -f update.mk $(LOAD_TARGETS) $(CSV_TARGETS) polish_db; \
	else \
	    echo "update: no new filings discovered; only the filer table was refreshed" >&2; \
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
	sqlite-utils lm20.db "update lm20 set date_fiscal_year_ends = replace(date_fiscal_year_ends, ' / ', ' ')"
	sqlite-utils convert lm20.db lm20 date_entered_into 'r.parsedate(value)'
	sqlite-utils convert lm20.db lm21 period_begin 'r.parsedate(value)'
	sqlite-utils convert lm20.db lm21 period_through 'r.parsedate(value)'
	# drop staging tables a pre-merge_csv.py version of this pipeline
	# may have left in the bootstrap database
	for t in $$(sqlite3 lm20.db "select name from sqlite_master where type = 'table' and name like 'raw_%'"); do \
	    sqlite3 lm20.db "drop table \"$$t\""; \
	done

# ============================================================================
# Loads: one transaction per source document
# ============================================================================

update_filing: filing.json update_filer | lm20.db
	python scripts/load_json.py lm20.db filing $<

update_forms: form.json update_filing | lm20.db
	python scripts/load_json.py lm20.db form $<

update_lm20: lm20.json update_filing | lm20.db
	python scripts/load_json.py lm20.db lm20 $<

update_lm21: lm21.json update_filing | lm20.db
	python scripts/load_json.py lm20.db lm21 $<

# Fields the full build drops, mirrored here.
MERGE_FLAGS_filer := --replace --ignore filerType
MERGE_FLAGS_attachment := --ignore files --ignore file_headers

$(CSV_TARGETS) update_filer: update_%: %.csv | lm20.db
	python scripts/merge_csv.py lm20.db $* $(MERGE_FLAGS_$*) < $<

$(CSV_TARGETS): update_filing

# ============================================================================
# Spider outputs
# ============================================================================

# Every discovered filer was discovered FROM a filing, so its detail
# feed must yield at least one item; fewer items than filers means the
# crawl was blocked (OLMS 403s), not that there was nothing to fetch.
filing.jl: sr_nums.txt
	scrapy crawl filings_incremental $(CACHE_FLAGS) -L INFO -a sr_nums_file=$< -O $@
	@[ "$$(wc -l < $@)" -ge "$$(wc -l < $<)" ] || \
	    (echo "ERROR: $@ has fewer filings than discovered filers; crawl was likely blocked" >&2 && exit 1)

employer.csv: sr_nums.txt
	scrapy crawl employers_incremental $(CACHE_FLAGS) -L INFO -a sr_nums_file=$< -O $@

attachment.csv: sr_nums.txt
	scrapy crawl attachments_incremental $(CACHE_FLAGS) -L INFO -a sr_nums_file=$< -O $@

sr_nums.txt: | lm20.db
	python scripts/discover_new_filings.py lm20.db > $@

# The filer list servlet always has hundreds of filers; an empty crawl
# means something is broken (e.g. OLMS blocking us), not an empty list.
filer.csv:
	scrapy crawl filers -L INFO -O $@
	@[ "$$(wc -l < $@)" -gt 1 ] || (echo "ERROR: $@ is empty" >&2 && exit 1)

# Bootstrap: fetch the prior nightly release if no local lm20.db.
lm20.db:
	curl -fsSL -o prev.zip $(PRIOR_DB_URL)
	unzip -o prev.zip lm20.db
	rm -f prev.zip

include common.mk
