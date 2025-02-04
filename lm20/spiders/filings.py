from email.message import Message

from scrapy import Spider
from scrapy.http import FormRequest, Request


class LM20(Spider):
    name = "filings"

    custom_settings = {
        "ITEM_PIPELINES": {
            "lm20.pipelines.TimestampToDatetime": 1,
            "lm20.pipelines.HeaderMimetypePipeline": 3,
        }
    }

    def start_requests(self):
        return [
            FormRequest(
                "https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet",
                formdata={"clearCache": "F", "page": "1"},
                cb_kwargs={"page": 1},
                callback=self.parse,
            )
        ]

    def parse(self, response, page):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet
        @filers_form
        @cb_kwargs {"page": 0}
        @returns requests 501 501
        """
        filers = response.json()["filerList"]
        for filer in filers:
            yield FormRequest(
                "https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet",
                formdata={"srNum": "C-" + str(filer["srNum"])},
                callback=self.parse_filings,
            )
        if len(filers) == 500:
            page += 1
            yield FormRequest(
                "https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet",
                formdata={"clearCache": "F", "page": str(page)},
                cb_kwargs={"page": page},
                callback=self.parse,
            )

    def parse_filings(self, response):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet
        @filings_form
        @returns items 2
        @scrapes amended
        """
        for filing in response.json()["detail"]:
            del filing["attachmentId"]
            del filing["fileName"]
            del filing["fileDesc"]

            filing["detailed_form_data"] = None
            filing["file_urls"] = []
            filing["file_headers"] = {}

            report_url = "https://olmsapps.dol.gov/query/orgReport.do?rptId={rptId}&rptForm={formLink}".format(
                **filing
            )

            filing["filing_url"] = report_url

            # These three conditions seem sufficient to identify that
            # a filing was submitted electronically and if we
            # request the filing form, we'll get back a web page
            # (though we might have to ask more than once)
            electronic_submission = all(
                (
                    filing["paperOrElect"] == "E",
                    filing["receiveDate"],
                    filing["rptId"] > 183135,
                )
            )

            if electronic_submission:
                report = None
                if filing["formLink"] == "LM20Form":
                    report = LM20Report
                elif filing["formLink"] == "LM21Form":
                    report = LM21Report
                else:
                    raise ValueError("Invalid formLink", filing["formLink"])

                yield Request(
                    report_url,
                    cb_kwargs={"item": filing, "report": report},
                    callback=self.parse_html_report,
                )
            else:
                yield Request(
                    report_url,
                    method="HEAD",
                    cb_kwargs={"item": filing},
                    callback=self.report_header,
                )

    def report_header(self, response, item):

        item["file_urls"] = [response.request.url]
        item["file_headers"] = {
            response.request.url: dict(response.headers.to_unicode_dict())
        }

        yield item

    def parse_html_report(self, response, item, report, attempts=0):

        # baffling, sometimes when you request some resources
        # it returns html and sometime it returns a pdf
        m = Message()
        m["content-type"] = response.headers.get("Content-Type").decode()
        content_type, _ = m.get_params()[0]

        keep_trying = True

        if content_type == "text/html" and b"Signature" in response.body:

            form_data = report.parse(response)

            if str(item["srNum"]) == form_data["file_number"] or attempts > 2:
                item["detailed_form_data"] = form_data
                yield item
                keep_trying = False
            else:
                attempts += 1

        if keep_trying:
            yield Request(
                response.request.url,
                cb_kwargs={"item": item, "report": report, "attempts": attempts},
                callback=self.parse_html_report,
                dont_filter=True,
            )


