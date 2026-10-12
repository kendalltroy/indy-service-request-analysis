"""Q1: Which call types and ZIP codes wait longest for a case to be closed?

Response time is CLOSEDDATE minus CREATEDDATE for closed cases. Medians are used
throughout because durations are heavily right-skewed: a few cases stay open for
years and would dominate a mean.
"""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

from clean import load_closed_cases, log_dropped
from config import MIN_CALL_TYPE_CASES, MIN_PAIR_CASES, MIN_ZIP_CASES
from labels import call_type_label
from plotting import save_figure, save_result, set_chart_title


def summarize_call_types(closed_df):
    """Count closed cases per call type. Most call types are rare, which is why
    later rankings need a minimum case count."""
    call_type = closed_df.groupby(["KEYWORD__C", "SUBCATEGORY__C"])
    call_type_counts = call_type.size().sort_values(ascending=False)
    # groupby silently skips rows with a missing key, so report how many that is.
    missing_call_type = closed_df["KEYWORD__C"].isna() | closed_df["SUBCATEGORY__C"].isna()
    log_dropped(missing_call_type.sum(), len(closed_df), "closed cases missing KEYWORD__C or SUBCATEGORY__C; excluded from call type analyses")

    print(f"\nNumber of call types: {len(call_type_counts)}")
    print(f"Total cases across call types: {call_type_counts.sum()}")
    print(f"\nMost common call type: {call_type_counts.idxmax()} ({call_type_counts.max()} cases)")
    print(f"Least common call type: {call_type_counts.idxmin()} ({call_type_counts.min()} cases)")
    print(f"Call types tied for the minimum: {(call_type_counts == call_type_counts.min()).sum()}")
    print(f"Mean cases per call type: {call_type_counts.mean():.1f}")
    print(f"Median cases per call type: {call_type_counts.median():.1f}")
    top_10_call_types = call_type_counts.head(10)
    print("\nTop 10 call types:\n", top_10_call_types)

    small_call_types = call_type_counts[call_type_counts < 1000]
    print(f"\nCall types with under 1000 cases: {len(small_call_types)} of {len(call_type_counts)}")
    print(f"Cases in those call types: {small_call_types.sum()} ({small_call_types.sum() / call_type_counts.sum():.1%} of all cases)")
    return call_type, call_type_counts, missing_call_type


def median_response_tables(closed_df, call_type, call_type_counts, missing_call_type):
    """Median response time by ZIP, by call type, and by ZIP + call type, each
    with its case count so thin groups can be filtered out."""
    missing_zip = closed_df["ZIP"].isna()
    log_dropped(missing_zip.sum(), len(closed_df), "closed cases missing ZIP__C; excluded from ZIP analyses")

    zip_response = (
        closed_df.groupby("ZIP")["RESPONSE_DAYS"]
        .agg(median_days="median", cases="size")
        .sort_values("median_days", ascending=False)
    )
    print("\nTop 10 ZIPs with the longest median response time (days):\n", zip_response.head(10).round(1))

    call_type_response = (
        call_type["CASE_DURATION"]
        .agg(lambda d: d.median().total_seconds() / 86400)
        .to_frame("median_days")
        .assign(cases=call_type_counts)
        .sort_values("median_days", ascending=False)
    )
    print("\nTop 10 call types with the longest median response time (days):\n", call_type_response.head(10).round(1))

    zip_call_type_response = (
        closed_df.groupby(["ZIP", "KEYWORD__C", "SUBCATEGORY__C"])["RESPONSE_DAYS"]
        .agg(median_days="median", cases="size")
        .sort_values("median_days", ascending=False)
    )
    log_dropped((missing_zip | missing_call_type).sum(), len(closed_df),
                "closed cases missing ZIP__C, KEYWORD__C or SUBCATEGORY__C; excluded from ZIP + call type analyses, the response time heatmap and seasonal pairs")
    print("\nTop 10 ZIP + call type pairs with the longest median response time (days):\n", zip_call_type_response.head(10).round(1))

    # The unfiltered top 10s above are dominated by groups with a handful of
    # cases. This distribution is what MIN_PAIR_CASES in config.py is based on.
    pair_cases = zip_call_type_response["cases"]
    pair_q1, pair_median, pair_q3 = pair_cases.quantile([0.25, 0.5, 0.75])
    pair_iqr = pair_q3 - pair_q1
    print(f"\nZIP + call type pairs: {len(pair_cases)}")
    print(f"Median cases per pair: {pair_median}")
    print(f"Lower quartile (Q1): {pair_q1}, Upper quartile (Q3): {pair_q3}, IQR: {pair_iqr}")
    print(f"Lower fence (Q1 - 1.5 * IQR): {pair_q1 - 1.5 * pair_iqr}")
    print(f"Pairs below Q1: {(pair_cases < pair_q1).sum()}")
    return zip_response, call_type_response, zip_call_type_response


