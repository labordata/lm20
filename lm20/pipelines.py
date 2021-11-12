import datetime

import dateutil.parser

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem


class TimestampToDatetime:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        time_fields = ('beginDate',
                       'endDate',
                       'registerDate',
                       'receiveDate')

        for field in time_fields:
            timestamp = adapter[field]
            if timestamp:
                adapter[field] = datetime.datetime.fromtimestamp(timestamp//1000).date()

        return item

class ReportLink:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        report_id = adapter.get('rptId')
        report_type = adapter.get('formLink')

        if report_id and report_type:
            if 'file_urls' not in item:
                item['file_urls'] = []

            report_url = f'https://olmsapps.dol.gov/query/orgReport.do?rptId={report_id}&rptForm={report_type}'

            adapter['file_urls'] = [ report_url ]

        return item
                                  
class Nullify:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        fields = ('termDate', 'empTrdName', 'empLabOrg', 'state', 'city', 'amount')
        null_synonyms = {'Not Available',
                         'Ongoing',
                         'Continuing',
                         'Not requred to subm',
                         'ongoing',
                         '000000',
                         '00/00/0000',
                         'MULTIPLE',
                         'na',
                         'NOT REQUIRED TO COMPLETE',
                         'NOT REQUIRED TO REPORT',
                         'NOT REQUIRED TO COMPLETE/SPECIAL ENFORCEMENT POLIC',
                         'NOT SHOWN',
                         'NONE',
                         'SEE ATTACHED LIST',
                         'MULTIPLE NAMES',
                         'MULTIPLE COMPANIES',
                         'MULT',
                         'NO CITY',
                         'No City',
                         '0',
                         '00',
                         '-1',
                         'ZZ',
                         }

        nulls = 0
        for field in fields:
            value = adapter[field]
            if value and (value in null_synonyms or not value.strip()):
                adapter[field] = None

            if not adapter[field]:
                nulls += 1

        if len(fields) == nulls:
            raise DropItem

        return item
        

class TitleCase:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        try:
            adapter['city'] = adapter['city'].title()
        except AttributeError:
            pass

        return item


class StandardDate:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        time_str = adapter['termDate']
        if time_str:
            adapter['termDate'] = dateutil.parser.parse(time_str).date()

        return item
