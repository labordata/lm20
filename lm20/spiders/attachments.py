from scrapy import Spider
from scrapy.http import FormRequest


class Attachments(Spider):
    name = "attachments"

    custom_settings = {
        'ITEM_PIPELINES': {
            'lm20.pipelines.AttachmentHeaders': 1,
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
                              formdata={'srNum': 'C-' + str(filer['srNum'])},
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
        @returns items 0
        """

        for filing in response.json()['detail']:
            if not filing['attachmentId']:
                continue
            attachment_ids = (filing['attachmentId'] or '').split(',')
            file_names = (filing['fileName'] or '').split(',')
            file_descriptions = (filing['fileDesc'] or '').split(',')

            attachments = zip(attachment_ids, file_names, file_descriptions)

            for attachment in attachments:
                attachment_id, file_name, file_description = attachment
                item = {
                    'rptId': filing['rptId'],
                    'attachment_id': attachment_id,
                    'filename': file_name,
                    'file_description': file_description,
                    'file_urls': [ f'https://olmsapps.dol.gov/query/orgReport.do?rptId={attachment_id}&rptForm=LM20FormAttachment' ]
                    }
                yield item
