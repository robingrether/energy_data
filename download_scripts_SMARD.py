"""
Script for loading electricity generation and consumption data for Germany from the SMARD API.

Author: Robin L. Grether

License: MIT License
"""

import os
import re
import time

import numpy as np
import pandas as pd
import requests

# timeout for API calls (in seconds)
TIMEOUT = 60

DE_GENERATION_TYPES = {
    ("Biomass", "Actual Aggregated"): "4066",  # alternative: 103
    ("Fossil Brown coal/Lignite", "Actual Aggregated"): "1223",  # alternative: 110
    ("Fossil Gas", "Actual Aggregated"): "4071",  # alternative: 112
    ("Fossil Hard coal", "Actual Aggregated"): "4069",  # alternative: 111
    ("Fossil Oil", "Actual Aggregated"): "115",
    ("Geothermal", "Actual Aggregated"): "105",
    ("Hydro Pumped Storage", "Actual Aggregated"): "4070",  # alternative: 113
    ("Hydro Pumped Storage", "Actual Consumption"): "4387",
    ("Hydro Run-of-river and poundage", "Actual Aggregated"): "104",
    ("Hydro Water Reservoir", "Actual Aggregated"): "118",
    ("Nuclear", "Actual Aggregated"): "1224",
    ("Other", "Actual Aggregated"): "119",
    ("Other renewable", "Actual Aggregated"): "107",
    ("Solar", "Actual Aggregated"): "4068",  # alternative: 102
    ("Waste", "Actual Aggregated"): "120",
    ("Wind Offshore", "Actual Aggregated"): "1225",  # alternative: 101
    ("Wind Onshore", "Actual Aggregated"): "4067",  # alternative: 100
}

DE_RESOURCE_MAPPINGS = {
    "KW-Energieträger.Wind (Onshore)": "Wind Onshore",
    "KW-Energieträger.Steinkohle": "Fossil Hard coal",
    "KW-Energieträger.Erdgas": "Fossil Gas",
    "KW-Energieträger.Pumpspeicher": "Hydro Pumped Storage",
    "KW-Energieträger.Sonstige konventionelle Energieträger": "Other",
    "KW-Energieträger.Photovoltaik": "Solar",
    "KW-Energieträger.Wind (Offshore)": "Wind Offshore",
    "KW-Energieträger.Laufwasser": "Hydro Run-of-river and poundage",
    "KW-Energieträger.Mineralölprodukte": "Fossil Oil",
    "KW-Energieträger.Abfall": "Waste",
    "KW-Energieträger.Kernenergie": "Nuclear",
    "KW-Energieträger.Braunkohle": "Fossil Brown coal/Lignite",
    "KW-Energieträger.Speicherwasser (ohne Pumpspeicher)": "Hydro Water Reservoir",
    "KW-Energieträger.Batteriespeicher": "Battery Storage",
    "KW-Energieträger.Biomasse": "Biomass",
    "KW-Energieträger.Wärme": "unknown",
    "KW-Energieträger.Wasserkraft": "Hydro",
}

DE_POWER_PLANT_LIST_PATH = "smard_power_plant_list.csv"
DE_POWER_PLANT_LIST_UPDATE_FREQ = 4 * 7 * 24 * 60 * 60
DE_POWER_PLANT_LIST = None

