# bazos-snowboard

Command-line search for used snowboards on [sport.bazos.cz](https://sport.bazos.cz/snowboard/).

You give it a Bazoš search (keyword, location, price range) plus a **regex**. It goes
through every results page and prints only the ads whose title or description matches
the regex. The regex is checked against the full ad text, not only the short summary
in the results list. Typical use: find boards of a specific length, which Bazoš itself
can't filter on.

Full ad texts are cached in a local SQLite file (`bazos_search.db`). Repeated searches
only download new ads, plus any cached ad older than 7 days.

## Setup

Requires Python 3.9+.

```bash
git clone <this repo>
cd bazos-snowboard
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# 160–175 cm boards, 1 000–6 000 Kč, within 50 km of Praha 1 (postal code 11000)
python scraper.py "(?<!\d)(16[0-9]|17[0-5])(?!\d)" --location 11000 --radius 50 --price-from 1000 --price-to 6000

# every ad in the snowboard category for the keyword "burton", saved to CSV
python scraper.py --query burton --csv burton.csv

# paste a query string copied from the Bazoš results URL (everything from "?")
python scraper.py "15[5-9]" --search-url "?hledat=snowboard&hlokalita=&humkreis=25&cenaod=&cenado=5000&order="
```

Output:

```
  1.   3 000 Kč | Praha 6 162 00       | 24.11.2026 | Freeride Snowboard Gravity Squadra 162 cm
     https://sport.bazos.cz/inzerat/.../freeride-snowboard-gravity-squadra-162-cm.php
```

| Option | Meaning |
|---|---|
| `pattern` | Regex matched case-insensitively against title + description. Default `.*` (everything). |
| `--query` | Bazoš keyword search. Default `snowboard`. |
| `--location`, `--radius` | Czech postal code (PSČ) and radius in km. |
| `--price-from`, `--price-to` | Price range in Kč. |
| `--search-url` | Raw Bazoš query string or full results URL. Overrides the filters above. |
| `--csv FILE` | Also write the matches to a CSV file (opens in Excel). |
| `--max-pages N` | Stop after N result pages (40 ads per page). |
| `--threads N` | Number of ads downloaded in parallel. Default 8; keep it modest to avoid HTTP 429. |
| `--cache-days N` | Re-download cached ads older than N days. Default 7. |
| `--stats`, `-v` | Show timing and cache statistics / log progress. |

### Regex tips

- `(?<!\d)16[0-9](?!\d)` matches 160–169 but not phone numbers or prices that
  contain those digits.
- Ads for jackets, boots etc. often mention a person's height ("na výšku 170").
  Add `cm` to the pattern, as in `(?<!\d)(16[0-9]|17[0-5]) ?cm`, if that
  catches too much.
- Wide boards: `16[0-9] ?w\b|wide`.

## Tests

```bash
python -m unittest discover tests
```

The tests run offline against a small synthetic HTML page.

## Notes

- This tool scrapes public Bazoš pages. Be reasonable with `--threads` and how often
  you run it.
- If Bazoš changes its HTML, the selectors live in `parse_list_page` in `searcher.py`
  and `fetch_ad_text` in `client.py`.
