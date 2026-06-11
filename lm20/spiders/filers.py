from scrapy import Spider

from olms.http import form_request


class LM20Filers(Spider):
    name = "filers"

    async def start(self):
        yield form_request(
            "https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet",
            formdata={"clearCache": "F", "page": "1"},
            cb_kwargs={"page": 1},
            callback=self.parse,
        )

    def parse(self, response, page):
        """
        @url https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet
        @filers_form
        @cb_kwargs {"page": 0}
        @returns items 500
        @returns requests 1 1
        """
        filers = response.json()["filerList"]
        self.logger.info(
            f"Page {page}: got {len(filers)} filers (status {response.status})"
        )
        yield from filers

        if len(filers) == 500:
            page += 1
            yield form_request(
                "https://olmsapps.dol.gov/olpdr/GetLM2021FilerListServlet",
                formdata={"clearCache": "F", "page": str(page)},
                cb_kwargs={"page": page},
                callback=self.parse,
            )