# bidding zones for day ahead prices query
BZ_DE_AT_LU = {
    "Name": "DE_AT_LU",
    "API ID": "251",
}  # Germany-Austria-Luxembourg: data available from 2015-01-05 to 2018-09-30
BZ_DE_LU = {
    "Name": "DE_LU",
    "API ID": "4169",
}  # Germany-Luxembourg: data available as of 2018-10-01
BZ_DE_LU_NEIGHBORS = {
    "Name": "DE_LU_NEIGHBORS",
    "API ID": "5078",
}  # average of all neighboring bidding zones of DE_LU: data available as of 2019-11-20
BZ_BE = {"Name": "BE", "API ID": "4996"}  # Belgium
BZ_NO_2 = {"Name": "NO_2", "API ID": "4997"}  # Norway: bidding zone #2 (south-west)
BZ_AT = {"Name": "AT", "API ID": "4170"}  # Austria: data available as of 2018-10-01
BZ_DK_1 = {"Name": "DK_1", "API ID": "252"}  # Denmark: bidding zone #1 (west)
BZ_DK_2 = {"Name": "DK_2", "API ID": "253"}  # Denmark: bidding zone #2 (east)
BZ_FR = {"Name": "FR", "API ID": "254"}  # France
BZ_IT_NORTH = {"Name": "IT_NORTH", "API ID": "255"}  # Italy: bidding zone north
BZ_NL = {"Name": "NL", "API ID": "256"}  # Netherlands
BZ_PL = {"Name": "PL", "API ID": "257"}  # Poland
BZ_SE_4 = {"Name": "SE_4", "API ID": "258"}  # Sweden: bidding zone #4 (south)
BZ_CH = {"Name": "CH", "API ID": "259"}  # Switzerland
BZ_SI = {"Name": "SI", "API ID": "260"}  # Slovenia
BZ_CZ = {"Name": "CZ", "API ID": "261"}  # Czechia
BZ_HU = {"Name": "HU", "API ID": "262"}  # Hungary


def download_day_ahead_prices(
    bidding_zone: dict, start: pd.Timestamp, end: pd.Timestamp
):
    """
    Download day-ahead electricity prices from the SMARD API.

        Parameters:
            bidding_zone (dict): Must be one of the above values called BZ_{name of bidding zone}.
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.

        Returns:
            (pd.DataFrame): The day-ahead electricity prices.

        Example:
            `download_day_ahead_prices(BZ_DE_LU, pd.Timestamp("2023-09-18", tz="Europe/Berlin"), pd.Timestamp("2023-09-18 23:59", tz="Europe/Berlin"))`
    """

    # convert time stamps
    start = start.tz_convert("Europe/Berlin")
    end = end.tz_convert("Europe/Berlin")

    # find weeks
    weeks = pd.date_range(
        start=(start - pd.Timedelta(weeks=1)).normalize(),
        end=end,
        freq="W-MON",
        tz="Europe/Berlin",
    )

    # remove 0th element if not needed
    if (len(weeks) > 1) and (weeks[1] <= start):
        weeks = weeks[1:]

    # start with no data
    df = None

    # iterate over all weeks
    for week in weeks:
        # get demand data per week
        data = _download_day_ahead_prices(bidding_zone, week)

        # concatenate data
        if df is None:
            df = data
        else:
            df = pd.concat([df, data])

    # only return data between specified start and end times
    return df[start:end]


def _download_day_ahead_prices(
    bidding_zone: dict,
    week: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/Berlin"),
):
    # convert time stamps
    week = week.tz_convert("Europe/Berlin")

    # URL to access demand data
    url = f"https://www.smard.de/app/chart_data/{bidding_zone['API ID']}/DE/{bidding_zone['API ID']}_DE_hour_{int(week.value // 1e6)}.json"

    # Make a GET request to fetch the json data
    response = requests.get(url, timeout=TIMEOUT)

    # Check if the request was successful
    if response.status_code == 200:
        # create DataFrame from responded json
        data = pd.DataFrame(
            response.json()["series"], columns=["timestamp", bidding_zone["Name"]]
        )

        # convert timestamps to pandas and set as index
        data["timestamp"] = pd.to_datetime(
            data["timestamp"].values, unit="ms", utc=True
        ).tz_convert("Europe/Berlin")
        data = data.set_index("timestamp")

        # return
        return data


