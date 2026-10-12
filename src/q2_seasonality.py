"""Q2: Which call types are seasonal, and how strongly?

Seasonality is measured on open + closed cases by created date. Demand happens
when a resident reports a problem, whether or not the case was ever closed, so
leaving out open cases would undercount recent months.
"""
import matplotlib.pyplot as plt
import pandas as pd

from clean import load_all_cases, load_closed_cases, log_dropped
from config import MIN_PAIR_CASES, season_names
from labels import call_type_label
from plotting import save_figure, save_result, set_chart_title

season_order = list(season_names.values())

# Call types grouped for the seasonal index. Stolen carts and dumped trash are
# combined because both are trash complaints handled by the same department.
INDEX_GROUPS = {
    "Street Chuckhole": [("chuckhole", "street (chuckhole)")],
    "Weeds: Private Property": [("weeds", "private property (complaint)")],
    "Stolen Carts and Trash Dumping": [
        ("trash", "96 gal cart - stolen"),
        ("illegal dumping and junk/trash", "trash accumulation or dumped materials"),
    ],
}


def busiest_pairs_by_season(closed_df):
    """The busiest ZIP + call type pairs in each season, to see whether the
    places generating the most cases shift through the year."""
    closed_df["SEASON"] = closed_df["CREATEDDATE"].dt.quarter.map(season_names)
    season_pairs = (
        closed_df.groupby(["SEASON", "ZIP", "KEYWORD__C", "SUBCATEGORY__C"])["RESPONSE_DAYS"]
        .agg(median_days="median", cases="size")
    )
    season_pairs_min = season_pairs[season_pairs["cases"] >= MIN_PAIR_CASES]

    for season in season_names.values():
        pairs = season_pairs_min.loc[season]
        print(f"\n=== {season} ({len(pairs)} ZIP + call type pairs with at least {MIN_PAIR_CASES} cases) ===")
        print("Top 3 by number of cases:\n", pairs.sort_values("cases", ascending=False).head(3).round(1))
    save_result(season_pairs_min, "q2_season_zip_call_type_pairs.csv")


def seasonal_share(all_cases_df):
    """Share of each call type's cases created in each season, for the 4 most
    common call types. Each row sums to 100%, so call types of very different
    sizes can be compared."""
    all_cases_df["SEASON"] = all_cases_df["CREATEDDATE"].dt.quarter.map(season_names)
    all_call_type_counts = all_cases_df.groupby(["KEYWORD__C", "SUBCATEGORY__C"]).size().sort_values(ascending=False)
    missing_all_call_type = all_cases_df["KEYWORD__C"].isna() | all_cases_df["SUBCATEGORY__C"].isna()
    log_dropped(missing_all_call_type.sum(), len(all_cases_df), "open + closed cases missing KEYWORD__C or SUBCATEGORY__C; excluded from the seasonal share heatmap")
    all_top_10_call_types = all_call_type_counts.head(10)
    open_count = (all_cases_df["STATUS"].str.strip().str.lower() == "open").sum()
    print(f"\nOpen + closed cases for seasonal analysis: {len(all_cases_df)} ({open_count} open)")

    top_10_df = all_cases_df.set_index(["KEYWORD__C", "SUBCATEGORY__C"])
    top_10_df = top_10_df[top_10_df.index.isin(all_top_10_call_types.index)].reset_index()
    top_10_df["CALL_TYPE"] = [call_type_label(ct) for ct in zip(top_10_df["KEYWORD__C"], top_10_df["SUBCATEGORY__C"])]

    share = pd.crosstab(top_10_df["CALL_TYPE"], top_10_df["SEASON"], normalize="index")[season_order] * 100
    share = share.loc[[call_type_label(ct) for ct in all_top_10_call_types.head(4).index]]
    save_result(share, "q2_seasonal_share.csv")
    return share


