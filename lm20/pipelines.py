import datetime
from email.message import Message
import hashlib
import mimetypes
import os
import re

import dateutil.parser

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from scrapy.pipelines.files import FilesPipeline
from scrapy.utils.python import to_bytes
from scrapy.http import Request


class TimestampToDatetime:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        time_fields = ("beginDate", "endDate", "registerDate", "receiveDate")

        for field in time_fields:
            timestamp = adapter[field]
            if timestamp:
                adapter[field] = datetime.datetime.fromtimestamp(
                    timestamp // 1000
                ).date()

        return item


class ReportLink:
    async def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        report_id = adapter.get("rptId")
        report_type = adapter.get("formLink")

        if report_id and report_type:
            if "file_urls" not in item:
                item["file_urls"] = []

            report_url = f"https://olmsapps.dol.gov/query/orgReport.do?rptId={report_id}&rptForm={report_type}"

            adapter["file_urls"] = [report_url]

            request = Request(report_url, method="HEAD")
            response = await spider.crawler.engine.download(request)

            adapter["file_headers"] = {request.url: response.headers}

        return item


class AttachmentHeaders:
    async def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        adapter["file_headers"] = {}
        for file_url in adapter["file_urls"]:

            request = Request(file_url, method="HEAD")
            response = await spider.crawler.engine.download(request)

            adapter["file_headers"][file_url] = response.headers

        return item


class Nullify:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        fields = ("termDate", "empTrdName", "empLabOrg", "state", "city", "amount")
        null_synonyms = {
            "Not Available",
            "Ongoing",
            "Continuing",
            "Not requred to subm",
            "ongoing",
            "000000",
            "00/00/0000",
            "MULTIPLE",
            "na",
            "NOT REQUIRED TO COMPLETE",
            "NOT REQUIRED TO REPORT",
            "NOT REQUIRED TO COMPLETE/SPECIAL ENFORCEMENT POLIC",
            "NOT SHOWN",
            "NONE",
            "SEE ATTACHED LIST",
            "MULTIPLE NAMES",
            "MULTIPLE COMPANIES",
            "MULT",
            "NO CITY",
            "No City",
            "0",
            "00",
            "-1",
            "ZZ",
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
            adapter["city"] = adapter["city"].title()
        except AttributeError:
            pass

        return item


class StandardDate:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        time_str = adapter["termDate"]
        if time_str:
            try:
                adapter["termDate"] = dateutil.parser.parse(time_str).date()
            except dateutil.parser._parser.ParserError:
                try:
                    if re.search('[a-zA-Z]', time_str):
                        # Contains letters, but can't be parsed. ex: "on-going"
                        adapter["termDate"] = time_str.lower()
                    elif time_str.isnumeric():
                        # Unformatted date. ex: MMDDYYYY
                        formatted_str = f"{time_str[:2]}/{time_str[2:4]}/{time_str[4:]}"
                        adapter["termDate"] = dateutil.parser.parse(formatted_str).date()
                    else:
                        # Incorrectly formatted date. ex: MMDD/YY
                        formatted_str = f"{time_str[:2]}/{time_str[2:]}"
                        if formatted_str.count('/') == 2:
                            adapter["termDate"] = dateutil.parser.parse(formatted_str).date()
                        else:
                            raise dateutil.parser._parser.ParserError
                except dateutil.parser._parser.ParserError:
                    print("Could not parse date from string:", time_str)
                    pass

        return item


class HeaderMimetypePipeline(FilesPipeline):
    def file_path(self, request, response=None, info=None, *, item=None):

        if response is None:
            headers = item["file_headers"][request.url]
        else:
            headers = response.headers

        media_guid = hashlib.sha1(to_bytes(request.url)).hexdigest()

        content_disposition = headers.get("Content-Disposition")
        content_type = headers.get("Content-Type")

        media_ext = self.get_media_ext(content_disposition, content_type)

        return f"full/{media_guid}{media_ext}"

    def get_media_ext(self, raw_content_disposition, raw_content_type):
        if raw_content_disposition:
            # Disposition and type occassionally come in as bytes objects
            try:
                content_disposition = raw_content_disposition.decode()
            except AttributeError:
                content_disposition = raw_content_disposition

            try:
                content_type = raw_content_type.decode()
            except AttributeError:
                content_type = raw_content_type

            m = Message()
            m["content-disposition"] = content_disposition
            filename = m.get_filename()

            media_ext = os.path.splitext(filename)[1]

            # Handles empty and wild extensions by trying to guess the
            # mime type then extension or default to empty string otherwise
            if media_ext not in mimetypes.types_map:
                media_ext = ""
                media_type = mimetypes.guess_type(filename)[0]

                if media_type:
                    media_ext = mimetypes.guess_extension(media_type)

                elif content_type:
                    media_ext = mimetypes.guess_extension(
                        content_type.split(";")[0]
                    )
        else:
            media_ext = ""

        if not media_ext or media_ext in {"", ".bin"}:
            media_ext = ".pdf"

        return media_ext