def download_DE_per_type_data(start: pd.Timestamp, end: pd.Timestamp, nett=False):
    """
    Download per type electricity generation data for Germany from the SMARD API.

        Parameters:
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.
            nett (bool): If true, generation and consumption data for each type is aggregated into a net generation series. (Only affects Hydro Pumped Storage.)

        Returns:
            (pd.DataFrame): The per type electricity generation data.
    """

    # convert time stamps
    start = start.tz_convert("Europe/Berlin")
    end = end.tz_convert("Europe/Berlin")

    # find weeks
    weeks = pd.date_range(
        start=(start - pd.Timedelta(weeks=1)).normalize(),
        end=end,
        freq="W-MON",
        tz="Europe/Berlin",
    )

    # remove 0th element if not needed
    if (len(weeks) > 1) and (weeks[1] <= start):
        weeks = weeks[1:]

    # start with no data
    df = None

    # iterate over all weeks
    for week in weeks:
        # get generation data per week
        data = _download_DE_per_type_data(week)

        # concatenate data
        if df is None:
            df = data
        else:
            df = pd.concat([df, data])

    # sum generation and consumption for each type
    if nett:
        # create new DataFrame for aggregation
        df_agg = pd.DataFrame(index=df.index)

        # iterate over all columns
        for column in df.columns:
            data = df[column]
            # treat consumption as negatives
            if "consumption" in str(column).lower():
                data *= -1

            # add new column or add values
            if column[0] not in df_agg.columns:
                df_agg[column[0]] = data
            else:
                df_agg[column[0]] += data

        df = df_agg

    # keep generation and consumption separate
    else:
        # convert columns to a MultiIndex
        df.columns = pd.MultiIndex.from_tuples(df.columns)

    # only return data between specified start and end times
    return df[start:end]


def _download_DE_per_type_data(
    week: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/Berlin")
):
    # convert time stamps
    week = week.tz_convert("Europe/Berlin")

    # start with no data
    df = None

    # iterate over all generation types
    for resource, tableId in DE_GENERATION_TYPES.items():
        # URL to access per type generation
        url = f"https://www.smard.de/app/chart_data/{tableId}/DE/{tableId}_DE_quarterhour_{int(week.value // 1e6)}.json"

        # Make a GET request to fetch the json data
        response = requests.get(url, timeout=TIMEOUT)

        # Check if the request was successful
        if response.status_code == 200:
            # create DataFrame from responded json
            data = pd.DataFrame(
                response.json()["series"], columns=["timestamp", resource]
            )

            # convert timestamps to pandas and set as index
            data["timestamp"] = pd.to_datetime(
                data["timestamp"].values, unit="ms", utc=True
            ).tz_convert("Europe/Berlin")
            data = data.set_index("timestamp")

            # concatenate data
            if df is None:
                df = data
            else:
                df = pd.concat([df, data], axis=1)

    # return and convert MWh -> MW
    return df * 4


def download_DE_demand_data(start: pd.Timestamp, end: pd.Timestamp):
    """
    Download electricity consumption data for Germany from the SMARD API.

        Parameters:
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.

        Returns:
            (pd.DataFrame): The electricity consumption data.
    """

    # convert time stamps
    start = start.tz_convert("Europe/Berlin")
    end = end.tz_convert("Europe/Berlin")

    # find weeks
    weeks = pd.date_range(
        start=(start - pd.Timedelta(weeks=1)).normalize(),
        end=end,
        freq="W-MON",
        tz="Europe/Berlin",
    )

    # remove 0th element if not needed
    if (len(weeks) > 1) and (weeks[1] <= start):
        weeks = weeks[1:]

    # start with no data
    df = None

    # iterate over all weeks
    for week in weeks:
        # get demand data per week
        data = _download_DE_demand_data(week)

        # concatenate data
        if df is None:
            df = data
        else:
            df = pd.concat([df, data])

    # only return data between specified start and end times
    return df[start:end]


