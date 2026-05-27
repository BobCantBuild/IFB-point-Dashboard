"""IFB Point Dashboard — Streamlit UI backed by SQLite."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import httpx as _req
import streamlit as st
import streamlit.components.v1 as components

import os as _os

DATA_FILE = Path(__file__).parent / "data" / "api_data.json"

# On Streamlit Cloud the app directory is read-only; use /tmp instead.
# Locally the app directory is writable, so the DB lives next to the code.
_APP_DIR = Path(__file__).parent
DB_PATH  = (_APP_DIR if _os.access(_APP_DIR, _os.W_OK) else Path("/tmp")) / "ifb_point.db"

STATUS_OPTIONS   = ["Contacted", "Not Contacted"]
INTEREST_OPTIONS = ["Interested", "Not Interested"]


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


# ─── Data architecture ───────────────────────────────────────────────────────
# Primary source: data/api_data.json committed by GitHub Actions every 30 min.
# Fallback: live httpx call (only works from IFB-whitelisted networks).
# SQLite stores ONLY user-edited follow-up fields (status, next_appointment,
# interested, remarks) — keyed by customer_id.
# ─────────────────────────────────────────────────────────────────────────────

_API_BASE = "https://bseapi.ifbsupport.com/api"
_API_USER = "IFBFollowUPAPP"
_API_PASS = "U29tZVJhbmRvbUJhc2U2NA=="
_API_CODE = "ADSF"

# ─── DB helpers ──────────────────────────────────────────────────────────────
# Design rules (to avoid the transaction-state bugs of the previous version):
#   1. No isolation_level=None — use Python sqlite3 default mode.
#   2. No executescript() — each DDL runs as a plain execute().
#   3. No manual BEGIN / COMMIT SQL — use `with conn:` context-manager which
#      auto-commits on success and auto-rolls-back on exception.
#   4. No shared / cached connections — every helper opens its own connection,
#      uses it, and closes it (the `with sqlite3.connect()` block handles that).
#   5. load_all() merges customers + followups with pandas (no SQL JOIN) so the
#      two writes are independent and can never interfere with each other.
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_tables() -> None:
    """Create both tables if they don't already exist. Safe to call many times."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id        TEXT PRIMARY KEY,
                customer_name      TEXT,
                purchase_date      TEXT,
                installation_type  TEXT,
                machine_type       TEXT,
                phone_number       TEXT,
                email_id           TEXT,
                ifb_point_id       TEXT,
                customer_follow_up TEXT,
                synced_at          TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS followups (
                customer_id      TEXT PRIMARY KEY,
                status           TEXT,
                next_appointment TEXT,
                interested       TEXT,
                remarks          TEXT,
                updated_at       TEXT DEFAULT (datetime('now'))
            )
        """)
        # Safe column migrations — only run ALTER if column is missing
        fu_cols = {r[1] for r in conn.execute("PRAGMA table_info(followups)").fetchall()}
        if "updated_at" not in fu_cols:
            conn.execute("ALTER TABLE followups ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))")
        cu_cols = {r[1] for r in conn.execute("PRAGMA table_info(customers)").fetchall()}
        if "installation_type" not in cu_cols:
            conn.execute("ALTER TABLE customers ADD COLUMN installation_type TEXT")
        conn.commit()


@st.cache_resource
def init_db_if_missing():
    """Run once per process (cache_resource) — create DB tables on first boot."""
    _ensure_tables()


def _fetch_live_api() -> list[dict]:
    """Direct API call via httpx — only works from networks IFB whitelisted.
    Used as a fallback when data/api_data.json is missing (local development).
    """
    u, p, code = _API_USER, _API_PASS, _API_CODE
    try:
        s = st.secrets["api"]
        u    = s.get("username",       u)
        p    = s.get("password",       p)
        code = s.get("ifb_point_code", code)
    except Exception:
        pass

    with _req.Client(timeout=20) as client:
        r1 = client.post(
            f"{_API_BASE}/Auth/login",
            json={"userName": u, "password": p},
            headers={"Content-Type": "application/json"},
        )
    if r1.status_code != 200:
        raise RuntimeError(f"Login HTTP {r1.status_code}: {r1.text[:200]}")
    tok = r1.json().get("token")
    if not tok:
        raise RuntimeError(f"Login OK but no token. Keys: {list(r1.json().keys())}")

    with _req.Client(timeout=25) as client:
        r2 = client.get(
            f"{_API_BASE}/IFBPointFollowUp/GetInstallationAgeingDetails",
            params={"IFBPointCode": code},
            headers={"Authorization": f"Bearer {tok}"},
        )
    if r2.status_code != 200:
        raise RuntimeError(f"GetInstallationAgeingDetails HTTP {r2.status_code}: {r2.text[:200]}")

    j = r2.json()
    records: list[dict] = []
    if isinstance(j, list):
        records = j
    elif isinstance(j, dict):
        for v in j.values():
            if isinstance(v, list):
                records.extend(v)
    return records


def fetch_api_records() -> tuple[list[dict], str]:
    """Return (records, source_label).
    Streamlit Cloud is firewalled out of bseapi.ifbsupport.com, so the
    primary data source is the JSON snapshot kept fresh by GitHub Actions.
    Live API is attempted only if the snapshot is missing.
    """
    if DATA_FILE.exists():
        blob = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        records = blob.get("records", []) if isinstance(blob, dict) else (blob or [])
        synced  = blob.get("synced_at_utc", "?") if isinstance(blob, dict) else "?"
        return records, f"snapshot · synced {synced} UTC"

    records = _fetch_live_api()
    return records, "live API"


def _safe_val(v):
    """Convert NaN / NaT / None to None so sqlite3 stores NULL."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _load_followups() -> pd.DataFrame:
    """
    Read every row from the followups table and return as a DataFrame.
    Opens its own connection and closes it immediately — no shared state.
    """
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            "SELECT customer_id, status, next_appointment, interested, remarks, updated_at "
            "FROM followups",
            conn,
        )


