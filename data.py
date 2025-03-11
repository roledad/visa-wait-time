'''
This module is for retrieving and processing the visa wait time data from the website
NOTE: The travel.state.gov website has deprecated on March 8th, 2025
'''
from datetime import datetime
import zipfile
import io
from typing import Union
import requests
from bs4 import BeautifulSoup

import numpy as np
import pandas as pd

# pylint: disable=C0116
# pylint: disable=C0301

class VisaWaitTimeData:
    """Class to retrieve and process the visa wait time data"""
    # URL of the ZIP file containing the world cities data
    SIMPLEMAP_URL = "https://simplemaps.com/static/data/world-cities/basic/simplemaps_worldcities_basicv1.77.zip"
    VISA_WAIT_TIME_URL = "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/global-visa-wait-times.html"
    MISSING_CITIES = {
        "Chennai ( Madras)": "Chennai",
        "Ciudad Juarez": "Ciudad Juarez",
        "Curacao": "Curacao",
        "Dar Es Salaam": "Dar es Salaam",
        "Kuwait": "Kuwait City",
        "Mexicali Tpf": "Mexicali",
        "Mumbai (Bombay)": "Mumbai",
        "N`Djamena": "N'Djamena",
        "Osaka/Kobe": "Osaka",
        "Port Au Prince": "Port-au-Prince",
        "Port Of Spain": "Port of Spain",
        "Quebec": "Quebec City",
        "Rio De Janeiro": "Rio de Janeiro",
        "St Georges": "Saint-Georges",
        "St Petersburg": "Saint Petersburg",
        "Tel Aviv": "Tel Aviv-Yafo",
        "Tijuana Tpf": "Tijuana",
        "Usun-New York": "New York",
        "Washington Refugee Processing Center": "Washington"
    }

    def __init__(self, asof_date: Union[datetime, str]):
        self.asof_date = str(asof_date.date) if isinstance(asof_date, datetime) else asof_date
        self.update_date = None
        # get the update date
        res = requests.get(VisaWaitTimeData.VISA_WAIT_TIME_URL, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "html.parser")
            child_soup = soup.find('div', class_="tsg-rwd-text parbase section")
            update_date = child_soup.find('p').text.strip().split("Last updated:")[1].strip()
            self.update_date = pd.to_datetime(update_date).strftime("%Y-%m-%d")

    def read_world_cities(self):
        """Read the world cities data from the ZIP file"""

        response = requests.get(VisaWaitTimeData.SIMPLEMAP_URL, timeout=10)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                file_names = z.namelist()   # List files in the ZIP
                print("Files in SIMPLEMAP ZIP:", file_names)

                csv_filename = "worldcities.csv"
                if csv_filename in file_names:  # Ensure this matches the exact file name
                    with z.open(csv_filename) as f:
                        df = pd.read_csv(f)
                        return df
                else:
                    print(f"{csv_filename} not found in ZIP.")
                    return None
        else:
            print("Failed to download ZIP file")
            return None

    def read_visa_wait_times(self):
        """Read the visa wait times data from the website"""

        df = pd.read_html(VisaWaitTimeData.VISA_WAIT_TIME_URL)[0]
        # clean the data on the table
        for col in df.columns[1:]:
            df[col] = df[col].fillna("")
            df[col] = df[col].where(~df[col].str.contains("Same Day"), "0 Day")
            str_time = "Closed|Non-Visa Processing Post|Emergency Appointments Only"
            df[col] = df[col].where(~df[col].str.contains(str_time), np.nan)
            # extract the number of days
            df[col] = df[col].str.split("Day", expand=True)[0].str.strip()
            df[col] = np.where(df[col] == "", np.nan, df[col])
            df[col] = df[col].astype("float")

        df["asof_date"] = self.asof_date
        df["update_date"] = self.update_date

        for col in df.columns:
            if "Interview Required" in col:
                df = df.rename(columns={col: col.split("Interview Required")[1].strip()})

        return df[["asof_date", "update_date"] + [col for col in df.columns if col not in ["asof_date", "update_date"]]]

    @staticmethod
    def select_dup_cities(city_df: pd.DataFrame, cities: list):
        "select the country of the city with the most population"

        city_countries_df = pd.DataFrame()
        for city in cities:
            df_city = city_df[city_df["city_ascii"] == city].copy()
            df_city = df_city.sort_values(by="population", ascending=False)
            city_countries_df = pd.concat([city_countries_df, df_city.head(1)], axis=0)
        city_countries_df = city_countries_df.reset_index(drop=True)

        return city_countries_df


    def map_city_country(self, city_df: pd.DataFrame, visa_df: pd.DataFrame):
        "map the cities in visa wait time data with the country in world cities data"

        # first pass of the city mapping
        city_countries_df = VisaWaitTimeData.select_dup_cities(city_df, visa_df["City/Post"].unique())
        df = visa_df.merge(
            city_countries_df[["country", "city_ascii", "iso2", "lat", "lng"]],
            left_on="City/Post", right_on="city_ascii", how="left")

        # second pass of unmapped cities
        null_df = df[df["country"].isnull()].drop(columns=["country", "city_ascii", "iso2", "lat", "lng"])
        null_df["city_ascii"] = null_df["City/Post"].map(VisaWaitTimeData.MISSING_CITIES)
        city_countries_df = VisaWaitTimeData.select_dup_cities(city_df, null_df["city_ascii"].unique())
        null_df = null_df.merge(
            city_countries_df[["country", "city_ascii", "iso2", "lat", "lng"]], on="city_ascii", how="left")
        df = pd.concat([df[df["country"].notnull()], null_df]).reset_index(drop=True)

        null_df = df[df["country"].isnull()]
        if not null_df.empty:
            print("Unmapped cities:", null_df["City/Post"].unique())

        return df[df["country"].notnull()]


def main():

    asof_date = datetime.today().date()
    visa_wait_data = VisaWaitTimeData(asof_date)
    city_df = visa_wait_data.read_world_cities()
    visa_df = visa_wait_data.read_visa_wait_times()
    df = visa_wait_data.map_city_country(city_df, visa_df)
    print(df.head())

if __name__ == "__main__":
    main()
