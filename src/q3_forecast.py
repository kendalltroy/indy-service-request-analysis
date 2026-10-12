"""Q3: Can a simple historical average tell the city where Q1 demand will land?

The forecast projects Q1 2022 cases for each call type + council district as
the average Q1 count over the training years, then checks it two ways:
  - precision: did the forecast pick the right top districts?
  - count error: how far off were the projected counts?
A deliberately simple baseline: if it already picks the right districts, a
department could use it for staffing without a modeling pipeline.
"""
import pandas as pd

from clean import cases_with_district, load_all_cases
from config import FORECAST_YEAR, TOP_DISTRICTS, TRAIN_YEARS
from labels import call_type_label
from plotting import save_result, save_table_png

GROUP_COLS = ["KEYWORD__C", "SUBCATEGORY__C", "COUNCIL_DISTRICT__C"]


def q1_cases():
    """Q1 (Jan-Mar) cases with a district and call type, tagged by local year."""
    forecast_df = cases_with_district(load_all_cases())
    local_created = forecast_df["CREATEDDATE"]
    forecast_df["YEAR"] = local_created.dt.year
    forecast_df["QUARTER"] = local_created.dt.quarter
    return forecast_df[forecast_df["QUARTER"] == 1]


def top_districts(counts, call_type, value_name):
    """The TOP_DISTRICTS busiest districts for one call type."""
    districts = counts.loc[call_type].sort_values(ascending=False).head(TOP_DISTRICTS)
    return districts.rename(value_name).rename_axis("COUNCIL_DISTRICT__C").reset_index()


def build_forecast(q1_df):
    """Average Q1 count per call type + district across the training years.

    Years with no cases for a pair are filled with 0 before averaging, so a pair
    that only appeared once is not projected as if it happened every year.
    """
    train_q1 = q1_df[q1_df["YEAR"].isin(TRAIN_YEARS)]
    train_years = sorted(int(y) for y in train_q1["YEAR"].unique())
    print(f"Q1s with data in {TRAIN_YEARS[0]}-{TRAIN_YEARS[-1]}: {train_years} (the data starts in June 2015, so there is no Q1 2015)")

    yearly_q1_counts = train_q1.groupby(GROUP_COLS + ["YEAR"]).size().unstack("YEAR", fill_value=0)
    forecast = yearly_q1_counts.reindex(columns=train_years, fill_value=0).mean(axis=1).rename("projected")

    top_3_forecast_call_types = forecast.groupby(["KEYWORD__C", "SUBCATEGORY__C"]).sum().sort_values(ascending=False).head(3).index
    forecast_table = pd.concat(
        [top_districts(forecast, ct, "projected").assign(CALL_TYPE=call_type_label(ct)) for ct in top_3_forecast_call_types],
        ignore_index=True,
    )[["CALL_TYPE", "COUNCIL_DISTRICT__C", "projected"]]
    print(f"\nForecast for Q1 {FORECAST_YEAR}: top {TOP_DISTRICTS} council districts for the 3 most common call types")
    print(f"(average Q1 cases, {train_years[0]}-{train_years[-1]})")
    print(forecast_table.round(1).to_string(index=False))

    forecast_cells = pd.DataFrame({
        "Call Type": forecast_table["CALL_TYPE"].mask(forecast_table["CALL_TYPE"].duplicated(), ""),
        "Council District": forecast_table["COUNCIL_DISTRICT__C"],
        "Projected # of Calls": forecast_table["projected"].map(lambda v: f"{v:,.1f}"),
    })
    save_table_png(
        forecast_cells,
        "q1-2022-forecast-top-districts-table.png",
        f"Q1 {FORECAST_YEAR} Forecast: Top {TOP_DISTRICTS} Council Districts for the 3 Most Common Call Types",
        f"Projected calls = average Q1 cases, {train_years[0]}–{train_years[-1]}",
    )
    return forecast_table, top_3_forecast_call_types, train_years


