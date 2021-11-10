import datetime

from itemadapter import ItemAdapter


class TimestampToDatetime:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        time_fields = ('beginDate',
                       'endDate',
                       'registerDate',
                       'receiveDate')

        filings = adapter['filings']
        for filing in filings:
            for field in time_fields:
                timestamp = filing[field]
                if timestamp:
                    filing[field] = datetime.datetime.fromtimestamp(timestamp//1000)

        return item

class ReportLink:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        filings = adapter['filings']
        for filing in filings:
            report_id = filing.get('rptId')
            report_type = filing.get('formLink')

            if report_id and report_type:
                if 'file_urls' not in item:
                    item['file_urls'] = []

                report_url = f'https://olmsapps.dol.gov/query/orgReport.do?rptId={report_id}&rptForm={report_type}'

                filing['report_url'] = report_url
                item['file_urls'].append(report_url)

        return item
                                  
