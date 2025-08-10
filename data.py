'''
This module is for retrieving and processing the visa wait time data from the website
NOTE: The travel.state.gov website has deprecated on March 8th, 2025
'''
from datetime import datetime
import zipfile
import io
import re
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
    SIMPLEMAP_URL = "https://simplemaps.com/static/data/world-cities/basic/simplemaps_worldcities_basicv1.901.zip"
    VISA_WAIT_TIME_URL = "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/global-visa-wait-times.html"
    MISSING_CITIES = {
        "Chennai (Madras)": "Chennai",
        "Ciudad Juarez": "Juarez",
        "Curacao": "Willemstad",
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

    VISA_TYPES = {
            "H,L,O,P,Q": "Petition-Based (H,L,O,P,Q)",
            "F,M,J": "Study and Exchange (F,M,J)",
            "C,D,C1/D": "Crew and Transit (C,D,C1/D)",
            "B1/B2": "Tourism and Visit (B1/B2)"}

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

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://simplemaps.com/data/world-cities",   # helps avoid 403 on some hosts
        }
        try:
            r = requests.get(VisaWaitTimeData.SIMPLEMAP_URL, timeout=20, headers=headers, allow_redirects=True)
            ctype = (r.headers.get("Content-Type") or "").lower()
            print(f"[CITY] GET {VisaWaitTimeData.SIMPLEMAP_URL} -> {r.status_code} final={r.url} ctype={ctype} len={r.headers.get('Content-Length')}")
            # Some providers return HTML with 200; ensure it's a ZIP (or begins with 'PK')
            if r.status_code != 200 or not ("zip" in ctype or r.content[:2] == b"PK"):
                raise RuntimeError(f"Unexpected response: status={r.status_code} ctype={ctype}")

            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                names = z.namelist()
                print("[CITY] Files in ZIP:", names)
                # SimpleMaps usually has exactly this name:
                target = "worldcities.csv"
                if target not in names:
                    # fallback: first CSV in the archive
                    csvs = [n for n in names if n.lower().endswith(".csv")]
                    if not csvs:
                        raise RuntimeError("No CSV file found inside ZIP")
                    target = csvs[0]
                with z.open(target) as f:
                    df = pd.read_csv(f)
            if df is None or df.empty:
                raise RuntimeError("Loaded cities CSV is empty")
            return df

        except Exception as e:
            # Make the failure obvious and stop boot with a clear message
            raise RuntimeError(f"City ZIP load failed: {e}") from e

    def read_visa_wait_times_old(self):
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

    def read_visa_wait_times(self):

        df = pd.read_html(VisaWaitTimeData.VISA_WAIT_TIME_URL)[0]
        for col in df.columns[1:]:
            df[col] = df[col].fillna("NA")
            df[col] = df[col].str.split("month", expand=True)[0].str.strip()
            df[col] = np.where(df[col].isnull(), "NA", df[col])
            df[col] = df[col].astype("str")
            if "Average wait times" in col:
                df = df.drop(columns=col)
            else:
                visa_type = re.search(r'\((.*?)\)', col).group(1)
                df = df.rename(columns={col: VisaWaitTimeData.VISA_TYPES.get(visa_type)})

        df["asof_date"] = self.asof_date
        df["update_date"] = self.update_date
        return df

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
