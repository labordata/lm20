CREATE TABLE IF NOT EXISTS "filer" (
   [srNum] INTEGER PRIMARY KEY,
   [companyName] TEXT,
   [companyCity] TEXT,
   [companyState] TEXT,
   [srFilerId] TEXT
);
CREATE TABLE IF NOT EXISTS "filing" (
   [address1] TEXT,
   [address2] TEXT,
   [amended] TEXT,
   [amendment] INTEGER,
   [beginDate] TEXT,
   [city] TEXT,
   [empLabOrg] TEXT,
   [endDate] TEXT,
   [file_checksum] TEXT,
   [file_path] TEXT,
   [file_status] TEXT,
   [filing_url] TEXT,
   [formFiled] TEXT,
   [originalRptId] INTEGER,
   [paperOrElect] TEXT,
   [receiveDate] TEXT,
   [registerDate] TEXT,
   [repOrgsCnt] INTEGER,
   [rptId] INTEGER PRIMARY KEY,
   [srFilerId] INTEGER,
   [srNum] INTEGER REFERENCES [filer]([srNum]),
   [state] TEXT,
   [yrCovered] INTEGER,
   [zip] TEXT
);
CREATE TABLE IF NOT EXISTS "contact" (
   [city] TEXT,
   [ein] TEXT,
   [name] TEXT,
   [organization] TEXT,
   [po_box,_bldg,_room_no,_if_any] TEXT,
   [state] TEXT,
   [street] TEXT,
   [title] TEXT,
   [zip_code] TEXT,
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [contact_type] TEXT
);
CREATE TABLE IF NOT EXISTS "employer" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [empLabOrg] TEXT,
   [empTrdName] TEXT,
   [city] TEXT,
   [state] TEXT,
   [termDate] TEXT,
   [amount] INTEGER
);
CREATE TABLE IF NOT EXISTS "lm20" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [amended] INTEGER,
   [date_fiscal_year_ends] TEXT,
   [direct] TEXT,
   [indirect] TEXT,
   [city] TEXT,
   [date_entered_into] TEXT,
   [ein] TEXT,
   [name] TEXT,
   [organization] TEXT,
   [po_box,_bldg,_room_no,_if_any] TEXT,
   [state] TEXT,
   [street] TEXT,
   [zip_code] TEXT,
   [notes] TEXT,
   [written_agreement] TEXT,
   [type_of_person] TEXT
);
CREATE TABLE IF NOT EXISTS "lm21" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [fees_for_professional_services] TEXT,
   [loans_made] TEXT,
   [officer_and_administrative_expenses] TEXT,
   [other_disbursements] TEXT,
   [publicity] TEXT,
   [total_disbursements_(sum_of_items_8-13)] TEXT,
   [total_disbursements_to_officers_and_employees] TEXT,
   [period_begin] TEXT,
   [period_through] TEXT,
   [ Employer Name] TEXT,
   [ Trade Name, If any] INTEGER,
   [Amount] TEXT,
   [Purpose] TEXT,
   [City] TEXT,
   [Name] TEXT,
   [Organization] TEXT,
   [P.O. B, B, Room N, if any] TEXT,
   [Street] TEXT,
   [Title] TEXT,
   [ZIP code] TEXT,
   [total_disbursements] TEXT
);
CREATE TABLE IF NOT EXISTS "performer" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [specific_activity_id] INTEGER REFERENCES [specific_activity]([id]),
   [performer_order] INTEGER,
   [city] TEXT,
   [ein] TEXT,
   [file_number] INTEGER,
   [name] TEXT,
   [organization] TEXT,
   [po_box,_bldg,_room_no,_if_any] INTEGER,
   [state] TEXT,
   [street] TEXT,
   [title] INTEGER,
   [zip] TEXT
);
CREATE TABLE IF NOT EXISTS "receipts" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [receipt_number] INTEGER,
   [amount] TEXT,
   [city] TEXT,
   [employer] TEXT,
   [mailing_address] INTEGER,
   [name] TEXT,
   [non-cash_payment] TEXT,
   [po_box,_bldg,_room_no,_if_any] TEXT,
   [state] TEXT,
   [street] TEXT,
   [termination_date] TEXT,
   [title] TEXT,
   [trade_name] TEXT,
   [type_of_payment] TEXT,
   [zip_code] INTEGER
);
CREATE TABLE IF NOT EXISTS "signatures" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [signature_number] INTEGER,
   [date] TEXT,
   [signed] TEXT,
   [telephone] INTEGER,
   [telephone_number] TEXT,
   [title] TEXT
);
CREATE TABLE IF NOT EXISTS "specific_activity" (
   [id] INTEGER PRIMARY KEY,
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [activity_order] INTEGER,
   [specific_extent_of_performance] TEXT,
   [specific_nature_of_activity] TEXT,
   [specific_period_of_performance] TEXT,
   [specific_subject_employees] TEXT,
   [specific_subject_labor_orgs] TEXT
);
CREATE TABLE IF NOT EXISTS "attachment" (
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [attachment_id] INTEGER PRIMARY KEY,
   [filename] TEXT,
   [file_description] TEXT,
   [file_urls] TEXT
);
CREATE TABLE IF NOT EXISTS "individual_disbursements" (
   [expense] TEXT,
   [name] TEXT,
   [salary] TEXT,
   [total] TEXT,
   [rptId] INTEGER REFERENCES [filing]([rptId]),
   [disbursement_order] INTEGER
);
