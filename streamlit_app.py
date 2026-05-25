"""IFB point Dashboard — Streamlit UI backed by SQLite."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "ifb_point.db"

DISPLAY_COLS = [
    "customer_id", "customer_name", "purchase_date", "machine_type",
    "phone_number", "email_id", "status", "next_appointment",
    "interested", "remarks",
]

COL_LABELS = {
    "customer_id": "Customer ID",
    "customer_name": "Customer name",
    "purchase_date": "Purchase Date",
    "machine_type": "Machine Type",
    "phone_number": "Phone number",
    "email_id": "Email ID",
    "status": "Status",
    "next_appointment": "Next appointment",
    "interested": "Interested / Not Interested",
    "remarks": "Remarks",
}

STATUS_OPTIONS = ["Contacted", "Not Contacted"]
INTEREST_OPTIONS = ["Interested", "Not Interested"]

SAMPLE_DATA = [
    (56372, 1449, "Kavin", "2019-04-25", "IFB TL-RCG 6.5kg Aqua - TL", "9950313198", "user2@example.com", None, None, None, None),
    (56372, 6112, "Sneha", "2019-06-30", "IFB Microwave Oven 30BRC2 - Microwave Oven", "9327108127", "user3@example.com", None, None, None, None),
    (56372, 4707, "Anu", "2019-09-04", "IFB Executive Plus ZXB - FL", "9910237661", "user4@example.com", None, None, None, None),
    (56372, 3738, "Meena", "2019-11-09", "IFB Turbo Dry MX - Dryer", "9603033340", "user5@example.com", None, None, None, None),
    (56372, 3029, "Rahul", "2020-01-14", "IFB Senator Plus SX - FL", "9307727705", "user6@example.com", None, None, None, None),
]

# --------------------------------------------------------------------------- #
# Data layer
# --------------------------------------------------------------------------- #
def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def load_all() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM customers", conn)
    df["purchase_date"] = pd.to_datetime(df["purchase_date"], errors="coerce").dt.date
    df["next_appointment"] = pd.to_datetime(df["next_appointment"], errors="coerce").dt.date
    return df


def update_row(customer_id, status, next_appt, interested, remarks):
    next_appt_str = next_appt.isoformat() if isinstance(next_appt, date) else None
    with get_conn() as conn:
        conn.execute(
            """UPDATE customers
               SET status=?, next_appointment=?, interested=?, remarks=?
               WHERE customer_id=?""",
            (status, next_appt_str, interested, remarks, customer_id),
        )
        conn.commit()


def _norm(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    return v


def diff_and_save(original: pd.DataFrame, edited: pd.DataFrame) -> int:
    editable = ["status", "next_appointment", "interested", "remarks"]
    o = original.set_index("customer_id")
    e = edited.set_index("customer_id")
    n = 0
    for cid, row in e.iterrows():
        if cid not in o.index:
            continue
        orig = o.loc[cid]
        if any(_norm(row[c]) != _norm(orig[c]) for c in editable):
            update_row(
                int(cid),
                row["status"] if pd.notna(row["status"]) else None,
                row["next_appointment"] if pd.notna(row["next_appointment"]) else None,
                row["interested"] if pd.notna(row["interested"]) else None,
                row["remarks"] if pd.notna(row["remarks"]) else None,
            )
            n += 1
    return n


# --------------------------------------------------------------------------- #
# Page setup + CSS
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="IFB Point Dashboard", layout="wide", page_icon=":bar_chart:")

CSS = """
<style>
  /* ----- Global ----- */
  .stApp { background: radial-gradient(1200px 600px at 10% -10%, #1a1f3a 0%, #0b1020 55%, #07091a 100%); }
  .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px; }
  header[data-testid="stHeader"] { background: transparent; }
  #MainMenu, footer { visibility: hidden; }

  /* ----- Hero ----- */
  .hero {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 45%, #ec4899 100%);
    border-radius: 18px;
    padding: 22px 28px;
    color: #fff;
    box-shadow: 0 10px 40px rgba(99,102,241,0.25);
    margin-bottom: 18px;
  }
  .hero h1 { margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.3px; }
  .hero p  { margin: 4px 0 0; opacity: 0.92; font-size: 14px; }
  .hero .pill {
    display: inline-block; padding: 4px 10px; border-radius: 999px;
    background: rgba(255,255,255,0.18); font-size: 12px; font-weight: 600;
    margin-left: 8px; backdrop-filter: blur(6px);
  }

  /* ----- KPI cards ----- */
  .kpi {
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015));
    border: 1px solid rgba(148,163,184,0.15);
    border-radius: 14px;
    padding: 16px 18px;
    height: 100%;
    transition: transform .15s ease, border-color .15s ease;
  }
  .kpi:hover { transform: translateY(-2px); border-color: rgba(139,92,246,0.55); }
  .kpi .label { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
  .kpi .value { font-size: 30px; font-weight: 800; margin-top: 6px; color: #f8fafc; }
  .kpi .sub   { font-size: 12px; color: #64748b; margin-top: 4px; }
  .kpi.k-total .value   { background: linear-gradient(90deg,#60a5fa,#a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .kpi.k-contacted .value { color: #34d399; }
  .kpi.k-interested .value { color: #f472b6; }
  .kpi.k-pending .value  { color: #fbbf24; }

  /* ----- Panel ----- */
  .panel {
    background: rgba(21,27,48,0.55);
    border: 1px solid rgba(148,163,184,0.12);
    border-radius: 14px;
    padding: 16px 18px 6px;
    margin-bottom: 14px;
    backdrop-filter: blur(8px);
  }
  .panel .ttl { font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700; margin-bottom: 6px; }

  /* ----- Section selector (radio as pills) ----- */
  div[role="radiogroup"] {
    gap: 8px !important;
    background: rgba(15,23,42,0.6);
    padding: 6px;
    border-radius: 12px;
    border: 1px solid rgba(148,163,184,0.12);
    width: fit-content;
  }
  div[role="radiogroup"] > label {
    background: transparent;
    border-radius: 8px;
    padding: 8px 16px !important;
    margin: 0 !important;
    cursor: pointer;
    transition: all .15s ease;
    color: #cbd5e1;
  }
  div[role="radiogroup"] > label:hover { background: rgba(139,92,246,0.12); }
  div[role="radiogroup"] > label[data-checked="true"],
  div[role="radiogroup"] > label:has(input:checked) {
    background: linear-gradient(135deg,#6366f1,#8b5cf6) !important;
    color: #fff !important;
    box-shadow: 0 6px 18px rgba(99,102,241,0.35);
  }
  div[role="radiogroup"] > label > div:first-child { display: none !important; }

  /* ----- Inputs ----- */
  div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background: rgba(15,23,42,0.6) !important;
    border-radius: 10px !important;
    border: 1px solid rgba(148,163,184,0.15) !important;
  }
  .stDateInput > div > div { background: rgba(15,23,42,0.6) !important; border-radius: 10px !important; }

  /* ----- Buttons ----- */
  .stButton > button {
    background: linear-gradient(135deg,#22c55e,#16a34a);
    color: #fff; border: 0; border-radius: 10px;
    padding: 10px 22px; font-weight: 700; letter-spacing: 0.3px;
    box-shadow: 0 8px 22px rgba(34,197,94,0.30);
    transition: transform .12s ease, box-shadow .12s ease;
  }
  .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 10px 26px rgba(34,197,94,0.42); }

  /* ----- Data editor ----- */
  div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(148,163,184,0.15);
    box-shadow: 0 10px 30px rgba(0,0,0,0.25);
  }

  /* ----- Section subheader ----- */
  .sec {
    display: flex; align-items: center; gap: 10px;
    margin: 6px 0 10px;
  }
  .sec .dot { width: 10px; height: 10px; border-radius: 999px; background: linear-gradient(135deg,#22d3ee,#8b5cf6); box-shadow: 0 0 12px rgba(139,92,246,0.6); }
  .sec h3 { margin: 0; font-size: 18px; font-weight: 700; color: #f1f5f9; }
  .sec .badge { font-size: 11px; padding: 2px 10px; border-radius: 999px; background: rgba(139,92,246,0.18); color: #c4b5fd; font-weight: 600; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

@st.cache_resource
def init_db_if_missing():
    """Create and seed DB on first run if missing. For Streamlit Cloud."""
    if DB_PATH.exists():
        return
    try:
        from seed_db import SCHEMA, COL_MAP
        excel_path = Path(r"C:\Users\aswin\Downloads\IFB point customer dummy data.xlsx")
        if excel_path.exists():
            df = pd.read_excel(excel_path)
            df = df.rename(columns=COL_MAP)
            df["purchase_date"] = pd.to_datetime(df["purchase_date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
            df["next_appointment"] = pd.to_datetime(df["next_appointment"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
            df["phone_number"] = df["phone_number"].astype(str)
            conn = sqlite3.connect(DB_PATH)
            conn.executescript(SCHEMA)
            df.to_sql("customers", conn, if_exists="append", index=False)
            conn.commit()
            conn.close()
            return
    except Exception:
        pass
    # Fallback: use sample data (for Streamlit Cloud)
    SCHEMA = """CREATE TABLE IF NOT EXISTS customers (
        ifb_point_id INTEGER, customer_id INTEGER PRIMARY KEY, customer_name TEXT,
        purchase_date TEXT, machine_type TEXT, phone_number TEXT, email_id TEXT,
        status TEXT, next_appointment TEXT, interested TEXT, remarks TEXT);"""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.executemany(
        """INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?)""", SAMPLE_DATA
    )
    conn.commit()
    conn.close()

init_db_if_missing()

if not DB_PATH.exists():
    st.error("Database not initialized. Local: run `python seed_db.py`. Cloud: ensure Excel file is accessible.")
    st.stop()

df_all = load_all()
today = date.today()

# --------------------------------------------------------------------------- #
# Hero
# --------------------------------------------------------------------------- #
st.markdown(
    f"""
    <div class="hero">
      <h1>IFB Point Dashboard <span class="pill">Live</span></h1>
      <p>Today's leads &nbsp;·&nbsp; {today.strftime('%A, %d %B %Y')}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# KPI row
# --------------------------------------------------------------------------- #
total = len(df_all)
contacted = int((df_all["status"] == "Contacted").sum())
interested = int((df_all["interested"] == "Interested").sum())
pending = int(df_all["status"].isna().sum() + (df_all["status"] == "Not Contacted").sum())

k1, k2, k3, k4 = st.columns(4)
for col, cls, label, value, sub in [
    (k1, "k-total",      "Total Leads",  total,      "in database"),
    (k2, "k-contacted",  "Contacted",    contacted,  f"{(contacted/total*100 if total else 0):.0f}% of total"),
    (k3, "k-interested", "Interested",   interested, "marked interested"),
    (k4, "k-pending",    "Pending",      pending,    "awaiting contact"),
]:
    col.markdown(
        f"""<div class="kpi {cls}">
              <div class="label">{label}</div>
              <div class="value">{value}</div>
              <div class="sub">{sub}</div>
            </div>""",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Filter panel
# --------------------------------------------------------------------------- #
st.markdown('<div class="panel"><div class="ttl">Filters</div>', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([1.2, 1.4, 1.4])

with fc1:
    section = st.radio(
        "Section",
        ["Today's lead", "Missed calls"],
        horizontal=True,
        label_visibility="collapsed",
    )

with fc2:
    min_pd = df_all["purchase_date"].dropna().min() or date(2019, 1, 1)
    max_pd = df_all["purchase_date"].dropna().max() or today
    date_range = st.date_input(
        "Purchase Date range",
        value=(min_pd, max_pd),
        min_value=min_pd,
        max_value=max_pd,
    )

with fc3:
    search_id = st.text_input("Search by Customer ID", placeholder="e.g. 1449")

st.markdown("</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Filter & display
# --------------------------------------------------------------------------- #
if section == "Missed calls":
    filtered = df_all.iloc[0:0].copy()
else:
    filtered = df_all.copy()
    if isinstance(date_range, tuple) and len(date_range) == 2:
        d_from, d_to = date_range
        filtered = filtered[filtered["purchase_date"].between(d_from, d_to)]
    if search_id.strip():
        try:
            cid = int(search_id.strip())
            filtered = filtered[filtered["customer_id"] == cid]
        except ValueError:
            st.warning("Customer ID must be a number.")

st.markdown(
    f"""<div class="sec">
          <span class="dot"></span>
          <h3>{section}</h3>
          <span class="badge">{len(filtered)} record{'s' if len(filtered)!=1 else ''}</span>
        </div>""",
    unsafe_allow_html=True,
)

view = filtered[DISPLAY_COLS].copy()
edited = st.data_editor(
    view,
    key=f"editor_{section}",
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    height=460,
    column_config={
        "customer_id":      st.column_config.NumberColumn(COL_LABELS["customer_id"], disabled=True, width="small"),
        "customer_name":    st.column_config.TextColumn(COL_LABELS["customer_name"], disabled=True, width="small"),
        "purchase_date":    st.column_config.DateColumn(COL_LABELS["purchase_date"], disabled=True, format="DD/MM/YYYY", width="small"),
        "machine_type":     st.column_config.TextColumn(COL_LABELS["machine_type"], disabled=True, width="medium"),
        "phone_number":     st.column_config.TextColumn(COL_LABELS["phone_number"], disabled=True, width="small"),
        "email_id":         st.column_config.TextColumn(COL_LABELS["email_id"], disabled=True, width="medium"),
        "status":           st.column_config.SelectboxColumn(
            COL_LABELS["status"], options=STATUS_OPTIONS, required=False, width="small",
            help="Contacted / Not Contacted",
        ),
        "next_appointment": st.column_config.DateColumn(
            COL_LABELS["next_appointment"], min_value=today, format="DD/MM/YYYY", width="small",
            help="Pick a future date",
        ),
        "interested":       st.column_config.SelectboxColumn(
            COL_LABELS["interested"], options=INTEREST_OPTIONS, required=False, width="small",
        ),
        "remarks":          st.column_config.TextColumn(COL_LABELS["remarks"], width="large"),
    },
)

if section == "Today's lead":
    sb1, sb2 = st.columns([1, 6])
    with sb1:
        if st.button("Save changes"):
            n = diff_and_save(filtered, edited)
            if n:
                st.success(f"Saved {n} row(s).")
                st.rerun()
            else:
                st.info("No changes to save.")
