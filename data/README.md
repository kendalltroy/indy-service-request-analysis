# Data

## Source

**Mayor's Action Center Legacy Service Cases**, published by the City of Indianapolis on its open data hub.

- Hub page: https://hub.arcgis.com/datasets/d2fda038f9c1448a985fb55647593499_3
- Service: `https://gis.indy.gov/server/rest/services/OpenData/OpenData_NonSpatial/MapServer`, layer "Mayor's Action Center Service Cases"
- Downloaded: October 9, 2026 (1,220,121 rows)

The city may update or retire this dataset, so a fresh download could differ from the one this analysis used.

## How to get the file

```bash
python src/download_data.py
```

This pages through the city's ArcGIS service 1,000 rows at a time and saves `data/raw/mac_legacy_service_cases.csv`. The file is written in the same format as the Hub's "Download CSV" button, so you can also download it by hand from the Hub page and save it under that name. If the file is already there, the script skips the download.

## Folders

| Folder | In git? | Contents |
|---|---|---|
| `raw/` | No | The downloaded CSV (about 230 MB). |
| `processed/` | No | `closed_cases.parquet` and `all_cases.parquet`, written by `src/clean.py`. |
| `sample/` | Yes | `mac_cases_sample.csv`, the first 1,000 rows of the raw file, so you can see the structure without downloading. |

## Data dictionary

| Column | Description |
|---|---|
| `OBJECTID` | Row id assigned by the ArcGIS service. Unique and increasing. |
| `CASENUMBER` | The city's case number. |
| `SOURCE_ID__C` | Id from the source system that created the case (blank for some cases). |
| `KEYWORD__C` | Broad call type, such as "Chuckhole" or "Trash". |
| `SUBCATEGORY__C` | Specific call type within the keyword, such as "Street (Chuckhole)". The analysis defines a call type as keyword + subcategory. |
| `INCIDENT_ADDRESS__C` | Street address of the reported problem. |
| `TOWNSHIP__C` | Marion County township. |
| `CITY__C` | City name, almost always Indianapolis. |
| `ZIP__C` | ZIP code of the incident address. |
| `COUNCIL_DISTRICT__C` | City-County Council district (1 to 25). |
| `CREATEDDATE` | When the case was opened, in UTC (`YYYY/MM/DD HH:MM:SS+00`). Converted to Indianapolis time in `clean.py`. |
| `LASTMODIFIEDDATE` | When the case record was last changed, in UTC. |
| `CLOSEDDATE` | When the case was closed, in UTC. Blank for open cases. |
| `STATUS` | Closed or open. Capitalization varies in the raw file, so `clean.py` lowercases it before filtering. |
| `ORIGIN` | How the case came in, such as Phone, RequestIndy Online or RequestIndy Mobile. |

### Columns added by `clean.py`

| Column | Description |
|---|---|
| `CASE_DURATION` | `CLOSEDDATE` minus `CREATEDDATE` (closed cases only). |
| `RESPONSE_DAYS` | `CASE_DURATION` in days. |
| `ZIP` | `ZIP__C` as a five-digit string, for grouping. |

## Known gaps

- From August 2022 on, cases have no subcategory or council district and use a different keyword list. The analysis keeps only cases created before August 1, 2022.
- About 12,000 cases from April and May 2019, mostly chuckholes and weeds, are missing a council district.