class LM21Report:
    @classmethod
    def parse(cls, response):

        form_dict = dict(
            file_number=cls._get_i_value(response, "1. File Number: C-"),
            period_begin=cls._get_i_value(response, " From: "),
            period_through=cls._get_i_value(response, " Through: "),
        )

        form_dict["person_filing"] = {}
        form_dict["person_filing"]["name_and_mailing_address"] = cls._section_three(
            response
        )
        form_dict["person_filing"][
            "any_other_name_or_address_necessary_to_verify_report"
        ] = cls._section_four(response)
        form_dict["signatures"] = cls._signatures(response)
        form_dict["receipts"] = cls._statement_of_receipts(response)
        form_dict["disbursements"] = cls._statement_of_disbursements(response)
        form_dict["schedule_disbursements"] = cls._schedule_of_disbursements(response)
        form_dict["total_disbursements"] = cls._get_i_value(
            response, "TOTAL DISBURSEMENTS FOR ALL REPORTABLE ACTIVITY:"
        )

        return form_dict

    @classmethod
    def _schedule_of_disbursements(cls, response):

        results = []
        section_xpath = "//div[@class='myTable' and descendant::span[@class='i-label' and text()='Schedule of Disbursements for Reportable Activity ']]"
        section = response.xpath(section_xpath)

        employers = section.xpath(".//div[@class='activityTable']")

        for employer in employers:
            parsed = {}
            for field in (
                "15.a. Employer Name:",
                "15.b. Trade Name, If any:",
                "Name:",
                "Title:",
                "Organization:",
                "P.O. Box., Bldg., Room No., if any:",
                "Street:",
                "City:",
                "ZIP code:",
                "15.d.Amount:",
                "15.e.Purpose:",
            ):
                clean_field = field.replace("\xa0", "").strip(" :")
                parsed[clean_field] = cls._get_i_value(employer, field)

            results.append(parsed)

        return results

    @classmethod
    def _statement_of_disbursements(cls, response):

        results = {}

        tables_xpath = ".//div[text()='Disbursements to Officers and Employees: ']/parent::div/parent::div[@class='row']/following-sibling::div[@class='row']/table[@class='addTable']"

        tables = response.xpath(tables_xpath)

        individual_disbursements = []
        fields = ("name", "salary", "expense", "total")
        for row in tables[0].xpath("./tr"):
            values = row.xpath("./th//text()").getall()
            individual_disbursements.append(dict(zip(fields, values)))

        results["individual_disbursements"] = individual_disbursements

        for row in tables[1].xpath("./tr"):
            index, field_name, *rest = row.xpath("./th//text()").getall()

            if rest:
                (value,) = rest
            else:
                value = ""

            results[clean_field(field_name)] = value

        return results

    @classmethod
    def _statement_of_receipts(cls, response):

        results = []
        section_xpath = "//div[@class='myTable' and descendant::span[@class='i-label' and text()='Statement of Receipts']]"
        section = response.xpath(section_xpath)

        receipts = section.xpath(".//div[@class='activityTable']")

        for receipt in receipts:
            parsed_receipts = {}
            for field in (
                "Employer:",
                "Trade Name:",
                "Name:",
                "Title:",
                "Mailing Address:",
                "P.O. Box., Bldg., Room No., if any:",
                "Street:",
                "City:",
                "State:",
                "ZIP Code:",
                "Termination Date:",
                "Amount:",
                "\xa0 \xa0 \xa0 Non-Cash Payment:",
                "\xa0\xa0\xa0 Type of Payment:",
            ):
                parsed_receipts[clean_field(field)] = cls._get_i_value(receipt, field)
            results.append(parsed_receipts)

        return results

    @classmethod
    def _signatures(cls, response):

        result = {17: {}, 18: {}}
        for signature_number in result:
            section = cls._signature_section(response, signature_number)
            for field in ("SIGNED:", "Title:", "Date:", "Telephone:"):
                result[signature_number][clean_field(field)] = cls._get_i_value(
                    section, field
                )

        return result

    @classmethod
    def _signature_section(cls, response, signature_number):

        result = response.xpath(
            f"//div[@class='myTable' and descendant::span[@class='i-label' and text()='{signature_number}.']]"
        )[1]

        return result

    @classmethod
    def _section_three(cls, response):
        return cls._parse_section(
            response,
            section_label="3. Name and mailing address (including Zip Code):",
            field_labels=(
                "Name:",
                "Title:",
                "Organization:",
                "P.O. Box., Bldg., Room No., if any:",
                "Street:",
                "City:",
                "State:",
                "ZIP code:",
            ),
        )

    @classmethod
    def _section_four(cls, response):
        return cls._parse_section(
            response,
            section_label="""4. Any other address where records necessary to
													verify this report are kept:""",
            field_labels=(
                "Name:",
                "Title:",
                "Organization:",
                "P.O. Box., Bldg., Room No., if any:",
                "Street:",
                "City:",
                "State:",
                "ZIP code:",
            ),
        )

    @classmethod
    def _parse_section(cls, response, section_label, field_labels):
        section = cls._section(response, section_label)

        section_dict = {}
        for field in field_labels:
            section_dict[clean_field(field)] = cls._get_i_value(section, field).strip()
        return section_dict

    @classmethod
    def _section(cls, response, label_text):

        xpath = f"//div[@class='i-sectionNumberTable' and descendant::span[@class='i-label' and text()='{label_text}']]/following-sibling::div[@class='i-sectionbody']"
        return response.xpath(xpath)

    @classmethod
    def _get_i_value(cls, tree, label_text):

        i_value_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::span[@class='i-value'][1]/text()"
        result = tree.xpath(i_value_xpath)

        if not result:
            i_checkbox_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::span[@class='i-xcheckbox'][1]/text()"
            result = tree.xpath(i_checkbox_xpath)

        if not result:
            nested_i_value_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::span[1]/span[@class='i-value']/text()"
            result = tree.xpath(nested_i_value_xpath)

        if not result:
            following_text_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::text()[1]"
            result = tree.xpath(following_text_xpath)

        if not result:
            nonnormal_i_value_xpath = f".//span[@class='i-label' and text()='{label_text}']/following-sibling::span[@class='i-value'][1]/text()"
            result = tree.xpath(nonnormal_i_value_xpath)

        return result.get(default="").strip()