def plot_seasonal_share(share):
    fig, ax = plt.subplots(figsize=(9, 4))
    cells = ax.imshow(share, aspect="auto", cmap="Blues", vmin=0, vmax=share.values.max())
    for row in range(share.shape[0]):
        for col in range(share.shape[1]):
            value = share.iat[row, col]
            # Switch to white text on the darkest cells so the label stays readable.
            text_color = "white" if value > 0.6 * share.values.max() else "#333333"
            ax.text(col, row, f"{value:.0f}%", ha="center", va="center", fontsize=9, color=text_color)
    ax.set_xticks(range(len(season_order)))
    ax.set_xticklabels(season_order)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(share.index)))
    ax.set_yticklabels(share.index, fontsize=9)
    set_chart_title(ax, "Seasonal Share of Cases by Call Type", "Each row sums to 100%", pad=28)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    colorbar = fig.colorbar(cells, ax=ax, shrink=0.6, pad=0.02)
    colorbar.set_label("Share of Call Type's Cases (%)")
    plt.tight_layout()
    save_figure(fig, "call-type-share-by-season-heatmap.png")


def seasonal_index(all_cases_df):
    """Average monthly cases in each season divided by the call type's average
    month over the whole period.

    Unlike a seasonal share, the index is not skewed by partial years: months
    with zero cases are filled in, so every season is averaged over the same
    calendar span. 1.0 means a typical month, 2.0 twice as busy.
    """
    all_months = pd.period_range(
        all_cases_df["CREATEDDATE"].min().tz_localize(None).to_period("M"),
        all_cases_df["CREATEDDATE"].max().tz_localize(None).to_period("M"),
        freq="M",
    )

    seasonal_index_rows = {}
    for name, call_types in INDEX_GROUPS.items():
        group_cases = all_cases_df.set_index(["KEYWORD__C", "SUBCATEGORY__C"])
        group_cases = group_cases[group_cases.index.isin(call_types)]
        monthly_counts = (
            group_cases["CREATEDDATE"].dt.tz_localize(None).dt.to_period("M")
            .value_counts()
            .reindex(all_months, fill_value=0)
        )
        baseline = monthly_counts.mean()
        season_avg = monthly_counts.groupby(monthly_counts.index.quarter.map(season_names)).mean()
        seasonal_index_rows[name] = (season_avg / baseline)[season_order]
        seasonal_index_rows[name]["Monthly avg (baseline)"] = baseline

    index_table = pd.DataFrame(seasonal_index_rows).T
    print(f"\nSeasonal index, open + closed cases ({all_months[0]} to {all_months[-1]}, 1.0 = the call type's average month)")
    print(index_table.round(2).to_string())
    save_result(index_table, "q2_seasonal_index.csv")
    return index_table


def plot_seasonal_index(index_table):
    index_values = index_table[season_order]

    fig, ax = plt.subplots(figsize=(9, 3.5))
    # Fixed 0-2 scale centered on 1.0 so color means the same thing for every call type.
    cells = ax.imshow(index_values, aspect="auto", cmap="Reds", vmin=0, vmax=2)
    for row in range(index_values.shape[0]):
        for col in range(index_values.shape[1]):
            value = index_values.iat[row, col]
            text_color = "white" if value > 1.2 else "#333333"
            ax.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=10, color=text_color)
    ax.set_xticks(range(len(season_order)))
    ax.set_xticklabels(season_order)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(index_values.index)))
    ax.set_yticklabels(index_values.index, fontsize=9)
    set_chart_title(ax, "Seasonal Index by Call Type", "1.0 = the call type's average month, darker = busier", pad=28)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    colorbar = fig.colorbar(cells, ax=ax, shrink=0.8, pad=0.02)
    colorbar.set_label("Seasonal Index")
    plt.tight_layout()
    save_figure(fig, "seasonal-index-heatmap.png")


def main():
    busiest_pairs_by_season(load_closed_cases())
    all_cases_df = load_all_cases()
    plot_seasonal_share(seasonal_share(all_cases_df))
    plot_seasonal_index(seasonal_index(all_cases_df))


if __name__ == "__main__":
    main()
