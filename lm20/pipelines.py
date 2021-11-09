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
