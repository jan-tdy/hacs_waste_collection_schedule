import json
from datetime import datetime

import requests
from waste_collection_schedule import Collection, Icons  # type: ignore[attr-defined]
from waste_collection_schedule.exceptions import SourceArgumentNotFound

TITLE = "Bedford Borough Council"
DESCRIPTION = "Source for bedford.gov.uk services for Bedford Borough Council, UK."
URL = "https://bedford.gov.uk"
TEST_CASES = {
    "Test_001": {"uprn": "100080009302"},
    "Test_002": {"uprn": "100081207036"},
    "Test_003": {"uprn": 100080018481},
    "Test_004": {"uprn": 100080023672},
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}
ICON_MAP = {
    "BLACK BIN": Icons.GENERAL_WASTE,
    "ORANGE BIN": Icons.RECYCLING,
    "GREEN BIN": Icons.ORGANIC,
    "CADDY BIN": Icons.BIO_KITCHEN,
}


class Source:
    def __init__(self, uprn):
        self._uprn = str(uprn).zfill(12)

    def fetch(self):

        s = requests.Session()
        r = s.get(
            f"https://bbaz-as-prod-bartecapi.azurewebsites.net/api/bincollections/residential/getbyuprn/{self._uprn}",
            headers=HEADERS,
        )

        # Check if response is empty or not JSON
        if not r.text or not r.text.strip():
            raise SourceArgumentNotFound(
                f"No data returned for UPRN {self._uprn}. Please check the UPRN is correct and the API is responding."
            )

        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise SourceArgumentNotFound(
                f"API returned HTTP {r.status_code} for UPRN {self._uprn}: {r.text[:200]}"
            ) from e

        try:
            json_data = json.loads(r.text)
        except json.JSONDecodeError as e:
            raise SourceArgumentNotFound(
                f"Invalid JSON response for UPRN {self._uprn}: {r.text[:200]}"
            ) from e

        # Check if BinCollections key exists and is valid
        if "BinCollections" not in json_data:
            raise SourceArgumentNotFound(
                f"No BinCollections data found for UPRN {self._uprn}. Response keys: {list(json_data.keys())}"
            )

        bin_collections = json_data.get("BinCollections", [])
        if not bin_collections:
            return []

        entries = []

        for day in bin_collections:
            for bin in day:
                entries.append(
                    Collection(
                        date=datetime.strptime(
                            bin["JobScheduledStart"], "%Y-%m-%dT00:00:00"
                        ).date(),
                        t=bin["BinType"],
                        icon=ICON_MAP.get(bin["BinType"].upper()),
                    )
                )

        return entries
