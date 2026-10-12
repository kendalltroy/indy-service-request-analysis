"""Exploratory charts that set up the three questions: how long cases stay
open, how closures move over time, and the chuckhole surge that motivates the
seasonality and forecast work."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow running this file directly

import matplotlib.pyplot as plt
import pandas as pd

from clean import load_all_cases, load_closed_cases, log_dropped
from config import CUTOFF
from plotting import save_figure, save_result, set_chart_title


def plot_duration_boxplot(closed_df):
    """Durations run from minutes to years, so the axis is linear up to one day
    and logarithmic beyond it; a plain log axis cannot show same-day closures."""
    duration_days = closed_df["CASE_DURATION"].dt.total_seconds() / 86400

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.boxplot(
        duration_days,
        orientation="horizontal",
        widths=0.5,
        patch_artist=True,
        boxprops=dict(facecolor="#2a78d6", edgecolor="#2a78d6", alpha=0.35),
        medianprops=dict(color="#2a78d6", linewidth=2),
        whiskerprops=dict(color="#555555"),
        capprops=dict(color="#555555"),
        flierprops=dict(marker="o", markersize=2, markerfacecolor="#999999", markeredgecolor="none", alpha=0.3),
    )
    ax.set_xscale("symlog", linthresh=1)
    day_ticks = [0, 1, 7, 30, 90, 365, 1000, 3000]
    ax.set_xticks(day_ticks)
    ax.set_xticklabels([f"{d:,}" for d in day_ticks])
    ax.minorticks_off()
    ax.set_xlabel("Days Open (Log Scale Above 1 Day)")
    ax.set_yticks([])
    set_chart_title(ax, "Time to Close Service Cases")
    ax.grid(axis="x", color="#e5e5e5")
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    plt.tight_layout()
    save_figure(fig, "closed-case-duration-boxplot.png")


def plot_closed_per_month(closed_df):
    """Closures per month through July 2022.

    Months after the cutoff would only count cases created before it, so their
    totals would look like a drop in closures that never happened.
    """
    closed_dates = closed_df["CLOSEDDATE"].dt.tz_localize(None)
    print(f"\nCLOSEDDATE range: {closed_dates.min()} to {closed_dates.max()}")
    closed_after_cutoff = closed_dates >= CUTOFF.tz_localize(None)
    log_dropped(closed_after_cutoff.sum(), len(closed_dates), f"closed cases closed on or after {CUTOFF:%B %d, %Y}; excluded from the closed cases per month chart")
    closed_dates = closed_dates[~closed_after_cutoff]
    month_bins = pd.date_range(closed_dates.min().to_period("M").to_timestamp(), CUTOFF.tz_localize(None), freq="MS")
    save_result(closed_dates.dt.to_period("M").value_counts().sort_index().rename("cases_closed"), "closed_cases_per_month.csv")

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.hist(closed_dates, bins=month_bins, color="#2a78d6", edgecolor="white", linewidth=0.5)
    ax.set_xlim(month_bins[0], month_bins[-1])
    ax.set_xlabel("Month Closed")
    ax.set_ylabel("Cases Closed")
    set_chart_title(ax, "Closed Service Cases per Month")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", color="#e5e5e5")
    ax.set_axisbelow(True)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    plt.tight_layout()
    save_figure(fig, "closed-cases-per-month.png")


def plot_chuckhole_per_year(all_cases_df):
    """Street chuckhole cases (open + closed) per created year. The first and
    last years are partial and drawn hollow so they are not read as dips."""
    chuckhole_cases = all_cases_df[
        (all_cases_df["KEYWORD__C"] == "chuckhole") & (all_cases_df["SUBCATEGORY__C"] == "street (chuckhole)")
    ]
    chuckhole_years = chuckhole_cases["CREATEDDATE"].dt.year
    chuckhole_per_year = chuckhole_years.value_counts().sort_index()
    partial_years = [chuckhole_per_year.index.min(), chuckhole_per_year.index.max()]
    print("\nChuckhole / street (chuckhole) cases per year (open + closed):\n", chuckhole_per_year.to_string())
    save_result(chuckhole_per_year.rename("cases"), "chuckhole_cases_per_year.csv")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(chuckhole_per_year.index, chuckhole_per_year.values, color="#2a78d6", linewidth=2, marker="o", markersize=7)
    ax.plot(partial_years, chuckhole_per_year[partial_years], linestyle="none", marker="o", markersize=7,
            markerfacecolor="white", markeredgecolor="#2a78d6", markeredgewidth=2)
    for year in partial_years:
        ax.annotate("Partial year", (year, chuckhole_per_year[year]), textcoords="offset points", xytext=(0, -16),
                    ha="center", fontsize=8, color="#666666")
    ax.set_xticks(chuckhole_per_year.index)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Year Created")
    ax.set_ylabel("Cases")
    set_chart_title(ax, "Street Chuckhole Cases per Year", "2015 starts in June and 2022 ends in July (the analysis cutoff)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(axis="y", color="#e5e5e5")
    ax.set_axisbelow(True)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    plt.tight_layout()
    save_figure(fig, "chuckhole-cases-per-year.png")


def main():
    closed_df = load_closed_cases()
    plot_duration_boxplot(closed_df)
    plot_closed_per_month(closed_df)
    plot_chuckhole_per_year(load_all_cases())


if __name__ == "__main__":
    main()
