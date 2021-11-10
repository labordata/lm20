import datetime

from itemadapter import ItemAdapter


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
                                  
