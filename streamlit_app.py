"""IFB Point Dashboard — Streamlit UI backed by SQLite."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "ifb_point.db"

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
def get_conn():
    return sqlite3.connect(DB_PATH)


def load_all() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM customers", conn)
    df["purchase_date"]    = pd.to_datetime(df["purchase_date"],    errors="coerce").dt.date
    df["next_appointment"] = pd.to_datetime(df["next_appointment"], errors="coerce").dt.date
    _today = date.today()
    df["customer_follow_up"] = df["purchase_date"].apply(
        lambda d: compute_follow_up(d, _today)
    )
    return df


def update_row(cid, status, next_appt, interested, remarks):
    appt_str = next_appt.isoformat() if isinstance(next_appt, date) else None
    with get_conn() as conn:
        conn.execute(
            "UPDATE customers SET status=?, next_appointment=?, interested=?, remarks=? "
            "WHERE customer_id=?",
            (status, appt_str, interested, remarks, cid),
        )
        conn.commit()


COL_MAP = {
    "IFB point ID": "ifb_point_id", "Customer_ID": "customer_id",
    "Customer name": "customer_name", "Purchase Date": "purchase_date",
    "Machine Type": "machine_type", "Phone number": "phone_number",
    "Email ID": "email_id", "Status": "status",
    "Next appointment": "next_appointment",
    "Interested/ Not Interested": "interested", "Remarks": "remarks",
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
    for src in [
        Path(r"C:\Users\aswin\Downloads\IFB point customer dummy data.xlsx"),
        Path(__file__).parent / "data.csv",
    ]:
        if src.exists():
            df = pd.read_excel(src) if src.suffix == ".xlsx" else pd.read_csv(src)
            break
    if df is not None:
        df = df.rename(columns=COL_MAP)
        for col in ("purchase_date", "next_appointment"):
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
        df["phone_number"] = df["phone_number"].astype(str)
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(DB_SCHEMA)
        df.to_sql("customers", conn, if_exists="append", index=False)
        conn.commit(); conn.close()


# --------------------------------------------------------------------------- #
# Page setup
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="IFB Point Dashboard", layout="wide", page_icon=":bar_chart:")

st.markdown("""
<style>
  .stApp { background:#F1F5F9; }
  .block-container { padding-top:1.4rem; padding-bottom:2rem; max-width:1440px; }
  header[data-testid="stHeader"] { background:transparent; }
  #MainMenu, footer { visibility:hidden; }

  /* ── Data editor / dataframe ── */
  div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] {
    border-radius:12px !important; overflow:hidden;
    border:1px solid #CBD5E1 !important;
    box-shadow:0 1px 8px rgba(0,0,0,.07) !important;
  }
  /* header row */
  div[data-testid="stDataEditor"] th,
  div[data-testid="stDataFrame"] th {
    background:#F1F5F9 !important; font-weight:700 !important;
    font-size:12px !important; text-transform:uppercase !important;
    letter-spacing:0.6px !important; color:#475569 !important;
    padding:10px 14px !important;
  }
  /* body cells */
  div[data-testid="stDataEditor"] td,
  div[data-testid="stDataFrame"] td {
    font-size:13px !important; padding:10px 14px !important;
    color:#1E293B !important;
  }

  /* ── Hero ── */
  .hero {
    background:#0F172A; border-radius:16px; padding:22px 28px;
    margin-bottom:18px; display:flex; align-items:center; justify-content:space-between;
  }
  .hero h1 { margin:0; font-size:22px; font-weight:700; color:#F8FAFC; }
  .hero p  { margin:4px 0 0; font-size:13px; color:#94A3B8; }
  .hero .pill {
    padding:5px 14px; border-radius:6px; background:#1E293B;
    font-size:12px; font-weight:600; color:#38BDF8; border:1px solid #334155;
  }

  /* ── Stats ── */
  .stats-row { display:flex; gap:12px; margin-bottom:16px; }
  .stat-solo {
    background:#fff; border:1px solid #E2E8F0; border-radius:14px;
    padding:20px 22px; min-width:120px; flex-shrink:0;
    box-shadow:0 1px 4px rgba(0,0,0,.06);
  }
  .s-label { font-size:11px; font-weight:600; color:#94A3B8; text-transform:uppercase; letter-spacing:1px; }
  .s-value { font-size:38px; font-weight:800; line-height:1; color:#0F172A; margin-top:6px; }
  .s-sub   { font-size:11px; color:#CBD5E1; margin-top:5px; }
  .stat-group {
    background:#fff; border:1px solid #E2E8F0; border-radius:14px;
    padding:16px 18px; flex:1; box-shadow:0 1px 4px rgba(0,0,0,.06);
  }
  .g-label { font-size:11px; font-weight:600; color:#94A3B8; text-transform:uppercase; letter-spacing:1px; margin-bottom:10px; }
  .g-inner { display:flex; gap:8px; }
  .sub-stat { flex:1; border-radius:8px; padding:10px 8px; text-align:center; background:#F8FAFC; border:1px solid #E2E8F0; }
  .ss-val   { font-size:22px; font-weight:800; line-height:1; color:#0F172A; }
  .ss-lbl   { font-size:10px; color:#64748B; margin-top:4px; }
  .ss-green .ss-val { color:#16A34A; } .ss-red   .ss-val { color:#DC2626; }
  .ss-grey  .ss-val { color:#475569; } .ss-blue  .ss-val { color:#2563EB; }
  .ss-teal  .ss-val { color:#0D9488; } .ss-indigo .ss-val { color:#4F46E5; }
  .ss-slate .ss-val { color:#334155; }

  /* ── Filter panel ── */
  .panel {
    background:#fff; border:1px solid #E2E8F0; border-radius:14px;
    padding:14px 20px 6px; margin-bottom:16px; box-shadow:0 1px 4px rgba(0,0,0,.05);
  }

  /* ── Section pill ── */
  div[role="radiogroup"] {
    gap:4px !important; background:#F1F5F9; padding:4px;
    border-radius:10px; border:1px solid #E2E8F0; width:fit-content;
  }
  div[role="radiogroup"] > label {
    background:transparent; border-radius:7px; padding:7px 18px !important;
    margin:0 !important; cursor:pointer; color:#334155 !important;
    font-weight:600; font-size:13px; transition:all .15s;
  }
  div[role="radiogroup"] > label:hover { background:#E2E8F0; }
  div[role="radiogroup"] > label[data-checked="true"],
  div[role="radiogroup"] > label:has(input:checked) {
    background:#2563EB !important; color:#fff !important;
  }
  div[role="radiogroup"] > label > div:first-child { display:none !important; }

  /* ── Inputs / selects ── */
  div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background:#F8FAFC !important; border-radius:6px !important; border:1px solid #E2E8F0 !important;
  }
  .stDateInput > div > div { background:#F8FAFC !important; border-radius:6px !important; }

  /* ── Buttons ── */
  .stButton > button {
    background:#0F172A; color:#F8FAFC; border:0; border-radius:8px;
    padding:6px 14px; font-weight:600; font-size:13px;
    height:36px !important; min-height:0 !important;
    line-height:1 !important;
  }
  .stButton > button:hover { background:#1E293B; }

  /* ── Section header ── */
  .sec { display:flex; align-items:center; gap:10px; margin:6px 0 14px; }
  .sec .dot { width:8px; height:8px; border-radius:999px; background:#2563EB; }
  .sec h3   { margin:0; font-size:16px; font-weight:700; color:#0F172A; }
  .sec .cnt { font-size:11px; padding:2px 10px; border-radius:999px; background:#F1F5F9;
              color:#64748B; font-weight:600; border:1px solid #E2E8F0; }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Boot
# --------------------------------------------------------------------------- #
init_db_if_missing()
if not DB_PATH.exists():
    st.error("Database not found. Run `python seed_db.py` locally.")
    st.stop()

df_all = load_all()
today  = date.today()


# --------------------------------------------------------------------------- #
# Hero
# --------------------------------------------------------------------------- #
st.markdown(f"""
<div class="hero">
  <div>
    <h1>IFB Point Dashboard</h1>
    <p>Customer Follow-Up Management &nbsp;&middot;&nbsp; {today.strftime('%A, %d %B %Y')}</p>
  </div>
  <span class="pill">&#9679;&nbsp; Live</span>
</div>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Stats row
# --------------------------------------------------------------------------- #
total        = len(df_all)
contacted    = int((df_all["status"]     == "Contacted").sum())
not_cont     = int((df_all["status"]     == "Not Contacted").sum())
s_empty      = total - contacted - not_cont
interested   = int((df_all["interested"] == "Interested").sum())
not_interest = int((df_all["interested"] == "Not Interested").sum())
i_empty      = total - interested - not_interest
fu           = df_all["customer_follow_up"].value_counts().to_dict()

def sub(cls, val, lbl):
    return f'<div class="sub-stat {cls}"><div class="ss-val">{val}</div><div class="ss-lbl">{lbl}</div></div>'

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
      {sub("ss-blue",   fu.get("Post Purchase Delight Call",0),          "Post Purchase")}
      {sub("ss-teal",   fu.get("Usage & Experience Feedback Call",0),     "Usage & Exp.")}
      {sub("ss-indigo", fu.get("Pre-Warranty Expiry Engagement Call",0),  "Pre-Warranty")}
      {sub("ss-slate",  fu.get("7-Year Loyalty Upgrade Call",0),          "7-Year Loyalty")}
    </div>
  </div>
</div>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
st.markdown('<div class="panel">', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns([1.2, 1.4, 1.4])
with fc1:
    section = st.radio("Section", ["Today's Lead", "Missed Leads"],
                       horizontal=True, label_visibility="collapsed")
with fc2:
    min_pd = df_all["purchase_date"].dropna().min() or date(2019, 1, 1)
    max_pd = df_all["purchase_date"].dropna().max() or today
    date_range = st.date_input("Lead Date range", value=(min_pd, max_pd),
                               min_value=min_pd, max_value=max_pd)
with fc3:
    search_q = st.text_input("Search", placeholder="Customer ID / Name / Phone / Email")
st.markdown('</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Filter
# --------------------------------------------------------------------------- #
if section == "Missed Leads":
    filtered = df_all.iloc[0:0].copy()
else:
    filtered = df_all.copy()
    if isinstance(date_range, tuple) and len(date_range) == 2:
        d0, d1 = date_range
        filtered = filtered[filtered["purchase_date"].between(d0, d1)]
    q = search_q.strip()
    if q:
        mask = (filtered["customer_name"].str.contains(q, case=False, na=False) |
                filtered["phone_number"].str.contains(q, case=False, na=False)  |
                filtered["email_id"].str.contains(q, case=False, na=False))
        try:
            mask |= (filtered["customer_id"] == int(q))
        except ValueError:
            pass
        filtered = filtered[mask]

st.markdown(f"""
<div class="sec">
  <span class="dot"></span>
  <h3>{section}</h3>
  <span class="cnt">{len(filtered)} record{'s' if len(filtered)!=1 else ''}</span>
</div>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Table  — st.data_editor (horizontal + vertical scroll, proper grid)
# --------------------------------------------------------------------------- #
DISPLAY_COLS = [
    "customer_follow_up", "customer_id", "customer_name", "purchase_date",
    "machine_type", "phone_number", "email_id",
    "status", "next_appointment", "interested", "remarks",
]

def _norm(v):
    return None if (v is None or v == "—" or
                    (isinstance(v, float) and pd.isna(v))) else v

def diff_and_save(original: pd.DataFrame, edited: pd.DataFrame) -> int:
    editable = ["status", "next_appointment", "interested", "remarks"]
    o = original.set_index("customer_id")
    e = edited.set_index("customer_id")
    saved = 0
    for cid, erow in e.iterrows():
        if cid not in o.index:
            continue
        orig = o.loc[cid]
        changed = False
        for col in editable:
            ov = _norm(orig[col])
            ev = _norm(erow[col])
            if isinstance(ov, pd.Timestamp): ov = ov.date()
            if isinstance(ev, pd.Timestamp): ev = ev.date()
            if ov != ev:
                changed = True
                break
        if changed:
            appt = erow["next_appointment"]
            update_row(
                int(cid),
                _norm(erow["status"]),
                appt if isinstance(appt, date) else None,
                _norm(erow["interested"]),
                _norm(erow["remarks"]),
            )
            saved += 1
    return saved

if len(filtered) == 0:
    st.info("No records match your filters.")
else:
    view = filtered[DISPLAY_COLS].copy()
    for c in ["status", "interested", "remarks"]:
        view[c] = view[c].fillna("—")

    is_today = (section == "Today's Lead")

    edited = st.data_editor(
        view,
        key=f"tbl_{section}",
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        height=600,
        column_config={
            "customer_follow_up": st.column_config.TextColumn(
                "Customer Follow-Up", disabled=True, width=220),
            "customer_id": st.column_config.NumberColumn(
                "ID", disabled=True, width=70),
            "customer_name": st.column_config.TextColumn(
                "Name", disabled=True, width=110),
            "purchase_date": st.column_config.DateColumn(
                "Purchase Date", disabled=True, format="DD/MM/YYYY", width=120),
            "machine_type": st.column_config.TextColumn(
                "Machine Type", disabled=True, width=200),
            "phone_number": st.column_config.TextColumn(
                "Phone", disabled=True, width=120),
            "email_id": st.column_config.TextColumn(
                "Email", disabled=True, width=180),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["—"] + STATUS_OPTIONS,
                disabled=not is_today, width=150,
                help="Click to update"),
            "next_appointment": st.column_config.DateColumn(
                "Next Appointment",
                disabled=not is_today,
                min_value=today, format="DD/MM/YYYY", width=150,
                help="Pick a future date"),
            "interested": st.column_config.SelectboxColumn(
                "Interested / Not Interested",
                options=["—"] + INTEREST_OPTIONS,
                disabled=not is_today, width=190,
                help="Click to update"),
            "remarks": st.column_config.TextColumn(
                "Remarks",
                disabled=not is_today, width=200,
                help="Type remarks"),
        },
    )

    if is_today:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        sc, _ = st.columns([1, 7])
        with sc:
            if st.button("Save changes", type="primary", use_container_width=True):
                n = diff_and_save(filtered, edited)
                if n:
                    st.success(f"Saved {n} row(s).")
                    st.rerun()
                else:
                    st.info("No changes to save.")
