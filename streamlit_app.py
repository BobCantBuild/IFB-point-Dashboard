"""IFB Point Dashboard — Streamlit UI backed by SQLite."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

DB_PATH = Path(__file__).parent / "ifb_point.db"

STATUS_OPTIONS   = ["Contacted", "Not Contacted"]
INTEREST_OPTIONS = ["Interested", "Not Interested"]


def _is_real_date(d) -> bool:
    """True only for an actual datetime.date (not NaT, NaN, None, or a string)."""
    if not isinstance(d, date):
        return False
    try:
        return not pd.isna(d)
    except (TypeError, ValueError):
        return True


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
st.set_page_config(page_title="IFB POINT - Customer Follow Up", layout="wide", page_icon=":bar_chart:")

st.markdown("""
<style>
  /* ── Typography: Inter for a premium feel ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
  html, body, .stApp, [class*="st-"] {
    font-family:'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif !important;
    -webkit-font-smoothing:antialiased;
    -moz-osx-font-smoothing:grayscale;
  }

  /* ── Design tokens ── */
  :root {
    --brand:#2563EB;   --brand-d:#1D4ED8;  --brand-l:#EFF6FF;
    --ink:#0F172A;     --slate:#475569;    --muted:#94A3B8;
    --line:#E2E8F0;    --bg:#F1F5F9;       --bg-soft:#F8FAFC;
    --good:#16A34A;    --good-bg:#DCFCE7;
    --warn:#F59E0B;    --warn-bg:#FEF3C7;
    --bad:#DC2626;     --bad-bg:#FEE2E2;
    --shadow-sm:0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06);
    --shadow-md:0 2px 4px rgba(15,23,42,.04), 0 8px 16px rgba(15,23,42,.06);
    --shadow-lg:0 4px 12px rgba(15,23,42,.06), 0 24px 48px rgba(15,23,42,.10);
    --ease:cubic-bezier(.4,0,.2,1);
  }

  /* ── Tabular numerals for all numbers (clean alignment) ── */
  .s-value, .ss-val, .cnt, .td.center, .td { font-variant-numeric:tabular-nums; }

  /* ── Smooth entry animations ── */
  @keyframes fadeInUp {
    from { opacity:0; transform:translateY(10px); }
    to   { opacity:1; transform:translateY(0); }
  }
  @keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
  @keyframes livePulse {
    0%,100% { box-shadow:0 0 0 0 rgba(16,185,129,0.55); }
    50%     { box-shadow:0 0 0 6px rgba(16,185,129,0); }
  }
  @keyframes shimmer {
    from { background-position:-200px 0; }
    to   { background-position:200px 0; }
  }
  .hero       { animation:fadeInUp .35s var(--ease) both; }
  .stats-row  { animation:fadeInUp .45s var(--ease) both; }
  .sec        { animation:fadeIn   .5s  var(--ease) both; }

  /* ── Page base ── */
  .stApp { background:var(--bg); overflow-x:auto; }
  .block-container {
    /* push scrollable content below the fixed header band */
    padding-top:260px !important; padding-bottom:2rem;
    max-width:1700px;
  }
  header[data-testid="stHeader"] { background:transparent; }
  #MainMenu, footer { visibility:hidden; }

  /* ── FIXED header band (hero + stats) — truly pinned, never scrolls ── */
  .fixed-header {
    position:fixed;
    top:0; left:0; right:0;
    z-index:9999;
    background:var(--bg);
    padding:0.7rem 1rem 0.3rem;
  }

  /* ── Filter panel anchor — collapse it ── */
  .element-container:has(#filter-anchor) {
    display:none !important;
  }
  /* Hide the 0-height JS-injection iframe */
  iframe[title="st_components_html_v1"],
  [data-testid="stCustomComponentV1"] {
    display:none !important; height:0 !important; min-height:0 !important;
  }

  /* ── Hero ── */
  .hero {
    background:
      radial-gradient(circle at 90% 0%, rgba(37,99,235,0.28) 0%, rgba(37,99,235,0) 55%),
      radial-gradient(circle at 0% 100%, rgba(56,189,248,0.15) 0%, rgba(56,189,248,0) 50%),
      linear-gradient(135deg,#0F172A 0%,#1E293B 100%);
    border-radius:14px; padding:10px 24px;
    margin-bottom:18px;
    display:flex; align-items:center; justify-content:space-between;
    box-shadow:var(--shadow-lg);
    position:relative; overflow:hidden;
  }
  .hero h1 {
    margin:0; font-size:24px; font-weight:800; color:#F8FAFC;
    letter-spacing:-0.3px; line-height:1.15;
  }
  .hero p  { margin:5px 0 0; font-size:13px; color:#94A3B8; font-weight:500; }
  .hero .pill {
    display:inline-flex; align-items:center; gap:8px;
    padding:7px 14px 7px 12px; border-radius:999px;
    background:rgba(16,185,129,0.12);
    font-size:12px; font-weight:700; color:#34D399;
    border:1px solid rgba(16,185,129,0.30);
    letter-spacing:0.3px;
  }
  .hero .pill::before {
    content:''; width:8px; height:8px; border-radius:50%;
    background:#10B981; box-shadow:0 0 0 0 rgba(16,185,129,0.6);
    animation:livePulse 2.2s var(--ease) infinite;
  }

  /* ── Stats ── */
  .stats-row { display:flex; gap:10px; margin-bottom:14px; flex-wrap:wrap; align-items:stretch; }
  .stat-solo, .stat-group {
    background:linear-gradient(180deg,#FFFFFF 0%,#FAFBFC 100%);
    border:1px solid var(--line); border-radius:12px;
    padding:10px 16px;
    box-shadow:var(--shadow-sm);
    transition:transform .25s var(--ease), box-shadow .25s var(--ease);
  }
  .stat-solo:hover, .stat-group:hover {
    transform:translateY(-2px);
    box-shadow:var(--shadow-md);
    border-color:#CBD5E1;
  }
  .stat-solo { min-width:120px; flex-shrink:0; }
  .stat-group { flex:1 1 280px; min-width:280px; padding:10px 14px; }

  .s-label, .g-label {
    font-size:10px; font-weight:700; color:var(--muted);
    text-transform:uppercase; letter-spacing:1.2px;
    display:flex; align-items:center; gap:6px;
  }
  .s-value {
    font-size:30px; font-weight:800; line-height:1; margin-top:5px;
    background:linear-gradient(135deg,var(--ink) 0%,#475569 100%);
    -webkit-background-clip:text; background-clip:text;
    color:transparent; letter-spacing:-1px;
  }
  .g-label { margin-bottom:7px; }
  .g-inner { display:flex; gap:6px; flex-wrap:wrap; }
  .sub-stat {
    flex:1; border-radius:8px; padding:7px 6px; text-align:center;
    background:var(--bg-soft); border:1px solid var(--line);
    transition:transform .2s var(--ease), background .2s var(--ease);
  }
  .sub-stat:hover { transform:translateY(-1px); background:#F1F5F9; }
  .ss-val   { font-size:18px; font-weight:800; line-height:1; color:var(--ink); }
  .ss-lbl   { font-size:10px; color:#64748B; margin-top:3px; font-weight:600; }
  .ss-green .ss-val { color:var(--good); }   .ss-red    .ss-val { color:var(--bad); }
  .ss-grey  .ss-val { color:#475569; }       .ss-blue   .ss-val { color:var(--brand); }
  .ss-teal  .ss-val { color:#0D9488; }       .ss-indigo .ss-val { color:#4F46E5; }
  .ss-slate .ss-val { color:#334155; }

  /* ── Filter panel ── */
  .panel {
    background:#fff; border:1px solid var(--line); border-radius:16px;
    padding:14px 20px 6px; margin-bottom:18px;
    box-shadow:var(--shadow-sm);
  }

  /* ── Section pill ── */
  div[role="radiogroup"] {
    gap:4px !important; background:#F1F5F9; padding:5px;
    border-radius:12px; border:1px solid var(--line); width:fit-content;
    box-shadow:inset 0 1px 2px rgba(15,23,42,0.04);
  }
  div[role="radiogroup"] > label {
    background:transparent; border-radius:8px; padding:8px 20px !important;
    margin:0 !important; cursor:pointer; color:var(--slate) !important;
    font-weight:600; font-size:13px;
    transition:all .2s var(--ease);
  }
  div[role="radiogroup"] > label:hover { background:#E2E8F0; color:var(--ink) !important; }
  div[role="radiogroup"] > label[data-checked="true"],
  div[role="radiogroup"] > label:has(input:checked) {
    background:linear-gradient(135deg,var(--brand) 0%,var(--brand-d) 100%) !important;
    color:#fff !important;
    box-shadow:0 2px 6px rgba(37,99,235,0.35);
  }
  div[role="radiogroup"] > label > div:first-child { display:none !important; }

  /* ── Inputs / selects ── */
  div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background:#F8FAFC !important; border-radius:6px !important; border:1px solid #E2E8F0 !important;
  }
  .stDateInput > div > div { background:#F8FAFC !important; border-radius:6px !important; }

  /* ── Buttons ── */
  .stButton > button {
    background:#0F172A; color:#F8FAFC; border:0; border-radius:6px;
    padding:0 10px; font-weight:600; font-size:13px;
    height:42px !important; min-height:42px !important;
    line-height:42px !important; display:inline-flex;
    align-items:center; justify-content:center;
  }
  .stButton > button:hover { background:#1E293B; }

  .stButton > button[disabled],
  .stButton > button:disabled {
    background:#F1F5F9 !important;
    color:#CBD5E1 !important;
    border:1px solid #E2E8F0 !important;
    cursor:not-allowed !important;
    opacity:1 !important;
  }

  /* ── Primary save button ── */
  .stButton > button[kind="primary"] {
    background:#2563EB !important; color:#fff !important;
  }
  .stButton > button[kind="primary"]:hover { background:#1D4ED8 !important; }

  /* ── Lead table (per-row st.columns) — clean minimal style ── */
  .th {
    background:#FFFFFF;
    padding:16px 14px;
    font-size:12.5px; font-weight:600;
    color:#334155; letter-spacing:0.2px;
    border-bottom:1px solid #E2E8F0;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    min-height:50px; display:flex; align-items:center;
  }
  .th.th-first { border-top-left-radius:14px; justify-content:center; }
  .th.th-last  { border-top-right-radius:14px; }

  .td {
    background:#FFFFFF; padding:20px 14px;
    font-size:13.5px; color:#1E293B; font-weight:400;
    border-bottom:1px solid #F1F5F9;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    min-height:64px; display:flex; align-items:center;
  }
  .td.alt     { background:#FFFFFF; }     /* no alternating — all white */
  .td.wrap    { white-space:normal; word-break:break-word; line-height:1.4; }
  /* Row hover: lift the whole row in light blue so eye can track left-to-right */
  [data-testid="stHorizontalBlock"]:has(.td):hover .td { background:#F8FAFC; }
  .td.muted   { color:#CBD5E1; justify-content:center; }
  .td.icon    { justify-content:center; padding:14px 0; }
  .td.center  { justify-content:center; }
  /* Right-edge breathing room so Remarks doesn't touch grey container */
  .td.td-last { padding-right:52px !important; }
  .th.th-last { padding-right:52px !important; }

  /* Status/Interested chips with colored dots */
  .chip {
    display:inline-flex; align-items:center; gap:8px;
    font-size:13.5px; color:#1E293B;
  }
  .chip::before {
    content:''; width:8px; height:8px; border-radius:50%;
    background:#CBD5E1;
  }
  .chip.green::before  { background:#16A34A; }
  .chip.red::before    { background:#DC2626; }
  .chip.slate::before  { background:#94A3B8; }

  /* Default secondary button (dialog Cancel etc.) — proper rectangular */
  .stButton > button[kind="secondary"] {
    background:#FFFFFF !important; color:#475569 !important;
    border:1px solid #CBD5E1 !important;
    height:42px !important; min-height:42px !important;
    padding:0 18px !important; font-size:13px !important; font-weight:600 !important;
    border-radius:8px !important;
  }
  .stButton > button[kind="secondary"]:hover {
    background:#F1F5F9 !important; border-color:#94A3B8 !important; color:#0F172A !important;
  }

  /* Polished primary button (dialog Save) */
  .stButton > button[kind="primary"] {
    background:#2563EB !important; color:#FFFFFF !important; border:0 !important;
    height:42px !important; min-height:42px !important;
    padding:0 18px !important; font-size:13px !important; font-weight:600 !important;
    border-radius:8px !important;
  }
  .stButton > button[kind="primary"]:hover { background:#1D4ED8 !important; }

  /* Pencil edit button — circular icon, ONLY inside table rows */
  [data-testid="stHorizontalBlock"]:has(.td) .stButton > button {
    background:#FFFFFF !important; color:#94A3B8 !important;
    border:1.5px solid #E2E8F0 !important;
    height:38px !important; min-height:38px !important;
    width:38px !important; min-width:38px !important;
    padding:0 !important; font-size:14px !important; font-weight:400 !important;
    border-radius:50% !important;
    margin:0 auto !important;
    line-height:1 !important;
    transition:all .15s ease;
  }
  [data-testid="stHorizontalBlock"]:has(.td) .stButton > button:hover {
    background:var(--brand-l) !important; color:var(--brand) !important;
    border-color:var(--brand) !important;
    transform:scale(1.12) rotate(-8deg);
    box-shadow:0 4px 12px rgba(37,99,235,0.25) !important;
  }
  [data-testid="stHorizontalBlock"]:has(.td) .stButton > button:active {
    transform:scale(0.95) rotate(0deg);
  }

  /* Kill row gaps so cell + button line up perfectly */
  [data-testid="stHorizontalBlock"] { gap:0 !important; margin:0 !important; }
  [data-testid="stVerticalBlock"]   { gap:0 !important; }
  .element-container                { margin:0 !important; padding:0 !important; }
  [data-testid="column"] > div      { gap:0 !important; }

  /* Restore breathing room inside the filter panel */
  .panel + div [data-testid="stHorizontalBlock"] { gap:14px !important; }

  /* ── Legacy data editor polish (kept for stats/etc) ── */
  [data-testid="stDataFrame"] {
    border:1px solid #E2E8F0; border-radius:14px; overflow:hidden;
    box-shadow:0 1px 4px rgba(0,0,0,.05); background:#fff;
  }
  [data-testid="stDataFrame"] [role="columnheader"] {
    background:#F1F5F9 !important;
    color:#475569 !important;
    font-weight:700 !important;
    font-size:11px !important;
    text-transform:uppercase;
    letter-spacing:0.6px;
  }

  /* ── Section header ── */
  .sec { display:flex; align-items:center; gap:10px; margin:6px 0 14px; flex-wrap:wrap; }
  .sec .dot {
    width:9px; height:9px; border-radius:999px;
    background:var(--brand);
    box-shadow:0 0 0 3px rgba(37,99,235,0.18);
  }
  .sec h3   {
    margin:0; font-size:17px; font-weight:800; color:var(--ink);
    letter-spacing:-0.2px;
  }
  .sec .cnt {
    font-size:11px; padding:3px 11px; border-radius:999px;
    background:var(--brand-l); color:var(--brand-d);
    font-weight:700; border:1px solid #BFDBFE;
    letter-spacing:0.3px;
  }
  .sec .sec-help { font-size:12px; color:var(--muted); font-weight:500; margin-left:4px; }

  /* ── Input focus ring (accessibility + polish) ── */
  div[data-baseweb="input"]:focus-within > div,
  div[data-baseweb="select"]:focus-within > div,
  .stDateInput:focus-within > div > div {
    border-color:var(--brand) !important;
    box-shadow:0 0 0 3px rgba(37,99,235,0.15) !important;
  }

  /* ── Uniform filter-row labels & control heights ── */
  /* Label above every filter control */
  [data-testid="stContainer"] label[data-testid="stWidgetLabel"],
  [data-testid="stContainer"] [data-testid="stWidgetLabel"] > div {
    font-size:10px !important; font-weight:700 !important;
    color:var(--slate) !important; text-transform:uppercase !important;
    letter-spacing:0.7px !important;
    margin-bottom:3px !important;
  }
  /* All inputs (date/text/select) — 34px tall, compact */
  [data-testid="stContainer"] div[data-baseweb="input"] > div,
  [data-testid="stContainer"] div[data-baseweb="select"] > div,
  [data-testid="stContainer"] .stDateInput > div > div {
    background:#FFFFFF !important;
    border:1px solid var(--line) !important;
    border-radius:8px !important;
    min-height:34px !important;
  }
  [data-testid="stContainer"] input,
  [data-testid="stContainer"] .stDateInput input {
    height:32px !important; font-size:12.5px !important;
  }
  /* Radio pill row — match the 34px height of the other inputs */
  [data-testid="stContainer"] div[role="radiogroup"] {
    height:34px !important;
    padding:3px !important;
  }
  [data-testid="stContainer"] div[role="radiogroup"] > label {
    height:28px !important; display:inline-flex !important; align-items:center !important;
    padding:0 14px !important; font-size:12px !important;
  }

  /* ── Print-friendly: hide chrome, show full data ── */
  @media print {
    .stApp { background:#FFFFFF !important; overflow:visible !important; }
    .block-container { max-width:none !important; padding:0 !important; }
    .hero, .panel, [data-testid="stToolbar"],
    [data-testid="stDownloadButton"], #refresh_btn,
    .stButton, header[data-testid="stHeader"] { display:none !important; }
    .th, .td { padding:8px 10px !important; min-height:auto !important;
               border-bottom:1px solid #94A3B8 !important; font-size:11px !important; }
    .stats-row, .sec { page-break-inside:avoid; }
    .td.wrap, .td.td-last { white-space:normal !important; }
  }
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
# Fixed header — hero + stats in one sticky block
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
<div class="fixed-header">
  <div class="hero">
    <div>
      <h1>📊&nbsp; IFB POINT &middot; Customer Follow Up</h1>
    </div>
    <span class="pill">LIVE</span>
  </div>
  <div class="stats-row">
    <div class="stat-solo">
      <div class="s-label">👥 Total Follow Up's</div>
      <div class="s-value">{total}</div>
    </div>
    <div class="stat-group">
      <div class="g-label">📞 Contact Status</div>
      <div class="g-inner">
        {sub("ss-green", contacted,    "Contacted")}
        {sub("ss-red",   not_cont,     "Not Contacted")}
        {sub("ss-grey",  s_empty,      "Empty")}
      </div>
    </div>
    <div class="stat-group">
      <div class="g-label">💬 Interest</div>
      <div class="g-inner">
        {sub("ss-green", interested,   "Interested")}
        {sub("ss-red",   not_interest, "Not Interested")}
        {sub("ss-grey",  i_empty,      "Empty")}
      </div>
    </div>
    <div class="stat-group">
      <div class="g-label">🎯 Follow-Up Stage</div>
      <div class="g-inner">
        {sub("ss-blue",   fu.get("Post Purchase Delight Call",0),          "Post Purchase")}
        {sub("ss-teal",   fu.get("Usage & Experience Feedback Call",0),     "Usage & Exp.")}
        {sub("ss-indigo", fu.get("Pre-Warranty Expiry Engagement Call",0),  "Pre-Warranty")}
        {sub("ss-slate",  fu.get("7-Year Loyalty Upgrade Call",0),          "7-Year Loyalty")}
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Section selector — read from session_state BEFORE filter logic runs
# --------------------------------------------------------------------------- #
_SEC_OPTS  = ["Open Followup", "Attempted Followup", "Missed Follow Up's"]
_SEC_EMOJI = {
    "Open Followup":      "📋",
    "Attempted Followup": "📞",
    "Missed Follow Up's": "⚠️",
}
section = st.session_state.get("_view_section", "Open Followup")
if section not in _SEC_OPTS:
    section = "Open Followup"


# --------------------------------------------------------------------------- #
# Filters (fixed bar — date range + search only)
# --------------------------------------------------------------------------- #
# Anchor marker — renders as its own element-container sibling, immediately
# before the filter columns element-container.  CSS collapses it to nothing
# and uses the adjacent-sibling selector (+) to fix the columns container.
st.markdown('<span id="filter-anchor"></span>', unsafe_allow_html=True)

fc1, fc2 = st.columns([1, 1], gap="medium")
with fc1:
    min_pd = df_all["purchase_date"].dropna().min() or date(2019, 1, 1)
    max_pd = df_all["purchase_date"].dropna().max() or today
    date_range = st.date_input(
        "Lead Date Range",
        value=(min_pd, max_pd),
        min_value=min_pd,
        max_value=max_pd,
        format="DD/MM/YYYY",
    )
with fc2:
    search_q = st.text_input(
        "Search",
        placeholder="Customer ID / Name / Phone / Email",
    )

# JS injection — walk the DOM to find the filter columns element-container
# (sibling after #filter-anchor) and force position:fixed on it directly.
# This bypasses all CSS selector reliability issues with Streamlit's DOM.
components.html("""
<script>
(function(){
  function fix(){
    try{
      var doc = window.parent.document;
      var a = doc.getElementById('filter-anchor');
      if(!a){ setTimeout(fix,120); return; }
      // Walk up to the element-container that wraps the anchor
      var ec = a;
      while(ec && !(ec.classList && ec.classList.contains('element-container')))
        ec = ec.parentElement;
      if(!ec){ setTimeout(fix,120); return; }
      // Next sibling element-container = the filter columns
      var n = ec.nextElementSibling;
      while(n && !(n.classList && n.classList.contains('element-container')))
        n = n.nextElementSibling;
      if(!n){ setTimeout(fix,120); return; }
      // Apply fixed positioning via inline style (highest CSS priority)
      n.style.setProperty('position','fixed','important');
      n.style.setProperty('top','172px','important');
      n.style.setProperty('left','0','important');
      n.style.setProperty('right','0','important');
      n.style.setProperty('z-index','9998','important');
      n.style.setProperty('background','#F1F5F9','important');
      n.style.setProperty('padding','0 1rem 0.6rem','important');
      n.style.setProperty('border-bottom','1px solid #E2E8F0','important');
      n.style.setProperty('box-shadow','0 3px 10px rgba(15,23,42,.06)','important');
    }catch(e){ setTimeout(fix,150); }
  }
  // Run on load and re-run on every Streamlit DOM update (rerun)
  fix();
  try{
    new MutationObserver(function(){ fix(); })
      .observe(window.parent.document.body, {childList:true, subtree:false});
  }catch(e){}
})();
</script>
""", height=0)


# --------------------------------------------------------------------------- #
# Filter
# --------------------------------------------------------------------------- #
if section == "Missed Follow Up's":
    # Overdue: scheduled appointment is in the past AND lead has not been contacted.
    today_d = today
    past_appt = df_all["next_appointment"].apply(
        lambda d: _is_real_date(d) and d < today_d
    )
    not_contacted = df_all["status"].fillna("").astype(str) != "Contacted"
    filtered = df_all[past_appt & not_contacted].copy()
elif section == "Attempted Followup":
    # Leads where a follow-up was attempted — status is either Contacted or Not Contacted
    attempted_mask = df_all["status"].fillna("").isin(["Contacted", "Not Contacted"])
    filtered = df_all[attempted_mask].copy()
else:
    # "Open Followup" — all leads
    filtered = df_all.copy()

# date range + search apply to BOTH sections
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

_sec_help  = {
    "Open Followup":      "All leads matching your current filters.",
    "Attempted Followup": "Leads where a follow-up was Contacted or Not Contacted.",
    "Missed Follow Up's": "Leads with overdue Next Appointment and not yet contacted.",
}.get(section, "")

sh1, sh2, sh3 = st.columns([3, 3.5, 1.1])
with sh1:
    st.radio(
        "View",
        options=_SEC_OPTS,
        index=_SEC_OPTS.index(section),
        key="_view_section",
        horizontal=True,
        label_visibility="collapsed",
    )
with sh2:
    st.markdown(f"""
    <div class="sec">
      <span class="dot"></span>
      <h3>{section}</h3>
      <span class="cnt">{len(filtered)} record{'s' if len(filtered)!=1 else ''}</span>
      <span class="sec-help">{_sec_help}</span>
    </div>""", unsafe_allow_html=True)
with sh3:
    if st.button("↻ Refresh", key="refresh_btn",
                 help="Reload data from the database",
                 use_container_width=True):
        st.cache_data.clear()
        try: st.cache_resource.clear()
        except Exception: pass
        st.rerun()


# --------------------------------------------------------------------------- #
# Data table — per-row ✏️ Edit button opens a modal dialog
# --------------------------------------------------------------------------- #

def _safe(v, fallback="—"):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return fallback
    s = str(v).strip()
    return fallback if s in ("", "NaT", "nan", "None") else s


def _fmt_date(d):
    if d is None:
        return "—"
    try:
        if pd.isna(d):
            return "—"
    except (TypeError, ValueError):
        pass
    if isinstance(d, date):
        try:
            return d.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return "—"
    try:
        parsed = pd.to_datetime(d, errors="coerce")
        if pd.isna(parsed):
            return "—"
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return "—"


# ── Modal dialog ────────────────────────────────────────────────────────────
@st.dialog("✏️  Edit Lead")
def edit_lead_dialog(row: dict):
    cid = int(row["customer_id"])
    name = row.get("customer_name") or "—"
    machine = row.get("machine_type") or "—"

    st.markdown(
        f"<div style='font-size:12px;color:#94A3B8;text-transform:uppercase;"
        f"letter-spacing:0.7px;margin-bottom:2px;'>Customer</div>"
        f"<div style='font-size:20px;font-weight:700;color:#0F172A;line-height:1.2;'>{name}</div>"
        f"<div style='font-size:12px;color:#94A3B8;margin:4px 0 16px;'>"
        f"ID {cid} &nbsp;·&nbsp; {machine}</div>",
        unsafe_allow_html=True,
    )

    cur_s = row.get("status")           if pd.notna(row.get("status"))           else None
    cur_i = row.get("interested")       if pd.notna(row.get("interested"))       else None
    cur_r = str(row.get("remarks"))     if pd.notna(row.get("remarks")) and row.get("remarks") else ""

    # Date can be None / pd.NaT / datetime.date — coerce safely
    raw_a = row.get("next_appointment")
    cur_a = None
    if raw_a is not None:
        try:
            if not pd.isna(raw_a):
                if isinstance(raw_a, date):
                    cur_a = raw_a
                else:
                    parsed = pd.to_datetime(raw_a, errors="coerce")
                    cur_a = parsed.date() if pd.notna(parsed) else None
        except (TypeError, ValueError):
            cur_a = None

    s_opts = ["—"] + STATUS_OPTIONS
    i_opts = ["—"] + INTEREST_OPTIONS

    ns = st.selectbox("Status", s_opts,
                      index=s_opts.index(cur_s) if cur_s in STATUS_OPTIONS else 0,
                      key=f"dlg_s_{cid}")
    na = st.date_input("Next Appointment",
                       value=cur_a, min_value=today, key=f"dlg_a_{cid}")
    ni = st.selectbox("Interested?", i_opts,
                      index=i_opts.index(cur_i) if cur_i in INTEREST_OPTIONS else 0,
                      key=f"dlg_i_{cid}")
    nr = st.text_area("Remarks", value=cur_r, height=110, key=f"dlg_r_{cid}")

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾  Save", type="primary", use_container_width=True,
                     key=f"dlg_save_{cid}"):
            try:
                update_row(
                    cid,
                    None if ns == "—" else ns,
                    na if isinstance(na, date) else None,
                    None if ni == "—" else ni,
                    nr.strip() or None,
                )
                st.toast(f"Saved changes for {name}", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed — {type(e).__name__}: {e}")
    with c2:
        if st.button("Cancel", use_container_width=True, key=f"dlg_cancel_{cid}"):
            st.rerun()


# ── Table rendering ─────────────────────────────────────────────────────────
# Editing is allowed in BOTH sections — a missed follow-up should be actionable.
read_only = False

if len(filtered) == 0:
    st.markdown(
        "<div style='text-align:center;padding:64px 20px;color:#94A3B8;"
        "background:#fff;border:1px solid #E2E8F0;border-radius:14px;"
        "box-shadow:0 1px 4px rgba(0,0,0,.04);font-size:14px;'>"
        "No records match the current filters.</div>",
        unsafe_allow_html=True,
    )
else:
    # ── Pagination ──────────────────────────────────────────────────────────
    PAGE_SIZE = 30
    total_rows  = len(filtered)
    total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)

    # reset page if filters changed the row count below current page's range
    pg_sig_key = f"pg_sig_{section}"
    sig = (section, total_rows, tuple(filtered["customer_id"].head(3).tolist()))
    if st.session_state.get(pg_sig_key) != sig:
        st.session_state[pg_sig_key] = sig
        st.session_state["page_num"] = 1

    st.session_state.setdefault("page_num", 1)
    page = max(1, min(st.session_state["page_num"], total_pages))
    st.session_state["page_num"] = page

    start = (page - 1) * PAGE_SIZE
    end   = min(start + PAGE_SIZE, total_rows)
    page_df = filtered.iloc[start:end]

    # column ratios:  edit  follow-up  id    name  date  machine  phone  email  status  appt  int   remarks
    R   = [0.4,      2.7,       0.45, 1.25, 0.95, 1.45,    0.95,  1.65,  1.0,    0.95, 1.05, 2.4]
    HDR = ["",       "Customer Follow-Up", "ID", "Customer Name", "Purchase Date",
           "Machine Type", "Phone", "Email", "Status", "Next Appt",
           "Interested?", "Remarks"]

    # Header row
    hdr = st.columns(R)
    last_i = len(HDR) - 1
    for i, (c, lbl) in enumerate(zip(hdr, HDR)):
        extra = (" th-first" if i == 0 else "") + (" th-last" if i == last_i else "")
        style = " style='padding-right:56px;margin-right:6px;'" if i == last_i else ""
        c.markdown(f"<div class='th{extra}'{style}>{lbl}</div>", unsafe_allow_html=True)

    def _status_chip(v):
        s = _safe(v)
        if s == "Contacted":     return f"<span class='chip green'>{s}</span>"
        if s == "Not Contacted": return f"<span class='chip red'>{s}</span>"
        if s == "—":             return "<span class='chip'>—</span>"
        return f"<span class='chip slate'>{s}</span>"

    def _interest_chip(v):
        s = _safe(v)
        if s == "Interested":     return f"<span class='chip green'>{s}</span>"
        if s == "Not Interested": return f"<span class='chip red'>{s}</span>"
        if s == "—":              return "<span class='chip'>—</span>"
        return f"<span class='chip slate'>{s}</span>"

    # Data rows
    for ri, (_, row) in enumerate(page_df.iterrows()):
        cid = int(row["customer_id"])
        cols = st.columns(R)

        # 0 — pencil edit icon (circular outlined button)
        with cols[0]:
            if not read_only:
                if st.button("✏️", key=f"edit_{cid}",
                             help=f"Edit lead {cid}"):
                    edit_lead_dialog(row.to_dict())
            else:
                st.markdown("<div class='td muted'>—</div>", unsafe_allow_html=True)

        # 1–11 data cells
        cols[1].markdown(f"<div class='td'>{_safe(row.get('customer_follow_up'))}</div>",                  unsafe_allow_html=True)
        cols[2].markdown(f"<div class='td center'>{cid}</div>",                                            unsafe_allow_html=True)
        cols[3].markdown(f"<div class='td'><b>{_safe(row.get('customer_name'))}</b></div>",                unsafe_allow_html=True)
        cols[4].markdown(f"<div class='td'>{_fmt_date(row.get('purchase_date'))}</div>",                   unsafe_allow_html=True)
        cols[5].markdown(f"<div class='td'>{_safe(row.get('machine_type'))}</div>",                        unsafe_allow_html=True)
        cols[6].markdown(f"<div class='td'>{_safe(row.get('phone_number'))}</div>",                        unsafe_allow_html=True)
        cols[7].markdown(f"<div class='td'>{_safe(row.get('email_id'))}</div>",                            unsafe_allow_html=True)
        cols[8].markdown(f"<div class='td'>{_status_chip(row.get('status'))}</div>",                       unsafe_allow_html=True)
        cols[9].markdown(f"<div class='td'>{_fmt_date(row.get('next_appointment'))}</div>",                unsafe_allow_html=True)
        cols[10].markdown(f"<div class='td'>{_interest_chip(row.get('interested'))}</div>",                unsafe_allow_html=True)
        _rem_full = _safe(row.get('remarks'))
        _rem_tip  = _rem_full.replace("'", "&#39;").replace('"', "&quot;")
        cols[11].markdown(
            f"<div class='td td-last' style='padding-right:48px;margin-right:8px;' title='{_rem_tip}'>"
            f"<span style='overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
            f"min-width:0;flex:1;display:block;'>{_rem_full}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Pagination bar ──────────────────────────────────────────────────────
    st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)
    pc1, pc2, pc3 = st.columns([1.2, 6, 1.2])
    with pc1:
        if st.button("◀  Previous", key="pg_prev", type="secondary",
                     use_container_width=True, disabled=(page <= 1)):
            st.session_state["page_num"] = page - 1
            st.rerun()
    with pc2:
        cap = "Click the ✏️ icon on any row to open the edit dialog."
        showing_from = start + 1 if total_rows else 0
        st.markdown(
            f"<div style='text-align:center;padding:10px 0;color:var(--slate);"
            f"font-size:13px;font-weight:600;font-variant-numeric:tabular-nums;'>"
            f"Showing <b style='color:var(--ink);'>{showing_from}–{end}</b> "
            f"of <b style='color:var(--ink);'>{total_rows}</b> "
            f"&nbsp;·&nbsp; Page "
            f"<span style='background:var(--brand-l);color:var(--brand-d);"
            f"padding:2px 8px;border-radius:6px;font-weight:700;'>{page}</span>"
            f" of <b>{total_pages}</b></div>"
            f"<div style='text-align:center;color:var(--muted);font-size:12px;"
            f"margin-top:2px;'>{cap}</div>",
            unsafe_allow_html=True,
        )
    with pc3:
        if st.button("Next  ▶", key="pg_next", type="secondary",
                     use_container_width=True, disabled=(page >= total_pages)):
            st.session_state["page_num"] = page + 1
            st.rerun()
