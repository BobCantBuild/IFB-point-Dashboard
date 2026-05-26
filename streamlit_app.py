"""IFB Point Dashboard — Streamlit UI backed by SQLite."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests as _req
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
        return "Post-Purchase"
    elif days <= 30:
        return "1st 30 days call"
    elif days <= 1460:
        return "Pre-AMC"
    else:
        return "8 Year Upgrade"


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
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.execute(
            "UPDATE customers SET status=?, next_appointment=?, interested=?, remarks=? "
            "WHERE customer_id=?",
            (status, appt_str, interested, remarks, cid),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise RuntimeError(f"No row found with customer_id={cid}")
    finally:
        conn.close()


# ─── Live API integration ────────────────────────────────────────────────────
# Two endpoints from IFB BSE:
#   POST /api/Auth/login                              → JWT Bearer token
#   GET  /api/IFBPointFollowUp/GetInstallationAgeingDetails?IFBPointCode=…
#                                                     → customer installation list
#
# Credentials + IFBPointCode come from .streamlit/secrets.toml (gitignored).
# Set the same keys in Streamlit Cloud → App Settings → Secrets.
# ─────────────────────────────────────────────────────────────────────────────

_API_BASE = "https://bseapi.ifbsupport.com/api"


def _api_creds() -> tuple[str, str, str]:
    """Return (username, password, ifb_point_code) from Streamlit secrets."""
    try:
        s = st.secrets["api"]
        return (
            s.get("username",       "IFBFollowUPAPP"),
            s.get("password",       ""),
            s.get("ifb_point_code", "ADSF"),
        )
    except Exception:
        return "IFBFollowUPAPP", "", "ADSF"


@st.cache_data(ttl=3300, show_spinner=False)   # cache token for 55 min (expires ~1 h)
def _api_token() -> str | None:
    """Login and return a Bearer token, or None if the API is unreachable."""
    u, p, _ = _api_creds()
    if not p:
        return None      # no credentials configured
    try:
        r = _req.post(
            f"{_API_BASE}/Auth/login",
            json={"userName": u, "password": p},
            timeout=10,
        )
        r.raise_for_status()
        j = r.json()
        # Try the field names most IFB BSE responses use
        return (
            j.get("token") or
            j.get("accessToken") or
            j.get("access_token") or
            (j.get("data") or {}).get("token") or
            (j.get("result") or {}).get("token")
        )
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)    # cache raw list for 5 min
def _fetch_api_raw() -> list | None:
    """Call GetInstallationAgeingDetails and return raw record list, or None."""
    _, _, code = _api_creds()
    tok = _api_token()
    if not tok:
        return None
    try:
        r = _req.get(
            f"{_API_BASE}/IFBPointFollowUp/GetInstallationAgeingDetails",
            params={"IFBPointCode": code},
            headers={"Authorization": f"Bearer {tok}"},
            timeout=15,
        )
        r.raise_for_status()
        j = r.json()
        # API may return a bare list or wrap it inside a key
        return j if isinstance(j, list) else (
            j.get("data") or j.get("records") or j.get("result") or []
        )
    except Exception:
        return None


# ── Field-name mapping: API response key → our SQLite column ─────────────────
# If the real API uses different names, update the LEFT-hand keys below.
# You can check the raw response by enabling "Show raw API response" in the
# sidebar (add st.sidebar.checkbox("Debug API") and print _fetch_api_raw()).
_API_FIELD_MAP: dict[str, str] = {
    # Customer identity
    "CustomerID":        "customer_id",
    "CustomerId":        "customer_id",
    "customerID":        "customer_id",
    "customerId":        "customer_id",
    # IFB Point branch
    "IFBPointID":        "ifb_point_id",
    "IFBPointId":        "ifb_point_id",
    "ifbPointId":        "ifb_point_id",
    # Name
    "CustomerName":      "customer_name",
    "customerName":      "customer_name",
    "Name":              "customer_name",
    # Phone
    "CustomerMobile":    "phone_number",
    "MobileNumber":      "phone_number",
    "PhoneNumber":       "phone_number",
    "Mobile":            "phone_number",
    "Phone":             "phone_number",
    # Email
    "CustomerEmail":     "email_id",
    "EmailID":           "email_id",
    "Email":             "email_id",
    # Machine / product
    "ProductCode":       "machine_type",
    "ModelNumber":       "machine_type",
    "MachineType":       "machine_type",
    "ProductName":       "machine_type",
    "Model":             "machine_type",
    # Dates
    "PurchaseDate":      "purchase_date",
    "InstallationDate":  "purchase_date",
    "SaleDate":          "purchase_date",
    "purchaseDate":      "purchase_date",
    "installationDate":  "purchase_date",
}

# Columns we upsert from API into SQLite (never touch follow-up tracking fields)
_API_UPSERT_COLS = ("customer_id", "ifb_point_id", "customer_name",
                    "purchase_date", "machine_type", "phone_number", "email_id")


def sync_api_to_db() -> tuple[bool, str]:
    """
    Pull the latest customer list from IFB BSE API and upsert base fields into
    SQLite.  Follow-up fields (status, next_appointment, interested, remarks)
    are NEVER overwritten — they're managed locally by the dashboard users.

    Returns (success: bool, human-readable message: str).
    """
    records = _fetch_api_raw()
    if not records:
        return False, "API unreachable or returned no data — showing local data."

    raw = pd.DataFrame(records)

    # Apply field map (first match wins — avoid duplicate targets)
    seen: set[str] = set()
    rename: dict[str, str] = {}
    for src, tgt in _API_FIELD_MAP.items():
        if src in raw.columns and tgt not in seen:
            rename[src] = tgt
            seen.add(tgt)
    if rename:
        raw = raw.rename(columns=rename)

    if "customer_id" not in raw.columns:
        cols = list(raw.columns[:10])
        return False, (
            f"API field mapping failed — 'customer_id' not found. "
            f"Actual columns: {cols}. Update _API_FIELD_MAP in the source."
        )

    upsert_cols = [c for c in _API_UPSERT_COLS if c in raw.columns]

    # Normalise
    if "purchase_date" in raw.columns:
        raw["purchase_date"] = (
            pd.to_datetime(raw["purchase_date"], errors="coerce")
            .dt.strftime("%Y-%m-%d")
        )
    if "phone_number" in raw.columns:
        raw["phone_number"] = raw["phone_number"].astype(str)

    df = raw[upsert_cols].dropna(subset=["customer_id"])

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(DB_SCHEMA)
        ins = upd = 0
        for _, row in df.iterrows():
            cid = row["customer_id"]
            exists = conn.execute(
                "SELECT 1 FROM customers WHERE customer_id=?", (cid,)
            ).fetchone()
            if exists:
                non_id = [c for c in upsert_cols if c != "customer_id"]
                set_sql = ", ".join(f"{c}=?" for c in non_id)
                vals = [row[c] for c in non_id] + [cid]
                conn.execute(
                    f"UPDATE customers SET {set_sql} WHERE customer_id=?", vals
                )
                upd += 1
            else:
                ph = ", ".join("?" for _ in upsert_cols)
                conn.execute(
                    f"INSERT INTO customers ({', '.join(upsert_cols)}) "
                    f"VALUES ({ph})",
                    [row[c] for c in upsert_cols],
                )
                ins += 1
        conn.commit()
        return True, f"✅ API sync OK — {ins} new · {upd} updated · {datetime.now().strftime('%H:%M:%S')}"
    except Exception as exc:
        return False, f"DB sync error: {exc}"
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
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


  /* ── Inputs / selects (default everywhere) ── */
  div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background:#F8FAFC !important; border-radius:6px !important; border:1px solid #E2E8F0 !important;
  }
  .stDateInput > div > div { background:#F8FAFC !important; border-radius:6px !important; }

  /* ── Filter-bar control polish: uniform 42px height, consistent look ── */
  .stDateInput > div > div,
  div[data-baseweb="input"] > div,
  div[data-baseweb="select"] > div {
    min-height:42px !important; height:42px !important;
    border-radius:10px !important;
    border:1px solid var(--line) !important;
    background:#FFFFFF !important;
    box-shadow:inset 0 1px 3px rgba(15,23,42,0.04);
    transition:border-color .18s var(--ease), box-shadow .18s var(--ease);
  }
  .stDateInput input,
  div[data-baseweb="input"] input,
  div[data-baseweb="select"] [role="combobox"] {
    font-size:13px !important;
    color:var(--ink) !important;
    text-align:center !important;
    font-weight:500 !important;
  }
  /* Focus ring */
  .stDateInput > div > div:focus-within,
  div[data-baseweb="input"] > div:focus-within,
  div[data-baseweb="select"] > div:focus-within {
    border-color:var(--brand) !important;
    box-shadow:0 0 0 3px rgba(37,99,235,0.12) !important;
  }
  /* Hover */
  .stDateInput > div > div:hover,
  div[data-baseweb="input"] > div:hover,
  div[data-baseweb="select"] > div:hover {
    border-color:#94A3B8 !important;
  }
  /* Selectbox dropdown arrow — keep it centred with text */
  div[data-baseweb="select"] [data-testid="stMarkdownContainer"] {
    display:flex; align-items:center; justify-content:center;
  }

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

  /* Primary button — dark blue (active toggle + dialog Save) */
  .stButton > button[kind="primary"] {
    background:linear-gradient(135deg,#1E3A8A 0%,#1D4ED8 100%) !important;
    color:#FFFFFF !important; border:0 !important;
    box-shadow:0 2px 8px rgba(29,78,216,0.35) !important;
    height:42px !important; min-height:42px !important;
    padding:0 18px !important; font-size:13px !important; font-weight:700 !important;
    border-radius:10px !important;
  }
  .stButton > button[kind="primary"]:hover {
    background:linear-gradient(135deg,#1e3a8a 0%,#1e40af 100%) !important;
    box-shadow:0 4px 12px rgba(29,78,216,0.45) !important;
  }

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

  /* ── Status header dropdown — looks like a plain header cell ── */
  [data-testid="stHorizontalBlock"]:has(.th) [data-testid="column"]:has([data-baseweb="select"]) div[data-baseweb="select"] > div {
    background:#FFFFFF !important; border:0 !important;
    border-bottom:1px solid #E2E8F0 !important;
    border-radius:0 !important; box-shadow:none !important;
    height:50px !important; min-height:50px !important;
    font-size:12.5px !important; font-weight:600 !important;
    color:#334155 !important; padding:0 14px !important;
  }
  [data-testid="stHorizontalBlock"]:has(.th) [data-testid="column"]:has([data-baseweb="select"]) div[data-baseweb="select"] > div:hover {
    background:#F1F5F9 !important; color:#0F172A !important;
  }
  /* Tint the cell green when Contacted is selected */
  [data-testid="stHorizontalBlock"]:has(.th) [data-testid="column"]:has([data-baseweb="select"]) [aria-selected="true"] ~ div[data-baseweb="select"] > div {
    background:#F0FDF4 !important;
  }

  /* ── Sortable column header buttons ── */
  /* Target buttons that live inside the header row (identified by .th siblings) */
  [data-testid="stHorizontalBlock"]:has(.th) .stButton > button {
    background:#FFFFFF !important; color:#334155 !important;
    border:0 !important; border-bottom:1px solid #E2E8F0 !important;
    border-radius:0 !important; box-shadow:none !important;
    height:50px !important; min-height:50px !important;
    width:100% !important; padding:0 14px !important;
    font-size:12.5px !important; font-weight:600 !important;
    letter-spacing:0.2px !important;
    justify-content:flex-start !important; align-items:center !important;
    display:flex !important; white-space:nowrap !important;
    transition:background .15s, color .15s;
  }
  [data-testid="stHorizontalBlock"]:has(.th) .stButton > button:hover {
    background:#F1F5F9 !important; color:#0F172A !important;
  }
  /* Active sort column — brand-tinted header */
  [data-testid="stHorizontalBlock"]:has(.th) .stButton > button.sort-active {
    color:var(--brand) !important; background:#EFF6FF !important;
  }

  /* ── API sync status badges ── */
  .api-ok {
    font-size:11px; font-weight:700; padding:4px 10px; border-radius:999px;
    background:rgba(16,185,129,0.12); color:#34D399;
    border:1px solid rgba(16,185,129,0.30); letter-spacing:0.3px;
  }
  .api-err {
    font-size:11px; font-weight:700; padding:4px 10px; border-radius:999px;
    background:rgba(220,38,38,0.10); color:#F87171;
    border:1px solid rgba(220,38,38,0.25); letter-spacing:0.3px;
    cursor:help;
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
# Boot — init DB, then sync from API (once per session; again after Refresh)
# --------------------------------------------------------------------------- #
init_db_if_missing()

# Try to pull fresh data from the IFB BSE API.
# On success it upserts into SQLite so load_all() gets live records.
# On failure the dashboard simply uses whatever is already in SQLite.
if not st.session_state.get("_api_synced"):
    _sync_ok, _sync_msg = sync_api_to_db()
    st.session_state["_api_synced"]   = True
    st.session_state["_api_sync_ok"]  = _sync_ok
    st.session_state["_api_sync_msg"] = _sync_msg

if not DB_PATH.exists():
    st.error("Database not found — API sync also failed. Run `python seed_db.py` to seed local data.")
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

_sync_ok  = st.session_state.get("_api_sync_ok",  False)
_sync_msg = st.session_state.get("_api_sync_msg", "Not synced yet")
_api_badge = (
    f'<span class="api-ok">🟢&nbsp;API Synced</span>'   if _sync_ok else
    f'<span class="api-err" title="{_sync_msg}">🔴&nbsp;Local data</span>'
)

st.markdown(f"""
<div class="fixed-header">
  <div class="hero">
    <div>
      <h1>📊&nbsp; IFB POINT &middot; Customer Follow Up</h1>
      <p style="margin:4px 0 0;font-size:12px;color:#94A3B8;">{_sync_msg}</p>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;">
      <span class="pill">LIVE</span>
      {_api_badge}
    </div>
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
        {sub("ss-blue",   fu.get("Post-Purchase",0),          "Post Purchase")}
        {sub("ss-teal",   fu.get("1st 30 days call",0),  "1st 30 Days")}
        {sub("ss-indigo", fu.get("Pre-AMC",0),           "Pre-AMC")}
        {sub("ss-slate",  fu.get("8 Year Upgrade",0),    "8 Year Upgrade")}
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Section selector — read from session_state BEFORE filter logic runs
# --------------------------------------------------------------------------- #
_SEC_OPTS  = ["Open", "Attempted"]
_SEC_EMOJI = {
    "Open":      "📋",
    "Attempted": "📞",
}
section = st.session_state.get("_view_section", "Open")
if section not in _SEC_OPTS:
    section = "Open"