def _download_DE_demand_data(
    week: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/Berlin")
):
    # convert time stamps
    week = week.tz_convert("Europe/Berlin")

    # URL to access demand data
    url = f"https://www.smard.de/app/chart_data/410/DE/410_DE_quarterhour_{int(week.value // 1e6)}.json"

    # Make a GET request to fetch the json data
    response = requests.get(url, timeout=TIMEOUT)

    # Check if the request was successful
    if response.status_code == 200:
        # create DataFrame from responded json
        data = pd.DataFrame(
            response.json()["series"], columns=["timestamp", "Actual Load"]
        )

        # convert timestamps to pandas and set as index
        data["timestamp"] = pd.to_datetime(
            data["timestamp"].values, unit="ms", utc=True
        ).tz_convert("Europe/Berlin")
        data = data.set_index("timestamp")

        # return and convert MWh -> MW
        return data * 4


def download_DE_per_unit_data(start: pd.Timestamp, end: pd.Timestamp):
    """
    Download per unit electricity generation data for Germany from the SMARD API.

        Parameters:
            start (pd.Timestamp): Beginning of required time span.
            end (pd.Timestamp): End of required time span.

        Returns:
            (pd.DataFrame): The per unit electricity generation data.
    """

    # convert time stamps
    start = start.tz_convert("Europe/Berlin")
    end = end.tz_convert("Europe/Berlin")

    # find weeks
    weeks = pd.date_range(
        start=(start - pd.Timedelta(weeks=1)).normalize(),
        end=end,
        freq="W-MON",
        tz="Europe/Berlin",
    )

    # remove 0th element if not needed
    if (len(weeks) > 1) and (weeks[1] <= start):
        weeks = weeks[1:]

    # start with no data
    df = None

    # iterate over all weeks
    for week in weeks:
        # get generation data per week
        data = _download_DE_per_unit_data(week)

        # concatenate data
        if df is None:
            df = data
        else:
            df = pd.concat([df, data])

    # convert columns to a MultiIndex
    df.columns = pd.MultiIndex.from_tuples(df.columns)

    # only return data between specified start and end times
    return df[start:end]


def _download_DE_per_unit_data(
    week: pd.Timestamp = pd.Timestamp("2023-09-18", tz="Europe/Berlin")
):
    # convert time stamps
    week = week.tz_convert("Europe/Berlin")

    # start with no data
    df = None

    # iterate over all power plants
    for _, plant in DE_POWER_PLANT_LIST.iterrows():
        # skip future plants
        if plant["Commissioning"] > (week.year + 1):
            continue

        # skip decommissioned plants
        if plant["Decommissioning"] < week.year:
            continue

        tableId = plant["API ID"]
        region = plant["Control Area"]

        # URL to access per unit generation
        url = f"https://www.smard.de/app/chart_data/{tableId}/{region}/{tableId}_{region}_quarterhour_{int(week.value // 1e6)}.json"

        # Make a GET request to fetch the json data
        response = requests.get(url, timeout=TIMEOUT)

        # Check if the request was successful
        if response.status_code == 200:
            # create DataFrame from responded json
            data = pd.DataFrame(
                response.json()["series"],
                columns=[
                    "timestamp",
                    (
                        plant["Power Plant Name"],
                        plant["Type"],
                        plant["Block Name"],
                        plant["EIC"],
                        plant["Control Area"],
                    ),
                ],
            )

            # convert timestamps to pandas and set as index
            data["timestamp"] = pd.to_datetime(
                data["timestamp"].values, unit="ms", utc=True
            ).tz_convert("Europe/Berlin")
            data = data.set_index("timestamp")

            # concatenate data
            if df is None:
                df = data
            else:
                df = pd.concat([df, data], axis=1)

    # return and convert MWh -> MW
    return df * 4


