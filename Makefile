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

lm20.db : form.csv lm20.csv lm21.csv
	csvs-to-sqlite form*.csv lm20.csv lm21.csv $@
                                              #TODO: rename/drop columns; set pk/fk
                                              #TODO: LM20 form scrape: [lm20.employer.date_entered_into], [lm20.employer.title]
                                              #TODO: LM21 form scrape: [lm21.period_begin], [lm21.period_through], ?[lm21.amended]



employer.csv :
	scrapy crawl employers -O $@

attachment.csv :
	scrapy crawl attachments -O $@

lm20.csv : lm20.json
	json-to-multicsv.pl --file $< \
                      --path /:table:lm20 \
                      --path /*/employer/:column \
                      --path /*/direct_or_indirect/:column \
                      --path /*/terms_and_conditions/:column

lm21.csv : lm21.json
	json-to-multicsv.pl --file $< \
                      --path /:table:lm21 \
                      --path /*/disbursements/:column \
                      --path /*/disbursements/individual_disbursements/:ignore \
                      --path /*/schedule_disbursements/:column

form.csv : form.json
	cat $< | jq 'INDEX(.rptId)' > rptidform.json
	json-to-multicsv.pl --file rptidform.json \
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

lm20.json : form.json
	cat $< | jq '[.[] | select (.formFiled == "LM-20") \
                    | {rptId, amended, employer, date_fiscal_year_ends, type_of_person,  \
                       direct_or_indirect, terms_and_conditions}]' > $@

lm21.json : form.json
	cat $< | jq '[.[] | select (.formFiled == "LM-21") \
                    | {rptId, period_begin, period_through, disbursements, \
                      schedule_disbursements, total_disbursements}]' > $@

form.json : filing.jl
	cat $< |  jq -s '.[] | .detailed_form_data + {rptId, formFiled} | select(.file_number)' | jq -s > $@

filing.jl :
	scrapy crawl filings -O $@

filer.csv :
	scrapy crawl filers -O $@