# --------------------------------------------------------------------------- #
# Filters (fixed bar — toggle | date range | search | refresh, one row)
# --------------------------------------------------------------------------- #
# Anchor marker — collapses to zero height; JS uses it to locate the next
# sibling element-container (the filter columns) and force position:fixed.
st.markdown('<span id="filter-anchor"></span>', unsafe_allow_html=True)

_FU_OPTS = [
    "All Follow-Up Stages",
    "Post-Purchase",
    "1st 30 days call",
    "Pre-AMC",
    "8 Year Upgrade",
]
_FU_LABEL = {
    "All Follow-Up Stages":                 "🌐  All Follow-Up Stages",
    "Post-Purchase":           "🎉  Post-Purchase",
    "1st 30 days call":  "🔄  1st 30 days call",
    "Pre-AMC":           "⏰  Pre-AMC",
    "8 Year Upgrade":    "🏆  8 Year Upgrade",
}
fc1, fc2, fc3, fc4, fc5 = st.columns([2, 1, 1, 1, 0.7], gap="small")
with fc1:
    t1, t2 = st.columns(2, gap="small")
    with t1:
        if st.button("📋  Open Followup's", key="btn_open",
                     use_container_width=True,
                     type="primary" if section == "Open" else "secondary"):
            st.session_state["_view_section"] = "Open"
            st.rerun()
    with t2:
        if st.button("📞  Attempted's", key="btn_att",
                     use_container_width=True,
                     type="primary" if section == "Attempted" else "secondary"):
            st.session_state["_view_section"] = "Attempted"
            st.rerun()