def apply_minimums(zip_response, call_type_response, zip_call_type_response):
    """Rerun the rankings with only groups that have enough cases for a stable median."""
    zip_response_min = zip_response[zip_response["cases"] >= MIN_ZIP_CASES]
    call_type_response_min = call_type_response[call_type_response["cases"] >= MIN_CALL_TYPE_CASES]
    zip_call_type_response_min = zip_call_type_response[zip_call_type_response["cases"] >= MIN_PAIR_CASES]

    print(f"\nZIPs with at least {MIN_ZIP_CASES} cases: {len(zip_response_min)} of {len(zip_response)}")
    print("Top 10 ZIPs with the longest median response time (days):\n", zip_response_min.head(10).round(1))
    print(f"\nCall types with at least {MIN_CALL_TYPE_CASES} cases: {len(call_type_response_min)} of {len(call_type_response)}")
    print("Top 10 call types with the longest median response time (days):\n", call_type_response_min.head(10).round(1))
    print(f"\nZIP + call type pairs with at least {MIN_PAIR_CASES} cases: {len(zip_call_type_response_min)} of {len(zip_call_type_response)}")
    print("Top 10 ZIP + call type pairs with the longest median response time (days):\n", zip_call_type_response_min.head(10).round(1))

    save_result(zip_response_min, "q1_zip_median_response.csv")
    save_result(call_type_response_min, "q1_call_type_median_response.csv")
    save_result(zip_call_type_response_min, "q1_zip_call_type_median_response.csv")
    return zip_response_min, call_type_response_min


def plot_longest_call_types(call_type_response_min):
    """Shown in years, not days, because the slowest call types take well over a year."""
    top_call_types = call_type_response_min.head(10).iloc[::-1]
    call_type_labels = [call_type_label(ct) for ct in top_call_types.index]

    fig, ax = plt.subplots(figsize=(11, 6))
    top_call_type_years = top_call_types["median_days"] / 365.25
    bars = ax.barh(call_type_labels, top_call_type_years, height=0.6, color="#2a78d6")
    ax.bar_label(bars, labels=[f"{y:.1f}" for y in top_call_type_years], padding=4, color="#333333", fontsize=9)
    ax.set_xlabel("Median Response Time (Years)")
    set_chart_title(ax, "Call Types with the Longest Median Response Time",
                    f"Call types with at least {MIN_CALL_TYPE_CASES} closed cases")
    ax.grid(axis="x", color="#e5e5e5")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    plt.tight_layout()
    save_figure(fig, "call-types-longest-response-time.png")


def plot_zip_call_type_heatmap(closed_df, call_type_counts, zip_response_min, zip_call_type_response):
    """Median response time for ZIPs with enough cases (rows, busiest first) and
    the 15 most common call types (columns), to show whether slow service is a
    neighborhood pattern or a call type pattern."""
    heatmap_call_types = call_type_counts.head(10).index.tolist() + call_type_counts.index[10:15].tolist()
    heatmap_call_type_labels = [call_type_label(ct) for ct in heatmap_call_types]

    heatmap_df = closed_df[closed_df["ZIP"].isin(zip_response_min.index)]
    heatmap_df = heatmap_df.set_index(["KEYWORD__C", "SUBCATEGORY__C"])
    heatmap_df = heatmap_df[heatmap_df.index.isin(heatmap_call_types)]
    heatmap_zips = heatmap_df["ZIP"].value_counts().index

    pair_medians = zip_call_type_response.reset_index()
    pair_medians["CALL_TYPE"] = [call_type_label(ct) for ct in zip(pair_medians["KEYWORD__C"], pair_medians["SUBCATEGORY__C"])]
    heatmap_medians = (
        pair_medians.pivot(index="ZIP", columns="CALL_TYPE", values="median_days")
        .reindex(index=heatmap_zips, columns=heatmap_call_type_labels)
    )
    print(f"\nResponse time heatmap: {heatmap_medians.notna().sum().sum()} of {heatmap_medians.size} cells have at least one case")
    print(f"Median days range: {np.nanmin(heatmap_medians.values):.2f} to {np.nanmax(heatmap_medians.values):.1f}")
    save_result(heatmap_medians, "q1_response_time_heatmap.csv")

    fig, ax = plt.subplots(figsize=(12, 13))
    median_cmap = plt.get_cmap("Oranges").copy()
    median_cmap.set_bad("#eeeeee")
    # Log color scale: medians run from minutes to years, and a linear scale would wash out everything under a month.
    cells = ax.imshow(heatmap_medians.clip(lower=0.1), aspect="auto", cmap=median_cmap, norm=LogNorm(vmin=0.1, vmax=np.nanmax(heatmap_medians.values)))
    ax.set_xticks(range(len(heatmap_medians.columns)))
    ax.set_xticklabels(heatmap_medians.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(heatmap_medians.index)))
    ax.set_yticklabels(heatmap_medians.index, fontsize=8)
    ax.set_xlabel("Call Type (15 Most Common)")
    ax.set_ylabel(f"ZIP Code (Min. {MIN_ZIP_CASES} Cases, Busiest at Top)")
    set_chart_title(ax, "Median Response Time by ZIP Code and Call Type", "Gray cells have no cases")
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    colorbar = fig.colorbar(cells, ax=ax, shrink=0.5, pad=0.02)
    colorbar.set_label("Median Response Time (Days, Log Scale)")
    colorbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    plt.tight_layout()
    save_figure(fig, "response-time-by-zip-and-call-type-heatmap.png")


def main():
    closed_df = load_closed_cases()
    call_type, call_type_counts, missing_call_type = summarize_call_types(closed_df)
    save_result(call_type_counts.rename("cases"), "q1_call_type_counts.csv")
    zip_response, call_type_response, zip_call_type_response = median_response_tables(
        closed_df, call_type, call_type_counts, missing_call_type)
    zip_response_min, call_type_response_min = apply_minimums(zip_response, call_type_response, zip_call_type_response)
    plot_longest_call_types(call_type_response_min)
    plot_zip_call_type_heatmap(closed_df, call_type_counts, zip_response_min, zip_call_type_response)


if __name__ == "__main__":
    main()
