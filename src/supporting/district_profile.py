"""Council district profile: which districts carry the most common call types,
and whether districts 11, 12 and 17, which top several of the forecast lists,
get more than their share of specific problems or just more cases overall."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # allow running this file directly

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

from clean import cases_with_district, load_all_cases, load_closed_cases, log_dropped
from labels import call_type_label
from plotting import save_result, save_table_png

FOCUS_DISTRICTS = [11, 12, 17]


def recent_district_call_types(closed_df):
    """Top 5 call types for closed cases created January 2021 through July 2022,
    with each one's top 3 districts and peak month. Limited to the most recent
    period so the district picture reflects current conditions."""
    district_raw = closed_df["COUNCIL_DISTRICT__C"]
    missing_district = district_raw.isna() | (district_raw.astype("string").str.strip() == "")
    district_df = closed_df[~missing_district].copy()
    district_df["COUNCIL_DISTRICT__C"] = district_df["COUNCIL_DISTRICT__C"].astype(float).astype("Int64")
    print()
    log_dropped(missing_district.sum(), len(closed_df), "closed cases missing COUNCIL_DISTRICT__C; excluded from the Jan 2021-Jul 2022 district analysis")
    print(f"Closed cases with a council district: {len(district_df)}")

    district_df = district_df[district_df["CREATEDDATE"].dt.year.between(2021, 2022)]
    print(f"Closed cases with a council district created in Jan 2021-Jul 2022: {len(district_df)}")

    district_call_type = district_df.groupby(["KEYWORD__C", "SUBCATEGORY__C"])
    missing_district_call_type = district_df["KEYWORD__C"].isna() | district_df["SUBCATEGORY__C"].isna()
    log_dropped(missing_district_call_type.sum(), len(district_df), "Jan 2021-Jul 2022 closed cases with a district missing KEYWORD__C or SUBCATEGORY__C; excluded from the top 5 call types")
    top_5_district_call_types = district_call_type.size().sort_values(ascending=False).head(5)
    print("\nTop 5 call types (cases with a council district, created Jan 2021-Jul 2022):\n", top_5_district_call_types)

    top_5_df = district_df.set_index(["KEYWORD__C", "SUBCATEGORY__C"])
    top_5_df = top_5_df[top_5_df.index.isin(top_5_district_call_types.index)].sort_index()

    rows = []
    for (keyword, subcategory), total in top_5_district_call_types.items():
        cases = top_5_df.loc[(keyword, subcategory)]

        top_districts = cases.groupby("COUNCIL_DISTRICT__C").size().sort_values(ascending=False).head(3)

        created_months = cases["CREATEDDATE"].sort_values().dt.tz_localize(None).dt.to_period("M")
        month_of_year_counts = created_months.dt.month.value_counts().sort_index()
        peak_month_of_year = month_of_year_counts.idxmax()
        peak_month_name = f"{pd.Timestamp(2000, peak_month_of_year, 1):%B}"

        print(f"\n=== {keyword} / {subcategory} ({total} cases) ===")
        print("Top 3 council districts:")
        for rank, (district, district_cases) in enumerate(top_districts.items(), start=1):
            print(f"  District {district}: {district_cases} cases ({district_cases / total:.1%})")
            rows.append({"call_type": call_type_label((keyword, subcategory)), "call_type_cases": total, "rank": rank,
                         "council_district": district, "district_cases": district_cases,
                         "district_share": district_cases / total, "peak_month": peak_month_name})
        print(f"Peak month of the year (Jan 2021-Jul 2022 combined): {peak_month_name} ({month_of_year_counts.max()} cases)")
    save_result(pd.DataFrame(rows), "district_top_call_types_2021_2022.csv", index=False)


def focus_district_shares(all_cases_df):
    """Share of all cases and of each top call type for the focus districts.

    The ratio table divides a district's share of a call type by its share of
    all cases: a district that is simply busy scores 1.0 everywhere, so values
    above 1.0 point to a problem that is concentrated there.
    """
    district_cases = cases_with_district(all_cases_df, log=False)

    district_share = (
        district_cases.groupby("COUNCIL_DISTRICT__C").size() / len(district_cases) * 100
    ).rename("% of all cases")

    share_call_types = district_cases.groupby(["KEYWORD__C", "SUBCATEGORY__C"]).size().sort_values(ascending=False).head(5).index
    call_type_district_counts = (
        district_cases.set_index(["KEYWORD__C", "SUBCATEGORY__C"])
        .loc[share_call_types]
        .groupby(["KEYWORD__C", "SUBCATEGORY__C", "COUNCIL_DISTRICT__C"]).size()
    )
    call_type_totals = call_type_district_counts.groupby(["KEYWORD__C", "SUBCATEGORY__C"]).transform("sum")
    call_type_share = (call_type_district_counts / call_type_totals * 100).unstack(["KEYWORD__C", "SUBCATEGORY__C"], fill_value=0)
    call_type_share.columns = [f"% of {call_type_label(ct)}" for ct in call_type_share.columns]

    district_share_table = pd.concat([district_share, call_type_share], axis=1).fillna(0).loc[FOCUS_DISTRICTS]
    print(f"\nDistricts {', '.join(map(str, FOCUS_DISTRICTS))}: share of all cases and of the 5 most common call types, citywide")
    print(f"(percentages are out of all {len(district_cases)} open + closed cases across every district)")
    print(district_share_table.round(1).to_string())
    save_result(district_share_table, "districts_11_12_17_share_of_cases.csv")

    call_type_share_ratio = district_share_table[call_type_share.columns].div(district_share_table["% of all cases"], axis=0)
    call_type_share_ratio.columns = [col.removeprefix("% of ") for col in call_type_share_ratio.columns]
    print("\nCall type share / share of all cases (1.0 = the district has the same share of the call type as of all cases)")
    print(call_type_share_ratio.round(2).to_string())
    save_result(call_type_share_ratio, "districts_11_12_17_call_type_share_ratio.csv")

    district_share_cells = district_share_table.map(lambda v: f"{v:.1f}%")
    district_share_cells.columns = ["All Cases" if col == "% of all cases" else col.removeprefix("% of ") for col in district_share_cells.columns]
    district_share_cells.insert(0, "District", district_share_table.index)
    save_table_png(
        district_share_cells,
        "districts-11-12-17-share-of-cases-table.png",
        "Districts 11, 12 and 17: Share of Citywide Cases by Call Type",
        f"Percent of all cases ({len(district_cases):,}) and of the 5 most common call types",
    )

    # Diverging colors centered on 1.0, muted (0.2-0.8 of the colormap) so the numbers stay readable.
    ratio_norm = TwoSlopeNorm(vmin=0, vcenter=1, vmax=2)
    ratio_colors = plt.get_cmap("RdBu_r")(ratio_norm(call_type_share_ratio.values) * 0.6 + 0.2)
    ratio_cells = call_type_share_ratio.map(lambda v: f"{v:.2f}")
    ratio_cells.insert(0, "District", call_type_share_ratio.index)
    save_table_png(
        ratio_cells,
        "districts-11-12-17-call-type-share-score-table.png",
        "Districts 11, 12 and 17: Call Type Share Relative to Share of All Cases",
        "1.0 = same share of the call type as of all cases; red = higher, blue = lower",
        cell_colors=[[None, *row] for row in ratio_colors],
    )


def main():
    recent_district_call_types(load_closed_cases())
    focus_district_shares(load_all_cases())


if __name__ == "__main__":
    main()