with fc2:
    fu_filter = st.selectbox(
        "Follow-Up Stage",
        options=_FU_OPTS,
        format_func=lambda x: _FU_LABEL.get(x, x),
        label_visibility="collapsed",
    )
with fc3:
    min_pd = df_all["purchase_date"].dropna().min() or date(2019, 1, 1)
    max_pd = df_all["purchase_date"].dropna().max() or today
    date_range = st.date_input(
        "📅  Lead Date Range",
        value=(min_pd, max_pd),
        min_value=min_pd,
        max_value=max_pd,
        format="DD/MM/YYYY",
        label_visibility="collapsed",
    )
with fc4:
    search_q = st.text_input(
        "Search",
        placeholder="🔍  Name · Phone · Email · ID",
        label_visibility="collapsed",
    )
with fc5:
    if st.button("↻  Refresh", key="refresh_btn",
                 help="Re-sync from API and reload",
                 use_container_width=True,
                 type="secondary"):
        st.cache_data.clear()
        try: st.cache_resource.clear()
        except Exception: pass
        # Force a fresh API pull on next run
        st.session_state.pop("_api_synced",   None)
        st.session_state.pop("_api_sync_ok",  None)
        st.session_state.pop("_api_sync_msg", None)
        st.rerun()

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
      n.style.setProperty('padding','0 22px','important');
      n.style.setProperty('min-height','62px','important');
      n.style.setProperty('overflow','visible','important');
      n.style.setProperty('border-bottom','1px solid #E2E8F0','important');
      n.style.setProperty('box-shadow','0 3px 10px rgba(15,23,42,.06)','important');

      // Vertically centre the columns row inside the fixed bar
      var hb = n.querySelector('[data-testid="stHorizontalBlock"]');
      if(hb){
        hb.style.setProperty('align-items','center','important');
        hb.style.setProperty('height','62px','important');
      }
      // Centre each column's inner wrapper and add side padding for spacing
      var colDivs = n.querySelectorAll('[data-testid="column"] > div');
      for(var i=0;i<colDivs.length;i++){
        colDivs[i].style.setProperty('display','flex','important');
        colDivs[i].style.setProperty('flex-direction','column','important');
        colDivs[i].style.setProperty('justify-content','center','important');
        colDivs[i].style.setProperty('height','62px','important');
        colDivs[i].style.setProperty('padding','0 6px','important');
      }
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
if section == "Attempted":
    # Leads where a follow-up was attempted — status is Contacted or Not Contacted
    attempted_mask = df_all["status"].fillna("").isin(["Contacted", "Not Contacted"])
    filtered = df_all[attempted_mask].copy()
