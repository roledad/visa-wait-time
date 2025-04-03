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
        ave_perm_processing_time_days = ave_perm_processing_time.loc[0, "Calendar Days"]

        if data_type == "PWD":
            return pwd
        elif data_type == "PERM":
            return {
                "perm review": perm_review_pd,
                "ave perm processing time": ave_perm_processing_time_asof,
                "ave perm_processing time in days": ave_perm_processing_time_days
            }
        else:
            raise ValueError("Invalid type. Must be 'PWD' or 'PERM'")


    def get_uscis_data(self):
        """Get the USCIS data from the website"""

        res = requests.get(url=ImmigrationData.USCIS_URL, timeout=10)
        try:
            soup = BeautifulSoup(res.content, "html.parser")
            child_soup = soup.find('a', class_="btn btn-lg btn-success")
            bulletin_link = child_soup.attrs['href']
            bulletin_link = "https://travel.state.gov" + bulletin_link
            print(bulletin_link)
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
            return emp_based_pd

        except requests.RequestException as e:
            print(f"Request error: {e}")
            return None


def main():

    asof_date = datetime.today().date()
    immigration_data = ImmigrationData(asof_date)
    emp_based_pd = immigration_data.get_uscis_data()
    print(emp_based_pd)
    pwd_reviews = immigration_data.get_dol_data("PWD")
    perm_reviews = immigration_data.get_dol_data("PERM")
    print(f"PWD reviews: {pwd_reviews}")
    print(perm_reviews)

if __name__ == "__main__":
    main()
