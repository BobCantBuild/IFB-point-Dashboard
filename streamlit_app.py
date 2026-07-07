"""IFB Point Dashboard — Streamlit UI backed by local SQLite (ifb_point.db)."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime as _dt, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_APP_DIR     = Path(__file__).resolve().parent
DB_PATH      = _APP_DIR / "ifb_point.db"
COUNTER_PATH = _APP_DIR / "ifb_counter.db"
LOGIN_DB         = _APP_DIR / "login.db"
LOGIN_MAPPING_DB = _APP_DIR / "login_mapping.db"
MASTER_FILE  = _APP_DIR / "IFB_Point_Master.txt"

# Startup migration: ensure reason/machine_Desc/dealerName columns exist in api_leads
try:
    import sqlite3 as _sqlite3_boot
    if DB_PATH.exists():
        with _sqlite3_boot.connect(DB_PATH) as _bc:
            _cols = {r[1] for r in _bc.execute("PRAGMA table_info(api_leads)").fetchall()}
            for _new_col in ("reason", "machine_Desc", "dealerName"):
                if _new_col not in _cols:
                    _bc.execute(f'ALTER TABLE api_leads ADD COLUMN "{_new_col}" TEXT')
            _bc.commit()
except Exception:
    pass


@lru_cache(maxsize=1)
def _load_master_codes() -> set[str]:
    """
    Return the full set of valid IFB Point codes from IFB_Point_Master.txt.
    Supports tab-separated format (code\tname) and legacy comma/whitespace format.
    Empty set if the master file is missing (treat all IDs as valid then).
    """
    if not MASTER_FILE.exists():
        return set()

    raw = MASTER_FILE.read_text(encoding="utf-8")
    lines = raw.split("\n")
    codes: set[str] = set()

    # Try tab-separated format first (new format: code\tname)
    has_tabs = any("\t" in line for line in lines if line.strip())
    if has_tabs:
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            code = parts[0].strip()
            if code:
                codes.add(code)
        if codes:
            return codes

    # Fallback to legacy format (comma-separated, whitespace-separated)
    tokens = (
        raw.replace("\r", " ")
           .replace("\n", " ")
           .replace("\t", " ")
           .replace(",", " ")
           .split()
    )
    return {t.strip() for t in tokens if t.strip()}


_EXCEL_MASTER = _APP_DIR.parent / "IFB Point Dashboard - notes" / "Unique_ChannelCode_ChannelName (1).xlsx"
_NAME_PREFIXES = ("IFB Industries Limit- ", "IFB Industries Limited- ", "IFB Industries Ltd- ")


def _clean_channel_name(name: str) -> str:
    """Strip known corporate prefixes that clutter the display name."""
    for prefix in _NAME_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


@lru_cache(maxsize=1)
def _load_channel_names() -> dict[str, str]:
    """
    Load channel code → friendly name mapping.
    Prefers IFB_Point_Master.txt (kept up to date manually); falls back to the Excel master file.
    Strips corporate prefixes so names are short and readable.
    """
    mapping: dict[str, str] = {}

    # Try txt first (authoritative, manually maintained)
    if MASTER_FILE.exists():
        raw = MASTER_FILE.read_text(encoding="utf-8", errors="replace")
        for line in raw.split("\n"):
            line = line.strip()
            if not line or "\t" not in line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                code = parts[0].strip()
                name = parts[1].strip()
                if code and name:
                    mapping[code] = _clean_channel_name(name)
        if mapping:
            return mapping

    # Fallback: Excel master file
    if _EXCEL_MASTER.exists():
        try:
            import pandas as pd
            df = pd.read_excel(_EXCEL_MASTER, dtype=str)
            code_col = df.columns[0]
            name_col = df.columns[1]
            for _, row in df.iterrows():
                code = str(row[code_col]).strip()
                name = str(row[name_col]).strip()
                if code and name and code != "nan":
                    mapping[code] = _clean_channel_name(name)
        except Exception:
            pass

    return mapping


_MASTER_CODES = _load_master_codes()
_CHANNEL_NAMES = _load_channel_names()


def _ensure_runtime_indexes() -> None:
    """Create non-destructive SQLite indexes for production read/write paths."""
    if DB_PATH.exists():
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.executescript(
                    """
                    CREATE INDEX IF NOT EXISTS idx_api_leads_ifb_point_id
                        ON api_leads(ifb_point, id DESC);
                    CREATE INDEX IF NOT EXISTS idx_api_leads_ifb_point_lead_date
                        ON api_leads(ifb_point, lead_date);
                    CREATE INDEX IF NOT EXISTS idx_api_leads_ifb_customer
                        ON api_leads(ifb_point, customer_id);
                    CREATE INDEX IF NOT EXISTS idx_api_leads_key
                        ON api_leads(key);
                    CREATE INDEX IF NOT EXISTS idx_api_leads_lead_date
                        ON api_leads(lead_date);
                    CREATE INDEX IF NOT EXISTS idx_api_leads_next_appointment
                        ON api_leads(next_appointment);
                    """
                )
                conn.commit()
        except Exception:
            pass

    if LOGIN_DB.exists():
        try:
            with sqlite3.connect(LOGIN_DB) as conn:
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_users_email_lower
                        ON users(LOWER(email))
                """)
                conn.commit()
        except Exception:
            pass

    if LOGIN_MAPPING_DB.exists():
        try:
            with sqlite3.connect(LOGIN_MAPPING_DB) as conn:
                conn.executescript(
                    """
                    CREATE INDEX IF NOT EXISTS idx_login_mapping_retail_email_lower
                        ON login_mapping(LOWER("Retail Email_ID"));
                    CREATE INDEX IF NOT EXISTS idx_login_mapping_email_lower
                        ON login_mapping(LOWER(Email_ID));
                    CREATE INDEX IF NOT EXISTS idx_login_mapping_regional_email_lower
                        ON login_mapping(LOWER("Regional Email_ID"));
                    CREATE INDEX IF NOT EXISTS idx_login_mapping_point
                        ON login_mapping(IFBpoint_id);
                    CREATE INDEX IF NOT EXISTS idx_login_mapping_region_branch_point
                        ON login_mapping(Region, Branch, IFBpoint_id);
                    """
                )
                conn.commit()
        except Exception:
            pass


_ensure_runtime_indexes()

# ── API config for customer detail lookup (eye icon) ──────────────────────────
_EYE_API_BASE = "https://bseapi.ifbsupport.com/api"
_EYE_API_USER = "IFBFollowUPAPP"
_EYE_API_PASS = "U29tZVJhbmRvbUJhc2U2NA=="

STATUS_OPTIONS   = ["Contacted", "RnR", "Not Reachable"]
INTEREST_OPTIONS = ["Interested", "Not Interested"]
REASON_OPTIONS   = ["Service issue", "Others"]


