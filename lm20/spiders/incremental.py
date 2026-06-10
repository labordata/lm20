from scrapy.http import FormRequest


class SrNumSpiderMixin:
    """Restrict a full-crawl spider to an explicit list of filers.

    Instead of paging through GetLM2021FilerListServlet, request the
    filing detail for each srNum passed via -a sr_nums=42,556 or
    -a sr_nums_file=/path/to/file (whitespace-separated). The srNums
    come from scripts/discover_new_filings.py.
    """

    def __init__(self, sr_nums=None, sr_nums_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nums = []
        if sr_nums:
            nums.extend(sr_nums.split(","))
        if sr_nums_file:
            with open(sr_nums_file) as f:
                nums.extend(f.read().split())
        nums = [n for n in nums if n.strip()]
        if not nums:
            raise ValueError(
                "pass either -a sr_nums=42,556 or -a sr_nums_file=/path/to/file"
            )
        self.sr_nums = sorted({int(n) for n in nums})

    async def start(self):
        for sr in self.sr_nums:
            yield FormRequest(
                "https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet",
                formdata={"srNum": "C-" + str(sr)},
                callback=self.parse_filings,
            )
