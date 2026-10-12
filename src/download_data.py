"""Download the Mayor's Action Center legacy service cases into data/raw/.

Source: https://hub.arcgis.com/datasets/d2fda038f9c1448a985fb55647593499_3

The Hub item points at an ArcGIS MapServer that returns at most 1,000 records
per request, so the table (about 1.2 million rows) is paged with resultOffset /
resultRecordCount. The output matches the Hub's CSV export (column order,
date format, UTF-8 with BOM) so clean.py reads either one.

Usage:
    python src/download_data.py            # skips the download if the file exists
    python src/download_data.py --output PATH
"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path

import requests

from config import ARCGIS_ITEM_ID, ARCGIS_LAYER_NAME, RAW_CSV

ITEM_URL = f"https://www.arcgis.com/sharing/rest/content/items/{ARCGIS_ITEM_ID}"
DATE_FIELDS = {"CREATEDDATE", "LASTMODIFIEDDATE", "CLOSEDDATE"}
# The service returns ISO timestamps ("2022-01-31T15:25:28.000Z"); the Hub CSV
# writes "2022/01/31 15:25:28+00", which is the format clean.py parses.
ISO_UTC = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?Z$")
MAX_PAGE_SIZE = 1000
RETRIES = 5


def get_json(url, **params):
    """GET with retries. ArcGIS reports errors inside a 200 response, so check
    the body as well as the status code."""
    params.setdefault("f", "json")
    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            body = response.json()
            if "error" in body:
                raise RuntimeError(body["error"])
            return body
        except (requests.RequestException, RuntimeError, ValueError) as error:
            if attempt == RETRIES:
                raise
            wait = 2 ** attempt
            print(f"  request failed ({error}); retrying in {wait}s")
            time.sleep(wait)


def find_layer():
    """Resolve the service URL from the Hub item, then pick the layer by name
    from /layers instead of trusting a hardcoded id that could be renumbered."""
    item = get_json(ITEM_URL)
    service_url = item["url"].rstrip("/")
    if service_url.rsplit("/", 1)[-1].isdigit():
        service_url = service_url.rsplit("/", 1)[0]

    service = get_json(f"{service_url}/layers")
    candidates = service.get("layers", []) + service.get("tables", [])
    matches = [layer for layer in candidates if layer["name"] == ARCGIS_LAYER_NAME]
    if len(matches) != 1:
        names = ", ".join(f"{layer['id']}: {layer['name']}" for layer in candidates)
        sys.exit(f"Expected one layer named {ARCGIS_LAYER_NAME!r} at {service_url}, found {len(matches)}. Layers: {names}")
    layer = matches[0]
    page_size = min(layer.get("maxRecordCount") or MAX_PAGE_SIZE, MAX_PAGE_SIZE)
    print(f"Found layer {layer['id']} ({layer['name']}) at {service_url}; page size {page_size}")
    return f"{service_url}/{layer['id']}", [field["name"] for field in layer["fields"]], page_size


def format_value(field, value):
    if value is None:
        return ""
    if field in DATE_FIELDS:
        match = ISO_UTC.match(value)
        if match:
            year, month, day, clock = match.groups()
            return f"{year}/{month}/{day} {clock}+00"
    return value


def download(output):
    layer_url, fields, page_size = find_layer()
    total = get_json(f"{layer_url}/query", where="1=1", returnCountOnly="true")["count"]
    print(f"Downloading {total:,} rows to {output}")

    # Write to a temporary file and rename at the end, so an interrupted run
    # never leaves a partial file that a later run would mistake for complete.
    partial = output.with_suffix(output.suffix + ".part")
    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    started = time.time()
    with open(partial, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(fields)
        while written < total:
            # Ordering by OBJECTID keeps pages stable and matches the Hub export's row order.
            page = get_json(
                f"{layer_url}/query", where="1=1", outFields=",".join(fields), orderByFields="OBJECTID ASC",
                resultOffset=written, resultRecordCount=page_size, returnGeometry="false",
            )
            rows = [feature["attributes"] for feature in page["features"]]
            if not rows:
                break
            writer.writerows([format_value(field, row.get(field)) for field in fields] for row in rows)
            written += len(rows)
            if written // page_size % 50 == 0 or written >= total:
                rate = written / (time.time() - started)
                print(f"  {written:,} / {total:,} rows ({written / total:.0%}), {rate:,.0f} rows/s", flush=True)

    if written != total:
        sys.exit(f"Downloaded {written:,} rows but the service reports {total:,}; leaving {partial} for inspection.")
    partial.replace(output)
    print(f"Done: {written:,} rows saved to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, default=RAW_CSV, help=f"where to save the CSV (default: {RAW_CSV})")
    output = parser.parse_args().output
    if output.exists():
        print(f"{output} already exists; skipping download. Delete it to download again.")
        return
    download(output)


if __name__ == "__main__":
    main()
