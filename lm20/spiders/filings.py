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

            callback = None
            if item['formLink'] == 'LM20Form':
                #callback = self.parse_lm20_html_report
                yield item
            elif item['formLink'] == 'LM21Form':
                callback = self.parse_lm21_html_report
            else:
                raise ValueError('Invalid formLink', item['formLink'])

            if callback:
                yield Request(response.request.url,
                              cb_kwargs={'item': item},
                              callback=callback)
                                

        else:
            item['file_urls'].append(response.request.url)
            item['file_headers'][response.request.url] = response.headers
            
            yield item
        

    def parse_lm20_html_report(self, response, item):

        form_data = LM20Report.parse(response)


        return item


    def parse_lm21_html_report(self, response, item):

        form_data = LM21Report.parse(response)

        return form_data

class LM21Report:

    @classmethod
    def parse(cls, response):

        form_dict = dict(
            file_number=cls._get_i_value(response, '1. File Number: C-'),
            period_begin=cls._get_i_value(response, ' From: '),
            period_through=cls._get_i_value(response, ' Through: '),
        )

        form_dict['person filing'] = {}
        form_dict['person filing']['name and mailing address'] = cls._section_three(response)
        form_dict['person filing']['any other name or address necessary to verify report'] = cls._section_four(response)
        form_dict['signatures'] = cls._signatures(response)
        form_dict['receipts'] = cls._statement_of_receipts(response)
        form_dict['disbursements'] = cls._statement_of_disbursements(response)

        
        breakpoint()

    @classmethod
    def _statement_of_disbursements(cls, response):

        results = {}
        
        tables_xpath = ".//div[text()='Disbursements to Officers and Employees: ']/parent::div/parent::div[@class='row']/following-sibling::div[@class='row']/table[@class='addTable']"

        tables = response.xpath(tables_xpath)

        individual_disbursements = []
        fields = ('name', 'salary', 'expense', 'total')
        for row in tables[0].xpath('./tr'):
            values = row.xpath('./th//text()').getall()
            individual_disbursements.append(dict(zip(fields, values)))

        results['individual disbursements'] = individual_disbursements

        for row in tables[1].xpath('./tr'):
            index, field_name, *rest = row.xpath('./th//text()').getall()

            if rest:
                value, = rest
            else:
                value = ''

            results[field_name.strip(' :')] = value

        return results
        
        
    @classmethod
    def _statement_of_receipts(cls, response):

        results = []
        section_xpath = "//div[@class='myTable' and descendant::span[@class='i-label' and text()='Statement of Receipts']]"
        section = response.xpath(section_xpath)

        receipts = section.xpath(".//div[@class='activityTable']")

        for receipt in receipts:
            parsed_receipts = {}
            for field in ('Employer:',
                          'Trade Name:',
                          'Name:',
                          'Title:',
                          'Mailing Address:',
                          'P.O. Box., Bldg., Room No., if any:',
                          'Street:',
                          'City:',
                          'State:',
                          'ZIP Code:',
                          'Termination Date:',
                          'Amount:',
                          '\xa0 \xa0 \xa0 Non-Cash Payment:',
                          '\xa0\xa0\xa0 Type of Payment:'):
                clean_field = field.replace('\xa0', '').strip(' :')
                parsed_receipts[clean_field] = cls._get_i_value(receipt,
                                                                field)
            results.append(parsed_receipts)
                          
        return results
        

    @classmethod
    def _signatures(cls, response):

        result = {17: {}, 18: {}}
        for signature_number in result:
            section = cls._signature_section(response, signature_number)
            for field in ('SIGNED:',
                          'Title:',
                          'Date:',
                          'Telephone:'):
                result[signature_number][field] = cls._get_i_value(section,
                                                                   field)

        return result

    @classmethod
    def _signature_section(cls, response, signature_number):

        return response.xpath(f"//div[@class='myTable' and descendant::span[@class='i-label' and text()='{signature_number}.']]")[1]


    @classmethod
    def _section_three(cls, response):
        return cls._parse_section(
            response,
            section_label='3. Name and mailing address (including Zip Code):',
            field_labels=('Name:',
                          'Title:',
                          'Organization:',
                          'P.O. Box., Bldg., Room No., if any:',
                          'Street:',
                          'City:',
                          'ZIP code:')
            )

    @classmethod
    def _section_four(cls, response):
        return cls._parse_section(
            response,
            section_label='''4. Any other address where records necessary to
													verify this report are kept:''',
            field_labels=('Name:',
                          'Title:',
                          'Organization:',
                          'P.O. Box., Bldg., Room No., if any:',
                          'Street:',
                          'City:',
                          'ZIP code:')
            )
    
            
    @classmethod
    def _parse_section(cls, response, section_label, field_labels):
        section = cls._section(
            response,
            section_label
        )

        section_dict = {}
        for field in field_labels:
            section_dict[field.strip(': ')] = cls._get_i_value(
                section,
                field).strip()
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
            following_text_xpath = f".//span[@class='i-label' and normalize-space(text())='{label_text}']/following-sibling::text()[1]"
            result = tree.xpath(following_text_xpath)

            
        return result.get(default='').strip()
        
        
