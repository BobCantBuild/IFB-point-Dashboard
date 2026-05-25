"""IFB point Dashboard — Streamlit UI backed by SQLite."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "ifb_point.db"

DISPLAY_COLS = [
    "customer_follow_up", "customer_id", "customer_name", "purchase_date",
    "machine_type", "phone_number", "email_id", "status",
    "next_appointment", "interested", "remarks",
]

COL_LABELS = {
    "customer_follow_up": "Customer Follow-Up",
    "customer_id": "Customer ID",
    "customer_name": "Customer name",
    "purchase_date": "Purchase Date",
    "machine_type": "Machine Type",
    "phone_number": "Phone number",
    "email_id": "Email ID",
    "status": "▾ Status",
    "next_appointment": "▾ Next Appointment",
    "interested": "▾ Interested / Not Interested",
    "remarks": "Remarks",
}

# Follow-up tiers (label, max days from today, accent colour)
FOLLOW_UP_TIERS = [
    ("Post Purchase Delight Call",           2,    "#22d3ee"),   # cyan
    ("Usage & Experience Feedback Call",     30,   "#a78bfa"),   # violet
    ("Pre-Warranty Expiry Engagement Call",  1440, "#fb923c"),   # orange  (48 months)
    ("7-Year Loyalty Upgrade Call",          2520, "#f472b6"),   # pink    (84 months)
]

def compute_follow_up(purchase_date: date | None, today: date) -> str | None:
    if purchase_date is None:
        return None
    days = (today - purchase_date).days
    if days <= 2:
        return "Post Purchase Delight Call"
    elif days <= 30:                # 2 days – 1 month
        return "Usage & Experience Feedback Call"
    elif days <= 1460:              # 1 month – 48 months (4 years)
        return "Pre-Warranty Expiry Engagement Call"
    else:                           # 48 months+ → 7-Year Loyalty Upgrade
        return "7-Year Loyalty Upgrade Call"

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
    _today = date.today()
    df["customer_follow_up"] = df["purchase_date"].apply(
        lambda d: compute_follow_up(d, _today)
    )
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
    if v is None or v == "Empty" or (isinstance(v, float) and pd.isna(v)):
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
            def _val(v):
                if v is None or v == "Empty" or (isinstance(v, float) and pd.isna(v)):
                    return None
                return v
            update_row(
                int(cid),
                _val(row["status"]),
                row["next_appointment"] if pd.notna(row["next_appointment"]) else None,
                _val(row["interested"]),
                _val(row["remarks"]),
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

  /* ----- Stats row (image-1 style) ----- */
  .stats-row {
    display: flex; gap: 10px; align-items: stretch;
    margin-bottom: 16px; flex-wrap: nowrap;
  }

  /* Single-value card (like "IN PIPELINE") */
  .stat-solo {
    background: rgba(21,27,48,0.7);
    border: 1px solid rgba(148,163,184,0.14);
    border-radius: 14px; padding: 18px 20px;
    min-width: 110px; display: flex; flex-direction: column;
    justify-content: space-between;
    transition: border-color .15s; flex-shrink: 0;
  }
  .stat-solo:hover { border-color: rgba(139,92,246,0.5); }
  .stat-solo .s-label { font-size: 11px; font-weight: 700; color: #64748b;
    text-transform: uppercase; letter-spacing: 1.2px; }
  .stat-solo .s-value { font-size: 36px; font-weight: 900; margin-top: 8px; line-height: 1;
    background: linear-gradient(90deg,#60a5fa,#a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .stat-solo .s-sub { font-size: 11px; color: #475569; margin-top: 6px; }

  /* Group card (like "ORDER ID MATCH") */
  .stat-group {
    background: rgba(21,27,48,0.7);
    border: 1px solid rgba(148,163,184,0.14);
    border-radius: 14px; padding: 14px 16px;
    flex: 1; transition: border-color .15s;
  }
  .stat-group:hover { border-color: rgba(139,92,246,0.4); }
  .stat-group .g-label { font-size: 11px; font-weight: 700; color: #64748b;
    text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 10px; }
  .stat-group .g-inner { display: flex; gap: 8px; }

  /* Sub-card inside group (e.g. "25 Match") */
  .sub-stat {
    flex: 1; border-radius: 9px; padding: 10px 12px;
    text-align: center; border: 1px solid transparent;
  }
  .sub-stat .ss-val  { font-size: 26px; font-weight: 800; line-height: 1; }
  .sub-stat .ss-lbl  { font-size: 11px; font-weight: 600; margin-top: 4px; opacity: 0.85; }

  /* Colour variants */
  .ss-green  { background: rgba(20,83,45,0.5);  border-color: rgba(34,197,94,0.25);  color: #4ade80; }
  .ss-red    { background: rgba(127,29,29,0.4); border-color: rgba(239,68,68,0.25);  color: #f87171; }
  .ss-grey   { background: rgba(30,41,59,0.6);  border-color: rgba(100,116,139,0.2); color: #94a3b8; }
  .ss-cyan   { background: rgba(8,51,68,0.6);   border-color: rgba(34,211,238,0.25); color: #22d3ee; }
  .ss-violet { background: rgba(46,16,101,0.5); border-color: rgba(167,139,250,0.25);color: #a78bfa; }
  .ss-orange { background: rgba(67,20,7,0.6);   border-color: rgba(251,146,60,0.25); color: #fb923c; }
  .ss-pink   { background: rgba(74,4,78,0.4);   border-color: rgba(244,114,182,0.25);color: #f472b6; }

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

  /* ----- Editable column legend ----- */
  .edit-legend {
    display: flex; gap: 16px; align-items: center;
    margin-bottom: 8px; flex-wrap: wrap;
  }
  .edit-legend .leg-item {
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; color: #94a3b8;
  }
  .edit-legend .dot-edit  { width: 8px; height: 8px; border-radius: 2px; background: #8b5cf6; }
  .edit-legend .dot-read  { width: 8px; height: 8px; border-radius: 2px; background: #334155; }
  .edit-tag {
    display: inline-block; font-size: 10px; font-weight: 700;
    padding: 2px 7px; border-radius: 4px;
    background: rgba(139,92,246,0.15); color: #a78bfa;
    border: 1px solid rgba(139,92,246,0.3);
    letter-spacing: 0.5px; text-transform: uppercase;
    margin-left: 6px;
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

DB_SCHEMA = """CREATE TABLE IF NOT EXISTS customers (
    ifb_point_id INTEGER, customer_id INTEGER PRIMARY KEY, customer_name TEXT,
    purchase_date TEXT, machine_type TEXT, phone_number TEXT, email_id TEXT,
    status TEXT, next_appointment TEXT, interested TEXT, remarks TEXT);"""


@st.cache_resource
def init_db_if_missing():
    """Create and seed DB on first run. Works locally (Excel) and on Streamlit Cloud (data.csv)."""
    if DB_PATH.exists():
        return

    df = None

    # 1) Try local Excel
    excel_path = Path(r"C:\Users\aswin\Downloads\IFB point customer dummy data.xlsx")
    if excel_path.exists():
        df = pd.read_excel(excel_path)

    # 2) Try committed CSV (works on Streamlit Cloud)
    if df is None:
        csv_path = Path(__file__).parent / "data.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)

    if df is not None:
        df = df.rename(columns=COL_MAP)
        df["purchase_date"] = pd.to_datetime(
            df["purchase_date"], dayfirst=True, errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        df["next_appointment"] = pd.to_datetime(
            df["next_appointment"], dayfirst=True, errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        df["phone_number"] = df["phone_number"].astype(str)
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(DB_SCHEMA)
        df.to_sql("customers", conn, if_exists="append", index=False)
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
# Stats row  (Image-1 style: solo card + grouped sub-cards)
# --------------------------------------------------------------------------- #
total      = len(df_all)
contacted  = int((df_all["status"] == "Contacted").sum())
not_cont   = int((df_all["status"] == "Not Contacted").sum())
s_empty    = total - contacted - not_cont

interested    = int((df_all["interested"] == "Interested").sum())
not_interest  = int((df_all["interested"] == "Not Interested").sum())
i_empty       = total - interested - not_interest

fu_counts = df_all["customer_follow_up"].value_counts().to_dict()
fu_pp   = fu_counts.get("Post Purchase Delight Call", 0)
fu_ue   = fu_counts.get("Usage & Experience Feedback Call", 0)
fu_pw   = fu_counts.get("Pre-Warranty Expiry Engagement Call", 0)
fu_7y   = fu_counts.get("7-Year Loyalty Upgrade Call", 0)

def sub(css, val, lbl):
    return f'<div class="sub-stat {css}"><div class="ss-val">{val}</div><div class="ss-lbl">{lbl}</div></div>'

stats_html = f"""
<div class="stats-row">

  <div class="stat-solo">
    <div class="s-label">Total Leads</div>
    <div class="s-value">{total}</div>
    <div class="s-sub">in database</div>
  </div>

  <div class="stat-group">
    <div class="g-label">Contact Status</div>
    <div class="g-inner">
      {sub("ss-green",  contacted,  "✓ Contacted")}
      {sub("ss-red",    not_cont,   "✗ Not Contacted")}
      {sub("ss-grey",   s_empty,    "— Empty")}
    </div>
  </div>

  <div class="stat-group">
    <div class="g-label">Interest</div>
    <div class="g-inner">
      {sub("ss-green",  interested,   "✓ Interested")}
      {sub("ss-red",    not_interest, "✗ Not Interested")}
      {sub("ss-grey",   i_empty,      "— Empty")}
    </div>
  </div>

  <div class="stat-group">
    <div class="g-label">Follow-Up Stage</div>
    <div class="g-inner">
      {sub("ss-cyan",   fu_pp,  "Post Purchase")}
      {sub("ss-violet", fu_ue,  "Usage & Exp.")}
      {sub("ss-orange", fu_pw,  "Pre-Warranty")}
      {sub("ss-pink",   fu_7y,  "7-Year Loyalty")}
    </div>
  </div>