def score_precision(q1_df, forecast_table, top_3_forecast_call_types):
    """A forecast district is a true positive if it was also one of the actual
    top districts in Q1 2022. Precision answers the staffing question: of the
    districts we would have sent extra crews to, how many needed them?"""
    actual = q1_df[q1_df["YEAR"] == FORECAST_YEAR].groupby(GROUP_COLS).size().rename("actual")

    actual_table = pd.concat(
        [top_districts(actual, ct, "actual").assign(CALL_TYPE=call_type_label(ct)) for ct in top_3_forecast_call_types],
        ignore_index=True,
    )[["CALL_TYPE", "COUNCIL_DISTRICT__C", "actual"]]
    forecast_pairs = set(zip(forecast_table["CALL_TYPE"], forecast_table["COUNCIL_DISTRICT__C"]))
    actual_table["in_forecast"] = [pair in forecast_pairs for pair in zip(actual_table["CALL_TYPE"], actual_table["COUNCIL_DISTRICT__C"])]
    print(f"\nActual Q1 {FORECAST_YEAR} (Jan-Mar): top {TOP_DISTRICTS} council districts for the same 3 call types")
    print(actual_table.to_string(index=False))
    save_result(actual_table, "q3_actual_top_districts.csv", index=False)

    actual_pairs = set(zip(actual_table["CALL_TYPE"], actual_table["COUNCIL_DISTRICT__C"]))
    forecast_table["true_positive"] = [pair in actual_pairs for pair in zip(forecast_table["CALL_TYPE"], forecast_table["COUNCIL_DISTRICT__C"])]
    precision_by_call_type = forecast_table.groupby("CALL_TYPE", sort=False)["true_positive"].agg(
        true_positives="sum", false_positives=lambda tp: (~tp).sum(), precision="mean"
    )
    true_positives = forecast_table["true_positive"].sum()
    false_positives = (~forecast_table["true_positive"]).sum()
    print(f"\nForecast precision (a predicted top {TOP_DISTRICTS} district is a true positive if it was also an actual top {TOP_DISTRICTS} district):")
    print(precision_by_call_type.round(2).to_string())
    print(f"Overall precision: {true_positives} / ({true_positives} + {false_positives}) = {true_positives / (true_positives + false_positives):.2f}")
    save_result(precision_by_call_type, "q3_precision_by_call_type.csv")
    return actual


def score_count_error(forecast_table, actual, top_3_forecast_call_types):
    """Count error = total absolute error / total actual cases across the 15
    forecast pairs. Absolute error, because over- and under-projections both
    misallocate crews and should not cancel out."""
    forecast_table["actual"] = [
        actual.get((*call_type, district), 0)
        for call_type, district in zip(top_3_forecast_call_types.repeat(TOP_DISTRICTS), forecast_table["COUNCIL_DISTRICT__C"])
    ]
    forecast_table["abs_error"] = (forecast_table["actual"] - forecast_table["projected"]).abs()
    count_error_by_call_type = forecast_table.groupby("CALL_TYPE", sort=False)[["projected", "actual", "abs_error"]].sum()
    count_error_by_call_type["count_error"] = count_error_by_call_type["abs_error"] / count_error_by_call_type["actual"]
    total_abs_error = forecast_table["abs_error"].sum()
    total_actual = forecast_table["actual"].sum()
    print(f"\nForecast count error for the {len(forecast_table)} forecast districts (total absolute error / total actual cases):")
    print(forecast_table[["CALL_TYPE", "COUNCIL_DISTRICT__C", "projected", "actual", "abs_error"]].round(1).to_string(index=False))
    print()
    print(count_error_by_call_type.round(2).to_string())
    print(f"Overall count error: {total_abs_error:.1f} / {total_actual} = {total_abs_error / total_actual:.1%}")
    save_result(forecast_table, "q3_forecast_vs_actual.csv", index=False)
    save_result(count_error_by_call_type, "q3_count_error_by_call_type.csv")
    return count_error_by_call_type, total_abs_error / total_actual


