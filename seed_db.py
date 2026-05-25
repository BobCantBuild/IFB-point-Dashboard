"""One-time seed: load the IFB point customer dummy data xlsx into SQLite.

Run once:  python seed_db.py
"""
import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent / "ifb_point.db"
XLSX_PATH = Path(r"C:\Users\aswin\Downloads\IFB point customer dummy data.xlsx")

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    ifb_point_id        INTEGER,
    customer_id         INTEGER PRIMARY KEY,
    customer_name       TEXT,
    purchase_date       TEXT,         -- ISO yyyy-mm-dd
    machine_type        TEXT,
    phone_number        TEXT,
    email_id            TEXT,
    status              TEXT,         -- 'Contacted' / 'Not Contacted' / NULL
    next_appointment    TEXT,         -- ISO yyyy-mm-dd / NULL
    interested          TEXT,         -- 'Interested' / 'Not Interested' / NULL
    remarks             TEXT
);
"""

COL_MAP = {
    "IFB point ID": "ifb_point_id",
    "Customer_ID": "customer_id",
    "Customer name": "customer_name",
    "Purchase Date": "purchase_date",
    "Machine Type": "machine_type",
    "Phone number": "phone_number",
    "Email ID": "email_id",
    "Status": "status",
    "Next appointment": "next_appointment",
    "Interested/ Not Interested": "interested",
    "Remarks": "remarks",
}


def main():
    if DB_PATH.exists():
        print(f"DB already exists at {DB_PATH}. Delete it to re-seed.")
        return

    df = pd.read_excel(XLSX_PATH)
    df = df.rename(columns=COL_MAP)

    df["purchase_date"] = pd.to_datetime(
        df["purchase_date"], dayfirst=True, errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    df["next_appointment"] = pd.to_datetime(
        df["next_appointment"], dayfirst=True, errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    df["phone_number"] = df["phone_number"].astype(str)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    df.to_sql("customers", conn, if_exists="append", index=False)
    conn.commit()
    print(f"Seeded {len(df)} rows into {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
