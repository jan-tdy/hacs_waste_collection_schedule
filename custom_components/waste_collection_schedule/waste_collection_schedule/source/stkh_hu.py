import logging
from datetime import datetime
from io import BytesIO

from curl_cffi import requests
from pypdf import PdfReader
from waste_collection_schedule import Collection, Icons
from waste_collection_schedule.exceptions import (
    SourceArgumentNotFound,
    SourceArgumentRequired,
)

_LOGGER = logging.getLogger(__name__)

TITLE = "STKH"
DESCRIPTION = "Source for STKH waste collection schedules (Hungary)"
URL = "https://stkh.hu"
COUNTRY = "hu"

TEST_CASES = {
    "Újkér": {"settlement": "Újkér", "postcode": "9472"},
    "Und": {"settlement": "Und", "postcode": "9464"},
}

ICON_MAP = {
    "Kevert hulladék": Icons.GENERAL_WASTE,
    "Szilárdhulladék": Icons.GENERAL_WASTE,
    "Szelektív": Icons.RECYCLING,
    "Biohulladék": Icons.ORGANIC,
    "Bio": Icons.ORGANIC,
    "Papír": Icons.PAPER,
    "Üveg": Icons.GLASS,
    "Fém": Icons.METAL,
    "Műanyag": Icons.RECYCLING,
}

PARAM_DESCRIPTIONS = {
    "en": {
        "settlement": "Settlement name (e.g., Újkér)",
        "postcode": "Postcode (e.g., 9472)",
    },
    "de": {
        "settlement": "Gemeindename (z.B. Újkér)",
        "postcode": "Postleitzahl (z.B. 9472)",
    },
    "it": {
        "settlement": "Nome della comunità (ad es. Újkér)",
        "postcode": "Codice postale (ad es. 9472)",
    },
    "fr": {
        "settlement": "Nom de la localité (ex. Újkér)",
        "postcode": "Code postal (ex. 9472)",
    },
}

PARAM_TRANSLATIONS = {
    "en": {
        "settlement": "Settlement",
        "postcode": "Postcode",
    },
    "de": {
        "settlement": "Gemeinde",
        "postcode": "Postleitzahl",
    },
    "it": {
        "settlement": "Comunità",
        "postcode": "Codice postale",
    },
    "fr": {
        "settlement": "Localité",
        "postcode": "Code postal",
    },
}

SETTLEMENT_URLS = {
    ("Újkér", "9472"): "https://stkh.hu/wp-content/uploads/2026/01/9472_Ujker_Hulladeknaptar2026.pdf",
    ("Und", "9464"): "https://stkh.hu/wp-content/uploads/2026/01/9464_Und_Hulladeknaptar2026.pdf",
    ("Pereszteg", "9484"): "https://stkh.hu/wp-content/uploads/2026/01/9484_Pereszteg_Hulladeknaptar2026.pdf",
    ("Fertőd", "9431"): "https://stkh.hu/wp-content/uploads/2026/01/9431_Fertod_Hulladeknaptar2026.pdf",
}


def fetch_pdf(settlement: str, postcode: str) -> BytesIO:
    """Download the schedule PDF for a specific settlement."""
    key = (settlement.strip(), postcode.strip())

    if key not in SETTLEMENT_URLS:
        _LOGGER.error("Settlement '%s' with postcode '%s' not found.", settlement, postcode)
        raise SourceArgumentNotFound("settlement", f"{settlement} ({postcode})")

    pdf_url = SETTLEMENT_URLS[key]
    _LOGGER.debug("Downloading PDF from %s", pdf_url)

    session = requests.Session(impersonate="chrome124")
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/129.0.0.0 Safari/537.36"
            ),
            "Accept": "application/pdf,text/html,application/xhtml+xml",
            "Accept-Language": "hu-HU,hu;q=0.9",
            "Referer": "https://stkh.hu/",
        }
    )

    response = session.get(pdf_url, timeout=30)
    response.raise_for_status()

    if response.headers.get("content-type", "").startswith("application/pdf") or response.content[:4] == b"%PDF":
        return BytesIO(response.content)

    _LOGGER.error("Failed to retrieve PDF: received %s instead", response.headers.get("content-type"))
    raise Exception(f"Could not download PDF from {pdf_url}")


def extract_text_from_pdf(pdf_file: BytesIO) -> str:
    """Extract text from the PDF."""
    _LOGGER.debug("Extracting text from PDF")
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()


def parse_schedule(text: str) -> list[dict]:
    """Parse STKH matrix-style PDF schedule (waste types × months × days)."""
    _LOGGER.debug("Parsing schedule from PDF text")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    schedule = []

    month_map = {
        "Január": 1,
        "Február": 2,
        "Március": 3,
        "Április": 4,
        "Május": 5,
        "Június": 6,
        "Július": 7,
        "Augusztus": 8,
        "Szeptember": 9,
        "Október": 10,
        "November": 11,
        "December": 12,
    }

    waste_types = []
    current_year = datetime.now().year
    month_days_map = {}

    i = 0
    while i < len(lines):
        line = lines[i]

        if any(month in line for month in month_map):
            if waste_types:
                for waste_type in waste_types:
                    numbers = []
                    j = i + 1
                    while j < len(lines) and lines[j] and not any(m in lines[j] for m in month_map):
                        try:
                            num = int(lines[j].split()[0])
                            numbers.append(num)
                            j += 1
                        except (ValueError, IndexError):
                            j += 1

                    for num in numbers:
                        month_match = next((m for m in month_map if m in line), None)
                        if month_match:
                            month = month_map[month_match]
                            try:
                                date = datetime(current_year, month, num).date()
                                schedule.append({"date": date, "waste_type": waste_type})
                            except ValueError:
                                pass

        else:
            for waste_type, icon in ICON_MAP.items():
                if waste_type in line:
                    waste_types.append(waste_type)
                    break

        i += 1

    return schedule


class Source:
    def __init__(self, settlement: str, postcode: str):
        if not settlement:
            raise SourceArgumentRequired("settlement", "Settlement name is required")
        if not postcode:
            raise SourceArgumentRequired("postcode", "Postcode is required")

        self.settlement = settlement.strip()
        self.postcode = postcode.strip()

    def fetch(self) -> list[Collection]:
        _LOGGER.debug(
            "Fetching schedule for %s (%s)",
            self.settlement,
            self.postcode,
        )

        pdf_file = fetch_pdf(self.settlement, self.postcode)
        pdf_text = extract_text_from_pdf(pdf_file)
        schedule = parse_schedule(pdf_text)

        if not schedule:
            _LOGGER.warning("No schedule data found for %s", self.settlement)

        return [
            Collection(
                date=item["date"],
                t=item["waste_type"],
                icon=ICON_MAP.get(item["waste_type"]),
            )
            for item in schedule
        ]
