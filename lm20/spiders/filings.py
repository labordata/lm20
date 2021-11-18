import cgi

from scrapy import Spider
from scrapy.http import FormRequest, Request


class LM20(Spider):
    name = "filings"

    custom_settings = {
        'ITEM_PIPELINES': {
            'lm20.pipelines.TimestampToDatetime': 1,
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

            report_url = 'https://olmsapps.dol.gov/query/orgReport.do?rptId={rptId}&rptForm={formLink}'.format(**filing)

            yield Request(report_url,
                          method='HEAD',
                          cb_kwargs={'item': filing},
                          callback=self.report_header)

    def report_header(self, response, item):

        item['file_urls'] = []
        item['file_headers'] = {}

        content_type, _ = cgi.parse_header(response.headers.get('Content-Type').decode())
        if content_type == 'text/html':

            
            if item['formLink'] == 'LM20Form':
                callback = self.parse_lm20_html_report
            elif item['formLink'] == 'LM21Form':
                callback = self.parse_lm21_html_report
            else:
                raise ValueError('Invalid formLink', item['formLink'])

            yield Request(response.request.url,
                          cb_kwargs={'item': item},
                          callback=callback)
                                

        else:
            item['file_urls'].append(response.request.url)
            item['file_headers'][response.request.url] = response.headers
            
            return item
        

    def parse_lm_20_html_report(self, response, item):

        breakpoint()

    def parse_lm_21_html_report(self, response, item):

        file_number = response.xpath("//span[@class='i-label' and text()='1. File Number: C-']/following-sibling::span[@class='i-value']/text()").get()
        period_begin = response.xpath("//span[@class='i-label' and text()=' From: ']/following-sibling::span[@class='i-value']/text()").get()
        period_through = response.xpath("//span[@class='i-label' and text()=' Through: ']/following-sibling::span[@class='i-value']/text()").get()

        person_filing_three = response.xpath("//div[@class='i-sectionNumberTable' and descendant::span[@class='i-label' and text()='3. Name and mailing address (including Zip Code):']]/following-sibling::div[@class='i-sectionbody']")
        person_filing_name = person_filing_three.xpath(".//span[@class='i-label' and text()='Name:']/following-sibling::span[@class='i-value']/text()").get()

        
        
