from scrapy import Spider
from scrapy.http import FormRequest


class Employers(Spider):
    name = "employers"

    custom_settings = {
        "ITEM_PIPELINES": {
            "lm20.pipelines.Nullify": 1,
            "lm20.pipelines.TitleCase": 2,
            "lm20.pipelines.StandardDate": 3,
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
        @returns request 1
        """

        for filing in response.json()["detail"]:
            yield FormRequest(
                "https://olmsapps.dol.gov/olpdr/GetAdditionalEmpsServlet",
                formdata={"rptId": str(filing["rptId"])},
                callback=self.parse_employer,
            )

    def parse_employer(self, response):
        """
        @url https://olmsapps.dol.gov/olpdr/GetAdditionalEmpsServlet
        @employers_form
        @returns items 1
        """

        employer_fields = (
            "rptId",
            "empLabOrg",
            "empTrdName",
            "city",
            "state",
            "termDate",
            "amount",
        )

        for employer in response.json()["detail"]:
            item = {field: employer[field] for field in employer_fields}
            yield item
