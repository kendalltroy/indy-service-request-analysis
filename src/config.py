"""Shared settings for the Mayor's Action Center analysis.

Every threshold and path lives here so the analysis modules stay in sync and
the reasoning behind each choice is written down in one place.
"""
from pathlib import Path

import pandas as pd


# Paths (all relative to the repo root, so the project runs from any clone)
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"
FIGURES_DIR = ROOT / "figures"
RESULTS_DIR = ROOT / "results"
REPORTS_DIR = ROOT / "reports"

RAW_CSV = RAW_DIR / "mac_legacy_service_cases.csv"
CLOSED_CASES_PARQUET = PROCESSED_DIR / "closed_cases.parquet"
ALL_CASES_PARQUET = PROCESSED_DIR / "all_cases.parquet"
CLEANING_LOG_CSV = RESULTS_DIR / "cleaning_log.csv"


# Data source
# ArcGIS Hub item for "Mayor's Action Center - Legacy Service Cases". The item
# points at a MapServer; download_data.py looks up the layer id from /layers.
ARCGIS_ITEM_ID = "d2fda038f9c1448a985fb55647593499"
ARCGIS_LAYER_NAME = "Mayor's Action Center Service Cases"


# Time handling
# Timestamps are stored in UTC. Indianapolis local time is used everywhere so a
# case reported at 9pm on December 31 counts toward the year and quarter the
# resident experienced, not the next UTC day.
TIMEZONE = "America/Indiana/Indianapolis"

# The city moved to a new case system in August 2022. Cases created from that
# month on have no subcategory or council district and use a different set of
# keywords, so they cannot be compared with earlier cases. Applied to
# CREATEDDATE; cases with a missing created date are kept until the closed/open
# steps log and drop them.
CUTOFF = pd.Timestamp("2022-08-01", tz=TIMEZONE)

# Minimum case counts for ranking medians (Q1: response times)
# Keeps only call types with meaningful volume. Without a minimum, the slowest
# call types in the ranking were ones with just one or two cases. At 300, every
# ranked call type happened far more than a few times, and the cut removes only
# a small share of the data: 158 of 271 call types are dropped, but together
# they hold 1.2% of closed cases.
MIN_CALL_TYPE_CASES = 300

# At least one case per month over the roughly 7 years of data (7 years x 12
# months = 84). A ZIP code that doesn't average one case a month isn't a
# significant source of work for the 311 center, so its median isn't ranked.
# Keeps 41 of 50 ZIP codes.
MIN_ZIP_CASES = 84

# The median number of cases per ZIP + call type pair, after the August 2022
# cutoff. Pairs below it come up fewer than about 2 times a year over the ~7
# years of data, too rarely to be a concern for the city. The upper half are the
# calls the city receives often enough to plan around.
MIN_PAIR_CASES = 16
# Seasons (Q2: seasonality)
# Calendar quarters of the created date. Quarters rather than meteorological
# seasons so the seasonal index lines up with the Q1 forecast.
season_names = {1: "Jan-Mar", 2: "Apr-Jun", 3: "Jul-Sep", 4: "Oct-Dec"}
# Forecast (Q3)
# Q1 counts from these years are averaged to project Q1 2022. The data starts
# in June 2015, so 2015 contributes no Q1 and the effective window is 2016-2021.
TRAIN_YEARS = range(2015, 2022)

# The last Q1 before the cutoff, so the forecast can be checked against actuals.
FORECAST_YEAR = 2022

# Number of council districts forecast per call type. Five is a short list a
# department could act on, and with 25 districts it is a real prediction rather
# than most of the city.
TOP_DISTRICTS = 5
