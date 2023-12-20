import download_scripts_SMARD as smard
import pandas as pd

start = pd.Timestamp("2023-01-01", tz="Europe/Berlin")
end = start + pd.Timedelta(days=6, hours=23, minutes=59)

start_2 = pd.Timestamp("2016-01-01", tz="Europe/Berlin")
end_2 = start_2 + pd.Timedelta(days=6, hours=23, minutes=59)


# ----------------------------
# Day-Ahead Electricity Prices
# ----------------------------

# Download day-ahead electricity prices for the Germany-Luxembourg bidding zone
smard.download_day_ahead_prices(smard.BZ_DE_LU, start, end)  # data available as of 2018-10-01

# Download day-ahead electricity prices for neighboring bidding zones
smard.download_day_ahead_prices(smard.BZ_AT, start, end)  # data available as of 2018-10-01
smard.download_day_ahead_prices(smard.BZ_BE, start, end)
smard.download_day_ahead_prices(smard.BZ_CH, start, end)
smard.download_day_ahead_prices(smard.BZ_CZ, start, end)
smard.download_day_ahead_prices(smard.BZ_DK_1, start, end)
smard.download_day_ahead_prices(smard.BZ_DK_2, start, end)
smard.download_day_ahead_prices(smard.BZ_FR, start, end)
smard.download_day_ahead_prices(smard.BZ_HU, start, end)
smard.download_day_ahead_prices(smard.BZ_IT_NORTH, start, end)
smard.download_day_ahead_prices(smard.BZ_NL, start, end)
smard.download_day_ahead_prices(smard.BZ_NO_2, start, end)
smard.download_day_ahead_prices(smard.BZ_PL, start, end)
smard.download_day_ahead_prices(smard.BZ_SE_4, start, end)
smard.download_day_ahead_prices(smard.BZ_SI, start, end)

# Download day-ahead electricity prices for old bidding zone
smard.download_day_ahead_prices(smard.BZ_DE_AT_LU, start_2, end_2)  # data available from 2015-01-05 to 2018-09-30

# Download average day-ahead prices in the neighboring zones of DE_LU
smard.download_day_ahead_prices(smard.BZ_DE_LU_NEIGHBORS, start, end)  # data available as of 2019-11-20


# -------------------------------
# Per-Type Electricity Generation
# -------------------------------

# Download per-type electricity generation
smard.download_DE_per_type_data(start, end)

# Download net per-type electricity generation (i.e., consumption/production of storage types is aggregated into a single series)
smard.download_DE_per_type_data(start, end, nett=True)


# -------------------------------
# Per-Unit Electricity Generation
# -------------------------------

# Download per-unit electricity generation
smard.download_DE_per_unit_data(start, end)

# Power plant list with additional information
smard.DE_POWER_PLANT_LIST


# ------------------
# Electricity Demand
# ------------------

# Download electricity demand
smard.download_DE_demand_data(start, end)
