"""
Script for loading electricity generation and consumption data for Great Britain and Ireland.

In the following script, Great Britain (GB) refers to the main island including England, Wales and Scotland,
but excluding external islands such as Orkney or the Isle of Man.
Likewise, Ireland (IE) refers to the island including the Republic of Ireland and Northern Ireland.
The cross-border flows GB <-> IE include the EWIC and Moyle interconnector.

Author: Robin L. Grether

License: MIT License
"""

from io import StringIO

import numpy as np
import pandas as pd
import requests
import yaml

# put your API Key here:
API_KEY = ""

# timeout for API calls (in seconds)
TIMEOUT = 60

GB_GENERATION_TYPES = [
    "Biomass",
    "Hydro Pumped Storage",
    "Hydro Run-of-river and poundage",
    "Fossil Hard coal",
    "Fossil Gas",
    "Fossil Oil",
    "Nuclear",
    "Other",
    "Wind Onshore",
    "Wind Offshore",
    "Solar",
]

# Technology shares for distribution of remaining generation, shares according to ESB 2022 Annual Report
IE_GENERATION_TYPES = [
    ("Fossil Hard coal", 0.133803),
    ("Fossil Gas", 0.715493),
    ("Fossil Oil", 0.012676),
    ("Hydro Run-of-river and poundage", 0.023944),
    ("Biomass", 0.023944),
    ("Hydro Pumped Storage", 0.008451),
    ("Other", 0.081690),
]


def download_GB_per_type_data(start: pd.Timestamp, end: pd.Timestamp):
    """
    Download per type electricity generation data for Great Britain from the BMRS API.

        Parameters:
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.

        Returns:
            (pd.DataFrame): The per type electricity generation data.
    """

    # obtain set of individual days within time span
    all_days = pd.date_range(
        start=start.tz_convert("Europe/London"),
        end=end.tz_convert("Europe/London"),
        normalize=True,
        tz="Europe/London",
    )

    # start with no data
    df = None

    # iterate over all days
    for date in all_days:
        # get generation data per day
        df_new = _download_GB_per_type_data(date)

        # concatenate data
        if df is None:
            df = df_new
        else:
            df = pd.concat([df, df_new])

    # only return data between specific start and end times
    return df[start:end]


def download_GB_demand_data(start: pd.Timestamp, end: pd.Timestamp):
    """
    Download electricity consumption data for Great Britain from the BMRS API.

        Parameters:
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.

        Returns:
            (pd.DataFrame): The electricity consumption data.
    """

    # obtain set of individual days within time span
    all_days = pd.date_range(
        start=start.tz_convert("Europe/London"),
        end=end.tz_convert("Europe/London"),
        normalize=True,
        tz="Europe/London",
    )

    # start with no data
    df = None

    # iterate over all days
    for date in all_days:
        # get demand data per day
        df_new = _download_GB_demand_data(date)

        # concatenate data
        if df is None:
            df = df_new
        else:
            df = pd.concat([df, df_new])

    # only return data between specific start and end times
    return df[start:end]


def _download_GB_per_type_data(
    date: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/London")
):
    # we need this complex procedure to automatically take care of leap hours
    range_start = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 00:00", tz="Europe/London")
    range_end = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 23:30", tz="Europe/London")
    date_range = pd.date_range(start=range_start, end=range_end, freq="30T")

    # create new DataFrame with proper timestamps as index
    df = pd.DataFrame(index=date_range, columns=GB_GENERATION_TYPES)

    # URL to access per type generation
    url = f"https://api.bmreports.com/BMRS/B1620/v1?APIKey={API_KEY}&SettlementDate={date.strftime('%Y-%m-%d')}&Period=*&ServiceType=csv"

    # Make a GET request to fetch the CSV data
    response = requests.get(url, timeout=TIMEOUT)

    # Check if the request was successful
    if response.status_code == 200:
        # Use StringIO to read the CSV data into a DataFrame
        data = pd.read_csv(StringIO(response.text), skiprows=4)

        # delete 'end of file' entry
        data = data.iloc[:-1]

        # sort data by hour
        data = data.sort_values(by=["Settlement Period"])

        # add data of each generation type to DataFrame
        for type in GB_GENERATION_TYPES:
            # select per type data
            type_data = data[data["Power System Resource  Type"] == type]

            # create index of existing data rows
            data_index = (
                np.array(type_data["Settlement Period"].values, dtype=np.int32) - 1
            )

            # add per type data to DataFrame
            df[type].iloc[data_index] = type_data["Quantity"].values

    return df


