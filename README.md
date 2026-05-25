# IFB Point Dashboard

A Streamlit dashboard backed by SQLite for tracking IFB point customer leads — view customer purchase history, mark contact status, schedule follow-up appointments, and capture remarks.

## Features

- **Today's lead** — full customer list from SQLite, with inline editing for follow-up fields
- **Missed calls** — placeholder section (empty table with headers)
- **Date range filter** on Purchase Date
- **Search by Customer ID**
- **KPI cards** — Total Leads, Contacted, Interested, Pending
- **Inline editing** for Status, Next appointment, Interested/Not Interested, Remarks
- Changes persist back to SQLite on **Save**

## Tech stack

- Python 3.10+
- [Streamlit](https://streamlit.io/) — UI
- SQLite (stdlib `sqlite3`) — storage
- pandas + openpyxl — Excel ingestion

## Project structure

```
IFB point Dashboard/
├── app.py                # Streamlit application
├── seed_db.py            # One-time loader: xlsx -> SQLite
├── requirements.txt      # Python dependencies
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml       # Dark theme + brand colors
├── .claude/
│   └── launch.json       # Claude Code preview server config
└── ifb_point.db          # SQLite database (generated, gitignored)
```

## Setup

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. Seed the database (one-time)

Place the source workbook at `C:\Users\<you>\Downloads\IFB point customer dummy data.xlsx` (or update `XLSX_PATH` in `seed_db.py`), then:

```powershell
python seed_db.py
```

This creates `ifb_point.db` with the `customers` table populated. If the DB already exists the script exits without overwriting — delete the file to re-seed.

### 3. Run the dashboard

```powershell
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Database schema

Table: `customers`

| Column            | Type    | Notes                                     |
|-------------------|---------|-------------------------------------------|
| ifb_point_id      | INTEGER | Hidden in UI                              |
| customer_id       | INTEGER | Primary key                               |
| customer_name     | TEXT    |                                           |
| purchase_date     | TEXT    | ISO `yyyy-mm-dd`                          |
| machine_type      | TEXT    |                                           |
| phone_number      | TEXT    |                                           |
| email_id          | TEXT    |                                           |
| status            | TEXT    | `Contacted` / `Not Contacted` / NULL      |
| next_appointment  | TEXT    | ISO date, future only                     |
| interested        | TEXT    | `Interested` / `Not Interested` / NULL    |
| remarks           | TEXT    |                                           |

## Editing workflow

1. Filter / search to the rows you want.
2. Edit any of the 4 user-fillable columns inline:
   - **Status** — dropdown
   - **Next appointment** — date picker (today onward)
   - **Interested / Not Interested** — dropdown
   - **Remarks** — free text
3. Click **Save changes**. Only modified rows are written to SQLite.
