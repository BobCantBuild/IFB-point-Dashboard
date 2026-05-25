"""IFB point Dashboard â€” Streamlit UI backed by SQLite."""
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
    "status": "â–¾ Status",
    "next_appointment": "â–¾ Next Appointment",
    "interested": "â–¾ Interested / Not Interested",
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
    elif days <= 30:                # 2 days â€“ 1 month
        return "Usage & Experience Feedback Call"
    elif days <= 1460:              # 1 month â€“ 48 months (4 years)
        return "Pre-Warranty Expiry Engagement Call"
    else:                           # 48 months+ â†’ 7-Year Loyalty Upgrade
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
  .stApp { background: #F1F5F9; }
  .block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1400px; }
  header[data-testid="stHeader"] { background: transparent; }
  #MainMenu, footer { visibility: hidden; }

  /* ----- Hero ----- */
  .hero {
    background: #0F172A;
    border-radius: 16px;
    padding: 22px 28px;
    margin-bottom: 18px;
    display: flex; align-items: center; justify-content: space-between;
  }
  .hero-left h1 { margin: 0; font-size: 22px; font-weight: 700;
    letter-spacing: -0.3px; color: #F8FAFC; }
  .hero-left p  { margin: 5px 0 0; font-size: 13px; color: #94A3B8; }
  .hero .pill {
    display: inline-block; padding: 5px 14px; border-radius: 6px;
    background: #1E293B; font-size: 12px; font-weight: 600;
    color: #38BDF8; letter-spacing: 0.3px; border: 1px solid #334155;
  }

  /* ----- Stats row ----- */
  .stats-row {
    display: flex; gap: 12px; align-items: stretch;
    margin-bottom: 16px; flex-wrap: nowrap;
  }

  /* Solo card */
  .stat-solo {
    background: #fff; border: 1px solid #E2E8F0;
    border-radius: 14px; padding: 20px 22px;
    min-width: 120px; display: flex; flex-direction: column;
    justify-content: space-between; flex-shrink: 0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  .stat-solo .s-label { font-size: 11px; font-weight: 600; color: #94A3B8;
    text-transform: uppercase; letter-spacing: 1px; }
  .stat-solo .s-value { font-size: 38px; font-weight: 800; margin-top: 8px;
    line-height: 1; color: #0F172A; }
  .stat-solo .s-sub { font-size: 11px; color: #CBD5E1; margin-top: 6px; }

  /* Group card */
  .stat-group {
    background: #fff; border: 1px solid #E2E8F0;
    border-radius: 14px; padding: 16px 18px; flex: 1;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  .stat-group .g-label { font-size: 11px; font-weight: 600; color: #94A3B8;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
  .stat-group .g-inner { display: flex; gap: 8px; }

  /* Sub-card */
  .sub-stat {
    flex: 1; border-radius: 8px; padding: 10px 10px 8px;
    text-align: center; background: #F8FAFC; border: 1px solid #E2E8F0;
  }
  .sub-stat .ss-val { font-size: 24px; font-weight: 800; line-height: 1; color: #0F172A; }
  .sub-stat .ss-lbl { font-size: 10px; font-weight: 500; margin-top: 5px;
    color: #64748B; letter-spacing: 0.3px; }

  /* Subtle tinted variants â€” only the number gets color */
  .ss-green .ss-val  { color: #16A34A; }
  .ss-red   .ss-val  { color: #DC2626; }
  .ss-grey  .ss-val  { color: #475569; }
  .ss-blue  .ss-val  { color: #2563EB; }
  .ss-teal  .ss-val  { color: #0D9488; }
  .ss-indigo .ss-val { color: #4F46E5; }
  .ss-rose  .ss-val  { color: #E11D48; }
  .ss-slate .ss-val  { color: #334155; }

  /* ----- Filter panel ----- */
  .panel {
    background: #fff; border: 1px solid #E2E8F0;
    border-radius: 14px; padding: 16px 20px 8px;
    margin-bottom: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  }
  .panel .ttl { font-size: 11px; color: #94A3B8; text-transform: uppercase;
    letter-spacing: 1px; font-weight: 600; margin-bottom: 8px; }

  /* ----- Section selector ----- */
  div[role="radiogroup"] {
    gap: 4px !important; background: #F1F5F9;
    padding: 4px; border-radius: 10px;
    border: 1px solid #E2E8F0; width: fit-content;
  }
  div[role="radiogroup"] > label {
    background: transparent; border-radius: 7px;
    padding: 7px 18px !important; margin: 0 !important;
    cursor: pointer; transition: all .15s ease;
    color: #334155 !important; font-weight: 600; font-size: 13px;
  }
  div[role="radiogroup"] > label:hover { background: #E2E8F0; color: #0F172A !important; }
  div[role="radiogroup"] > label[data-checked="true"],
  div[role="radiogroup"] > label:has(input:checked) {
    background: #2563EB !important; color: #FFFFFF !important;
    box-shadow: 0 1px 6px rgba(37,99,235,0.25);
  }
  div[role="radiogroup"] > label > div:first-child { display: none !important; }

  /* ----- Row spacing in dataframe ----- */
  [data-testid="stDataFrame"] tr td,
  [data-testid="stDataFrame"] tr th {
    padding-top: 10px !important;
    padding-bottom: 10px !important;
    font-size: 13px !important;
  }

  /* ----- Edit panel card ----- */
  .edit-panel {
    background: #fff; border: 1px solid #BFDBFE;
    border-left: 4px solid #2563EB;
    border-radius: 12px; padding: 18px 22px;
    margin-top: 12px;
    box-shadow: 0 2px 12px rgba(37,99,235,0.08);
  }
  .edit-panel .ep-title { font-size: 13px; font-weight: 700; color: #1E40AF;
    text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px; }
  .edit-panel .ep-sub { font-size: 12px; color: #64748B; margin-bottom: 14px; }

  /* ----- Inputs ----- */
  div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background: #F8FAFC !important; border-radius: 8px !important;
    border: 1px solid #E2E8F0 !important;
  }
  .stDateInput > div > div { background: #F8FAFC !important; border-radius: 8px !important; }

  /* ----- Button ----- */
  .stButton > button {
    background: #0F172A; color: #F8FAFC;
    border: 0; border-radius: 8px;
    padding: 9px 22px; font-weight: 600; font-size: 13px;
    transition: background .15s ease;
  }
  .stButton > button:hover { background: #1E293B; }

  /* ----- Data editor ----- */
  div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    border-radius: 12px; overflow: hidden;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06);
  }

  /* ----- Editable legend ----- */
  .edit-legend { display: flex; gap: 14px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
  .edit-legend .leg-item { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #94A3B8; }
  .edit-legend .dot-edit { width: 8px; height: 8px; border-radius: 2px; background: #2563EB; }
  .edit-legend .dot-read { width: 8px; height: 8px; border-radius: 2px; background: #CBD5E1; }
  .edit-tag {
    display: inline-block; font-size: 10px; font-weight: 600;
    padding: 2px 7px; border-radius: 4px;
    background: #EFF6FF; color: #2563EB;
    border: 1px solid #BFDBFE;
    letter-spacing: 0.4px; text-transform: uppercase; margin-left: 4px;
  }

  /* ----- Section subheader ----- */
  .sec { display: flex; align-items: center; gap: 10px; margin: 6px 0 10px; }
  .sec .dot { width: 8px; height: 8px; border-radius: 999px; background: #2563EB; }
  .sec h3 { margin: 0; font-size: 16px; font-weight: 700; color: #0F172A; }
  .sec .badge { font-size: 11px; padding: 2px 10px; border-radius: 999px;
    background: #F1F5F9; color: #64748B; font-weight: 600;
    border: 1px solid #E2E8F0; }

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
      <div class="hero-left">
        <h1>IFB Point Dashboard</h1>
        <p>Customer Follow-Up Management &nbsp;Â·&nbsp; {today.strftime('%A, %d %B %Y')}</p>
      </div>
      <span class="pill">â— &nbsp;Live</span>
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
      {sub("ss-green",  contacted,  "Contacted")}
      {sub("ss-red",    not_cont,   "Not Contacted")}
      {sub("ss-grey",   s_empty,    "Empty")}
    </div>
  </div>

  <div class="stat-group">
    <div class="g-label">Interest</div>
    <div class="g-inner">
      {sub("ss-green",  interested,   "Interested")}
      {sub("ss-red",    not_interest, "Not Interested")}
      {sub("ss-grey",   i_empty,      "Empty")}
    </div>
  </div>

  <div class="stat-group">
    <div class="g-label">Follow-Up Stage</div>
    <div class="g-inner">
      {sub("ss-blue",   fu_pp,  "Post Purchase")}
      {sub("ss-teal",   fu_ue,  "Usage & Exp.")}
      {sub("ss-indigo", fu_pw,  "Pre-Warranty")}
      {sub("ss-slate",  fu_7y,  "7-Year Loyalty")}
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

# Legend
st.markdown("""
<div class="edit-legend">
  <div class="leg-item"><span class="dot-read"></span> Read-only</div>
  <div class="leg-item"><span class="dot-edit"></span> Use ✏️ to edit a row</div>
  <span style="font-size:12px;color:#94A3B8;margin-left:4px;">
    Editable:
    <span class="edit-tag">â–¾ Status</span>
    <span class="edit-tag">â–¾ Next Appointment</span>
    <span class="edit-tag">â–¾ Interested</span>
    <span class="edit-tag">Remarks</span>
  </span>
</div>
""", unsafe_allow_html=True)

# ---------- Table ----------
if section == "Today's lead":
    # Allow multiple rows in edit mode at once.
    edit_rows = st.session_state.get("edit_rows", set())
    if not isinstance(edit_rows, set):
        edit_rows = set()
    st.session_state["edit_rows"] = edit_rows

    header_cols = st.columns([1.6, 0.7, 1.0, 0.9, 1.8, 0.9, 1.6, 1.0, 1.0, 1.2, 2.0, 0.9])
    headers = [
        COL_LABELS["customer_follow_up"],
        COL_LABELS["customer_id"],
        COL_LABELS["customer_name"],
        COL_LABELS["purchase_date"],
        COL_LABELS["machine_type"],
        COL_LABELS["phone_number"],
        COL_LABELS["email_id"],
        COL_LABELS["status"],
        COL_LABELS["next_appointment"],
        COL_LABELS["interested"],
        COL_LABELS["remarks"],
        "",
    ]
    for c, h in zip(header_cols, headers):
        with c:
            st.markdown(f"**{h}**")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    for _, row in filtered.iterrows():
        cid = int(row["customer_id"])
        is_editing = cid in edit_rows

        cur_status = row["status"] if pd.notna(row["status"]) else None
        cur_appt = row["next_appointment"] if pd.notna(row["next_appointment"]) else None
        cur_int = row["interested"] if pd.notna(row["interested"]) else None
        cur_rem = row["remarks"] if pd.notna(row["remarks"]) else ""

        cols = st.columns([1.6, 0.7, 1.0, 0.9, 1.8, 0.9, 1.6, 1.0, 1.0, 1.2, 2.0, 0.9])

        with cols[0]:
            st.write(row.get("customer_follow_up") or "")
        with cols[1]:
            st.write(cid)
        with cols[2]:
            st.write(row.get("customer_name") or "")
        with cols[3]:
            st.write(row.get("purchase_date") or "")
        with cols[4]:
            st.write(row.get("machine_type") or "")
        with cols[5]:
            st.write(row.get("phone_number") or "")
        with cols[6]:
            st.write(row.get("email_id") or "")

        if is_editing:
            with cols[7]:
                new_status = st.selectbox(
                    "Status",
                    ["Empty"] + STATUS_OPTIONS,
                    index=(["Empty"] + STATUS_OPTIONS).index(cur_status) if cur_status in STATUS_OPTIONS else 0,
                    key=f"row_status_{cid}",
                    label_visibility="collapsed",
                )
            with cols[8]:
                new_appt = st.date_input(
                    "Next Appointment",
                    value=cur_appt if cur_appt else None,
                    min_value=today,
                    key=f"row_appt_{cid}",
                    label_visibility="collapsed",
                )
            with cols[9]:
                new_int = st.selectbox(
                    "Interested",
                    ["Empty"] + INTEREST_OPTIONS,
                    index=(["Empty"] + INTEREST_OPTIONS).index(cur_int) if cur_int in INTEREST_OPTIONS else 0,
                    key=f"row_int_{cid}",
                    label_visibility="collapsed",
                )
            with cols[10]:
                new_rem = st.text_input(
                    "Remarks",
                    value=cur_rem,
                    key=f"row_rem_{cid}",
                    label_visibility="collapsed",
                )

            with cols[11]:
                save_btn, cancel_btn = st.columns(2)
                with save_btn:
                    if st.button("💾", key=f"row_save_{cid}", help="Save"):
                        update_row(
                            cid,
                            None if new_status == "Empty" else new_status,
                            new_appt if isinstance(new_appt, date) else None,
                            None if new_int == "Empty" else new_int,
                            new_rem if new_rem.strip() else None,
                        )
                        edit_rows.discard(cid)
                        st.session_state["edit_rows"] = edit_rows
                        st.success(f"Saved â€” {row.get('customer_name') or cid}")
                        st.rerun()
                with cancel_btn:
                    if st.button("âœ•", key=f"row_cancel_{cid}", help="Cancel"):
                        edit_rows.discard(cid)
                        st.session_state["edit_rows"] = edit_rows
                        st.rerun()
        else:
            with cols[7]:
                st.write(cur_status or "Empty")
            with cols[8]:
                st.write(cur_appt or "Empty")
            with cols[9]:
                st.write(cur_int or "Empty")
            with cols[10]:
                st.write(cur_rem or "Empty")
            with cols[11]:
                if st.button("âœ", key=f"row_edit_{cid}", help="Edit"):
                    edit_rows.add(cid)
                    st.session_state["edit_rows"] = edit_rows
                    st.rerun()

        st.divider()
else:
    # Add a visual edit-indicator column for display
    view = filtered[DISPLAY_COLS].copy()
    for _col in ["status", "interested", "remarks"]:
        view[_col] = view[_col].fillna("Empty")
    view.insert(len(view.columns), "âœ", "")

    # ---------- Read-only table ----------
    COLUMN_CONFIG_RO = {
        "customer_follow_up": st.column_config.TextColumn(COL_LABELS["customer_follow_up"], width="medium"),
        "customer_id":        st.column_config.NumberColumn(COL_LABELS["customer_id"], width="small"),
        "customer_name":      st.column_config.TextColumn(COL_LABELS["customer_name"], width="small"),
        "purchase_date":      st.column_config.DateColumn(COL_LABELS["purchase_date"], format="DD/MM/YYYY", width="small"),
        "machine_type":       st.column_config.TextColumn(COL_LABELS["machine_type"], width="medium"),
        "phone_number":       st.column_config.TextColumn(COL_LABELS["phone_number"], width="small"),
        "email_id":           st.column_config.TextColumn(COL_LABELS["email_id"], width="medium"),
        "status":             st.column_config.TextColumn(COL_LABELS["status"], width="small"),
        "next_appointment":   st.column_config.DateColumn(COL_LABELS["next_appointment"], format="DD/MM/YYYY", width="small"),
        "interested":         st.column_config.TextColumn(COL_LABELS["interested"], width="small"),
        "remarks":            st.column_config.TextColumn(COL_LABELS["remarks"], width="large"),
        "âœ":                  st.column_config.TextColumn("", width="small"),
    }

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        height=480,
        column_config=COLUMN_CONFIG_RO,
        key=f"df_{section}",
    )
