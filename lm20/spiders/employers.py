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

    def _iter_filings(self, response):
        return response.json()["detail"]

    def parse_filings(self, response):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet
        @filings_form
        @returns request 1
        """

        for filing in self._iter_filings(response):
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


class IncrementalEmployers(Employers):
    """Fetch additional-employer rows for new filings only.

    Accepts the same sr_nums / sr_nums_file inputs as IncrementalFilings,
    plus an optional max_known_rpt_id to skip already-indexed rptIds."""

    name = "employers_incremental"

    def __init__(
        self, sr_nums=None, sr_nums_file=None, max_known_rpt_id=None, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        nums = []
        if sr_nums:
            nums.extend(sr_nums.split(","))
        if sr_nums_file:
            with open(sr_nums_file) as f:
                nums.extend(f.read().split())
        if not nums:
            raise ValueError(
                "pass either -a sr_nums=42,556 or -a sr_nums_file=/path/to/file"
            )
        self.sr_nums = sorted({int(n) for n in nums if n.strip()})
        self.max_known_rpt_id = int(max_known_rpt_id) if max_known_rpt_id else None

    def start_requests(self):
        return [
            FormRequest(
                "https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet",
                formdata={"srNum": "C-" + str(sr)},
                callback=self.parse_filings,
            )
            for sr in self.sr_nums
        ]

    def _iter_filings(self, response):
        for filing in response.json()["detail"]:
            if (
                self.max_known_rpt_id is not None
                and filing["rptId"] <= self.max_known_rpt_id
            ):
                continue
            yield filing