</div>
"""
st.markdown(stats_html, unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Filter panel
# --------------------------------------------------------------------------- #
st.markdown('<div class="panel"><div class="ttl">Filters</div>', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([1.2, 1.4, 1.4])

with fc1:
    section = st.radio(
        "Section",
        ["Today's lead", "Missed Leads"],
        horizontal=True,
        label_visibility="collapsed",
    )

with fc2:
    min_pd = df_all["purchase_date"].dropna().min() or date(2019, 1, 1)
    max_pd = df_all["purchase_date"].dropna().max() or today
    date_range = st.date_input(
        "Lead Date range",
        value=(min_pd, max_pd),
        min_value=min_pd,
        max_value=max_pd,
    )

with fc3:
    search_q = st.text_input(
        "Search",
        placeholder="Customer ID / Name / Phone / Email",
    )

st.markdown("</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Filter & display
# --------------------------------------------------------------------------- #
if section == "Missed Leads":
    filtered = df_all.iloc[0:0].copy()
else:
    filtered = df_all.copy()
    if isinstance(date_range, tuple) and len(date_range) == 2:
        d_from, d_to = date_range
        filtered = filtered[filtered["purchase_date"].between(d_from, d_to)]
    q = search_q.strip()
    if q:
        # Search across Customer ID, Customer Name, Phone number, Email ID
        mask = (
            filtered["customer_name"].str.contains(q, case=False, na=False) |
            filtered["phone_number"].str.contains(q, case=False, na=False) |
            filtered["email_id"].str.contains(q, case=False, na=False)
        )
        # Also try numeric match on customer_id
        try:
            mask |= (filtered["customer_id"] == int(q))
        except ValueError:
            pass
        filtered = filtered[mask]

st.markdown(
    f"""<div class="sec">
          <span class="dot"></span>
          <h3>{section}</h3>
          <span class="badge">{len(filtered)} record{'s' if len(filtered)!=1 else ''}</span>
        </div>""",
    unsafe_allow_html=True,
)

# Legend showing editable vs read-only
st.markdown("""
<div class="edit-legend">
  <div class="leg-item"><span class="dot-read"></span> Read-only</div>
  <div class="leg-item"><span class="dot-edit"></span> Editable — click a cell to update</div>
  <span style="margin-left:4px;font-size:12px;color:#94a3b8;">
    Editable columns:
    <span class="edit-tag">▾ Status</span>
    <span class="edit-tag">▾ Next Appointment</span>
    <span class="edit-tag">▾ Interested / Not Interested</span>
    <span class="edit-tag">Remarks</span>
  </span>
