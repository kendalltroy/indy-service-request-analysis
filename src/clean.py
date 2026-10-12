"""Load the raw Mayor's Action Center export and build the two cleaned tables
every analysis starts from:

  data/processed/closed_cases.parquet  closed cases with a response time
  data/processed/all_cases.parquet     open + closed cases, for volume and seasonality

Every filtering step is printed and recorded in results/cleaning_log.csv so the
row counts behind each analysis can be traced back to the raw file.
"""
import pandas as pd

from config import (
    ALL_CASES_PARQUET, CLEANING_LOG_CSV, CLOSED_CASES_PARQUET, CUTOFF, RAW_CSV, TIMEZONE,
)

DATE_COLS = ["CREATEDDATE", "LASTMODIFIEDDATE", "CLOSEDDATE"]
CALL_TYPE_COLS = ["KEYWORD__C", "SUBCATEGORY__C"]
DISTRICT_CASE_COLS = ["CREATEDDATE", "KEYWORD__C", "SUBCATEGORY__C", "COUNCIL_DISTRICT__C"]

cleaning_log = []


def log_dropped(dropped, total, reason, step=None):
    """Print how many rows a step drops and what share that is.

    Steps given a name are also kept for the cleaning log, so silent row loss
    (for example from groupby skipping missing keys) is always visible.
    """
    print(f"Dropped {dropped:,} of {total:,} ({dropped / total:.2%}) {reason}")
    if step is not None:
        cleaning_log.append({
            "step": step, "rows_before": total, "rows_dropped": int(dropped),
            "rows_after": total - int(dropped), "pct_dropped": round(dropped / total * 100, 4), "reason": reason,
        })


def clean_call_type_text(series):
    """The same call type is typed with stray spaces and mixed case in
    different years, so normalize before grouping."""
    return series.str.strip().str.replace(r"\s+", " ", regex=True).str.lower()


def load_raw():
    serv_df = pd.read_csv(RAW_CSV, encoding="utf-8-sig")
    serv_df.head()
    print(serv_df.head())
    print(serv_df.describe())
    cleaning_log.append({"step": "raw", "rows_before": len(serv_df), "rows_dropped": 0, "rows_after": len(serv_df),
                         "pct_dropped": 0.0, "reason": f"rows in {RAW_CSV.name}"})
    return serv_df


def parse_dates(serv_df):
    """Parse the UTC timestamps and convert to Indianapolis time, reporting any
    values that are missing or fail to parse rather than silently coercing them."""
    for col in DATE_COLS:
        raw = serv_df[col]
        missing = raw.isna().sum()
        empty = (raw.astype("string").str.strip() == "").sum()
        serv_df[col] = pd.to_datetime(raw, format="%Y/%m/%d %H:%M:%S%z", errors="coerce").dt.tz_convert(TIMEZONE)
        unparseable = serv_df[col].isna().sum() - missing - empty
        print(f"{col}: missing={missing}, empty={empty}, unparseable={unparseable}, dtype={serv_df[col].dtype}")
    return serv_df


def apply_cutoff(serv_df):
    """Drop cases created after the August 2022 system change (see config.CUTOFF).

    Missing created dates compare as False here, so those rows survive and are
    logged by the closed and open steps instead.
    """
    after_cutoff = serv_df["CREATEDDATE"] >= CUTOFF
    print()
    log_dropped(after_cutoff.sum(), len(serv_df), f"cases created on or after {CUTOFF:%B %d, %Y}; excluded from every analysis",
                step="cutoff")
    return serv_df[~after_cutoff].copy()


