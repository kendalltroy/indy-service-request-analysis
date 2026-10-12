"""Run the full pipeline: clean the raw export, then every analysis.

Writes data/processed/*.parquet, figures/*.png and results/*.csv.
Run src/download_data.py first if data/raw/ is empty.
"""
import sys

import clean
import q1_response_times
import q2_seasonality
import q3_forecast
from config import RAW_CSV
from supporting import district_profile, exploratory


def main():
    if not RAW_CSV.exists():
        sys.exit(f"{RAW_CSV} not found. Run `python src/download_data.py` first.")
    clean.main()
    exploratory.main()
    q1_response_times.main()
    q2_seasonality.main()
    district_profile.main()
    q3_forecast.main()


if __name__ == "__main__":
    main()
