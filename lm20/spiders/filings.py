from scrapy import Spider
from scrapy.http import FormRequest


class LM20(Spider):
    name = "filings"

    def start_requests(self):
        return [ FormRequest("https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet",
                             formdata={'clearCache': 'F', 'page': '1'},
                             callback=self.parse), 
                FormRequest("https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet",
                             formdata={'clearCache': 'F', 'page': '2'},
                             callback=self.parse) ]

    def parse(self, response):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet
        @filers_form
        @returns requests 500 500
        """
        
        filers = response.json()
        for filer in filers['filerList']:
            yield FormRequest("https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet",
                              formdata={'srFilerId': filer['srFilerId']},
                              callback=self.parse_filings,
                              cb_kwargs={'filer': filer})

            
            

    def parse_filings(self, response, filer):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM2021FilerDetailServlet
        @filings_form
        @cb_kwargs {"filer": {}}
        @returns items 1 1
        @scrapes filings
        
        """

        filings = response.json()['detail']
        filer['filings'] = filings

        yield filer

