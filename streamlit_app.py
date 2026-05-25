"""IFB Point Dashboard — Streamlit UI backed by SQLite."""
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
    "customer_id":        "Customer ID",
    "customer_name":      "Customer Name",
    "purchase_date":      "Purchase Date",
    "machine_type":       "Machine Type",
    "phone_number":       "Phone Number",
    "email_id":           "Email ID",
    "status":             "Status",
    "next_appointment":   "Next Appointment",
    "interested":         "Interested / Not Interested",
    "remarks":            "Remarks",
}

STATUS_OPTIONS   = ["Contacted", "Not Contacted"]
INTEREST_OPTIONS = ["Interested", "Not Interested"]


def compute_follow_up(purchase_date: date | None, today: date) -> str | None:
    if purchase_date is None:
        return None
    days = (today - purchase_date).days
    if days <= 2:
        return "Post Purchase Delight Call"
    elif days <= 30:
        return "Usage & Experience Feedback Call"
    elif days <= 1460:
        return "Pre-Warranty Expiry Engagement Call"
    else:
        return "7-Year Loyalty Upgrade Call"


# --------------------------------------------------------------------------- #
# Data layer
# --------------------------------------------------------------------------- #
def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def load_all() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM customers", conn)
    df["purchase_date"]     = pd.to_datetime(df["purchase_date"],     errors="coerce").dt.date
    df["next_appointment"]  = pd.to_datetime(df["next_appointment"],  errors="coerce").dt.date
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
            def _v(v):
                return None if (v is None or v == "Empty" or
                                (isinstance(v, float) and pd.isna(v))) else v
            update_row(
                int(cid),
                _v(row["status"]),
                row["next_appointment"] if pd.notna(row["next_appointment"]) else None,
                _v(row["interested"]),
                _v(row["remarks"]),
            )
            n += 1
    return n


COL_MAP = {
    "IFB point ID":              "ifb_point_id",
    "Customer_ID":               "customer_id",
    "Customer name":             "customer_name",
    "Purchase Date":             "purchase_date",
    "Machine Type":              "machine_type",
    "Phone number":              "phone_number",
    "Email ID":                  "email_id",
    "Status":                    "status",
    "Next appointment":          "next_appointment",
    "Interested/ Not Interested":"interested",
    "Remarks":                   "remarks",
}

DB_SCHEMA = """CREATE TABLE IF NOT EXISTS customers (
    ifb_point_id INTEGER, customer_id INTEGER PRIMARY KEY, customer_name TEXT,
    purchase_date TEXT, machine_type TEXT, phone_number TEXT, email_id TEXT,
    status TEXT, next_appointment TEXT, interested TEXT, remarks TEXT);"""