def _download_GB_demand_data(
    date: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/London")
):
    # we need this complex procedure to automatically take care of leap hours
    range_start = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 00:00", tz="Europe/London")
    range_end = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 23:30", tz="Europe/London")
    date_range = pd.date_range(start=range_start, end=range_end, freq="30T")

    # create new DataFrame with proper timestamps as index
    df = pd.DataFrame(index=date_range, columns=["Actual Load"])

    # URL to access demand data
    url = f"https://api.bmreports.com/BMRS/B0610/v1?APIKey={API_KEY}&SettlementDate={date.strftime('%Y-%m-%d')}&Period=*&ServiceType=csv"

    # Make a GET request to fetch the CSV data
    response = requests.get(url, timeout=TIMEOUT)

    # Check if the request was successful
    if response.status_code == 200:
        # Use StringIO to read the CSV data into a DataFrame
        data = pd.read_csv(StringIO(response.text), skiprows=4)

        # delete 'end of file' entry
        data = data.iloc[:-1]

        # sort data by hour
        data = data.sort_values(by=["SettlementPeriod"])

        # create index of existing data rows
        data_index = np.array(data["SettlementPeriod"].values, dtype=np.int32) - 1

        # add load data to DataFrame
        df["Actual Load"].iloc[data_index] = data["Quantity"].values

    return df


def download_IE_per_type_data(start: pd.Timestamp, end: pd.Timestamp):
    """
    Download per type electricity generation data for EirGrid, i.e., Republic of Ireland and Northern Ireland.

        Parameters:
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.

        Returns:
            (pd.DataFrame): The per type electricity generation data.
    """

    # obtain set of individual days within time span
    all_days = pd.date_range(
        start=start.tz_convert("Europe/Dublin"),
        end=end.tz_convert("Europe/Dublin"),
        normalize=True,
        tz="Europe/Dublin",
    )

    # start with no data
    df = None

    # iterate over all days
    for date in all_days:
        # get generation data per day
        df_new = _download_IE_per_type_data(date)

        # concatenate data
        if df is None:
            df = df_new
        else:
            df = pd.concat([df, df_new])

    # only return data between specific start and end times
    return df[start:end]


def download_IE_demand_data(start: pd.Timestamp, end: pd.Timestamp):
    """
    Download electricity consumption data for EirGrid, i.e., Republic of Ireland and Northern Ireland.

        Parameters:
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.

        Returns:
            (pd.DataFrame): The electricity consumption data.
    """

    # obtain set of individual days within time span
    all_days = pd.date_range(
        start=start.tz_convert("Europe/Dublin"),
        end=end.tz_convert("Europe/Dublin"),
        normalize=True,
        tz="Europe/Dublin",
    )

    # start with no data
    df = None

    # iterate over all days
    for date in all_days:
        # get demand data per day
        df_new = _download_IE_demand_data(date)

        # concatenate data
        if df is None:
            df = df_new
        else:
            df = pd.concat([df, df_new])

    # only return data between specific start and end times
    return df[start:end]


def _download_IE_per_type_data(
    date: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/Dublin")
):
    # we need this complex procedure to automatically take care of leap hours
    range_start = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 00:00", tz="Europe/Dublin")
    range_end = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 23:45", tz="Europe/Dublin")
    date_range = pd.date_range(start=range_start, end=range_end, freq="15T")

    # create DataFrame with proper timestamps as index
    df = pd.DataFrame(index=date_range, columns=["Wind Onshore", "Total Generation"])

    # load wind generation and total generation
    for area, col in [
        ("windactual", "Wind Onshore"),
        ("generationactual", "Total Generation"),
    ]:
        # URL to access data
        url = f"https://www.smartgriddashboard.com/DashboardService.svc/data?area={area}&region=ALL&datefrom={date.strftime('%d-%b-%Y')}+00%3A00&dateto={date.strftime('%d-%b-%Y')}+23%3A59"

        # Make a GET request to fetch the JSON data
        response = requests.get(url, timeout=TIMEOUT)

        # Check if response was successful
        if response.status_code == 200:
            # create DataFrame from responded rows
            data = pd.DataFrame(response.json()["Rows"])

            # everything normal
            if len(date_range) == 96:
                df[col] = data["Value"].values

            # change from winter to summer time, skip empty rows
            elif len(date_range) == 92:
                df[col].iloc[:4] = data["Value"].iloc[:4].values
                df[col].iloc[4:] = data["Value"].iloc[8:].values

            # change from summer to winter time, skip ambiguous rows
            elif len(date_range) == 100:
                df[col].iloc[:4] = data["Value"].iloc[:4].values
                df[col].iloc[12:] = data["Value"].iloc[8:].values

    # calculate remaining generation
    df["Remaining"] = df["Total Generation"].values - df["Wind Onshore"].values

    # -----------------------------------------------------
    # Further calculations for individual generation types:
    # -----------------------------------------------------

    for type, share in IE_GENERATION_TYPES:
        df[type] = df["Remaining"].values * share

    # drop interim columns
    df = df.drop(labels=["Total Generation", "Remaining"], axis=1)

    return df