def _update_DE_power_plant_list():
    # check last update
    if (not os.path.isfile(DE_POWER_PLANT_LIST_PATH)) or (
        time.time() - os.path.getmtime(DE_POWER_PLANT_LIST_PATH)
        >= DE_POWER_PLANT_LIST_UPDATE_FREQ
    ):
        lang = None

        # URL to access language data (power plant names etc.)
        url = "https://www.smard.de/app/assets/translations/lang-de.json"
        response = requests.get(url, timeout=TIMEOUT)

        # check if the request was successful
        if response.status_code == 200:
            # parse json lang data
            lang = response.json()
        else:
            # return if the request failed
            return

        # URL to access the power plant list
        url = "https://www.smard.de/app/power_plant_data/power_plant_metadata.json"
        response = requests.get(url, timeout=TIMEOUT)

        # Check if the request was successful
        if response.status_code == 200:
            # create empty array to collect data
            data = []

            # create regex for year
            year_regex = re.compile("([0-9]{4})")

            # collect properties of all plants
            for plant in response.json()["plants"]:
                # collect properties of all blocks
                for block in plant["blocks"]:
                    # skip blocks that are not present in SMARD API
                    if block["productionId"] is None:
                        continue

                    # check for SEE
                    if "SEE" in block["id"]:
                        see = block["id"]
                    else:
                        see = " "

                    # check power plant name
                    if plant["name"] in lang:
                        power_plant_name = lang[plant["name"]]
                    else:
                        power_plant_name = " "

                    # check block name
                    if block["name"] in lang:
                        block_name = lang[block["name"]]
                    else:
                        block_name = " "

                    # check city
                    if plant["city"] in lang:
                        city = lang[plant["city"]]
                    else:
                        city = " "

                    # check type
                    if plant["resource"] in DE_RESOURCE_MAPPINGS:
                        resource = DE_RESOURCE_MAPPINGS[plant["resource"]]
                    else:
                        resource = " "

                    # check commissioning
                    if isinstance(block["commissioning"], int):
                        commissioning = block["commissioning"]
                    else:
                        match = year_regex.search(block["commissioning"])
                        if match is not None:
                            # we need float because int does not support inf
                            commissioning = float(match.group(1))
                        else:
                            commissioning = -np.inf

                    # check decommissioning
                    match = year_regex.search(block["status"])
                    if match is not None:
                        # we need float because int does not support inf
                        decommissioning = float(match.group(1))
                    else:
                        decommissioning = np.inf

                    # append to data array
                    data.append(
                        [
                            block["blockNumber"],
                            block["blockCode"],
                            see,
                            power_plant_name,
                            block_name,
                            plant["company"],
                            city,
                            plant["postalCode"],
                            plant["address"],
                            float(plant["coordinates"][0]),
                            float(plant["coordinates"][1]),
                            resource,
                            float(block["power"]),
                            plant["regionId"],
                            block["productionId"],
                            commissioning,
                            decommissioning,
                        ]
                    )

            # create power plant DataFrame
            power_plants = pd.DataFrame(
                data=data,
                columns=[
                    "BNA",
                    "EIC",
                    "SEE",
                    "Power Plant Name",
                    "Block Name",
                    "Company",
                    "City",
                    "Postal Code",
                    "Address",
                    "Latitude",
                    "Longitude",
                    "Type",
                    "Capacity",
                    "Control Area",
                    "API ID",
                    "Commissioning",
                    "Decommissioning",
                ],
            )

            # merge duplicates (sum up power, concat the resource string)
            power_plants = (
                power_plants.groupby("API ID")
                .agg(
                    {
                        "BNA": "first",
                        "EIC": "first",
                        "SEE": "first",
                        "Power Plant Name": "first",
                        "Block Name": "first",
                        "Company": "first",
                        "City": "first",
                        "Postal Code": "first",
                        "Address": "first",
                        "Latitude": "first",
                        "Longitude": "first",
                        "Type": "first",
                        "Capacity": "sum",
                        "Control Area": "first",
                        "Commissioning": "first",
                        "Decommissioning": "first",
                    }
                )
                .reset_index()
            )

            # save power plant list to csv
            power_plants.to_csv(DE_POWER_PLANT_LIST_PATH)

    # check if file exists
    if os.path.isfile(DE_POWER_PLANT_LIST_PATH):
        # read power plant list
        global DE_POWER_PLANT_LIST
        DE_POWER_PLANT_LIST = pd.read_csv(DE_POWER_PLANT_LIST_PATH, index_col=0)


_update_DE_power_plant_list()