def load_all() -> tuple[pd.DataFrame, str]:
    """
    1. Fetch customer records from the JSON snapshot (or live API).
    2. Upsert them into the `customers` SQLite table.
    3. Load followups from the `followups` table separately.
    4. Merge the two DataFrames with pandas (no SQL JOIN — simpler, no
       transaction interference between the write and the read).

    Returns (merged_df, source_label).
    """
    records, source = fetch_api_records()

    _COLS = [
        "customer_id", "customer_name", "purchase_date",
        "installation_type", "machine_type",
        "phone_number", "email_id", "ifb_point_id",
        "customer_follow_up",
        "status", "next_appointment", "interested", "remarks", "updated_at",
    ]

    if not records:
        return pd.DataFrame(columns=_COLS), source

    # ── Build customer DataFrame from API records ────────────────────────
    df = pd.DataFrame(records)
    df["customer_id"]   = df["customer_id"].astype(str)
    df["phone_number"]  = df.get("phone_number", pd.Series(dtype=str)).astype(str)
    df["purchase_date"] = pd.to_datetime(
        df.get("purchase_date"), errors="coerce"
    ).dt.date

    for col in ("customer_name", "installation_type", "machine_type",
                "email_id", "ifb_point_id"):
        if col not in df.columns:
            df[col] = None

    today = date.today()
    df["customer_follow_up"] = df["purchase_date"].apply(
        lambda d: compute_follow_up(d, today) if isinstance(d, date) else None
    )

    # ── Upsert API records into `customers` table ────────────────────────
    # `with sqlite3.connect() as conn:` auto-commits on success.
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO customers
               (customer_id, customer_name, purchase_date,
                installation_type, machine_type,
                phone_number, email_id, ifb_point_id,
                customer_follow_up, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    str(row.customer_id),
                    _safe_val(row.customer_name),
                    row.purchase_date.isoformat() if isinstance(row.purchase_date, date) else None,
                    _safe_val(row.installation_type),
                    _safe_val(row.machine_type),
                    str(row.phone_number),
                    _safe_val(row.email_id),
                    _safe_val(row.ifb_point_id),
                    _safe_val(row.customer_follow_up),
                    source,
                )
                for row in df.itertuples(index=False)
            ],
        )
        conn.commit()

    # ── Load followups and merge with pandas ─────────────────────────────
    fu_df = _load_followups()

    if fu_df.empty:
        for col in ("status", "next_appointment", "interested", "remarks", "updated_at"):
            df[col] = None
        merged = df
    else:
        fu_df["customer_id"] = fu_df["customer_id"].astype(str)
        merged = df.merge(
            fu_df[["customer_id", "status", "next_appointment",
                   "interested", "remarks", "updated_at"]],
            on="customer_id",
            how="left",
        )

    # ── Coerce date columns ───────────────────────────────────────────────
    merged["purchase_date"]    = pd.to_datetime(merged["purchase_date"],    errors="coerce").dt.date
    merged["next_appointment"] = pd.to_datetime(merged["next_appointment"], errors="coerce").dt.date

    return merged, source