def _get_api_token() -> str | None:
    """Login to IFB API and return JWT token. Cached in session_state for the session."""
    if "_api_jwt_token" in st.session_state:
        return st.session_state["_api_jwt_token"]
    try:
        r = httpx.post(
            f"{_EYE_API_BASE}/Auth/login",
            json={"userName": _EYE_API_USER, "password": _EYE_API_PASS},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if r.status_code == 200:
            tok = r.json().get("token")
            if tok:
                st.session_state["_api_jwt_token"] = tok
                return tok
    except Exception:
        pass
    return None


def _fetch_customer_details(customer_id: str) -> dict | None:
    """
    Call the IFB API to get decrypted phone & email for a customer.
    Returns {"mobileNo": "...", "emailID": "..."} or None on failure.
    """
    token = _get_api_token()
    if not token:
        return None
    try:
        r = httpx.get(
            f"{_EYE_API_BASE}/IFBPointFollowUp/GetIFBPointFollowUpCustomerDetails",
            params={"CustCode": customer_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


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


def _resolve_point_code() -> str | None:
    """Read the IFB Point code from the URL query string (?id= or ?ifb_point_code=).
    Returns None when no code is present — URL is the single source of truth."""
    try:
        qp = st.query_params
        q_id = qp.get("id")
        if isinstance(q_id, str) and q_id.strip():
            return q_id.strip()
        q_code = qp.get("ifb_point_code")
        if isinstance(q_code, str) and q_code.strip():
            return q_code.strip()
    except Exception:
        pass
    return None


def _parse_api_date(v: Any) -> date | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        dt = pd.to_datetime(s, errors="coerce")
    except Exception:
        return None
    if pd.isna(dt):
        return None
    try:
        return dt.date()
    except Exception:
        return None


# ─── DB bucket → display stage label ─────────────────────────────────────────
_BUCKET_TO_STAGE = {
    "twoDays_details":         "Post-Purchase",
    "twoDaysDetails":          "Post-Purchase",
    "oneMonth_details":        "1st 30 days call",
    "oneMonthDetails":         "1st 30 days call",
    "fortySevenMonthDetails":  "Pre-AMC",
    "fortySevenMonth_details": "Pre-AMC",
    "eightyFourMonthDetails":  "8 Year Upgrade",
    "eightyFourMonth_details": "8 Year Upgrade",
}


def _read_db(ifb_point_code: str) -> list[dict]:
    """
    Read all rows for one franchise from ifb_point.db.
    Returns one dict per unique key (latest row wins).
    status/next_appointment/interested/remarks come straight from SQLite
    — no secondary JSON merge needed.
    """
    if not DB_PATH.exists():
        return []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, key, customer_id, customer_name, purchase_date,
                       installationdate, machine_type, phone_number, alt_number,
                       email_id, "pinCode", "serialNo", "machine_Desc", "dealerName",
                       ifb_point, lead_date,
                       follow_up, status, next_appointment, interested, remarks,
                       final_status, reason
                  FROM api_leads
                 WHERE ifb_point = ?
                 ORDER BY id DESC
                """,
                (ifb_point_code,),
            ).fetchall()
    except Exception:
        return []

    seen: set[str] = set()
    out:  list[dict] = []
    for r in rows:
        k = (r["key"] or "").strip() or str(r["id"])
        if k in seen:
            continue
        seen.add(k)
        out.append({
            "customer_id":        r["customer_id"],
            "customer_name":      r["customer_name"],
            "purchase_date":      r["purchase_date"],
            "installation_date":  r["installationdate"],
            "machine_type":       r["machine_type"],
            "phone_number":       r["phone_number"],
            "alt_number":         r["alt_number"],
            "email_id":           r["email_id"],
            "pin_code":           r["pinCode"],
            "serial_no":          r["serialNo"],
            "machine_desc":       r["machine_Desc"],
            "dealer_name":        r["dealerName"],
            "ifb_point_code":     r["ifb_point"],
            "lead_date":          r["lead_date"],
            "customer_follow_up": _BUCKET_TO_STAGE.get(r["follow_up"] or "", r["follow_up"] or ""),
            "status":             r["status"],
            "next_appointment":   r["next_appointment"],
            "interested":         r["interested"],
            "remarks":            r["remarks"],
            "final_status":       r["final_status"] if "final_status" in r.keys() else None,
            "reason":             r["reason"]       if "reason"       in r.keys() else None,
        })
    return out


def load_all() -> tuple[pd.DataFrame, str]:
    """
    Fetch customer records from ifb_point.db for the franchise code in the URL.
    SQLite is the single source of truth — status/next_appointment/interested/
    remarks are read directly from api_leads (no followups.json merge).
    Returns (df, source_label).
    """
    point_code = _resolve_point_code()

    _COLS = [
        "customer_id", "customer_name", "purchase_date",
        "machine_type", "phone_number", "email_id",
        "customer_follow_up", "lead_date", "status", "next_appointment", "interested", "remarks",
    ]

    if not point_code:
        return pd.DataFrame(columns=_COLS), "no-url-param"

    if _MASTER_CODES and point_code not in _MASTER_CODES:
        return pd.DataFrame(columns=_COLS), f"invalid-id · {point_code}"

    rows = _read_db(point_code)
    if not rows:
        return pd.DataFrame(columns=_COLS), f"no-data · {point_code}"

    df = pd.DataFrame(rows)
    df["customer_id"]   = df["customer_id"].astype(str)
    df["phone_number"]  = df["phone_number"].astype(str)

    if "purchase_date" in df.columns:
        df["purchase_date"] = df["purchase_date"].apply(_parse_api_date)
    if "installation_date" in df.columns:
        df["installation_date"] = df["installation_date"].apply(_parse_api_date)
    # lead_date is stored as DD-MM-YYYY by sync_api.py — parse to date
    if "lead_date" in df.columns:
        df["lead_date"] = pd.to_datetime(
            df["lead_date"], format="%d-%m-%Y", errors="coerce"
        ).dt.date
    if "next_appointment" in df.columns:
        df["next_appointment"] = pd.to_datetime(df["next_appointment"], errors="coerce").dt.date

    for col in ("customer_name", "machine_type", "email_id",
                "customer_follow_up", "status", "interested", "remarks",
                "machine_desc", "dealer_name", "reason"):
        if col not in df.columns:
            df[col] = None

    # Compute follow-up stage from purchase_date when API bucket is absent
    today = date.today()
    df["customer_follow_up"] = df.apply(
        lambda r: r["customer_follow_up"] or (
            compute_follow_up(r["purchase_date"], today)
            if isinstance(r["purchase_date"], date) else None
        ),
        axis=1,
    )

    df["purchase_date"] = pd.to_datetime(df["purchase_date"], errors="coerce").dt.date

    return df, f"sqlite · {len(df)} rows"


def _ensure_counter_db() -> None:
    """Create ifb_counter.db and the edit_log table if they don't exist yet.
    Also runs idempotent migrations for older schemas.
    """
    with sqlite3.connect(COUNTER_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS edit_log (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                key              TEXT,
                counter          INTEGER,
                saved_at         TEXT,
                call_status      TEXT,
                next_appointment TEXT,
                interested       TEXT,
                final_status     TEXT,
                remarks          TEXT
            )
        """)
        # Migrations: add columns if table existed before this change
        existing = {r[1] for r in conn.execute("PRAGMA table_info(edit_log)").fetchall()}
        if "counter" not in existing:
            conn.execute("ALTER TABLE edit_log ADD COLUMN counter INTEGER")
        if "reason" not in existing:
            conn.execute("ALTER TABLE edit_log ADD COLUMN reason TEXT")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_edit_log_key_status
                ON edit_log(key, call_status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_edit_log_key
                ON edit_log(key)
        """)
        conn.commit()


def _append_counter_db(key: str, status, appt_str, interested, final_status, remarks, reason=None) -> None:
    """Append one immutable history row to ifb_counter.db — never overwrites.
    counter = how many times this composite key has been saved (1-based).
    """
    try:
        _ensure_counter_db()
        saved_at = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(COUNTER_PATH) as conn:
            # Count existing rows for this key to derive the next counter value
            prev = conn.execute(
                "SELECT COUNT(*) FROM edit_log WHERE key = ?", (key,)
            ).fetchone()[0]
            counter = prev + 1

            conn.execute(
                """INSERT INTO edit_log
                       (key, counter, saved_at, call_status, next_appointment,
                        interested, final_status, remarks, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (key, counter, saved_at, status, appt_str, interested, final_status, remarks, reason),
            )
            conn.commit()
    except Exception:
        pass  # counter DB is non-critical — never block the main save


def update_row(cid: str, status, next_appt, interested, remarks, final_status=None, reason=None) -> dict:
    """Save user edits directly to SQLite api_leads — single source of truth.
    Simultaneously appends an immutable history row to ifb_counter.db.
    """
    appt_str   = next_appt.isoformat() if isinstance(next_appt, date) else None
    cid        = str(cid)
    point_code = _resolve_point_code() or ""

    result = {"rows_updated": 0, "error": None}
    try:
        # ── 1. Update ifb_point.db (overwrite as before) ─────────────────────
        with sqlite3.connect(DB_PATH) as conn:
            # Fetch the composite key for this customer so we can log it
            key_row = conn.execute(
                "SELECT key FROM api_leads WHERE customer_id = ? AND ifb_point = ? LIMIT 1",
                (cid, point_code),
            ).fetchone()
            composite_key = key_row[0] if key_row else f"{point_code}-{cid}"

        # ── 2. RnR auto-LOST rule ─────────────────────────────────────────────
        # If this key already has 3 RnR saves in the counter DB,
        # the 4th save (any status) automatically forces Final Status = LOST.
        try:
            _ensure_counter_db()
            with sqlite3.connect(COUNTER_PATH) as cconn:
                rnr_count = cconn.execute(
                    "SELECT COUNT(*) FROM edit_log WHERE key = ? AND call_status = 'RnR'",
                    (composite_key,),
                ).fetchone()[0]
            if rnr_count >= 3:
                final_status = "LOST"
                result["auto_lose"] = True
        except Exception:
            pass  # non-critical — don't block the save

        # ── 3. Write to ifb_point.db ──────────────────────────────────────────
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                """UPDATE api_leads
                      SET status = ?, next_appointment = ?, interested = ?,
                          remarks = ?, final_status = ?, reason = ?
                    WHERE customer_id = ? AND ifb_point = ?""",
                (status, appt_str, interested, remarks, final_status, reason, cid, point_code),
            )
            conn.commit()
            result["rows_updated"] = cur.rowcount

        # ── 4. Append to ifb_counter.db (with the possibly-forced LOST) ──────
        _append_counter_db(composite_key, status, appt_str, interested, final_status, remarks, reason)

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


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
    padding-top:10px !important; padding-bottom:2rem;
    max-width:1700px;
  }

  /* Collapse only the hidden helper elements (custom components / st.html scripts).
     The fixed-header is now in normal flow, so it should NOT be collapsed. */
  .element-container:has([data-testid="stCustomComponentV1"]),
  .element-container:has([data-testid="stHtml"]) {
    height:0 !important; min-height:0 !important;
    margin:0 !important; padding:0 !important;
    overflow:hidden !important;
  }

  /* ── Header band (hero + stats) — sticky to the top of the scrolling
     viewport so it stays pinned while the rest of the page scrolls underneath.
     Unlike position:fixed, sticky needs no JS-measured height/padding sync,
     so it holds up across every breakpoint (desktop/tablet/mobile).
     The sticky position must be set on Streamlit's own stElementContainer
     wrapper (position:relative), not on .fixed-header itself — that wrapper
     becomes the sticky containing block and, being only as tall as its
     content, would otherwise confine the stick to a few px and neutralize it. */
  .element-container:has(.fixed-header) {
    position:sticky !important;
    top:0;
    z-index:40;
    background:var(--bg);
    padding-bottom:14px !important;
  }
  .fixed-header {
    background:var(--bg);
    padding:0.7rem 1rem 0.5rem;
    margin-bottom:14px;
    border:1px solid #E2E8F0;
    border-top:none;
    border-radius:0 0 8px 8px;
    box-shadow:0 4px 10px -3px rgba(15,23,42,0.08);
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
    flex:1; border-radius:8px; padding:6px 4px; text-align:center;
    background:var(--bg-soft); border:1px solid var(--line);
    transition:transform .2s var(--ease), background .2s var(--ease);
    min-width:0;
  }
  .sub-stat:hover { transform:translateY(-1px); background:#F1F5F9; }
  .ss-val   { font-size:16px; font-weight:800; line-height:1; color:var(--ink); }
  .ss-lbl   { font-size:9px; color:#64748B; margin-top:3px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .ss-green .ss-val { color:var(--good); }   .ss-red    .ss-val { color:var(--bad); }
  .ss-grey  .ss-val { color:#475569; }       .ss-blue   .ss-val { color:var(--brand); }
  .ss-warn  .ss-val { color:#D97706; }
  .ss-teal  .ss-val { color:#0D9488; }       .ss-indigo .ss-val { color:#4F46E5; }
  .ss-slate .ss-val { color:#334155; }

  /* Dual total|today layout in stat-solo */
  .stat-solo-dual { min-width:160px; }
  .s-dual-row { display:grid; grid-template-columns:1fr auto 1fr; align-items:baseline; margin-top:5px; }
  .s-dual-col { text-align:center; }
  .s-dual-sep { font-size:22px; font-weight:300; color:#CBD5E1; line-height:1; padding:0 6px; }
  .s-today { color:var(--brand) !important; -webkit-background-clip:unset !important; background-clip:unset !important; background:none !important; }
  .s-sub-lbl { font-size:9px; font-weight:600; color:#64748B; text-transform:uppercase; margin-top:2px; }
  .s-sub-today { color:var(--brand); }

  /* Dual total|today layout in sub-stat cards */
  .ss-dual { display:grid; grid-template-columns:1fr auto 1fr; align-items:baseline; }
  .ss-sep  { font-size:14px; font-weight:300; color:#CBD5E1; line-height:1; text-align:center; }
  .ss-sep-lbl { font-size:8px; font-weight:300; color:#CBD5E1; line-height:1; text-align:center; }
  .ss-dual .ss-val { text-align:center; }
  .ss-dual .ss-lbl { text-align:center; margin-top:3px; font-size:8px; }
  .ss-today { color:var(--brand) !important; font-size:14px; }
  .ss-lbl-today { color:var(--brand) !important; }

  /* ── Filter panel ── */
  .st-key-filter_panel {
    background:#fff; border:1px solid var(--line); border-radius:16px;
    padding:8px 12px 6px; margin-bottom:18px;
    box-shadow:var(--shadow-sm);
  }

  /* Strip only left/right padding from row wrappers (keeps width clean).
     The gap between rows comes from padding-top on row 2's wrapper. */
  .st-key-filter_panel [data-testid="stVerticalBlockBorderWrapper"],
  .st-key-filter_panel [data-testid="stVerticalBlockBorderWrapper"] > div,
  .st-key-filter_panel [data-testid="stVerticalBlockBorderWrapper"] > div > div {
    padding-left:0 !important;
    padding-right:0 !important;
    margin-left:0 !important;
    margin-right:0 !important;
    padding-top:0 !important;
    padding-bottom:0 !important;
    margin-top:0 !important;
    margin-bottom:0 !important;
  }
  /* Row 2 gets an explicit top gap */
  .st-key-filter_panel .st-key-filter_row_bottom {
    margin-top:4px !important;
  }

  /* ── Row 1: ALL controls at 34px ──
     Prefix with .st-key-filter_panel to beat the later generic
     [data-testid="stContainer"] rule which has the same specificity. */
  .st-key-filter_panel .st-key-filter_row_top .stButton > button,
  .st-key-filter_panel .st-key-filter_row_top .stButton > button[kind="primary"],
  .st-key-filter_panel .st-key-filter_row_top .stButton > button[kind="secondary"] {
    height:34px !important; min-height:34px !important; max-height:34px !important;
    line-height:34px !important; font-size:12px !important;
    border-radius:10px !important; padding:0 10px !important;
  }
  .st-key-filter_panel .st-key-filter_row_top .stDateInput > div > div,
  .st-key-filter_panel .st-key-filter_row_top div[data-baseweb="input"] > div,
  .st-key-filter_panel .st-key-filter_row_top div[data-baseweb="select"] > div {
    height:34px !important; min-height:34px !important; max-height:34px !important;
    border-radius:10px !important; padding:0 !important;
    display:flex !important; align-items:center !important;
  }
  .st-key-filter_panel .st-key-filter_row_top .stDateInput input,
  .st-key-filter_panel .st-key-filter_row_top div[data-baseweb="input"] input {
    height:34px !important; line-height:34px !important;
    padding:0 10px !important; font-size:12px !important;
  }

  /* ── Row 2: ALL controls at 34px (same as row 1 — avoids vertical misalignment) ── */
  .st-key-filter_panel .st-key-filter_row_bottom .stButton > button,
  .st-key-filter_panel .st-key-filter_row_bottom .stButton > button[kind="primary"],
  .st-key-filter_panel .st-key-filter_row_bottom .stButton > button[kind="secondary"] {
    height:34px !important; min-height:34px !important; max-height:34px !important;
    line-height:34px !important; font-size:12px !important;
    border-radius:10px !important; padding:0 10px !important;
  }
  /* Clamp the BaseWeb OUTER wrapper (40px default) down to 34px —
     this is what was causing the 3px upward shift vs the buttons */
  .st-key-filter_panel .st-key-filter_row_bottom div[data-baseweb="input"],
  .st-key-filter_panel .st-key-filter_row_bottom div[data-baseweb="select"],
  .st-key-filter_panel .st-key-filter_row_bottom .stTextInput,
  .st-key-filter_panel .st-key-filter_row_bottom .stSelectbox {
    height:34px !important; max-height:34px !important;
    overflow:visible !important;
  }
  .st-key-filter_panel .st-key-filter_row_bottom div[data-baseweb="select"] > div,
  .st-key-filter_panel .st-key-filter_row_bottom div[data-baseweb="input"] > div {
    height:34px !important; min-height:34px !important; max-height:34px !important;
    border-radius:10px !important; padding:0 !important;
    display:flex !important; align-items:center !important;
  }
  .st-key-filter_panel .st-key-filter_row_bottom div[data-baseweb="select"] [role="combobox"],
  .st-key-filter_panel .st-key-filter_row_bottom div[data-baseweb="input"] input {
    height:34px !important; line-height:1.3 !important;
    padding:0 10px !important; font-size:12px !important;
  }

  /* Kill hidden labels — Streamlit's label_visibility="collapsed" uses
     visibility:hidden which still consumes height and offsets inputs
     downward relative to neighbouring buttons. Force display:none instead. */
  .st-key-filter_panel .st-key-filter_row_top [data-testid="stWidgetLabel"],
  .st-key-filter_panel .st-key-filter_row_bottom [data-testid="stWidgetLabel"],
  .st-key-filter_panel .st-key-filter_row_top label,
  .st-key-filter_panel .st-key-filter_row_bottom label {
    display:none !important;
    height:0 !important; min-height:0 !important;
    margin:0 !important; padding:0 !important;
  }

  /* Filter-bar row layout: keep each row as clean, even columns */
  .st-key-filter_row_top [data-testid="stHorizontalBlock"],
  .st-key-filter_row_bottom [data-testid="stHorizontalBlock"]{
    align-items:center;
    gap:8px !important;
    margin:0 !important;
  }
  /* Each column itself is a flex column — center its single child vertically */
  .st-key-filter_row_top [data-testid="stHorizontalBlock"] > [data-testid="column"],
  .st-key-filter_row_bottom [data-testid="stHorizontalBlock"] > [data-testid="column"]{
    display:flex;
    flex-direction:column;
    justify-content:center;
    min-width:0;
  }

  .st-key-filter_row_top [data-testid="stHorizontalBlock"] > [data-testid="column"] > div,
  .st-key-filter_row_bottom [data-testid="stHorizontalBlock"] > [data-testid="column"] > div{
    flex:1 1 auto;
    min-width:0;
  }

  .st-key-filter_row_top .stButton,
  .st-key-filter_row_bottom .stButton,
  .st-key-filter_row_top .stDateInput,
  .st-key-filter_row_bottom .stSelectbox,
  .st-key-filter_row_bottom .stTextInput {
    margin:0 !important;
  }

  /* Also collapse the element-container inside each filter row column */
  .st-key-filter_row_top .element-container,
  .st-key-filter_row_bottom .element-container {
    margin:0 !important; padding:0 !important;
  }


  /* ── Inputs / selects (default everywhere) ── */
  div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
    background:#F8FAFC !important; border-radius:6px !important; border:1px solid #E2E8F0 !important;
  }
  .stDateInput > div > div { background:#F8FAFC !important; border-radius:6px !important; }

  /* Remove outer BaseWeb wrapper border on date input — inner div already has one */
  .stDateInput [data-baseweb="input"] {
    border:none !important; background:transparent !important; box-shadow:none !important;
  }

  /* ── Filter-bar control polish: 34px height to match toggle buttons ── */
  .stDateInput > div > div,
  div[data-baseweb="input"] > div,
  div[data-baseweb="select"] > div {
    min-height:34px !important;
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
    line-height:1.4 !important;
    padding-top:8px !important;
    padding-bottom:8px !important;
  }
  .st-key-filter_row_bottom div[data-baseweb="select"] [data-testid="stMarkdownContainer"],
  .st-key-filter_row_bottom div[data-baseweb="input"] input {
    justify-content:flex-start !important;
    text-align:left !important;
    padding-left:12px !important;
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
  /* Fix: select text was clipped at the bottom (descenders like g/p).
     Use normal line-height + flex vertical-centering instead of a
     fixed 34px line-height that pinned the text and cut it off. */
  div[data-baseweb="select"] [role="combobox"] {
    line-height:1.4 !important;
    display:flex !important;
    align-items:center !important;
  }
  div[data-baseweb="select"] [data-testid="stMarkdownContainer"],
  div[data-baseweb="select"] [data-testid="stMarkdownContainer"] p {
    line-height:1.4 !important;
    font-size:11px !important;
  }

  /* ── Buttons ── */
  .stButton > button {
    background:#0F172A; color:#F8FAFC; border:0; border-radius:8px;
    padding:0 14px; font-weight:600; font-size:13px;
    height:36px !important; min-height:36px !important; max-height:36px !important;
    line-height:36px !important; display:inline-flex;
    align-items:center; justify-content:center; white-space:nowrap;
    width:100%;
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

  /* ── Lead table — horizontally scrollable with sticky icon columns ── */

  /* The tbl_area container scrolls horizontally */
  .st-key-tbl_area {
    overflow-x:auto; overflow-y:hidden;
    -webkit-overflow-scrolling:touch;
    scrollbar-color:#94A3B8 #F1F5F9;
    padding-bottom:4px;
    border:1px solid #E2E8F0;
    border-radius:14px;
    box-shadow:0 1px 3px rgba(15,23,42,0.04), 0 4px 12px rgba(15,23,42,0.03);
  }
  .st-key-tbl_area::-webkit-scrollbar { height:12px; }
  .st-key-tbl_area::-webkit-scrollbar-track { background:#F1F5F9; border-radius:6px; }
  .st-key-tbl_area::-webkit-scrollbar-thumb { background:#94A3B8; border-radius:6px; min-width:60px; }
  .st-key-tbl_area::-webkit-scrollbar-thumb:hover { background:#64748B; }
  .st-key-tbl_area { scrollbar-width:auto; }
  .st-key-tbl_area.dragging { cursor:grabbing; user-select:none; }

  /* Force each row (stHorizontalBlock) to a fixed wide width so columns don't squish */
  .st-key-tbl_area [data-testid="stHorizontalBlock"] {
    min-width:2200px !important;
    flex-wrap:nowrap !important;
  }
  /* Override Streamlit's mobile rule that makes each column full-width
     (calc(100% - 24px)) — without this, columns stack vertically on small screens */
  .st-key-tbl_area [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width:0 !important;
    flex-shrink:1 !important;
  }

  /* Sticky edit column (first) */
  .st-key-tbl_area [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
    position:sticky !important;
    left:0 !important;
    z-index:3 !important;
    background:#FFFFFF !important;
    width:52px !important; min-width:52px !important; max-width:52px !important;
    flex:0 0 52px !important;
    box-shadow:6px 0 6px -4px rgba(15,23,42,0.08);
  }
  /* Sticky eye column (last) */
  .st-key-tbl_area [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
    position:sticky !important;
    right:0 !important;
    z-index:3 !important;
    background:#FFFFFF !important;
    width:52px !important; min-width:52px !important; max-width:52px !important;
    flex:0 0 52px !important;
    box-shadow:-6px 0 6px -4px rgba(15,23,42,0.08);
  }

  .th {
    background:#F8FAFC;
    padding:14px 14px;
    font-size:12.5px; font-weight:600;
    color:#334155; letter-spacing:0.2px;
    border-bottom:2px solid #E2E8F0;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    min-height:48px; display:flex; align-items:center;
  }
  /* Sticky columns in the header row — match .th background and remove shadow lines */
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.th) > [data-testid="stColumn"]:first-child,
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.th) > [data-testid="stColumn"]:last-child {
    background:#F8FAFC !important;
    box-shadow:none !important;
  }

  .td {
    background:transparent; padding:16px 14px;
    font-size:13.5px; color:#1E293B; font-weight:400;
    border-bottom:1px solid #F1F5F9;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    min-height:56px; display:flex; align-items:center;
  }
  /* Last data row — no bottom border (the container border is enough) */
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td):last-child .td {
    border-bottom:none;
  }
  /* Row hover */
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td):hover .td { background:#F8FAFC; }
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td):hover > [data-testid="stColumn"]:first-child,
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td):hover > [data-testid="stColumn"]:last-child {
    background:#F8FAFC !important;
  }
  .td.wrap    { white-space:normal; word-break:break-word; line-height:1.4; }
  .td.muted   { color:#CBD5E1; justify-content:center; }
  .td.icon    { justify-content:center; padding:14px 0; }
  .td.center  { justify-content:center; }

  /* Status/Interested chips with colored dots */
  .chip {
    display:inline-flex; align-items:center; gap:6px;
    font-size:13px; color:#1E293B;
    white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis;
    max-width:100%;
  }
  .chip::before {
    content:''; width:8px; height:8px; border-radius:50%;
    background:#CBD5E1; flex-shrink:0;
  }
  .chip.green::before  { background:#16A34A; }
  .chip.red::before    { background:#DC2626; }
  .chip.warn::before   { background:#D97706; }
  .chip.slate::before  { background:#94A3B8; }
  .chip.nodot::before  { display:none; }

  /* Default secondary button (dialog Cancel etc.) — proper rectangular */
  .stButton > button[kind="secondary"] {
    background:#FFFFFF !important; color:#475569 !important;
    border:1px solid #CBD5E1 !important;
    height:36px !important; min-height:36px !important; max-height:36px !important;
    padding:0 14px !important; font-size:13px !important; font-weight:600 !important;
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
    height:36px !important; min-height:36px !important; max-height:36px !important;
    padding:0 14px !important; font-size:13px !important; font-weight:700 !important;
    border-radius:8px !important;
  }
  .stButton > button[kind="primary"]:hover {
    background:linear-gradient(135deg,#1a1f35 0%,#242c45 100%) !important;
    box-shadow:0 4px 12px rgba(15,23,42,0.45) !important;
  }

  /* Center icon buttons vertically inside their column cell. */
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td) [data-testid="stColumn"]:first-child [data-testid="stVerticalBlock"],
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td) [data-testid="stColumn"]:last-child [data-testid="stVerticalBlock"] {
    justify-content:center !important;
    flex-direction:column !important;
    min-height:56px;
  }

  /* Pencil / eye button — circular icon, inside table data rows */
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td) .stButton > button {
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
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td) .stButton > button:hover {
    background:var(--brand-l) !important; color:var(--brand) !important;
    border-color:var(--brand) !important;
    transform:scale(1.12) rotate(-8deg);
    box-shadow:0 4px 12px rgba(37,99,235,0.25) !important;
  }
  .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td) .stButton > button:active {
    transform:scale(0.95) rotate(0deg);
  }

  /* Kill row gaps so cell + button line up perfectly */
  [data-testid="stHorizontalBlock"] { gap:0 !important; margin:0 !important; }
  [data-testid="stVerticalBlock"]   { gap:0 !important; }
  .element-container                { margin:0 !important; padding:0 !important; }

  /* Restore normal vertical spacing INSIDE the edit-lead modal dialog so
     the "Final Status" heading no longer collides with the WIN/Null/LOST
     buttons. Scoped strictly to the dialog — table layout stays untouched. */
  [data-testid="stDialog"] [data-testid="stVerticalBlock"] { gap:0.5rem !important; }
  [data-testid="stDialog"] .element-container { margin:4px 0 !important; }
  [data-testid="stDialog"] .fs-label {
    display:block;
    font-size:13px; font-weight:600; color:#475569;
    margin:14px 0 8px !important;
    line-height:1.3 !important;
  }
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
  [data-testid="stContainer"] .stDateInput input {
    height:34px !important;
    min-height:34px !important;
    line-height:34px !important;
    padding:0 10px !important;
    font-size:12.5px !important;
  }
  /* Select combobox: NO fixed line-height (that clipped descenders like g/p).
     Parent container already flex-centers it vertically. */
  [data-testid="stContainer"] div[data-baseweb="select"] [role="combobox"] {
    height:auto !important;
    min-height:0 !important;
    line-height:1.3 !important;
    padding:0 10px !important;
    font-size:11px !important;
    display:flex !important;
    align-items:center !important;
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
  .filter-row-gap { height:22px; }

  /* ── Tablet & small desktop (≤1100px) — condense stats ── */
  @media (max-width: 1100px) {
    .block-container {
      padding-left:14px !important; padding-right:14px !important;
    }
    .fixed-header { padding:8px 8px 6px !important; }
    .hero h1 { font-size:18px !important; }
    .stats-row { gap:10px !important; }
    .stat-solo, .stat-group { padding:9px 10px !important; }
    .s-value { font-size:22px !important; }
    .ss-val { font-size:13px !important; }
    .ss-lbl { font-size:9px !important; }
  }

  /* ── Mobile fallback (≤768px): stack stats vertically ── */
  @media (max-width: 768px) {
    .stApp { overflow-x:hidden !important; }
    .block-container {
      padding:8px 8px 24px !important;
      max-width:100% !important;
    }
    .fixed-header {
      padding:8px 4px 4px !important;
      max-width:100% !important;
    }
    .hero {
      padding:10px 12px !important;
      margin-bottom:10px !important;
      border-radius:12px !important;
    }
    .hero h1 { font-size:16px !important; line-height:1.25 !important; }
    .stats-row {
      display:grid !important;
      grid-template-columns:1fr 1fr !important;
      gap:8px !important;
      margin-bottom:10px !important;
    }
    .stat-solo, .stat-group {
      min-width:0 !important;
      padding:8px 9px !important;
      border-radius:10px !important;
    }
    .stat-group { grid-column:1 / -1; }
    .stat-group .ss-row { gap:6px !important; }
    .s-value { font-size:19px !important; }
    .ss-val { font-size:13px !important; }
    .ss-lbl { font-size:8px !important; }
    .st-key-filter_panel { padding:8px !important; margin-bottom:10px !important; }

    /* Table: keep horizontal scroll, slightly narrower min-width so it doesn't
       feel like the table is empty when first viewed */
    .st-key-tbl_area { padding-bottom:6px !important; }
    .st-key-tbl_area [data-testid="stHorizontalBlock"] {
      min-width:1700px !important;
    }
    .th {
      font-size:11px !important;
      padding:8px 8px !important;
      min-height:36px !important;
    }
    .td {
      min-height:42px !important;
      padding:8px 8px !important;
      font-size:11.5px !important;
    }
    .st-key-tbl_area [data-testid="stHorizontalBlock"]:has(.td) .stButton > button {
      height:32px !important; min-height:32px !important;
      width:32px !important; min-width:32px !important;
      font-size:12px !important;
    }
    div[data-testid="stHorizontalBlock"] { gap:0.25rem !important; }
  }

  /* ── Extra-small phones (≤420px) ── */
  @media (max-width: 420px) {
    .hero h1 { font-size:14px !important; }
    .stats-row { grid-template-columns:1fr !important; }
    .stat-solo, .stat-group { padding:7px 8px !important; }
    .s-value { font-size:17px !important; }
    .st-key-tbl_area [data-testid="stHorizontalBlock"] {
      min-width:1500px !important;
    }
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
    .tbl-scroll { overflow-x:visible !important; }
    .stats-row, .sec { page-break-inside:avoid; }
    .td.wrap { white-space:normal !important; }
  }
</style>
""", unsafe_allow_html=True)

# -- Drag-to-scroll removed from here; injected after table via st.markdown --

# --------------------------------------------------------------------------- #
# Admin overview dashboard — aggregate visualisation across all IFB Points.
# Shown after sign-in when there is no franchise code in the URL.
# --------------------------------------------------------------------------- #
from overview_dashboard import render_overview_dashboard as _render_overview_dashboard_ext


_STAGE_COLORS  = {"Post-Purchase": "#2563EB", "1st 30 days call": "#0891B2",
                  "Pre-AMC": "#D97706", "8 Year Upgrade": "#7C3AED", "Other": "#94A3B8"}
_STATUS_COLORS = {"Contacted": "#16A34A", "Not Contacted": "#DC2626",
                  "RnR": "#D97706", "Pending": "#CBD5E1"}


def _get_allowed_codes(email: str) -> set[str]:
    """Return IFBpoint_id values assigned to this email in login_mapping.db.

    Checks Regional Email_ID first (widest scope), then Retail Email_ID, then Email_ID.
    """
    try:
        _e = email.strip().lower()
        with sqlite3.connect(LOGIN_MAPPING_DB) as _mc:
            for col in ('"Regional Email_ID"', '"Retail Email_ID"', "Email_ID"):
                rows = _mc.execute(
                    f"SELECT IFBpoint_id FROM login_mapping WHERE LOWER({col})=?",
                    (_e,),
                ).fetchall()
                codes = {r[0] for r in rows if r[0]}
                if codes:
                    return codes
        return set()
    except Exception:
        return set()


# Login gate — when there is NO IFB code in the URL:
#   • not signed in  → show ONLY the sign-in screen
#   • signed in      → show the all-points overview dashboard
# Everything else on the page is suppressed for the no-code case.
# --------------------------------------------------------------------------- #
if not _resolve_point_code():
    if st.session_state.get("_authed"):
        _allowed_codes = _get_allowed_codes(st.session_state.get("_authed_email", ""))
        _render_overview_dashboard_ext(DB_PATH, _CHANNEL_NAMES, _BUCKET_TO_STAGE, _allowed_codes,
                                      login_mapping_db=LOGIN_MAPPING_DB,
                                      user_email=st.session_state.get("_authed_email", ""),
                                      master_file=MASTER_FILE)
        st.stop()

    # Strip the fixed-header top padding + restore normal vertical spacing
    # (global gap:0 / margin:0 rules otherwise collapse the login layout).
    st.markdown(
        """<style>
          .block-container { padding-top:64px !important; }
          /* Restore spacing inside the login screen only */
          [data-testid="stForm"] { padding:22px 22px 8px !important;
                                    border:1px solid #E2E8F0 !important;
                                    border-radius:14px !important;
                                    background:#FFFFFF !important;
                                    box-shadow:0 4px 16px rgba(15,23,42,.06) !important; }
          [data-testid="stForm"] [data-testid="stVerticalBlock"] { gap:0.9rem !important; }
          [data-testid="stForm"] .element-container { margin:0 !important; }
        </style>""",
        unsafe_allow_html=True,
    )
    _lc1, _lc2, _lc3 = st.columns([1, 1.1, 1])
    with _lc2:
        st.markdown(
            "<div style='text-align:center;padding-bottom:28px;'>"
            "<div style='font-size:36px;font-weight:800;color:#0F172A;letter-spacing:-0.5px;'>"
            "📊 IFB POINT</div>"
            "<div style='font-size:15px;color:#94A3B8;font-weight:500;margin-top:6px;'>"
            "Customer Follow-Up &middot; Sign in to continue</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            _email = st.text_input("Email", placeholder="you@ifb.com")
            _password = st.text_input("Password", type="password", placeholder="••••••••")
            _submitted = st.form_submit_button(
                "Sign In", use_container_width=True, type="primary"
            )

        if _submitted:
            _valid = False
            try:
                with sqlite3.connect(LOGIN_DB) as _lcon:
                    _row = _lcon.execute(
                        "SELECT 1 FROM users WHERE LOWER(email)=? AND password=?",
                        (_email.strip().lower(), _password),
                    ).fetchone()
                    _valid = _row is not None
            except Exception:
                pass
            if _valid:
                st.session_state["_authed"] = True
                st.session_state["_authed_email"] = _email.strip().lower()
                st.rerun()
            else:
                st.error("❌ Invalid email or password.")

    st.stop()


# --------------------------------------------------------------------------- #
# Boot — fetch live API data on every page load (no caching, errors are visible)
# --------------------------------------------------------------------------- #
try:
    df_all, _source = load_all()
    st.session_state["_api_sync_ok"]  = True
    st.session_state["_api_sync_msg"] = f"{_source} · {len(df_all)} records"
except Exception as _exc:
    st.session_state["_api_sync_ok"]  = False
    st.session_state["_api_sync_msg"] = f"{type(_exc).__name__}: {_exc}"
    df_all = pd.DataFrame(columns=[
        "customer_id", "customer_name", "purchase_date",
        "machine_type", "phone_number", "email_id",
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
rnr_count    = int((df_all["status"]     == "RnR").sum())
not_reach    = int((df_all["status"]     == "Not Reachable").sum())
not_cont     = total - contacted - rnr_count - not_reach
interested   = int((df_all["interested"] == "Interested").sum())
not_interest = int((df_all["interested"] == "Not Interested").sum())
fu           = df_all["customer_follow_up"].value_counts().to_dict()

# Today's counts — leads whose lead_date == today
_df_today      = df_all[df_all["lead_date"] == today] if "lead_date" in df_all.columns else pd.DataFrame()
today_total    = len(_df_today)
today_contacted = int((_df_today["status"] == "Contacted").sum()) if not _df_today.empty else 0
today_rnr       = int((_df_today["status"] == "RnR").sum()) if not _df_today.empty else 0
today_not_reach = int((_df_today["status"] == "Not Reachable").sum()) if not _df_today.empty else 0
today_not_cont  = today_total - today_contacted - today_rnr - today_not_reach

def sub(cls, val, lbl):
    return f'<div class="sub-stat {cls}"><div class="ss-val">{val}</div><div class="ss-lbl">{lbl}</div></div>'

def sub2(cls, val, tval, lbl):
    return (f'<div class="sub-stat {cls}">'
            f'<div class="ss-dual">'
            f'<span class="ss-val">{val}</span>'
            f'<span class="ss-sep">|</span>'
            f'<span class="ss-val ss-today">{tval}</span></div>'
            f'<div class="ss-dual">'
            f'<span class="ss-lbl">{lbl}</span>'
            f'<span class="ss-sep-lbl">|</span>'
            f'<span class="ss-lbl ss-lbl-today">Today</span></div>'
            f'</div>')

_sync_ok  = st.session_state.get("_api_sync_ok",  False)
_sync_msg = st.session_state.get("_api_sync_msg", "Syncing…")
_badge_html = (
    '<span class="api-ok">🟢&nbsp;API Synced</span>' if _sync_ok else
    '<span class="api-err">🔴&nbsp;Sync failed</span>'
)

_ifb_code = _resolve_point_code()

# IFB Point Name — read from the channel names mapping (IFB_Point_Master.txt)
# Falls back to database column if mapping is unavailable
_ifb_name = ""
if _ifb_code and _ifb_code in _CHANNEL_NAMES:
    _ifb_name = _CHANNEL_NAMES[_ifb_code]
elif _ifb_code and not df_all.empty and "ifb_point_name" in df_all.columns:
    _n = df_all["ifb_point_name"].dropna()
    if not _n.empty:
        _ifb_name = str(_n.iloc[0]).strip()

# For display: use channel name if available, otherwise show the code
_ifb_display = _ifb_name if _ifb_name else (_ifb_code or "—")

st.markdown(f"""<div class="fixed-header">
  <div class="hero">
    <div>
      <h1>📊&nbsp; IFB POINT &middot; Customer Follow Up</h1>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;">
    </div>
  </div>
  <div class="stats-row">
    <div class="stat-solo">
      <div class="s-label">🏪 {_ifb_display}</div>
      <div class="s-value" style="font-size:22px;letter-spacing:1px;">Code: {_ifb_code or "—"}</div>
    </div>
    <div class="stat-solo stat-solo-dual">
      <div class="s-label">👥 Total Follow Up</div>
      <div class="s-dual-row">
        <div class="s-dual-col"><div class="s-value">{total}</div><div class="s-sub-lbl">All</div></div>
        <div class="s-dual-sep">|</div>
        <div class="s-dual-col"><div class="s-value s-today">{today_total}</div><div class="s-sub-lbl s-sub-today">Today</div></div>
      </div>
    </div>
    <div class="stat-group" style="flex:1.8 1 440px;min-width:440px;">
      <div class="g-label">📞 Contact Status</div>
      <div class="g-inner">
        {sub2("ss-green", contacted,    today_contacted, "Contacted")}
        {sub2("ss-red",   not_cont,     today_not_cont,  "Not Contacted")}
        {sub2("ss-warn",  rnr_count,    today_rnr,       "RnR")}
        {sub2("ss-slate", not_reach,    today_not_reach, "Not Reachable")}
      </div>
    </div>
    <div class="stat-group" style="flex:0.6 1 180px;min-width:180px;">
      <div class="g-label">💬 Interest</div>
      <div class="g-inner">
        {sub("ss-green", interested,   "Interested")}
        {sub("ss-red",   not_interest, "Not Interested")}
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
# Lead view selector (Today / Missed / NextAppt) — read from session_state
# --------------------------------------------------------------------------- #
lead_view = st.session_state.get("_lead_view", "Today")
if lead_view not in ["Today", "Missed", "NextAppt"]:
    lead_view = "Today"

# --------------------------------------------------------------------------- #
# Section selector — Open / Attempted — read from session_state BEFORE filter
# When "Next Appointment" is active, section toggles are disabled.
# --------------------------------------------------------------------------- #
_SEC_OPTS = ["Open", "Attempted"]
section   = st.session_state.get("_view_section", "Open")
if section not in _SEC_OPTS:
    section = "Open"


# --------------------------------------------------------------------------- #
# Filter bar — two rows in a white card panel
# --------------------------------------------------------------------------- #
# Date selector bounds come from the actual lead_date range in the DB
_lds   = ([d for d in df_all["lead_date"] if isinstance(d, date)]
          if "lead_date" in df_all.columns else [])
min_pd = min(_lds) if _lds else date(2019, 1, 1)
max_pd = max(_lds) if _lds else today

# Always initialize session_state defaults — prevents KeyError on any page load
if "lead_date_range" not in st.session_state:
    st.session_state["lead_date_range"] = (min_pd, max_pd)

# Default values used when no point code in URL (filter bar hidden)
date_range = (min_pd, max_pd)
fu_filter  = "All Follow-Up Stages"
search_q   = ""

if _ifb_code:
    with st.container():
        with st.container(key="filter_panel"):
            with st.container(key="filter_row_top"):
                r1c1, r1c2, r1c3, r1c4 = st.columns([2.2, 2.2, 2.2, 3.4], gap="small")
                with r1c1:
                    if st.button("📅  Today Follow Up", key="btn_today",
                                 use_container_width=True,
                                 type="primary" if lead_view == "Today" else "secondary"):
                        st.session_state["_lead_view"] = "Today"
                        st.session_state["_view_section"] = "Open"
                        st.rerun()
                with r1c2:
                    if st.button("⚠️  Missed Follow Up", key="btn_missed",
                                 use_container_width=True,
                                 type="primary" if lead_view == "Missed" else "secondary"):
                        st.session_state["_lead_view"] = "Missed"
                        st.session_state["_view_section"] = "Open"
                        st.rerun()
                with r1c3:
                    if st.button("📆  Follow Up Date", key="btn_nextappt",
                                 use_container_width=True,
                                 type="primary" if lead_view == "NextAppt" else "secondary"):
                        st.session_state["_lead_view"] = "NextAppt"
                        st.rerun()
                with r1c4:
                    if st.session_state.get("_lead_date_range_sig") != _resolve_point_code():
                        st.session_state["lead_date_range"] = (min_pd, max_pd)
                        st.session_state["_lead_date_range_sig"] = _resolve_point_code()
                    date_range = st.date_input(
                        "Lead Date Range",
                        value=st.session_state["lead_date_range"],
                        min_value=min_pd,
                        max_value=max_pd,
                        key="lead_date_range",
                        format="DD/MM/YYYY",
                        label_visibility="collapsed",
                    )

            # Real Streamlit containers give us stable hooks so the two rows
            # can be spaced independently without relying on markdown wrappers.
            with st.container(key="filter_row_bottom"):
                _FU_OPTS = [
                    "All Follow-Up Stages", "Post-Purchase",
                    "1st 30 days call", "Pre-AMC", "8 Year Upgrade",
                    "Greetings",
                ]
                _FU_LABEL = {
                    "All Follow-Up Stages": "🌐  All Follow-Up Stages",
                    "Post-Purchase":        "🎉  Post-Purchase",
                    "1st 30 days call":     "🔄  1st 30 days call",
                    "Pre-AMC":              "⏰  Pre-AMC",
                    "8 Year Upgrade":       "🏆  8 Year Upgrade",
                    "Greetings":            "🎊  Greetings",
                }
                _appt_active = lead_view == "NextAppt"
                r2c1, r2c2, r2c3, r2c4 = st.columns([2.2, 2.2, 3, 2.6], gap="small")
                with r2c1:
                    if st.button("📋  Open Followup", key="btn_open",
                                 use_container_width=True,
                                 disabled=_appt_active,
                                 type="primary" if section == "Open" and not _appt_active else "secondary"):
                        st.session_state["_view_section"] = "Open"
                        st.rerun()
                with r2c2:
                    if st.button("📞  Attempted", key="btn_att",
                                 use_container_width=True,
                                 disabled=_appt_active,
                                 type="primary" if section == "Attempted" and not _appt_active else "secondary"):
                        st.session_state["_view_section"] = "Attempted"
                        st.rerun()
                with r2c3:
                    fu_filter = st.selectbox(
                        "Stage",
                        options=_FU_OPTS,
                        format_func=lambda x: _FU_LABEL.get(x, x),
                        label_visibility="collapsed",
                    )
                with r2c4:
                    search_q = st.text_input(
                        "Search",
                        placeholder="🔍  Name ",
                        label_visibility="collapsed",
                    )

st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

# JS injection — measure the fixed-header height and set `.block-container`
# padding-top to match it. Filter rows scroll naturally with the page
# content (no pin), eliminating the empty-gap artifact.
st.html("""
<script>
(function(){
  /* st.html renders inline (no iframe), so we use document directly.
     Falls back to window.parent.document for any sandboxed context. */
  // Header is now in normal document flow at all widths — no padding-top
  // calculation needed. This block is intentionally a no-op kept for legacy
  // hook compatibility.
})();

</script>
""")


# --------------------------------------------------------------------------- #
# Filter
# --------------------------------------------------------------------------- #
filtered = df_all.copy()

# 1. lead_view filter
#    "Today"    → lead_date == today
#    "Missed"   → lead_date <  today (everything up to and including yesterday)
#    "NextAppt" → next_appointment == today (ignores lead_date & section)
if lead_view == "NextAppt":
    # Next Appointment view: show rows where next_appointment == today
    if "next_appointment" in filtered.columns:
        filtered = filtered[
            filtered["next_appointment"].apply(
                lambda d: isinstance(d, date) and d == today
            )
        ]
    else:
        filtered = filtered.iloc[0:0]  # empty
else:
    if "lead_date" in filtered.columns:
        if lead_view == "Today":
            filtered = filtered[filtered["lead_date"] == today]
        elif lead_view == "Missed":
            filtered = filtered[
                filtered["lead_date"].apply(
                    lambda d: isinstance(d, date) and d < today
                )
            ]

    # 2. section filter on status (only when NOT in NextAppt mode)
    #    "Attempted" → any call attempt made (Contacted / Not Contacted / RnR / Not Reachable)
    #    "Open"      → all leads (no status restriction)
    if section == "Attempted" and "status" in filtered.columns:
        attempted_mask = filtered["status"].fillna("").isin(["Contacted", "Not Contacted", "RnR", "Not Reachable"])
        filtered = filtered[attempted_mask].copy()

# follow-up stage filter
if fu_filter != "All Follow-Up Stages":
    filtered = filtered[filtered["customer_follow_up"] == fu_filter]

# date range (on lead_date) + search apply to all sections
if isinstance(date_range, tuple) and len(date_range) == 2 and "lead_date" in filtered.columns:
    d0, d1 = date_range
    filtered = filtered[
        filtered["lead_date"].apply(
            lambda d: isinstance(d, date) and d0 <= d <= d1
        )
    ]
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
    cid     = str(row["customer_id"])
    name    = row.get("customer_name") or "—"
    machine = row.get("machine_desc")  or "—"
    pincode = str(row.get("pin_code") or "").strip() or "—"

    st.markdown(
        f"<div style='font-size:12px;color:#94A3B8;text-transform:uppercase;"
        f"letter-spacing:0.7px;margin-bottom:2px;'>Customer</div>"
        f"<div style='font-size:20px;font-weight:700;color:#0F172A;line-height:1.2;'>{name}</div>"
        f"<div style='font-size:12px;color:#94A3B8;margin:4px 0 16px;'>"
        f"ID {cid} &nbsp;·&nbsp; 📍 {pincode} &nbsp;·&nbsp; ⚙️ {machine}</div>",
        unsafe_allow_html=True,
    )

    # ── Saved values ────────────────────────────────────────────────────────
    cur_s  = row.get("status")      if pd.notna(row.get("status")      or "") else None
    cur_i  = row.get("interested")  if pd.notna(row.get("interested")  or "") else None
    cur_r  = str(row.get("remarks") or "") if pd.notna(row.get("remarks") or "") else ""
    cur_fs = row.get("final_status") if pd.notna(row.get("final_status") or "") else None
    cur_reason = row.get("reason") if pd.notna(row.get("reason") or "") else None

    raw_a = row.get("next_appointment")
    cur_a = None
    if raw_a is not None:
        try:
            if not pd.isna(raw_a):
                cur_a = raw_a if isinstance(raw_a, date) else pd.to_datetime(raw_a, errors="coerce").date()
        except (TypeError, ValueError):
            cur_a = None
    _tomorrow = today + timedelta(days=1)
    # Clamp any past/today date to tomorrow (min allowed)
    if isinstance(cur_a, date) and cur_a < _tomorrow:
        cur_a = _tomorrow

    # ── Q1: Status (always shown) ────────────────────────────────────────────
    ns = st.selectbox(
        "Call Status", STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(cur_s) if cur_s in STATUS_OPTIONS else None,
        placeholder="Contacted / RnR / Not Reachable",
        key=f"dlg_s_{cid}",
    )

    # defaults for fields that may not render
    ni       = None
    na       = None
    nfs      = None
    nr       = ""
    n_reason = None

    # ── Conditional flow ─────────────────────────────────────────────────────
    if ns == "Contacted":
        # Q2: Interested?
        ni = st.selectbox(
            "Interested?", INTEREST_OPTIONS,
            index=INTEREST_OPTIONS.index(cur_i) if cur_i in INTEREST_OPTIONS else None,
            placeholder="Interested / Not Interested",
            key=f"dlg_i_{cid}",
        )

        # Q3: Reason — only shown when Not Interested
        if ni == "Not Interested":
            n_reason = st.selectbox(
                "Reason", REASON_OPTIONS,
                index=REASON_OPTIONS.index(cur_reason) if cur_reason in REASON_OPTIONS else None,
                placeholder="Select a reason",
                key=f"dlg_reason_{cid}",
            )

        # Q3b: Next Appointment — only shown when Interested (skip if Not Interested)
        if ni == "Interested":
            na = st.date_input("Next Appointment",
                               value=cur_a, min_value=_tomorrow, key=f"dlg_a_{cid}")

        # Q4: Remarks (150 char limit + live JS counter)
        nr = st.text_area("Remarks", value=cur_r, height=90,
                          max_chars=150, key=f"dlg_r_{cid}")
        _left = 150 - len(nr)
        _clr  = "#16A34A" if _left > 50 else "#D97706" if _left > 15 else "#DC2626"
        st.html(f"""
<div id="rc_{cid}" style="text-align:right;font-size:11px;font-weight:600;
     color:{_clr};margin-top:-10px;">{_left} / 150 left</div>
<script>
(function(){{
  var counter = document.getElementById('rc_{cid}');
  function init(){{
    var dlg = document.querySelector('[data-testid="stDialog"]');
    if(!dlg || !counter) return false;
    var ta = dlg.querySelector('textarea');
    if(!ta) return false;
    function upd(){{
      var left = 150 - ta.value.length;
      counter.textContent = left + ' / 150 left';
      counter.style.color = left > 50 ? '#16A34A' : left > 15 ? '#D97706' : '#DC2626';
    }}
    ta.addEventListener('input', upd);
    upd();
    return true;
  }}
  var t = setInterval(function(){{ if(init()) clearInterval(t); }}, 50);
}})();
</script>""")

        # Final Status — auto-derived:
        #   Interested     → None
        #   Not Interested → "LOST"
        nfs = "LOST" if ni == "Not Interested" else None

        # Save enabled when all visible fields are filled:
        # · Interested? must be answered
        # · If Interested → Next Appointment must be set
        # · If Not Interested → Reason must be selected
        # · Remarks must not be empty
        _appt_ok   = (isinstance(na, date)) if ni == "Interested" else True
        _reason_ok = (n_reason is not None) if ni == "Not Interested" else True
        _can_save  = (ni is not None) and _appt_ok and _reason_ok and (nr.strip() != "")

    elif ns in ("Not Contacted", "RnR"):
        # Q2: Next Appointment (mandatory, starts from tomorrow)
        na = st.date_input("Next Appointment",
                           value=cur_a, min_value=_tomorrow, key=f"dlg_a_{cid}")

        # Q3: Remarks (150 char limit + live JS counter)
        nr = st.text_area("Remarks", value=cur_r, height=90,
                          max_chars=150, key=f"dlg_r_{cid}")
        _left = 150 - len(nr)
        _clr  = "#16A34A" if _left > 50 else "#D97706" if _left > 15 else "#DC2626"
        st.html(f"""
<div id="rc_{cid}" style="text-align:right;font-size:11px;font-weight:600;
     color:{_clr};margin-top:-10px;">{_left} / 150 left</div>
<script>
(function(){{
  var counter = document.getElementById('rc_{cid}');
  function init(){{
    var dlg = document.querySelector('[data-testid="stDialog"]');
    if(!dlg || !counter) return false;
    var ta = dlg.querySelector('textarea');
    if(!ta) return false;
    function upd(){{
      var left = 150 - ta.value.length;
      counter.textContent = left + ' / 150 left';
      counter.style.color = left > 50 ? '#16A34A' : left > 15 ? '#D97706' : '#DC2626';
    }}
    ta.addEventListener('input', upd);
    upd();
    return true;
  }}
  var t = setInterval(function(){{ if(init()) clearInterval(t); }}, 50);
}})();
</script>""")

        # Save enabled when all visible fields are filled:
        # · Next Appointment must be a valid date
        # · Remarks must not be empty
        _can_save = (isinstance(na, date)) and (nr.strip() != "")

    elif ns == "Not Reachable":
        # Q2: Remarks only (150 char limit + live JS counter)
        nr = st.text_area("Remarks", value=cur_r, height=90,
                          max_chars=150, key=f"dlg_r_{cid}")
        _left = 150 - len(nr)
        _clr  = "#16A34A" if _left > 50 else "#D97706" if _left > 15 else "#DC2626"
        st.html(f"""
<div id="rc_{cid}" style="text-align:right;font-size:11px;font-weight:600;
     color:{_clr};margin-top:-10px;">{_left} / 150 left</div>
<script>
(function(){{
  var counter = document.getElementById('rc_{cid}');
  function init(){{
    var dlg = document.querySelector('[data-testid="stDialog"]');
    if(!dlg || !counter) return false;
    var ta = dlg.querySelector('textarea');
    if(!ta) return false;
    function upd(){{
      var left = 150 - ta.value.length;
      counter.textContent = left + ' / 150 left';
      counter.style.color = left > 50 ? '#16A34A' : left > 15 ? '#D97706' : '#DC2626';
    }}
    ta.addEventListener('input', upd);
    upd();
    return true;
  }}
  var t = setInterval(function(){{ if(init()) clearInterval(t); }}, 50);
}})();
</script>""")

        # Save enabled when Remarks not empty
        _can_save = (nr.strip() != "")

    else:
        # No status selected yet
        _can_save = False

    # ── Save / Cancel ────────────────────────────────────────────────────────
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾  Save", type="primary", use_container_width=True,
                     key=f"dlg_save_{cid}"):
            if not _can_save:
                # Build per-field error list + red-border CSS
                _err_fields = []
                _err_css    = []

                def _sel_border(key):
                    return (f'.st-key-{key} [data-baseweb="select"] > div:first-child'
                            f'{{border:1.5px solid #DC2626 !important;'
                            f'box-shadow:0 0 0 1px #DC2626 !important;border-radius:6px !important;}}')

                def _inp_border(key):
                    return (f'.st-key-{key} [data-baseweb="input"]'
                            f'{{border:1.5px solid #DC2626 !important;'
                            f'box-shadow:0 0 0 1px #DC2626 !important;}}')

                def _ta_border(key):
                    return (f'.st-key-{key} textarea'
                            f'{{border:1.5px solid #DC2626 !important;'
                            f'box-shadow:0 0 0 1px #DC2626 !important;border-radius:6px !important;}}')

                if ns is None:
                    _err_fields.append("Call Status")
                    _err_css.append(_sel_border(f"dlg_s_{cid}"))

                if ns == "Contacted":
                    if ni is None:
                        _err_fields.append("Interested?")
                        _err_css.append(_sel_border(f"dlg_i_{cid}"))
                    if ni == "Not Interested" and n_reason is None:
                        _err_fields.append("Reason")
                        _err_css.append(_sel_border(f"dlg_reason_{cid}"))
                    if ni == "Interested" and not isinstance(na, date):
                        _err_fields.append("Next Appointment")
                        _err_css.append(_inp_border(f"dlg_a_{cid}"))
                    if nr.strip() == "":
                        _err_fields.append("Remarks")
                        _err_css.append(_ta_border(f"dlg_r_{cid}"))

                elif ns in ("Not Contacted", "RnR"):
                    if not isinstance(na, date):
                        _err_fields.append("Next Appointment")
                        _err_css.append(_inp_border(f"dlg_a_{cid}"))
                    if nr.strip() == "":
                        _err_fields.append("Remarks")
                        _err_css.append(_ta_border(f"dlg_r_{cid}"))

                elif ns == "Not Reachable":
                    if nr.strip() == "":
                        _err_fields.append("Remarks")
                        _err_css.append(_ta_border(f"dlg_r_{cid}"))

                st.markdown(
                    f"<style>{''.join(_err_css)}</style>"
                    f"<div style='color:#DC2626;font-size:12px;font-weight:500;"
                    f"margin-top:4px;line-height:1.6;'>"
                    f"Required: {' &nbsp;·&nbsp; '.join(_err_fields)}</div>",
                    unsafe_allow_html=True,
                )
            else:
                try:
                    result = update_row(
                        cid,
                        ns,
                        na if isinstance(na, date) else None,
                        ni if ni and ni != "—" else None,
                        nr.strip() or None,
                        nfs,
                        n_reason,
                    )
                    _rows = result.get("rows_updated", 0)
                    _err  = result.get("error")
                    if _err:
                        st.warning(f"⚠️ SQLite write failed — {_err}")
                    else:
                        if result.get("auto_lose"):
                            st.toast("🔴 3 RnR attempts reached — Final Status auto-set to LOST", icon="❌")
                        else:
                            st.toast(
                                f"✅ Saved — {_rows} row{'s' if _rows != 1 else ''} updated",
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
    # Pick a context-aware message depending on WHY there are no records
    _src = st.session_state.get("_api_sync_msg", "")
    if not _ifb_code:
        _no_rec_html = "<b style='color:#DC2626;font-size:18px;'>❌ Invalid Code</b>"
    elif "invalid-id" in _src:
        _no_rec_html = f"<b style='color:#DC2626;font-size:18px;'>❌ Invalid ID - {_ifb_code}</b>"
    elif "no-data" in _src:
        _no_rec_html = (
            f"<b style='color:#475569;font-size:16px;'>No records for IFB Point {_ifb_code}</b><br>"
            "<span style='font-size:13px;'>"
        )
    else:
        _no_rec_html = "No records match the current filters."
    if _no_rec_html:
        st.markdown(
            "<div id='no-records-msg' style='text-align:center;padding:64px 20px;color:#94A3B8;"
            "background:#fff;border:1px solid #E2E8F0;border-radius:14px;"
            f"box-shadow:0 1px 4px rgba(0,0,0,.04);line-height:1.8;'>{_no_rec_html}</div>",
            unsafe_allow_html=True,
        )
else:
    # ── Table as @st.fragment — only this section re-renders on eye/page
    #    clicks. Header, stats, filters stay completely frozen. ───────────
    @st.fragment
    def _render_table(df_filt, sec):
        PAGE_SIZE = 30
        total_rows  = len(df_filt)
        total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)

        pg_sig_key = f"pg_sig_{sec}"
        sig = (sec, total_rows, tuple(df_filt["customer_id"].head(3).tolist()))
        if st.session_state.get(pg_sig_key) != sig:
            st.session_state[pg_sig_key] = sig
            st.session_state["page_num"] = 1

        st.session_state.setdefault("page_num", 1)
        page = max(1, min(st.session_state["page_num"], total_pages))
        st.session_state["page_num"] = page

        start = (page - 1) * PAGE_SIZE
        end   = min(start + PAGE_SIZE, total_rows)
        page_df = df_filt.iloc[start:end]

        # Column ratios: edit, 14 data cols, eye
        R = [0.35, 1.2, 1.6, 1.2, 1.5, 1.1, 1.3, 1.8, 1.6, 1.1, 1.0, 1.2, 1.0, 1.0, 1.0, 0.35]
        HDR = ["", "Follow-Up", "Customer Name", "Phone", "Email",
               "Purchase Date", "Machine Type", "Machine Desc", "Dealer Name",
               "Call Status", "Next Appt", "Interested?", "Remarks", "Final Status", "Reason", ""]

        def _status_chip(v):
            s = _safe(v)
            if s == "Contacted":     return f"<span class='chip green'>{s}</span>"
            if s == "Not Contacted": return f"<span class='chip red'>{s}</span>"
            if s == "RnR":           return f"<span class='chip warn'>{s}</span>"
            if s == "—":             return "<span class='chip'>—</span>"
            return f"<span class='chip slate'>{s}</span>"

        def _interest_chip(v):
            s = _safe(v)
            if s == "Interested":     return f"<span class='chip green'>{s}</span>"
            if s == "Not Interested": return f"<span class='chip red'>{s}</span>"
            if s == "—":              return "<span class='chip'>—</span>"
            return f"<span class='chip slate'>{s}</span>"

        def _on_eye_click(cid: str):
            # If the same row is clicked again → toggle it off
            current = st.session_state.get("_revealed", {})
            if cid in current:
                st.session_state["_revealed"] = {}
                return
            # New row clicked → fetch and show ONLY this row (clear any previous)
            details = _fetch_customer_details(cid)
            if details is not None:
                mob = (details.get("mobileNo") or "").strip()
                eml = (details.get("emailID")  or "").strip()
                st.session_state["_revealed"] = {
                    cid: {
                        "mobileNo": mob if mob else "N/A",
                        "emailID":  eml if eml else "N/A",
                    }
                }
            else:
                st.session_state["_eye_error"] = True

        if st.session_state.pop("_eye_error", False):
            st.toast("Could not fetch customer details — API error", icon="⚠️")

        with st.container(key="tbl_area"):
            # Header row
            hdr = st.columns(R)
            last_i = len(HDR) - 1
            for i, (c, lbl) in enumerate(zip(hdr, HDR)):
                c.markdown(f"<div class='th'>{lbl}</div>", unsafe_allow_html=True)

            for ri, (_, row) in enumerate(page_df.iterrows()):
                cid = str(row["customer_id"])
                cols = st.columns(R)

                with cols[0]:
                    if st.button("✏️", key=f"edit_{ri}_{cid}", help=f"Edit lead {cid}"):
                        edit_lead_dialog(row.to_dict())

                _name_raw = (str(row.get('customer_name') or '')).strip()
                if _name_raw:
                    _name_html = f"<b>{_safe(_name_raw)}</b>"
                else:
                    _mt = str(row.get('machine_type') or '').strip() or 'Customer'
                    _name_html = f"<span style='color:#94A3B8;font-style:italic;'>(unnamed {_mt.lower()})</span>"

                _revealed = st.session_state.get("_revealed", {})
                _rev = _revealed.get(cid)
                if _rev:
                    _phone_display = _rev.get("mobileNo") or "N/A"
                    _email_display = _rev.get("emailID")  or "N/A"
                    _ph_style = "color:#16A34A;font-weight:600;" if _phone_display != "N/A" else "color:#94A3B8;"
                    _em_style = "color:#16A34A;font-weight:600;" if _email_display != "N/A" else "color:#94A3B8;"
                else:
                    _phone_display = _safe(row.get('phone_number'))
                    _email_display = _safe(row.get('email_id'))
                    _ph_style = ""
                    _em_style = ""

                cols[1].markdown(f"<div class='td'>{_safe(row.get('customer_follow_up'))}</div>", unsafe_allow_html=True)
                cols[2].markdown(f"<div class='td'>{_name_html}</div>", unsafe_allow_html=True)
                cols[3].markdown(f"<div class='td' style='{_ph_style}'>{_phone_display}</div>", unsafe_allow_html=True)
                cols[4].markdown(f"<div class='td' style='{_em_style}'>{_email_display}</div>", unsafe_allow_html=True)
                cols[5].markdown(f"<div class='td'>{_fmt_date(row.get('purchase_date'))}</div>", unsafe_allow_html=True)
                cols[6].markdown(f"<div class='td'>{_safe(row.get('machine_type'))}</div>", unsafe_allow_html=True)
                cols[7].markdown(f"<div class='td'>{_safe(row.get('machine_desc'))}</div>", unsafe_allow_html=True)
                cols[8].markdown(f"<div class='td'>{_safe(row.get('dealer_name'))}</div>", unsafe_allow_html=True)
                cols[9].markdown(f"<div class='td'>{_status_chip(row.get('status'))}</div>", unsafe_allow_html=True)
                cols[10].markdown(f"<div class='td'>{_fmt_date(row.get('next_appointment'))}</div>", unsafe_allow_html=True)
                cols[11].markdown(f"<div class='td'>{_interest_chip(row.get('interested'))}</div>", unsafe_allow_html=True)

                _rem_full = _safe(row.get('remarks'))
                _rem_tip  = _rem_full.replace("'", "&#39;").replace('"', "&quot;")
                cols[12].markdown(
                    f"<div class='td' title='{_rem_tip}'>"
                    f"<span style='overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
                    f"min-width:0;flex:1;display:block;'>{_rem_full}</span></div>",
                    unsafe_allow_html=True,
                )

                _fs = _safe(row.get('final_status'))
                if _fs == "WIN":
                    _fs_html = "<span class='chip nodot'>🏆 WIN</span>"
                elif _fs == "LOST":
                    _fs_html = "<span class='chip nodot'>❌ LOST</span>"
                else:
                    _fs_html = "<span class='chip'>—</span>"
                cols[13].markdown(f"<div class='td center'>{_fs_html}</div>", unsafe_allow_html=True)

                _reason_full = _safe(row.get('reason'))
                _reason_tip  = _reason_full.replace("'", "&#39;").replace('"', "&quot;")
                cols[14].markdown(
                    f"<div class='td' title='{_reason_tip}'>"
                    f"<span style='overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
                    f"min-width:0;flex:1;display:block;'>{_reason_full}</span></div>",
                    unsafe_allow_html=True,
                )

                with cols[15]:
                    _already_revealed = cid in st.session_state.get("_revealed", {})
                    st.button(
                        "🔓" if _already_revealed else "👁️",
                        key=f"view_{ri}_{cid}",
                        help=f"View lead {cid}",
                        on_click=_on_eye_click,
                        args=(cid,),
                    )


        # -- Right-click drag-to-scroll for the table (mouse-only horizontal scroll) --
        st.markdown("""
        <img src="" onerror="
          (function(){
            var el=document.querySelector('.st-key-tbl_area');
            if(!el||el.dataset.dragInit) return;
            el.dataset.dragInit='1';
            var isDown=false,startX,sl,didDrag=false;
            el.addEventListener('mousedown',function(e){
              if(e.button!==2) return;
              isDown=true; didDrag=false;
              el.classList.add('dragging');
              startX=e.pageX; sl=el.scrollLeft;
              e.preventDefault();
            });
            el.addEventListener('contextmenu',function(e){
              if(didDrag) e.preventDefault();
            });
            document.addEventListener('mouseup',function(e){
              if(e.button===2 && isDown){ isDown=false; el.classList.remove('dragging'); }
            });
            document.addEventListener('mousemove',function(e){
              if(!isDown) return;
              e.preventDefault();
              didDrag=true;
              el.scrollLeft=sl-(e.pageX-startX);
            });
          })();
        " style="display:none;">
        """, unsafe_allow_html=True)

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

    _render_table(filtered, section)