class LM20Report:
    @classmethod
    def parse(cls, response):

        form_dict = dict(
            file_number=cls._get_i_value(response, "1.a. File Number: C-"),
            amended=cls._get_i_value(response, "Amended:"),
        )

        form_dict["person_filing"] = {}
        form_dict["person_filing"]["name_and_mailing_address"] = cls._contact_block(
            response, "Name and mailing address (including Zip Code):"
        )
        form_dict["person_filing"][
            "any_other_name_or_address_necessary_to_verify_report"
        ] = cls._contact_block(
            response,
            """Other address where records necessary to
													verify this report are kept:""",
        )

        form_dict["date_fiscal_year_ends"] = " ".join(
            response.xpath(
                "//span[@class='i-label' and text()='Date fiscal year ends:']/following-sibling::span//text()"
            ).getall()
        )

        form_dict["type_of_person"] = cls._type_of_person(response)

        form_dict["employer"] = cls._contact_block(
            response,
            "Full name and address of employer  with whom made (include ZIP Code):",
        )

        form_dict["employer"]["date_entered_into"] = cls._get_i_value(
            response, "Date entered into"
        )

        form_dict["signatures"] = cls._signatures(response)

        form_dict["direct_or_indirect"] = cls._direct_or_indirect(response)

        form_dict["terms_and_conditions"] = cls._terms_and_conditions(response)

        form_dict["specific_activities"] = cls._specific_activities(response)

        return form_dict

    @classmethod
    def _contact_block(cls, response, section_label):
        return cls._parse_section(
            response,
            section_label=section_label,
            field_labels=(
                "Name:",
                "Title:",
                "Organization:",
                "P.O. Box., Bldg., Room No., if any:",
                "Street:",
                "City:",
                "State:",
                "ZIP code:",
            ),
        )

    @classmethod
    def _type_of_person(cls, response):

        person_type = {
            "Individual \xa0 \xa0 \xa0 b.": "Individual",
            "Partnership": "Partnership",
            "Corporation C d.": "Corporation C",
            "Other": "Other",
        }

        section = cls._section(response, "Type of person")

        checkboxes = section.xpath(
            "./span[@class='i-xcheckbox' or @class='i-nocheckbox']"
        )
        checked_value = None

        for box in checkboxes:
            value = box.xpath("./text()").get(default="").strip()
            label = person_type[
                box.xpath("./following-sibling::text()[1]").get().strip()
            ]

            if value == "X":
                assert checked_value is None
                checked_value = label

        assert checked_value is not None
        return checked_value

    @classmethod
    def _parse_section(cls, response, section_label, field_labels):
        section = cls._section(response, section_label)

        section_dict = {}
        for field in field_labels:
            section_dict[clean_field(field)] = cls._get_i_value(section, field).strip()
        return section_dict

    @classmethod
    def _section(cls, response, label_text):

        xpath = f"//div[@class='i-sectionNumberTable' and descendant::span[@class='i-label' and text()='{label_text}']]/following-sibling::div[@class='i-sectionbody']"
        return response.xpath(xpath)

    @classmethod
    def _get_i_value(cls, tree, label_text):

        i_value_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::span[@class='i-value'][1]/text()"
        result = tree.xpath(i_value_xpath)

        if not result:
            i_checkbox_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::span[@class='i-xcheckbox'][1]/text()"
            result = tree.xpath(i_checkbox_xpath)

        if not result:
            nested_i_value_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::span[1]/span[@class='i-value']/text()"
            result = tree.xpath(nested_i_value_xpath)

        if not result:
            following_text_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::text()[1]"
            result = tree.xpath(following_text_xpath)

        return result.get(default="").strip()

    @classmethod
    def _signatures(cls, response):

        result = {13: {}, 14: {}}
        for signature_number in result:
            section = cls._signature_section(response, signature_number)
            for field in ("SIGNED:", "Title:", "Date:", "Telephone Number:"):
                result[signature_number][clean_field(field)] = cls._get_i_value(
                    section, field
                )

        return result

    @classmethod
    def _signature_section(cls, response, signature_number):

        result = response.xpath(
            f"//div[@class='myTable' and descendant::span[@class='i-label' and text()='{signature_number}.']]"
        )[1]

        return result

    @classmethod
    def _direct_or_indirect(cls, response):

        label_text = """Check the appropriate box(es) to indicate
														whether an object
														of the activities undertaken is directly
														or
														indirectly:"""

        section = response.xpath(
            f"//div[@class='i-sectionNumberTable' and descendant::span[@class='i-label' and text()='{label_text}']]/following-sibling::div[@class='activityTable']"
        )

        direct_text = """To persuade employees to exercise or not to
													exercise, or persuade employees as to the manner of
													exercising, the right to organize and bargain collectively
													through representatives of their own choosing."""
        indirect_text = """To supply an employer with information
													concerning the activities of employees or a labor
													organization in connection with a labor dispute involving
													such employer, except information for use solely in
													conjunction with an administrative or arbitral proceeding
													or
													a criminal or civil judicial proceeding."""

        direct = section.xpath(
            f".//div[@class='row' and descendant::div[text()='{direct_text}']]//span[@class='i-xcheckbox']/text()"
        )

        indirect = section.xpath(
            f".//div[@class='row' and descendant::div[text()='{indirect_text}']]//span[@class='i-xcheckbox']/text()"
        )

        return {"direct": direct.get(), "indirect": indirect.get()}

    @classmethod
    def _terms_and_conditions(cls, response):
        section = response.xpath(
            "//div[@class='i-sectionNumberTable' and descendant::span[@class='i-label' and text()='Terms and conditions.']]/following-sibling::div[@class='activityTable']"
        )

        written_agreement = section.xpath(
            ".//div[@class='row' and descendant::span[text()='Written Agreement/Arrangement']]//span[@class='i-xcheckbox']/text()"
        )

        notes = section.xpath(".//div[@class='row'][2]/div/text()")

        return {
            "written_agreement": written_agreement.get(default=""),
            "notes": notes.get(default=""),
        }

    @classmethod
    def _specific_activities(cls, response):

        section = response.xpath(
            "//div[@class='myTable' and descendant::span[@class='i-label' and text()='Specific Activities to be performed']]"
        )

        activities = section.xpath(
            ".//div[@class='row' and descendant::span[@class='i-label' and text()='Activity']]"
        )

        activities_list = []

        for i, activity in enumerate(activities, 1):
            subsection = activity.xpath(
                f"./following-sibling::div[@class='row' and count(preceding-sibling::div[@class='row' and descendant::span[@class='i-label' and text()='Activity']])={i}]"
            )

            nature_of_activity = cls._get_i_value(subsection, "a. Nature of activity:")

            period_of_performance = subsection.xpath(
                """.//div[@class='i-sectionNumberTable' and descendant::span[@class='i-label' and text()='11.b.Period during which activities
														performed:']]/following-sibling::div/span[@class='i-value']/text()"""
            ).get(default="")

            extent_of_performance = subsection.xpath(
                ".//span[@class='i-label' and text()='11.c. Extent of performance:']/following-sibling::div[@class='i-sectionbody']/div[@class='i-value']/text()"
            ).get(default="")

            performers = subsection.xpath(
                "./div[descendant::div[@class='i-sectionNumberTable' and descendant::span[@class='i-label' and text()='11.d.']]]"
            )

            performer_list = []
            for performer in performers:
                performer_dict = {}
                performer_section = performer.xpath("./div[@class='row']")

                fields = (
                    "\xa0 Name:",
                    "\xa0 \xa0 \xa0 \xa0 \xa0Organization:",
                    " \xa0 P.O. Box, Bldg., Room No., If any:",
                    "Street:",
                    "City:",
                    "State:",
                    "Zip:",
                )

                for field in fields:
                    performer_dict[clean_field(field)] = cls._get_i_value(
                        performer_section, field
                    )

                performer_list.append(performer_dict)

            subject_employees = subsection.xpath(
                ".//div[@class='row' and descendant::span[@class='i-label' and text()=' 12.a. Identify subject groups of employees:']]/following-sibling::div[@class='i-sectionbody']/span[@class='i-value']/text()"
            ).get(default="")

            subject_labor_orgs = subsection.xpath(
                ".//div[@class='row' and descendant::span[@class='i-label' and text()=' 12.b. Identify subject labor organizations:']]/following-sibling::div//span[@class='i-value']/text()"
            ).get(default="")

            activities_list.append(
                {
                    "nature_of_activity": nature_of_activity,
                    "period_of_performance": period_of_performance,
                    "extent_of_performance": extent_of_performance,
                    "performers": performer_list,
                    "subject_employees": subject_employees,
                    "subject_labor_orgs": subject_labor_orgs,
                }
            )

        return activities_list


def clean_field(string):

    return (
        string.replace("\xa0", "")
        .strip(" :")
        .replace(".", "")
        .replace(" ", "_")
        .lower()
    )
