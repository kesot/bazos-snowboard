"""Configuration and URL helpers for the Bazos snowboard scraper."""

from urllib.parse import urlencode, urljoin

DOMAIN = "sport.bazos.cz"
CATEGORY = "snowboard"
BASE_URL = f"https://{DOMAIN}"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130 Safari/537.36"
)

DEFAULT_THREADS = 8
DEFAULT_CACHE_DAYS = 7
DEFAULT_DB_PATH = "bazos_search.db"


def build_search_query(query: str = "", location: str = "", radius: int = 25,
                       price_from: str = "", price_to: str = "") -> str:
    """Build the query string Bazos uses for a category search.

    location is a Czech postal code (e.g. 11000 for Praha 1); radius is in km.
    """
    params = {
        "hledat": query,
        "hlokalita": location,
        "humkreis": radius,
        "cenaod": price_from,
        "cenado": price_to,
        "order": "",
    }
    return "?" + urlencode(params)


def first_page_url(search_url: str) -> str:
    """Turn a query string (or a full Bazos URL) into the first results page URL."""
    if search_url.startswith("http://") or search_url.startswith("https://"):
        return search_url
    return f"{BASE_URL}/{CATEGORY}/{search_url.lstrip('/')}"


def absolute_url(relative_url: str) -> str:
    return urljoin(BASE_URL + "/", relative_url)
