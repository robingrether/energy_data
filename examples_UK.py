import download_scripts_UK as uk_api
import pandas as pd

start = pd.Timestamp("2023-01-01", tz="Europe/London")
end = start + pd.Timedelta(days=6, hours=23, minutes=59)


# -------------------------------
# Per-Type Electricity Generation
# -------------------------------

# Download per-type electricity generation for Great Britain
uk_api.download_GB_per_type_data(start, end)

# Download per-type electricity generation for Ireland (incl. Northern Ireland)
uk_api.download_IE_per_type_data(start, end)


# ------------------
# Electricity Demand
# ------------------

# Download electricity demand for Great Britain
uk_api.download_GB_demand_data(start, end)

# Download electricity demand for Ireland (incl. Northern Ireland)
uk_api.download_IE_demand_data(start, end)


# ------------------
# Cross-border flows
# ------------------

# Download cross-border flows (GB > IE and IE > GB)
uk_api.download_GB_IE_flows(start, end)