else:
    # "Open Followup" — all leads
    filtered = df_all.copy()

# follow-up stage filter
if fu_filter != "All Follow-Up Stages":
    filtered = filtered[filtered["customer_follow_up"] == fu_filter]

# date range + search apply to all sections
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

# Status header dropdown filter — read from session_state before widget renders
_STATUS_FILTER_OPTS = ["All", "🟢  Contacted", "🔴  Not Contacted"]
_sf = st.session_state.get("status_filter_sel", "All")
if _sf == "🟢  Contacted":
    filtered = filtered[filtered["status"].fillna("") == "Contacted"]
elif _sf == "🔴  Not Contacted":
    filtered = filtered[filtered["status"].fillna("") == "Not Contacted"]

_sec_help  = {
    "Open":      "All leads matching your current filters.",
    "Attempted": "Leads where a follow-up was Contacted or Not Contacted.",
}.get(section, "")

st.markdown(f"""
<div class="sec">
  <span class="cnt">{len(filtered)} record{'s' if len(filtered)!=1 else ''}</span>
  <span class="sec-help">{_sec_help}</span>
</div>""", unsafe_allow_html=True)


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


# ── Sort state ──────────────────────────────────────────────────────────────
st.session_state.setdefault("sort_col", None)
st.session_state.setdefault("sort_dir", "asc")