</div>
""", unsafe_allow_html=True)

# Replace None/NaN with "Empty" for display in text/select columns
view = filtered[DISPLAY_COLS].copy()
for _col in ["status", "interested", "remarks"]:
    view[_col] = view[_col].fillna("Empty")

edited = st.data_editor(
    view,
    key=f"editor_{section}",
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    height=460,
    column_config={
        "customer_follow_up": st.column_config.TextColumn(
            COL_LABELS["customer_follow_up"], disabled=True, width="medium",
            help="Auto-calculated from Purchase Date",
        ),
        "customer_id":        st.column_config.NumberColumn(COL_LABELS["customer_id"], disabled=True, width="small"),
        "customer_name":      st.column_config.TextColumn(COL_LABELS["customer_name"], disabled=True, width="small"),
        "purchase_date":      st.column_config.DateColumn(COL_LABELS["purchase_date"], disabled=True, format="DD/MM/YYYY", width="small"),
        "machine_type":       st.column_config.TextColumn(COL_LABELS["machine_type"], disabled=True, width="medium"),
        "phone_number":       st.column_config.TextColumn(COL_LABELS["phone_number"], disabled=True, width="small"),
        "email_id":           st.column_config.TextColumn(COL_LABELS["email_id"], disabled=True, width="medium"),
        "status":             st.column_config.SelectboxColumn(
            COL_LABELS["status"],
            options=["Empty"] + STATUS_OPTIONS,
            required=False,
            width="medium",
            help="Click to select: Contacted / Not Contacted",
        ),
        "next_appointment":   st.column_config.DateColumn(
            COL_LABELS["next_appointment"],
            min_value=today,
            format="DD/MM/YYYY",
            width="medium",
            help="Click to pick a future date",
        ),
        "interested":         st.column_config.SelectboxColumn(
            COL_LABELS["interested"],
            options=["Empty"] + INTEREST_OPTIONS,
            required=False,
            width="medium",
            help="Click to select: Interested / Not Interested",
        ),
        "remarks":            st.column_config.TextColumn(
            COL_LABELS["remarks"], width="large",
            help="Click to type remarks",
        ),
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