@st.cache_resource
def init_db_if_missing():
    if DB_PATH.exists():
        return
    df = None
    excel_path = Path(r"C:\Users\aswin\Downloads\IFB point customer dummy data.xlsx")
    if excel_path.exists():
        df = pd.read_excel(excel_path)
    if df is None:
        csv_path = Path(__file__).parent / "data.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path)
    if df is not None:
        df = df.rename(columns=COL_MAP)
        df["purchase_date"]    = pd.to_datetime(df["purchase_date"],    dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
        df["next_appointment"] = pd.to_datetime(df["next_appointment"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
        df["phone_number"]     = df["phone_number"].astype(str)
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(DB_SCHEMA)
        df.to_sql("customers", conn, if_exists="append", index=False)
        conn.commit()
        conn.close()


# --------------------------------------------------------------------------- #
# Page config + CSS
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="IFB Point Dashboard", layout="wide", page_icon=":bar_chart:")

CSS = """
<style>
  .stApp { background: #F1F5F9; }
  .block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1440px; }
  header[data-testid="stHeader"] { background: transparent; }
  #MainMenu, footer { visibility: hidden; }

  /* Hero */
  .hero {
    background: #0F172A; border-radius: 16px;
    padding: 22px 28px; margin-bottom: 18px;
    display: flex; align-items: center; justify-content: space-between;
  }
  .hero-left h1 { margin:0; font-size:22px; font-weight:700; color:#F8FAFC; letter-spacing:-0.3px; }
  .hero-left p  { margin:5px 0 0; font-size:13px; color:#94A3B8; }
  .hero .pill {
    display:inline-block; padding:5px 14px; border-radius:6px;
    background:#1E293B; font-size:12px; font-weight:600;
    color:#38BDF8; letter-spacing:0.3px; border:1px solid #334155;
  }

  /* Stats row */
  .stats-row { display:flex; gap:12px; align-items:stretch; margin-bottom:16px; flex-wrap:nowrap; }

  .stat-solo {
    background:#fff; border:1px solid #E2E8F0; border-radius:14px;
    padding:20px 22px; min-width:120px; flex-shrink:0;
    display:flex; flex-direction:column; justify-content:space-between;
    box-shadow:0 1px 4px rgba(0,0,0,0.06);
  }
  .stat-solo .s-label { font-size:11px; font-weight:600; color:#94A3B8; text-transform:uppercase; letter-spacing:1px; }
  .stat-solo .s-value { font-size:38px; font-weight:800; margin-top:8px; line-height:1; color:#0F172A; }
  .stat-solo .s-sub   { font-size:11px; color:#CBD5E1; margin-top:6px; }

  .stat-group {
    background:#fff; border:1px solid #E2E8F0; border-radius:14px;
    padding:16px 18px; flex:1; box-shadow:0 1px 4px rgba(0,0,0,0.06);
  }
  .stat-group .g-label { font-size:11px; font-weight:600; color:#94A3B8; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px; }
  .stat-group .g-inner { display:flex; gap:8px; }

  .sub-stat { flex:1; border-radius:8px; padding:10px 10px 8px; text-align:center; background:#F8FAFC; border:1px solid #E2E8F0; }
  .sub-stat .ss-val { font-size:24px; font-weight:800; line-height:1; color:#0F172A; }
  .sub-stat .ss-lbl { font-size:10px; font-weight:500; margin-top:5px; color:#64748B; letter-spacing:0.3px; }

  .ss-green  .ss-val { color:#16A34A; }
  .ss-red    .ss-val { color:#DC2626; }
  .ss-grey   .ss-val { color:#475569; }
  .ss-blue   .ss-val { color:#2563EB; }
  .ss-teal   .ss-val { color:#0D9488; }
  .ss-indigo .ss-val { color:#4F46E5; }
  .ss-slate  .ss-val { color:#334155; }

  /* Filter panel */
  .panel {
    background:#fff; border:1px solid #E2E8F0; border-radius:14px;
    padding:16px 20px 8px; margin-bottom:16px; box-shadow:0 1px 4px rgba(0,0,0,0.05);
  }
  .panel .ttl { font-size:11px; color:#94A3B8; text-transform:uppercase; letter-spacing:1px; font-weight:600; margin-bottom:8px; }

  /* Section tabs (radio) */
  div[role="radiogroup"] {
    gap:4px !important; background:#F1F5F9; padding:4px;
    border-radius:10px; border:1px solid #E2E8F0; width:fit-content;
  }
  div[role="radiogroup"] > label {
    background:transparent; border-radius:7px; padding:7px 18px !important;
    margin:0 !important; cursor:pointer; transition:all .15s ease;
    color:#334155 !important; font-weight:600; font-size:13px;
  }
  div[role="radiogroup"] > label:hover { background:#E2E8F0; color:#0F172A !important; }
  div[role="radiogroup"] > label[data-checked="true"],
  div[role="radiogroup"] > label:has(input:checked) {
    background:#2563EB !important; color:#FFFFFF !important;
    box-shadow:0 1px 6px rgba(37,99,235,0.25);
  }
  div[role="radiogroup"] > label > div:first-child { display:none !important; }

  /* Data table */
  div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    border-radius:12px; overflow:hidden;
    border:1px solid #E2E8F0; box-shadow:0 1px 6px rgba(0,0,0,0.06);
  }

  /* Inputs */
  div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background:#F8FAFC !important; border-radius:8px !important; border:1px solid #E2E8F0 !important;
  }
  .stDateInput > div > div { background:#F8FAFC !important; border-radius:8px !important; }

  /* Buttons */
  .stButton > button {
    background:#0F172A; color:#F8FAFC; border:0; border-radius:8px;
    padding:9px 22px; font-weight:600; font-size:13px; transition:background .15s;
  }
  .stButton > button:hover { background:#1E293B; }

  /* Section header */
  .sec { display:flex; align-items:center; gap:10px; margin:6px 0 12px; }
  .sec .dot { width:8px; height:8px; border-radius:999px; background:#2563EB; }
  .sec h3 { margin:0; font-size:16px; font-weight:700; color:#0F172A; }
  .sec .badge {
    font-size:11px; padding:2px 10px; border-radius:999px;
    background:#F1F5F9; color:#64748B; font-weight:600; border:1px solid #E2E8F0;
  }

  /* Edit tag legend */
  .edit-tag {
    display:inline-block; font-size:10px; font-weight:600;
    padding:2px 7px; border-radius:4px; background:#EFF6FF; color:#2563EB;
    border:1px solid #BFDBFE; letter-spacing:0.4px; text-transform:uppercase; margin-left:4px;
  }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Boot
# --------------------------------------------------------------------------- #
init_db_if_missing()

if not DB_PATH.exists():
    st.error("Database not found. Run `python seed_db.py` locally, or check data.csv on Streamlit Cloud.")
    st.stop()

df_all = load_all()
today  = date.today()

# --------------------------------------------------------------------------- #
# Hero
# --------------------------------------------------------------------------- #
st.markdown(
    f"""<div class="hero">
      <div class="hero-left">
        <h1>IFB Point Dashboard</h1>
        <p>Customer Follow-Up Management &nbsp;&middot;&nbsp; {today.strftime('%A, %d %B %Y')}</p>
      </div>
      <span class="pill">&#9679;&nbsp; Live</span>
    </div>""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Stats row
# --------------------------------------------------------------------------- #
total        = len(df_all)
contacted    = int((df_all["status"]    == "Contacted").sum())
not_cont     = int((df_all["status"]    == "Not Contacted").sum())
s_empty      = total - contacted - not_cont
interested   = int((df_all["interested"] == "Interested").sum())
not_interest = int((df_all["interested"] == "Not Interested").sum())
i_empty      = total - interested - not_interest

fu_counts = df_all["customer_follow_up"].value_counts().to_dict()
fu_pp = fu_counts.get("Post Purchase Delight Call", 0)
fu_ue = fu_counts.get("Usage & Experience Feedback Call", 0)
fu_pw = fu_counts.get("Pre-Warranty Expiry Engagement Call", 0)
fu_7y = fu_counts.get("7-Year Loyalty Upgrade Call", 0)

def sub(css, val, lbl):
    return (f'<div class="sub-stat {css}">'
            f'<div class="ss-val">{val}</div>'
            f'<div class="ss-lbl">{lbl}</div></div>')

st.markdown(f"""
<div class="stats-row">
  <div class="stat-solo">
    <div class="s-label">Total Leads</div>
    <div class="s-value">{total}</div>
    <div class="s-sub">in database</div>
  </div>
  <div class="stat-group">
    <div class="g-label">Contact Status</div>
    <div class="g-inner">
      {sub("ss-green", contacted,    "Contacted")}
      {sub("ss-red",   not_cont,     "Not Contacted")}
      {sub("ss-grey",  s_empty,      "Empty")}
    </div>
  </div>
  <div class="stat-group">
    <div class="g-label">Interest</div>
    <div class="g-inner">
      {sub("ss-green", interested,   "Interested")}
      {sub("ss-red",   not_interest, "Not Interested")}
      {sub("ss-grey",  i_empty,      "Empty")}
    </div>
  </div>
  <div class="stat-group">
    <div class="g-label">Follow-Up Stage</div>
    <div class="g-inner">
      {sub("ss-blue",   fu_pp, "Post Purchase")}
      {sub("ss-teal",   fu_ue, "Usage & Exp.")}
      {sub("ss-indigo", fu_pw, "Pre-Warranty")}
      {sub("ss-slate",  fu_7y, "7-Year Loyalty")}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
st.markdown('<div class="panel"><div class="ttl">Filters</div>', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([1.2, 1.4, 1.4])

with fc1:
    section = st.radio(
        "Section", ["Today's Lead", "Missed Leads"],
        horizontal=True, label_visibility="collapsed",
    )
with fc2:
    min_pd = df_all["purchase_date"].dropna().min() or date(2019, 1, 1)
    max_pd = df_all["purchase_date"].dropna().max() or today
    date_range = st.date_input(
        "Lead Date range", value=(min_pd, max_pd),
        min_value=min_pd, max_value=max_pd,
    )
with fc3:
    search_q = st.text_input("Search", placeholder="Customer ID / Name / Phone / Email")

st.markdown("</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Filter data
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
        mask = (
            filtered["customer_name"].str.contains(q, case=False, na=False) |
            filtered["phone_number"].str.contains(q, case=False, na=False)  |
            filtered["email_id"].str.contains(q, case=False, na=False)
        )
        try:
            mask |= (filtered["customer_id"] == int(q))
        except ValueError:
            pass
        filtered = filtered[mask]

# --------------------------------------------------------------------------- #
# Section header
# --------------------------------------------------------------------------- #
st.markdown(
    f"""<div class="sec">
      <span class="dot"></span>
      <h3>{section}</h3>
      <span class="badge">{len(filtered)} record{'s' if len(filtered) != 1 else ''}</span>
    </div>""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Per-row inline edit table
# --------------------------------------------------------------------------- #

# column ratios:  follow-up | id | name | date | machine | phone | email | status | appt | interest | remarks | action
RATIOS = [1.8, 0.55, 0.9, 0.8, 1.5, 0.85, 1.4, 0.9, 0.85, 1.1, 1.6, 0.55]
HEADERS = [
    "Customer Follow-Up", "ID", "Name", "Purchase Date",
    "Machine Type", "Phone", "Email",
    "Status", "Next Appt", "Interested?", "Remarks", "",
]

def _cell(col, value, muted=False):
    """Render a read-only table cell."""
    color = "#94A3B8" if muted else "#1E293B"
    col.markdown(
        f"<div style='font-size:12.5px;color:{color};padding:6px 2px;"
        f"line-height:1.4;overflow:hidden;text-overflow:ellipsis;"
        f"white-space:nowrap'>{value}</div>",
        unsafe_allow_html=True,
    )

def _safe(v, fallback="—"):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "NaT", "nan", "None"):
        return fallback
    return str(v)

# ── session state ─────────────────────────────────────────────────────────
if "editing_cid" not in st.session_state:
    st.session_state["editing_cid"] = None

# ── table header ──────────────────────────────────────────────────────────
hdr = st.columns(RATIOS, gap="small")
for col, lbl in zip(hdr, HEADERS):
    col.markdown(
        f"<div style='font-size:11px;font-weight:700;color:#64748B;"
        f"text-transform:uppercase;letter-spacing:0.7px;"
        f"padding:4px 2px 8px;border-bottom:2px solid #E2E8F0'>{lbl}</div>",
        unsafe_allow_html=True,
    )

# ── data rows ─────────────────────────────────────────────────────────────
if len(filtered) == 0:
    st.markdown(
        "<div style='text-align:center;padding:40px;color:#94A3B8;"
        "font-size:14px'>No records match your filters.</div>",
        unsafe_allow_html=True,
    )
else:
    for _, row in filtered.iterrows():
        cid        = int(row["customer_id"])
        is_editing = (st.session_state["editing_cid"] == cid)

        cur_status = row["status"]           if pd.notna(row.get("status"))           else None
        cur_appt   = row["next_appointment"] if pd.notna(row.get("next_appointment")) else None
        cur_int    = row["interested"]       if pd.notna(row.get("interested"))       else None
        cur_rem    = str(row["remarks"])     if pd.notna(row.get("remarks")) and row["remarks"] else ""

        cols = st.columns(RATIOS, gap="small")

        # ── always read-only columns ──────────────────────────────────────
        _cell(cols[0], _safe(row.get("customer_follow_up")))
        _cell(cols[1], cid, muted=True)
        _cell(cols[2], _safe(row.get("customer_name")))
        pd_str = row["purchase_date"].strftime("%d/%m/%Y") if row.get("purchase_date") and pd.notna(row["purchase_date"]) else "—"
        _cell(cols[3], pd_str, muted=True)
        _cell(cols[4], _safe(row.get("machine_type")))
        _cell(cols[5], _safe(row.get("phone_number")))
        _cell(cols[6], _safe(row.get("email_id")))

        # ── editable columns ──────────────────────────────────────────────
        if is_editing and section == "Today's Lead":
            with cols[7]:
                new_status = st.selectbox(
                    "Status", ["Empty"] + STATUS_OPTIONS,
                    index=(["Empty"] + STATUS_OPTIONS).index(cur_status)
                          if cur_status in STATUS_OPTIONS else 0,
                    key=f"s_{cid}", label_visibility="collapsed",
                )
            with cols[8]:
                new_appt = st.date_input(
                    "Appt", value=cur_appt if isinstance(cur_appt, date) else None,
                    min_value=today, key=f"a_{cid}", label_visibility="collapsed",
                )
            with cols[9]:
                new_int = st.selectbox(
                    "Interested", ["Empty"] + INTEREST_OPTIONS,
                    index=(["Empty"] + INTEREST_OPTIONS).index(cur_int)
                          if cur_int in INTEREST_OPTIONS else 0,
                    key=f"i_{cid}", label_visibility="collapsed",
                )
            with cols[10]:
                new_rem = st.text_input(
                    "Remarks", value=cur_rem,
                    key=f"r_{cid}", label_visibility="collapsed",
                )
            # save + cancel icons
            with cols[11]:
                st.markdown("<div style='padding-top:4px'>", unsafe_allow_html=True)
                if st.button("💾", key=f"sv_{cid}", help="Save changes"):
                    update_row(
                        cid,
                        None if new_status == "Empty" else new_status,
                        new_appt if isinstance(new_appt, date) else None,
                        None if new_int    == "Empty" else new_int,
                        new_rem.strip() or None,
                    )
                    st.session_state["editing_cid"] = None
                    st.rerun()
                if st.button("✕", key=f"cx_{cid}", help="Cancel"):
                    st.session_state["editing_cid"] = None
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        else:
            _cell(cols[7],  _safe(cur_status,  "Empty"))
            ap_str = cur_appt.strftime("%d/%m/%Y") if cur_appt and pd.notna(cur_appt) else "Empty"
            _cell(cols[8],  ap_str, muted=(ap_str == "Empty"))
            _cell(cols[9],  _safe(cur_int,     "Empty"))
            _cell(cols[10], _safe(cur_rem,     "—"))
            with cols[11]:
                st.markdown("<div style='padding-top:4px'>", unsafe_allow_html=True)
                if section == "Today's Lead":
                    if st.button("✏️", key=f"ed_{cid}", help="Edit this row"):
                        st.session_state["editing_cid"] = cid
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        # thin row divider
        st.markdown(
            "<hr style='margin:2px 0;border:none;border-top:1px solid #F1F5F9'>",
            unsafe_allow_html=True,
        )
