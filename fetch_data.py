"""
Download every drug recall from the openFDA drug enforcement API.

Results are saved one year per file in data/raw/ so the rest of the project
runs offline. Years that are already saved get skipped, so if the API errors
out partway through you can just run it again.

API docs: https://open.fda.gov/apis/drug/enforcement/
Paging:   https://open.fda.gov/apis/paging/ (max 1,000 records per request)
Limits:   240 requests/minute and 1,000/day without an API key

Usage: python fetch_data.py
"""

import gzip
import json
import time
from datetime import date
from pathlib import Path

import requests

URL = "https://api.fda.gov/drug/enforcement.json"
RAW_DIR = Path("data/raw")
FIRST_YEAR = 2012  # earliest report_date in the dataset


def get(url, params, tries=8):
    """GET one page, waiting and retrying if the server is busy or errors."""
    for attempt in range(1, tries + 1):
        resp = requests.get(url, params=params, timeout=60)
        if resp.status_code in (200, 404):  # 404 just means no results
            return resp
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = 5 * attempt
            print(f"  got {resp.status_code}, retrying in {wait}s")
            time.sleep(wait)
        else:
            break
    resp.raise_for_status()


def fetch_year(year):
    """Get all recalls reported in one year, following the API's next-page links."""
    records = []
    url = URL
    params = {
        "search": f"report_date:[{year}0101 TO {year}1231]",
        "limit": 1000,
        "sort": "report_date:asc",
    }
    meta = {}

    while url:
        resp = get(url, params)
        if resp.status_code == 404:
            break
        body = resp.json()
        meta = body["meta"]
        records += body["results"]
        print(f"  {year}: {len(records)} / {meta['results']['total']}")

        # The next page's URL comes back in the Link header (search_after paging).
        # No Link header means this was the last page.
        next_page = resp.links.get("next")
        url = next_page["url"] if next_page else None
        params = None
        time.sleep(1)

    if meta and len(records) != meta["results"]["total"]:
        raise RuntimeError(f"{year}: expected {meta['results']['total']} records, got {len(records)}")
    return records, meta


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for year in range(FIRST_YEAR, date.today().year + 1):
        path = RAW_DIR / f"enforcement_{year}.json.gz"
        if path.exists():
            print(f"{year}: already saved")
            continue

        records, meta = fetch_year(year)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump({
                "pulled_on": date.today().isoformat(),
                "api_last_updated": meta.get("last_updated"),
                "record_count": len(records),
                "results": records,
            }, f)
        print(f"{year}: saved {len(records)} records")


if __name__ == "__main__":
    main()