def _download_IE_demand_data(
    date: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/Dublin")
):
    # we need this complex procedure to automatically take care of leap hours
    range_start = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 00:00", tz="Europe/Dublin")
    range_end = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 23:45", tz="Europe/Dublin")
    date_range = pd.date_range(start=range_start, end=range_end, freq="15T")

    # create DataFrame with proper timestamps as index
    df = pd.DataFrame(index=date_range, columns=["Actual Load"])

    # URL to access data
    url = f"https://www.smartgriddashboard.com/DashboardService.svc/data?area=demandactual&region=ALL&datefrom={date.strftime('%d-%b-%Y')}+00%3A00&dateto={date.strftime('%d-%b-%Y')}+23%3A59"

    # Make a GET request to fetch the JSON data
    response = requests.get(url, timeout=TIMEOUT)

    # Check if response was successful
    if response.status_code == 200:
        # create DataFrame from responded rows
        data = pd.DataFrame(response.json()["Rows"])

        # everything normal
        if len(date_range) == 96:
            df["Actual Load"] = data["Value"].values

        # change from winter to summer time, skip empty rows
        elif len(date_range) == 92:
            df["Actual Load"].iloc[:4] = data["Value"].iloc[:4].values
            df["Actual Load"].iloc[4:] = data["Value"].iloc[8:].values

        # change from summer to winter time, skip ambiguous rows
        elif len(date_range) == 100:
            df["Actual Load"].iloc[:4] = data["Value"].iloc[:4].values
            df["Actual Load"].iloc[12:] = data["Value"].iloc[8:].values

    return df


def download_GB_IE_flows(start: pd.Timestamp, end: pd.Timestamp):
    """
    Download interconnection data between National Grid (GB) and EirGrid.

        Parameters:
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.

        Returns:
            (pd.DataFrame): The interconnection data.
    """

    # obtain set of individual days within time span
    all_days = pd.date_range(
        start=start.tz_convert("Europe/Dublin"),
        end=end.tz_convert("Europe/Dublin"),
        normalize=True,
        tz="Europe/Dublin",
    )

    # start with no data
    df = None

    # iterate over all days
    for date in all_days:
        # get interconnection data per day
        df_new = _download_GB_IE_flows(date)

        # concatenate data
        if df is None:
            df = df_new
        else:
            df = pd.concat([df, df_new])

    # only return data between specific start and end times
    return df[start:end]


def _download_GB_IE_flows(
    date: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/Dublin")
):
    # we need this complex procedure to automatically take care of leap hours
    range_start = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 00:00", tz="Europe/Dublin")
    range_end = pd.Timestamp(f"{date.strftime('%Y-%m-%d')} 23:45", tz="Europe/Dublin")
    date_range = pd.date_range(start=range_start, end=range_end, freq="15T")

    # create DataFrame with proper timestamps as index
    df = pd.DataFrame(index=date_range, columns=["Inter EWIC", "Inter Moyle"])

    # URL to access data
    url = f"https://www.smartgriddashboard.com/DashboardService.svc/data?area=interconnection&region=ALL&datefrom={date.strftime('%d-%b-%Y')}+00%3A00&dateto={date.strftime('%d-%b-%Y')}+23%3A59"

    # Make a GET request to fetch the JSON data
    response = requests.get(url, timeout=TIMEOUT)

    # Check if response was successful
    if response.status_code == 200:
        # create DataFrame from responded rows
        data = pd.DataFrame(response.json()["Rows"])

        for field, col in [
            ("INTER_EWIC", "Inter EWIC"),
            ("INTER_MOYLE", "Inter Moyle"),
        ]:
            field_data = data[data["FieldName"] == field]

            # everything normal
            if len(date_range) == 96:
                df[col] = field_data["Value"].values

            # change from winter to summer time, skip empty rows
            elif len(date_range) == 92:
                df[col].iloc[:4] = field_data["Value"].iloc[:4].values
                df[col].iloc[4:] = field_data["Value"].iloc[8:].values

            # change from summer to winter time, skip ambiguous rows
            elif len(date_range) == 100:
                df[col].iloc[:4] = field_data["Value"].iloc[:4].values
                df[col].iloc[12:] = field_data["Value"].iloc[8:].values

    # calculate total interconnection flow
    # ATTENTION: we need the conversion to numerical array, otherwise np.isnan below will produce errors
    total_flow = np.array(
        df["Inter EWIC"].values + df["Inter Moyle"].values, dtype=np.float64
    )

    # create mask for non-nan values
    mask = np.logical_not(np.isnan(total_flow))

    # create separate columns per direction of flow, but keep nan values
    df["GB > IE"] = np.where(mask, np.where(total_flow > 0, total_flow, 0), np.nan)
    df["IE > GB"] = np.where(mask, np.where(total_flow < 0, -total_flow, 0), np.nan)

    # drop original columns
    df = df.drop(labels=["Inter EWIC", "Inter Moyle"], axis=1)

    return df
