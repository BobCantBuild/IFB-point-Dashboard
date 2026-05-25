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
  /* ── Page base ── */
  .stApp { background:#F1F5F9; overflow-x:hidden; }
  .block-container {
    padding-top:1.4rem; padding-bottom:2rem;
    width:100% !important; max-width:1640px !important;
  }
  header[data-testid="stHeader"] { background:transparent; }
  #MainMenu, footer { visibility:hidden; }

  /* ── Remove st.columns gap ── */
  [data-testid="stHorizontalBlock"] { gap:0 !important; margin:0 !important; }
  [data-testid="column"] { min-width:0 !important; }
  [data-testid="stVerticalBlock"] { gap:0px !important; }

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
  .stats-row { display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; align-items:stretch; }
  .stat-solo {
    background:#fff; border:1px solid #E2E8F0; border-radius:14px;
    padding:20px 22px; min-width:130px; flex-shrink:0;
    box-shadow:0 1px 4px rgba(0,0,0,.06);
  }
  .s-label { font-size:11px; font-weight:600; color:#94A3B8; text-transform:uppercase; letter-spacing:1px; }
  .s-value { font-size:38px; font-weight:800; line-height:1; color:#0F172A; margin-top:6px; }
  .s-sub   { font-size:11px; color:#CBD5E1; margin-top:5px; }
  .stat-group {
    background:#fff; border:1px solid #E2E8F0; border-radius:14px;
    padding:16px 18px; flex:1 1 320px; min-width:320px; box-shadow:0 1px 4px rgba(0,0,0,.06);
  }
  .g-label { font-size:11px; font-weight:600; color:#94A3B8; text-transform:uppercase; letter-spacing:1px; margin-bottom:10px; }
  .g-inner { display:flex; gap:8px; flex-wrap:wrap; }
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
    background:#0F172A; color:#F8FAFC; border:0; border-radius:6px;
    padding:0 10px; font-weight:600; font-size:13px;
    height:42px !important; min-height:42px !important;
    line-height:42px !important; display:inline-flex;
    align-items:center; justify-content:center;
  }
  .stButton > button:hover { background:#1E293B; }

  /* ── Kill every source of vertical gap inside table rows ── */
  [data-testid="stHorizontalBlock"] { gap:0 !important; margin:0 !important; padding:0 !important; }
  [data-testid="stVerticalBlock"]   { gap:0 !important; }
  .element-container                { margin:0 !important; padding:0 !important; }
  [data-testid="column"] > div      { gap:0 !important; }

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
# Per-row inline-edit table  (with horizontal scroll via fixed page width)
# --------------------------------------------------------------------------- #

# col widths in proportional units — total ≈ 16.5 (maps to 1640px page)
#         fu    id    name  date   machine  phone  email   status  appt   int    rem   edit  save
RATIOS = [2.3,  0.65, 1.2,  1.0,   2.0,   1.1,   1.8,    1.1,    1.05,  1.3,   2.0,  0.5,  0.5]
LABELS = ["Customer Follow-Up","ID","Name","Purchase Date",
          "Machine Type","Phone","Email",
          "Status","Next Appt","Interested?","Remarks","&nbsp;","&nbsp;"]

N = len(RATIOS)  # 13 columns (0-10 data, 11 edit, 12 save)
OUTER = "#94A3B8"
INNER = "#E2E8F0"
HEAD_BG = "#F1F5F9"
ALT = ["#FFFFFF", "#F8FAFC"]


def _safe(v, fallback="—"):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return fallback
    s = str(v).strip()
    return fallback if s in ("", "NaT", "nan", "None") else s


def _cell(col, html, bg, top=False, left=False, right=False,
          last=False, header=False, wrap=False):
    bt  = f"border-top:2px solid {OUTER};"    if top   else ""
    bl  = f"border-left:2px solid {OUTER};"   if left  else ""
    br  = f"border-right:2px solid {OUTER};"  if right else f"border-right:1px solid {INNER};"
    bb  = f"border-bottom:2px solid {OUTER};" if last  else f"border-bottom:1px solid {INNER};"
    fw  = "700"     if header else "400"
    fs  = "10.5px"  if header else "13px"
    clr = "#475569" if header else "#1E293B"
    tt  = "text-transform:uppercase;letter-spacing:0.7px;" if header else ""
    ws  = "white-space:normal;word-break:break-word;" if wrap else "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
    col.markdown(
        f"<div style='background:{bg};padding:10px 12px;font-size:{fs};"
        f"font-weight:{fw};color:{clr};{tt}{ws}"
        f"min-height:42px;{bt}{bl}{br}{bb}'>{html}</div>",
        unsafe_allow_html=True,
    )


# session state
if "editing_cid" not in st.session_state:
    st.session_state["editing_cid"] = None

# ── header ────────────────────────────────────────────────────────────────────
hdr = st.columns(RATIOS)
for i, (c, lbl) in enumerate(zip(hdr, LABELS)):
    _cell(c, lbl, HEAD_BG, header=True, top=True,
          left=(i == 0), right=(i == N - 1),
          wrap=(i in (0, 10)))

# ── rows ─────────────────────────────────────────────────────────────────────
if len(filtered) == 0:
    st.markdown(
        "<div style='text-align:center;padding:48px;color:#94A3B8;font-size:14px;"
        f"border-left:2px solid {OUTER};border-right:2px solid {OUTER};"
        f"border-bottom:2px solid {OUTER};background:#fff'>No records found.</div>",
        unsafe_allow_html=True,
    )
else:
    total_rows = len(filtered)
    for ri, (_, row) in enumerate(filtered.iterrows()):
        cid    = int(row["customer_id"])
        is_end = (ri == total_rows - 1)
        is_ed  = (st.session_state["editing_cid"] == cid) and (section == "Today's Lead")
        bg     = ALT[ri % 2]

        cur_s = row["status"]           if pd.notna(row.get("status"))           else None
        cur_a = row["next_appointment"] if pd.notna(row.get("next_appointment")) else None
        cur_i = row["interested"]       if pd.notna(row.get("interested"))       else None
        cur_r = str(row["remarks"])     if pd.notna(row.get("remarks")) and row["remarks"] else ""

        dc = st.columns(RATIOS)

        # read-only cells
        pd_s = row["purchase_date"].strftime("%d/%m/%Y") if row.get("purchase_date") and pd.notna(row["purchase_date"]) else "—"
        _cell(dc[0], _safe(row.get("customer_follow_up")),        bg, left=True, last=is_end, wrap=True)
        _cell(dc[1], str(cid),                                   bg,            last=is_end)
        _cell(dc[2], f"<b>{_safe(row.get('customer_name'))}</b>", bg,           last=is_end)
        _cell(dc[3], pd_s,                                       bg,            last=is_end)
        _cell(dc[4], _safe(row.get("machine_type")),             bg,            last=is_end)
        _cell(dc[5], _safe(row.get("phone_number")),             bg,            last=is_end)
        _cell(dc[6], _safe(row.get("email_id")),                 bg,            last=is_end)

        if is_ed:
            with dc[7]:
                ns = st.selectbox("Status", ["—"] + STATUS_OPTIONS,
                    index=(["—"]+STATUS_OPTIONS).index(cur_s) if cur_s in STATUS_OPTIONS else 0,
                    key=f"s_{cid}", label_visibility="collapsed")
            with dc[8]:
                na = st.date_input("Appt",
                    value=cur_a if isinstance(cur_a, date) else None,
                    min_value=today, key=f"a_{cid}", label_visibility="collapsed")
            with dc[9]:
                ni = st.selectbox("Interested", ["—"] + INTEREST_OPTIONS,
                    index=(["—"]+INTEREST_OPTIONS).index(cur_i) if cur_i in INTEREST_OPTIONS else 0,
                    key=f"i_{cid}", label_visibility="collapsed")
            with dc[10]:
                nr = st.text_input("Remarks", value=cur_r,
                    key=f"r_{cid}", label_visibility="collapsed")
            # col 11 = Cancel (✕),  col 12 = Save (💾)
            with dc[11]:
                if st.button("✕", key=f"cx_{cid}", help="Cancel",
                             use_container_width=True):
                    st.session_state["editing_cid"] = None
                    st.rerun()
            with dc[12]:
                if st.button("💾", key=f"sv_{cid}", help="Save",
                             use_container_width=True):
                    update_row(cid,
                        None if ns == "—" else ns,
                        na if isinstance(na, date) else None,
                        None if ni == "—" else ni,
                        nr.strip() or None)
                    st.session_state["editing_cid"] = None
                    st.rerun()
        else:
            ap_s = cur_a.strftime("%d/%m/%Y") if cur_a else "—"
            _cell(dc[7],  _safe(cur_s, "—"), bg,                        last=is_end)
            _cell(dc[8],  ap_s,              bg,                        last=is_end)
            _cell(dc[9],  _safe(cur_i, "—"), bg,                        last=is_end)
            _cell(dc[10], _safe(cur_r, "—"), bg, right=True, last=is_end, wrap=True)
            # col 11 = Edit (✏️),  col 12 = Save (empty in view mode)
            with dc[11]:
                if section == "Today's Lead":
                    if st.button("✏️", key=f"ed_{cid}",
                                 help="Edit row", use_container_width=True):
                        st.session_state["editing_cid"] = cid
                        st.rerun()
            with dc[12]:
                pass  # save column is empty until row is in edit mode