_sort_col = st.session_state["sort_col"]
_sort_dir = st.session_state["sort_dir"]

# Apply sort to filtered before pagination
if _sort_col and _sort_col in filtered.columns:
    filtered = filtered.sort_values(
        _sort_col,
        ascending=(_sort_dir == "asc"),
        na_position="last",
    )

def _sort_hdr(col, label):
    """Render a clickable sort header button with directional triangle."""
    if _sort_col == col:
        icon = " ▲" if _sort_dir == "asc" else " ▼"
    else:
        icon = " ▾"
    if st.button(f"{label}{icon}", key=f"sort_{col}", use_container_width=True):
        if st.session_state["sort_col"] == col:
            st.session_state["sort_dir"] = "desc" if _sort_dir == "asc" else "asc"
        else:
            st.session_state["sort_col"] = col
            st.session_state["sort_dir"] = "asc"
        st.rerun()

def _status_filter_hdr():
    """Compact selectbox in the Status header cell."""
    st.selectbox(
        "Status",
        options=_STATUS_FILTER_OPTS,
        index=_STATUS_FILTER_OPTS.index(
            st.session_state.get("status_filter_sel", "All")
        ),
        key="status_filter_sel",
        label_visibility="collapsed",
    )

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

    # column ratios:  edit  follow-up  name  date  machine  phone  email  status  appt  int   remarks
    R   = [0.4,      2.7,       1.25, 0.95, 1.45,    0.95,  1.65,  1.0,    0.95, 1.05, 2.4]
    HDR = ["",       "Customer Follow-Up", "Customer Name", "Purchase Date",
           "Machine Type", "Phone", "Email", "Status", "Next Appt",
           "Interested?", "Remarks"]

    # Header row
    # index 7 = Status (3-state cycle), index 9 = Interested? (asc/desc sort)
    hdr = st.columns(R)
    last_i = len(HDR) - 1
    for i, (c, lbl) in enumerate(zip(hdr, HDR)):
        if i == 7:
            with c:
                _status_filter_hdr()
        elif i == 9:
            with c:
                _sort_hdr("interested", "Interested?")
        else:
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

        # 1–10 data cells
        cols[1].markdown(f"<div class='td'>{_safe(row.get('customer_follow_up'))}</div>",   unsafe_allow_html=True)
        cols[2].markdown(f"<div class='td'><b>{_safe(row.get('customer_name'))}</b></div>", unsafe_allow_html=True)
        cols[3].markdown(f"<div class='td'>{_fmt_date(row.get('purchase_date'))}</div>",    unsafe_allow_html=True)
        cols[4].markdown(f"<div class='td'>{_safe(row.get('machine_type'))}</div>",         unsafe_allow_html=True)
        cols[5].markdown(f"<div class='td'>{_safe(row.get('phone_number'))}</div>",         unsafe_allow_html=True)
        cols[6].markdown(f"<div class='td'>{_safe(row.get('email_id'))}</div>",             unsafe_allow_html=True)
        cols[7].markdown(f"<div class='td'>{_status_chip(row.get('status'))}</div>",        unsafe_allow_html=True)
        cols[8].markdown(f"<div class='td'>{_fmt_date(row.get('next_appointment'))}</div>", unsafe_allow_html=True)
        cols[9].markdown(f"<div class='td'>{_interest_chip(row.get('interested'))}</div>",  unsafe_allow_html=True)
        _rem_full = _safe(row.get('remarks'))
        _rem_tip  = _rem_full.replace("'", "&#39;").replace('"', "&quot;")
        cols[10].markdown(
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
