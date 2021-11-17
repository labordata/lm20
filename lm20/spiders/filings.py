from scrapy import Spider
from scrapy.http import FormRequest


class LM20(Spider):
    name = "filings"

    custom_settings = {
        'ITEM_PIPELINES': {
            'lm20.pipelines.TimestampToDatetime': 1,
            'lm20.pipelines.ReportLink': 2,
            'lm20.pipelines.HeaderMimetypePipeline': 3
        }
    }

    def start_requests(self):
        return [ FormRequest("https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet",
                             formdata={'clearCache': 'F', 'page': '1'},
                             cb_kwargs={'page': 1},
                             callback=self.parse) ]

    def parse(self, response, page):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet
        @filers_form
        @cb_kwargs {"page": 0}
        @returns requests 501 501
        """
        
        filers = response.json()['filerList']
        for filer in filers:
            yield FormRequest("https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet",
                              formdata={'srFilerId': filer['srFilerId']},
                              callback=self.parse_filings)
        if len(filers) == 500:
            page += 1
            yield FormRequest("https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet",
                              formdata={'clearCache': 'F', 'page': str(page)},
                              cb_kwargs={'page': page},
                              callback=self.parse)

    def parse_filings(self, response):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet
        @filings_form
        @returns items 55
        @scrapes amended
        """

        for filing in response.json()['detail']:
            del filing['attachmentId']
            del filing['fileName']
            del filing['fileDesc']

            yield filing