def build_closed_cases(serv_df, status):
    """Closed cases with a CASE_DURATION. A case needs both dates for a response
    time, so rows missing either one are dropped."""
    closed_df = serv_df[status == "closed"].copy()
    cleaning_log.append({"step": "closed status", "rows_before": len(serv_df), "rows_dropped": len(serv_df) - len(closed_df),
                         "rows_after": len(closed_df), "pct_dropped": round((len(serv_df) - len(closed_df)) / len(serv_df) * 100, 4),
                         "reason": "keep STATUS == closed for the closed-case table"})
    missing_dates = closed_df["CREATEDDATE"].isna() | closed_df["CLOSEDDATE"].isna()
    print()
    log_dropped(missing_dates.sum(), len(closed_df), "closed cases missing CREATEDDATE or CLOSEDDATE; excluded from every closed-case analysis",
                step="closed missing dates")

    closed_df = closed_df[~missing_dates].copy()
    closed_df.insert(
        closed_df.columns.get_loc("CLOSEDDATE") + 1,
        "CASE_DURATION",
        closed_df["CLOSEDDATE"] - closed_df["CREATEDDATE"],
    )
    print(f"Closed cases remaining: {len(closed_df)}")
    print(closed_df[["CREATEDDATE", "CLOSEDDATE", "CASE_DURATION"]].head())
    print(closed_df["CASE_DURATION"].describe())
    # A negative duration would mean a case closed before it opened, i.e. bad timestamps.
    print(f"Negative durations: {(closed_df['CASE_DURATION'] < pd.Timedelta(0)).sum()}")

    for col in CALL_TYPE_COLS:
        before = closed_df[col].nunique()
        closed_df[col] = clean_call_type_text(closed_df[col])
        print(f"\n{col}: {before} unique values before cleaning, {closed_df[col].nunique()} after, {closed_df[col].isna().sum()} missing")

    closed_df["RESPONSE_DAYS"] = closed_df["CASE_DURATION"].dt.total_seconds() / 86400
    # ZIP__C is read as a float (46220.0); go through Int64 so missing ZIPs stay missing instead of becoming "nan".
    closed_df["ZIP"] = closed_df["ZIP__C"].astype("Int64").astype("string")
    return closed_df


def build_open_cases(serv_df, status):
    """Open cases still count toward call volume and seasonality, but only if
    we know when they were created."""
    open_cases = serv_df[status == "open"].copy()
    for col in CALL_TYPE_COLS:
        open_cases[col] = clean_call_type_text(open_cases[col])
    missing_open_created = open_cases["CREATEDDATE"].isna()
    log_dropped(missing_open_created.sum(), len(open_cases), "open cases missing CREATEDDATE; excluded from every open + closed analysis",
                step="open missing created date")
    return open_cases[~missing_open_created]


def load_closed_cases():
    return pd.read_parquet(CLOSED_CASES_PARQUET)


def load_all_cases():
    return pd.read_parquet(ALL_CASES_PARQUET)


def missing_call_type_or_district(cases):
    """Rows missing a created date, call type or council district (null or blank)."""
    blank = cases[DISTRICT_CASE_COLS].isna().any(axis=1)
    for col in DISTRICT_CASE_COLS[1:]:
        blank |= cases[col].astype("string").str.strip() == ""
    return blank


def cases_with_district(all_cases_df, log=True):
    """Open + closed cases that can be placed on the council district map by
    call type. Used by the forecast and the district profile.

    Blank strings are treated as missing because a blank district or call type
    cannot be assigned any more than a null one can.
    """
    district_cases = all_cases_df[DISTRICT_CASE_COLS].copy()
    blank = missing_call_type_or_district(district_cases)
    district_cases = district_cases[~blank].copy()
    # Stored as floats (11.0) because of the missing values; whole-number districts read better in tables.
    district_cases["COUNCIL_DISTRICT__C"] = district_cases["COUNCIL_DISTRICT__C"].astype(float).astype("Int64")
    if log:
        print()
        log_dropped(blank.sum(), len(all_cases_df),
                    f"open + closed cases with a missing or blank {', '.join(DISTRICT_CASE_COLS)}; excluded from the forecast, storm test and district share tables")
        print(f"Open + closed cases left for forecasting: {len(district_cases)}")
    return district_cases


def main():
    serv_df = parse_dates(load_raw())
    serv_df = apply_cutoff(serv_df)
    status = serv_df["STATUS"].str.strip().str.lower()

    closed_df = build_closed_cases(serv_df, status)
    open_cases = build_open_cases(serv_df, status)
    all_cases_df = pd.concat([closed_df, open_cases], ignore_index=True)
    cleaning_log.append({"step": "open + closed", "rows_before": len(closed_df) + len(open_cases), "rows_dropped": 0,
                         "rows_after": len(all_cases_df), "pct_dropped": 0.0, "reason": "closed + open cases combined"})

    # The district filter is applied later by the forecast and district modules; record it here so the log is complete.
    blank = missing_call_type_or_district(all_cases_df)
    cleaning_log.append({"step": "missing call type or district", "rows_before": len(all_cases_df), "rows_dropped": int(blank.sum()),
                         "rows_after": len(all_cases_df) - int(blank.sum()), "pct_dropped": round(blank.sum() / len(all_cases_df) * 100, 4),
                         "reason": "forecast and district tables need a created date, call type and council district"})

    CLOSED_CASES_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    closed_df.to_parquet(CLOSED_CASES_PARQUET)
    all_cases_df.to_parquet(ALL_CASES_PARQUET)
    CLEANING_LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cleaning_log).to_csv(CLEANING_LOG_CSV, index=False)


if __name__ == "__main__":
    main()