def storm_test(q1_df, forecast_table, top_3_forecast_call_types, train_years, count_error_by_call_type, full_q1_error):
    """Does the February 2022 winter storm explain the count error?

    Rerun the same forecast with February left out of both the training
    averages and the 2022 actuals, on the same 15 call type + district pairs,
    so the two count errors are directly comparable. If the storm were the
    cause, the error would drop sharply without February.
    """
    jan_mar_df = q1_df[q1_df["CREATEDDATE"].dt.month.isin([1, 3])]
    jan_mar_yearly = (
        jan_mar_df[jan_mar_df["YEAR"].isin(TRAIN_YEARS)]
        .groupby(GROUP_COLS + ["YEAR"]).size()
        .unstack("YEAR", fill_value=0)
        .reindex(columns=train_years, fill_value=0)
    )
    jan_mar_forecast = jan_mar_yearly.mean(axis=1)
    jan_mar_actual = jan_mar_df[jan_mar_df["YEAR"] == FORECAST_YEAR].groupby(GROUP_COLS).size()

    forecast_pair_keys = [
        (*call_type, district)
        for call_type, district in zip(top_3_forecast_call_types.repeat(TOP_DISTRICTS), forecast_table["COUNCIL_DISTRICT__C"])
    ]
    no_feb_table = forecast_table[["CALL_TYPE", "COUNCIL_DISTRICT__C"]].copy()
    no_feb_table["projected"] = [jan_mar_forecast.get(key, 0) for key in forecast_pair_keys]
    no_feb_table["actual"] = [jan_mar_actual.get(key, 0) for key in forecast_pair_keys]
    no_feb_table["abs_error"] = (no_feb_table["actual"] - no_feb_table["projected"]).abs()
    no_feb_error_by_call_type = no_feb_table.groupby("CALL_TYPE", sort=False)[["projected", "actual", "abs_error"]].sum()
    no_feb_error_by_call_type["count_error"] = no_feb_error_by_call_type["abs_error"] / no_feb_error_by_call_type["actual"]
    no_feb_error_by_call_type["full_q1_count_error"] = count_error_by_call_type["count_error"]
    no_feb_abs_error = no_feb_table["abs_error"].sum()
    no_feb_actual = no_feb_table["actual"].sum()
    print(f"\nStorm test: count error for January + March only (February excluded, average of {train_years[0]}-{train_years[-1]})")
    print(no_feb_table.round(1).to_string(index=False))
    print()
    print(no_feb_error_by_call_type.round(2).to_string())
    print(f"Overall count error, Jan + Mar only: {no_feb_abs_error:.1f} / {no_feb_actual} = {no_feb_abs_error / no_feb_actual:.1%}")
    print(f"Overall count error, full Q1: {full_q1_error:.1%}")
    save_result(no_feb_error_by_call_type, "q3_storm_test.csv")

    storm_cells = pd.DataFrame({
        "Call Type": [*no_feb_error_by_call_type.index, "Overall"],
        "Projected\n(Jan + Mar)": [*no_feb_error_by_call_type["projected"], no_feb_table["projected"].sum()],
        "Actual\n(Jan + Mar)": [*no_feb_error_by_call_type["actual"], no_feb_actual],
        "Absolute\nError": [*no_feb_error_by_call_type["abs_error"], no_feb_abs_error],
        "Count Error\n(Jan + Mar)": [*no_feb_error_by_call_type["count_error"], no_feb_abs_error / no_feb_actual],
        "Count Error\n(Full Q1)": [*no_feb_error_by_call_type["full_q1_count_error"], full_q1_error],
    })
    for col in ["Projected\n(Jan + Mar)", "Actual\n(Jan + Mar)", "Absolute\nError"]:
        storm_cells[col] = storm_cells[col].map(lambda v: f"{v:,.0f}")
    for col in ["Count Error\n(Jan + Mar)", "Count Error\n(Full Q1)"]:
        storm_cells[col] = storm_cells[col].map(lambda v: f"{v:.1%}")
    save_table_png(
        storm_cells,
        "q1-2022-storm-test-count-error-table.png",
        f"Storm Test: Q1 {FORECAST_YEAR} Count Error with February Excluded",
        "Count error = total absolute error / total actual calls, across the 15 forecast districts",
        cell_colors=[[None] * 6] * (len(storm_cells) - 1) + [["#f2f2f2"] * 6],
    )
    # Result: the count error stays high with February excluded, so the storm
    # is not a likely explanation for the forecast missing on counts.


def main():
    q1_df = q1_cases()
    forecast_table, top_3_forecast_call_types, train_years = build_forecast(q1_df)
    actual = score_precision(q1_df, forecast_table, top_3_forecast_call_types)
    count_error_by_call_type, full_q1_error = score_count_error(forecast_table, actual, top_3_forecast_call_types)
    storm_test(q1_df, forecast_table, top_3_forecast_call_types, train_years, count_error_by_call_type, full_q1_error)


if __name__ == "__main__":
    main()