def update_row(cid: str, status, next_appt, interested, remarks) -> dict:
    """
    Persist user edits for one customer into the `followups` table.

    Uses a fresh sqlite3.connect() with the default Python transaction mode
    (no isolation_level=None, no manual BEGIN/COMMIT SQL).
    `with conn:` auto-commits on success and auto-rolls-back on exception.
    Returns the stored row so the dialog can confirm what was saved.
    """
    appt_str = next_appt.isoformat() if isinstance(next_appt, date) else None
    cid = str(cid)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO followups
               (customer_id, status, next_appointment, interested, remarks, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (cid, status, appt_str, interested, remarks),
        )
        conn.commit()
        row = conn.execute(
            """SELECT customer_id, status, next_appointment,
                      interested, remarks, updated_at
               FROM followups WHERE customer_id = ?""",
            (cid,),
        ).fetchone()

    if row is None:
        raise RuntimeError(f"Save appeared to succeed but followup row {cid!r} is missing.")
    return dict(zip(
        ["customer_id", "status", "next_appointment", "interested", "remarks", "updated_at"],
        row,
    ))


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

  /* Zero out every Streamlit container above .block-container so it starts
     at viewport top — eliminates the ~140px offset Streamlit Cloud adds */
  header[data-testid="stHeader"],
  [data-testid="stToolbar"],
  #MainMenu, footer {
    display:none !important;
  }
  [data-testid="stAppViewContainer"],
  [data-testid="stMainBlockContainer"] {
    padding-top:0 !important; margin-top:0 !important;
  }

  .block-container {
    /* JS sets the exact value; fallback = 0 so there is never a white gap
       before JS fires. A brief overlap (< 80ms) is acceptable. */
    padding-top:0px !important; padding-bottom:2rem;
    max-width:1700px;
  }

  /* Filter rows scroll naturally with the content — only the hero+stats
     band stays pinned. This avoids the empty-gap artifact caused by
     unreliable position:fixed pinning of dynamic Streamlit elements. */

  /* Collapse element-container wrappers around fixed/hidden elements */
  .element-container:has(.fixed-header),
  .element-container:has([data-testid="stCustomComponentV1"]) {
    height:0 !important; min-height:0 !important;
    margin:0 !important; padding:0 !important;
    overflow:hidden !important;
  }

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
  /* Collapse the JS-injection iframe wrapper without display:none
     (display:none on the wrapper can prevent the iframe script from running) */
  [data-testid="stCustomComponentV1"] {
    height:0 !important; min-height:0 !important;
    overflow:hidden !important; pointer-events:none !important;
  }
  iframe[title="st_components_html_v1"] {
    height:0 !important; width:0 !important; min-height:0 !important;
    border:none !important; display:block !important;
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
  .stat-solo {
    min-width:120px; flex-shrink:0;
    display:flex; flex-direction:column;
    align-items:center; justify-content:center;
    text-align:center;
  }
  .stat-solo .s-label { justify-content:center; }
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

  /* ── Filter-bar control polish: 34px height to match toggle buttons ── */
  .stDateInput > div > div,
  div[data-baseweb="input"] > div,
  div[data-baseweb="select"] > div {
    min-height:34px !important; height:34px !important;
    border-radius:10px !important;
    border:1px solid var(--line) !important;
    background:#FFFFFF !important;
    box-shadow:inset 0 1px 3px rgba(15,23,42,0.04);
    transition:border-color .18s var(--ease), box-shadow .18s var(--ease);
  }
  .stDateInput input,
  div[data-baseweb="input"] input,
  div[data-baseweb="select"] [role="combobox"] {
    font-size:12px !important;
    color:var(--ink) !important;
    text-align:center !important;
    font-weight:500 !important;
    line-height:34px !important;
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
    padding:0 10px; font-weight:600; font-size:12px;
    height:34px !important; min-height:34px !important;
    line-height:34px !important; display:inline-flex;
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
    height:34px !important; min-height:34px !important;
    padding:0 14px !important; font-size:12px !important; font-weight:600 !important;
    border-radius:8px !important;
  }
  .stButton > button[kind="secondary"]:hover {
    background:#F1F5F9 !important; border-color:#94A3B8 !important; color:#0F172A !important;
  }

  /* Primary button — hero gradient (active toggle + dialog Save) */
  .stButton > button[kind="primary"] {
    background:linear-gradient(135deg,#0F172A 0%,#1E293B 100%) !important;
    color:#FFFFFF !important; border:0 !important;
    box-shadow:0 2px 8px rgba(15,23,42,0.35) !important;
    height:34px !important; min-height:34px !important;
    padding:0 14px !important; font-size:12px !important; font-weight:700 !important;
    border-radius:10px !important;
  }
  .stButton > button[kind="primary"]:hover {
    background:linear-gradient(135deg,#1a1f35 0%,#242c45 100%) !important;
    box-shadow:0 4px 12px rgba(15,23,42,0.45) !important;
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
    height:34px !important;
    min-height:34px !important;
    padding:0 !important;
    display:flex !important;
    align-items:center !important;
  }
  [data-testid="stContainer"] input,
  [data-testid="stContainer"] .stDateInput input,
  [data-testid="stContainer"] div[data-baseweb="select"] [role="combobox"] {
    height:34px !important;
    min-height:34px !important;
    line-height:34px !important;
    padding:0 10px !important;
    font-size:12.5px !important;
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

  /* ── Filter rows layout ── */
  .filter-wrap { max-width:1700px; margin:0 auto; }
  .filter-row-gap { height:14px; }

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
# Boot — fetch live API data on every page load (no caching, errors are visible)
# --------------------------------------------------------------------------- #
init_db_if_missing()

try:
    df_all, _source = load_all()
    st.session_state["_api_sync_ok"]  = True
    st.session_state["_api_sync_msg"] = f"{_source} · {len(df_all)} records"
except Exception as _exc:
    st.session_state["_api_sync_ok"]  = False
    st.session_state["_api_sync_msg"] = f"{type(_exc).__name__}: {_exc}"
    df_all = pd.DataFrame(columns=[
        "customer_id", "customer_name", "purchase_date",
        "installation_type", "machine_type",
        "phone_number", "email_id", "ifb_point_id",
        "customer_follow_up",
        "status", "next_appointment", "interested", "remarks", "updated_at",
    ])
    st.error(f"⚠️ Unable to load data — {type(_exc).__name__}: {_exc}")

today = date.today()


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
_sync_msg = st.session_state.get("_api_sync_msg", "Syncing…")
_badge_html = (
    '<span class="api-ok">🟢&nbsp;API Synced</span>' if _sync_ok else
    '<span class="api-err">🔴&nbsp;Sync failed</span>'
)

# Read Franchise / IFB Point Code from the JSON snapshot (falls back to _API_CODE)
_ifb_code = _API_CODE
if DATA_FILE.exists():
    try:
        _blob = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        _ifb_code = _blob.get("ifb_point_code", _API_CODE) or _API_CODE
    except Exception:
        pass

st.markdown(f"""
<div class="fixed-header">
  <div class="hero">
    <div>
      <h1>📊&nbsp; IFB POINT &middot; Customer Follow Up</h1>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;">
      <p style="margin:0;font-size:12px;color:#94A3B8;">{_sync_msg}</p>
    </div>
  </div>
  <div class="stats-row">
    <div class="stat-solo">
      <div class="s-label">🏪 IFB Point Code</div>
      <div class="s-value" style="font-size:22px;letter-spacing:1px;">{_ifb_code}</div>
    </div>
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
# Lead view selector (Today / Missed) — read from session_state
# --------------------------------------------------------------------------- #
lead_view = st.session_state.get("_lead_view", "Today")
if lead_view not in ["Today", "Missed"]:
    lead_view = "Today"

# --------------------------------------------------------------------------- #
# Section selector — Open / Attempted — read from session_state BEFORE filter
# --------------------------------------------------------------------------- #
_SEC_OPTS = ["Open", "Attempted"]
section   = st.session_state.get("_view_section", "Open")
if section not in _SEC_OPTS:
    section = "Open"


# --------------------------------------------------------------------------- #
# Filters (two fixed rows)
# --------------------------------------------------------------------------- #
# Anchor marker — JS locates the two sibling element-containers and pins them.
st.markdown('<span id="filter-anchor"></span>', unsafe_allow_html=True)

st.markdown('<div class="filter-wrap">', unsafe_allow_html=True)

# ── Row 1: Lead type toggles + date range ──────────────────────────────────
_pds   = [d for d in df_all["purchase_date"] if isinstance(d, date)]
min_pd = min(_pds) if _pds else date(2019, 1, 1)
max_pd = max(_pds) if _pds else today

lr1, lr2, lr3 = st.columns([1, 1, 2], gap="medium")
with lr1:
    if st.button("📅  Today Leads", key="btn_today",
                 use_container_width=True,
                 type="primary" if lead_view == "Today" else "secondary"):
        st.session_state["_lead_view"] = "Today"
        st.rerun()
with lr2:
    if st.button("⚠️  Missed Leads", key="btn_missed",
                 use_container_width=True,
                 type="primary" if lead_view == "Missed" else "secondary"):
        st.session_state["_lead_view"] = "Missed"
        st.rerun()
with lr3:
    date_range = st.date_input(
        "📅  Lead Date Range",
        value=(min_pd, max_pd),
        min_value=min_pd,
        max_value=max_pd,
        format="DD/MM/YYYY",
        label_visibility="collapsed",
    )

# gap between the two filter rows
st.markdown('<div class="filter-row-gap"></div>', unsafe_allow_html=True)

# ── Row 2: Open/Attempted toggles + stage filter + search ─────────────────
_FU_OPTS = [
    "All Follow-Up Stages",
    "Post-Purchase",
    "1st 30 days call",
    "Pre-AMC",
    "8 Year Upgrade",
]
_FU_LABEL = {
    "All Follow-Up Stages": "🌐  All Follow-Up Stages",
    "Post-Purchase":        "🎉  Post-Purchase",
    "1st 30 days call":     "🔄  1st 30 days call",
    "Pre-AMC":              "⏰  Pre-AMC",
    "8 Year Upgrade":       "🏆  8 Year Upgrade",
}
rc1, rc2, rc3, rc4 = st.columns([1, 1, 1, 1], gap="medium")
with rc1:
    if st.button("📋  Open Followup's", key="btn_open",
                 use_container_width=True,
                 type="primary" if section == "Open" else "secondary"):
        st.session_state["_view_section"] = "Open"
        st.rerun()
with rc2:
    if st.button("📞  Attempted's", key="btn_att",
                 use_container_width=True,
                 type="primary" if section == "Attempted" else "secondary"):
        st.session_state["_view_section"] = "Attempted"
        st.rerun()
with rc3:
    fu_filter = st.selectbox(
        "Follow-Up Stage",
        options=_FU_OPTS,
        format_func=lambda x: _FU_LABEL.get(x, x),
        label_visibility="collapsed",
    )
with rc4:
    search_q = st.text_input(
        "Search",
        placeholder="🔍  Name · Phone · Email · ID",
        label_visibility="collapsed",
    )

st.markdown("</div>", unsafe_allow_html=True)

# small spacer so the data table has breathing room below the filter rows
st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

# JS injection — measure the fixed-header height and set `.block-container`
# padding-top to match it. Filter rows scroll naturally with the page
# content (no pin), eliminating the empty-gap artifact.
components.html("""
<script>
(function(){
  function run(){
    try{
      var doc = window.parent.document;
      var fh  = doc.querySelector('.fixed-header');
      if(!fh) return false;
      var hdrRect = fh.getBoundingClientRect();
      var hdrH = Math.ceil(hdrRect.height);
      if(hdrH < 40) return false;

      var bc = doc.querySelector('.block-container');
      if(!bc) return false;

      // Keep it simple: content should start just below the fixed header.
      // Using header height avoids occasional overestimates that create
      // a large blank gap between the stats row and the filter rows.
      var paddingTop = Math.max(0, hdrH + 12);
      bc.style.setProperty('padding-top', paddingTop+'px','important');

      return true;
    }catch(e){ return false; }
  }

  // Retry every 80 ms until the rows are successfully pinned, then stop polling.
  // MutationObserver re-runs on Streamlit rerenders.
  var _timer = setInterval(function(){
    if(run()) clearInterval(_timer);
  }, 80);

  var _dbt = null;
  try{
    new MutationObserver(function(){
      clearTimeout(_dbt);
      _dbt = setTimeout(run, 80);
    }).observe(window.parent.document.body, {childList:true, subtree:false});
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
    # also match on the customer_id string directly
    mask |= filtered["customer_id"].astype(str).str.contains(q, case=False, na=False)
    filtered = filtered[mask]



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
    cid = str(row["customer_id"])
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
                saved = update_row(
                    cid,
                    None if ns == "—" else ns,
                    na if isinstance(na, date) else None,
                    None if ni == "—" else ni,
                    nr.strip() or None,
                )
                st.toast(
                    f"✅ Saved to DB — "
                    f"Status: {saved.get('status') or '—'}  |  "
                    f"Appt: {saved.get('next_appointment') or '—'}  |  "
                    f"Interested: {saved.get('interested') or '—'}",
                    icon="💾",
                )
                st.rerun()
            except Exception as e:
                st.error(f"❌ Save failed — {type(e).__name__}: {e}")
    with c2:
        if st.button("Cancel", use_container_width=True, key=f"dlg_cancel_{cid}"):
            st.rerun()


# ── Table rendering ─────────────────────────────────────────────────────────
if len(filtered) == 0:
    st.markdown(
        "<div id='no-records-msg' style='text-align:center;padding:64px 20px;color:#94A3B8;"
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

    # column ratios:  edit  follow-up  name  date  inst-type  machine  phone  email  status  appt  int   remarks
    R   = [0.4,      2.7,       1.25, 0.95,      1.0,  1.45,    0.95,  1.65,  1.0,    0.95, 1.05, 2.4]
    HDR = ["",       "Customer Follow-Up", "Customer Name", "Purchase Date",
           "Install Type", "Machine Type", "Phone", "Email",
           "Status", "Next Appt", "Interested?", "Remarks"]

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
        cid = str(row["customer_id"])
        cols = st.columns(R)

        # 0 — pencil edit icon (circular outlined button)
        with cols[0]:
            if st.button("✏️", key=f"edit_{cid}", help=f"Edit lead {cid}"):
                edit_lead_dialog(row.to_dict())

        # 1–11 data cells
        cols[1].markdown(f"<div class='td'>{_safe(row.get('customer_follow_up'))}</div>",   unsafe_allow_html=True)
        cols[2].markdown(f"<div class='td'><b>{_safe(row.get('customer_name'))}</b></div>", unsafe_allow_html=True)
        cols[3].markdown(f"<div class='td'>{_fmt_date(row.get('purchase_date'))}</div>",    unsafe_allow_html=True)
        cols[4].markdown(f"<div class='td'>{_safe(row.get('installation_type'))}</div>",    unsafe_allow_html=True)
        cols[5].markdown(f"<div class='td'>{_safe(row.get('machine_type'))}</div>",         unsafe_allow_html=True)
        cols[6].markdown(f"<div class='td'>{_safe(row.get('phone_number'))}</div>",         unsafe_allow_html=True)
        cols[7].markdown(f"<div class='td'>{_safe(row.get('email_id'))}</div>",             unsafe_allow_html=True)
        cols[8].markdown(f"<div class='td'>{_status_chip(row.get('status'))}</div>",        unsafe_allow_html=True)
        cols[9].markdown(f"<div class='td'>{_fmt_date(row.get('next_appointment'))}</div>", unsafe_allow_html=True)
        cols[10].markdown(f"<div class='td'>{_interest_chip(row.get('interested'))}</div>", unsafe_allow_html=True)
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
