'''
Script to get the data from USCIS and DOL for the PWD, PERM, GC processing time
'''
from datetime import datetime
from typing import Union
import requests
from bs4 import BeautifulSoup
import pandas as pd

# pylint: disable=C0115
# pylint: disable=C0116
# pylint: disable=C0301

class ImmigrationData:

    DOL_URL = "https://flag.dol.gov/processingtimes"
    USCIS_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"


    def __init__(self, asof_date: Union[datetime, str]):
        self.asof_date = str(asof_date.date) if isinstance(asof_date, datetime) else asof_date

        self.emp_based_pd = self.get_uscis_data()
        self.emp_based_bulletin = self.get_uscis_data(title=True)
        self.pwd_reviews = self.get_dol_data("PWD")
        self.perm_reviews = self.get_dol_data("PERM")

    def get_dol_data(self, data_type: str):
        """Get the DOL data from the website"""
        dol_perm = pd.read_html(ImmigrationData.DOL_URL)

        pwd_h1b = dol_perm[3]
        pwd_h1b.columns = ['Receipt Month', 'Remaining Requests']
        pwd_perm = dol_perm[5]
        pwd_perm.columns = ['Receipt Month', 'Remaining Requests']

        pwd = pd.merge(pwd_h1b, pwd_perm, on="Receipt Month", how="outer", suffixes=["_hib", "_perm"])
        pwd["Receipt Month"] = pd.to_datetime(pwd["Receipt Month"], format="%B %Y").dt.strftime("%Y-%m")
        pwd = pwd.sort_values("Receipt Month", ascending=False)

        perm_review = dol_perm[6]
        perm_review_pd = perm_review[perm_review["Processing Queue"] == "Analyst Review"].loc[0, "Priority Date"]

        ave_perm_processing_time = dol_perm[7]
        ave_perm_processing_time_asof = ave_perm_processing_time.loc[0, "Month"]
        ave_perm_processing_time_days = int(ave_perm_processing_time.loc[0, "Calendar Days"])

        if data_type == "PWD":
            return pwd
        elif data_type == "PERM":
            return {
                "Perm Review PD": perm_review_pd,
                "Ave. Processing Days": ave_perm_processing_time_days,
                "Last Update": ave_perm_processing_time_asof,
            }
        else:
            raise ValueError("Invalid type. Must be 'PWD' or 'PERM'")


    def get_uscis_data(self, title: bool=False):
        """Get the USCIS data from the website"""

        res = requests.get(url=ImmigrationData.USCIS_URL, timeout=10)
        try:
            soup = BeautifulSoup(res.content, "html.parser")
            child_soup = soup.find_all('a', class_="btn btn-lg btn-success")
            if len(child_soup) == 2 and "href" in child_soup[1].attrs:
                child_soup = child_soup[1]
            else:
                child_soup = child_soup[0]

            bulletin_title = f"Visa Bulletin for {child_soup.text}"
            bulletin_link = "https://travel.state.gov" + child_soup.attrs['href']
            visa_bulltetin = pd.read_html(bulletin_link)

            cols = ['Employment-type', 'All Chargeability Areas Except Those Listed', 'CHINA-mainland born', 'INDIA', 'MEXICO', 'PHILIPPINES']
            emp_based_a = visa_bulltetin[7]
            emp_based_a.columns = cols
            emp_based_a = emp_based_a[1:].copy()
            emp_based_a["table"] = "a"

            emp_based_b = visa_bulltetin[8]
            emp_based_b.columns = cols
            emp_based_b = emp_based_b[1:].copy()
            emp_based_b["table"] = "b"

            emp_based_pd = pd.concat([emp_based_a, emp_based_b], ignore_index=True)
            for col in cols[1:6]:
                emp_based_pd[col] = pd.to_datetime(emp_based_pd[col], format="%d%b%y", errors="coerce").dt.strftime("%Y-%m-%d")
            return bulletin_title if title else emp_based_pd.sort_values("Employment-type")

        except requests.RequestException as e:
            print(f"Request error: {e}")
            return None


def main():

    asof_date = datetime.today().date()
    immigration_data = ImmigrationData(asof_date)

    print(f"{immigration_data.emp_based_bulletin}: {asof_date}")
    print(immigration_data.emp_based_pd)
    print("PWD reviews: \n", immigration_data.pwd_reviews)
    print(f"PERM reviews: {immigration_data.perm_reviews}")


if __name__ == "__main__":
    main()
