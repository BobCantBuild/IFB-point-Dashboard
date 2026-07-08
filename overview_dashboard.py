"""IFB Point — Analytics Console (Overview Dashboard).

Renders the admin analytics screen shown at /?auth=ok.
Called from streamlit_app.py; receives shared state as arguments
to avoid circular imports.

Usage (from streamlit_app.py):
    from overview_dashboard import render_overview_dashboard
    render_overview_dashboard(DB_PATH, _CHANNEL_NAMES, _BUCKET_TO_STAGE)
"""
from __future__ import annotations

import html
import math
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Constants ─────────────────────────────────────────────────────────────────

_KPI_STYLE = {
    "Total Stores":              ("#4F46E5", "#EEF2FF", "🏪"),
    "Total Customers Allocated": ("#0EA5E9", "#F0F9FF", "👥"),
    "Calls Attempted":           ("#16A34A", "#F0FDF4", "✅"),
    "Interested Customers":      ("#7C3AED", "#F5F3FF", "⭐"),
    "Not Contacted":             ("#DC2626", "#FEF2F2", "🚫"),
    "Calls Connected":           ("#D97706", "#FFFBEB", "📞"),
}

_BAR_SERIES = {
    "Total Customers Allocated": "#4F46E5",
    "Calls Attempted":           "#16A34A",
    "Not Contacted":             "#DC2626",
    "RnR":                       "#D97706",
}

_OVERVIEW_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  /* ── Base: crisp white + soft lavender tint ── */
  .stApp { background:#F0F2FF !important; font-family:'Inter',sans-serif !important; }
  .block-container { padding:10px 20px 6px !important; max-width:100% !important; }
  [data-testid="stHeader"], #MainMenu, footer { display:none !important; }
  section.main [data-testid="stVerticalBlock"] { gap:0.28rem !important; }
  section.main [data-testid="stHorizontalBlock"] { margin:0 !important; }
  * { box-sizing:border-box; }

  /* ── Bordered container padding ── */
  [data-testid="stVerticalBlockBorderWrapper"] > div > div {
    padding:7px 10px !important; gap:0 !important;
  }

  /* ── Plotly charts ── */
  /* Inner chart card — single clean card */
  [data-testid="stPlotlyChart"] {
    background:#FFFFFF !important; border:1px solid #E0E7FF !important;
    border-radius:14px !important; padding:3px 5px !important;
    box-shadow:0 2px 12px rgba(79,70,229,0.08) !important;
  }
  /* Outer wrapper boxes (KPI row + the 3 sections): keep their SPACE so
     nothing shifts, but hide the border line → no double-border. */
  .st-key-kpi_row, .st-key-sec_day, .st-key-sec_week, .st-key-sec_month {
    border-color:transparent !important;
    box-shadow:none !important;
    background:transparent !important;
  }

  /* Push the entire rail (search + buttons + list) down to sit flush
     with the KPI row content rather than the container top edge. */
  .st-key-two_pane > div:first-child > div:first-child {
    margin-top:14px !important;
  }

  /* Align the main column's top with the rail so KPIs sit horizontally
     parallel to search + All/Clear. The rail's first child has margin-top:14px;
     mirror the same on the main column's first child. Strip kpi_row wrapper
     padding so KPI cards fill the height cleanly. */
  .st-key-two_pane > div:nth-child(2) > div:first-child {
    margin-top:14px !important;
  }
  .st-key-kpi_row {
    padding:0 !important;
    margin-bottom:14px !important;
  }
  .st-key-kpi_row > div > div {
    padding:0 !important;
  }

  /* ── Segment toggle checkboxes ── */
  /* Bold BLACK label — must win over all other rules */
  .st-key-sec_day   [data-testid="stCheckbox"] label p,
  .st-key-sec_week  [data-testid="stCheckbox"] label p,
  .st-key-sec_month [data-testid="stCheckbox"] label p {
    font-size:11px !important; font-weight:900 !important;
    color:#000000 !important; white-space:nowrap !important;
    display:inline !important; visibility:visible !important;
    opacity:1 !important;
  }
  /* Compact row — no extra vertical space */
  .st-key-sec_day   [data-testid="stCheckbox"],
  .st-key-sec_week  [data-testid="stCheckbox"],
  .st-key-sec_month [data-testid="stCheckbox"] {
    padding:1px 2px !important; margin:0 !important;
  }
  /* Circle shape base — colored per-segment via dynamic CSS injected at render time */
  .st-key-sec_day   [data-baseweb="checkbox"] > span:first-child,
  .st-key-sec_week  [data-baseweb="checkbox"] > span:first-child,
  .st-key-sec_month [data-baseweb="checkbox"] > span:first-child {
    border-radius:50% !important;
    width:13px !important; height:13px !important;
  }
  /* Un-checked label — clearly muted so you can see what's off */
  .st-key-sec_day   [data-testid="stCheckbox"]:not(:has(input:checked)) label p,
  .st-key-sec_week  [data-testid="stCheckbox"]:not(:has(input:checked)) label p,
  .st-key-sec_month [data-testid="stCheckbox"]:not(:has(input:checked)) label p {
    color:#9CA3AF !important; font-weight:500 !important;
    text-decoration:line-through !important;
  }

  /* ── Buttons ── */
  .stButton > button {
    background:#FFFFFF !important; color:#4F46E5 !important;
    border:1.5px solid #C7D2FE !important; border-radius:8px !important;
    font-weight:700 !important; font-size:11px !important;
    height:28px !important; min-height:28px !important;
    padding:0 12px !important; transition:all .15s ease !important;
    box-shadow:0 1px 3px rgba(79,70,229,0.10) !important;
  }
  .stButton > button:hover {
    background:#4F46E5 !important; color:#FFFFFF !important;
    border-color:#4F46E5 !important;
    box-shadow:0 4px 12px rgba(79,70,229,0.30) !important;
  }

  /* ── Search / multiselect ── */
  /* Outer BaseWeb wrapper — remove its own border so only the inner input shows one */
  [data-testid="stTextInput"] [data-baseweb="input"] {
    border:none !important; background:transparent !important;
    box-shadow:none !important;
  }
  [data-testid="stTextInput"] input,
  div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background:#FFFFFF !important; border:1.5px solid #C7D2FE !important;
    border-radius:9px !important; color:#1E1B4B !important;
    font-size:12px !important; box-shadow:none !important;
    min-height:32px !important;
  }
  div[data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within {
    border-color:#6366F1 !important; box-shadow:0 0 0 3px rgba(99,102,241,0.15) !important;
  }
  /* Chip tags */
  div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background:#EEF2FF !important; border:1px solid #C7D2FE !important;
    border-radius:6px !important; color:#4F46E5 !important;
    font-weight:600 !important;
  }

  /* ── Divider ── */
  hr { border-color:#E0E7FF !important; margin:5px 0 !important; }

  /* ── Scope badge ── */
  .scope-badge {
    display:inline-block; background:linear-gradient(135deg,#6366F1,#8B5CF6);
    border-radius:20px; padding:2px 12px; font-size:10.5px; font-weight:700;
    color:#FFFFFF; margin-top:4px;
    box-shadow:0 2px 8px rgba(99,102,241,0.35);
  }

  /* ── Rail multiselect styling ── */
  .st-key-two_pane > div:first-child div[data-testid="stMultiSelect"] {
    margin-bottom:6px !important;
  }
  .st-key-two_pane > div:first-child [data-testid="stWidgetLabel"] {
    font-size:11px !important; font-weight:700 !important;
    color:#4F46E5 !important; letter-spacing:0.3px !important;
  }
  .st-key-two_pane > div:first-child div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    min-height:34px !important; font-size:12px !important;
  }
  .st-key-two_pane > div:first-child div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background:#EEF2FF !important; border:1px solid #C7D2FE !important;
    border-radius:6px !important; color:#4F46E5 !important; font-weight:600 !important;
    font-size:11px !important; max-width:140px !important;
  }
  .st-key-two_pane > div:first-child div[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
    overflow:hidden !important; text-overflow:ellipsis !important; white-space:nowrap !important;
  }

  /* ── Mobile fallback: stack overview controls instead of forcing desktop width ── */
  @media (max-width: 768px) {
    .block-container { padding:8px 10px 18px !important; }
    .st-key-two_pane > div {
      flex-direction:column !important;
    }
    .st-key-two_pane > div > div {
      width:100% !important;
      flex:1 1 auto !important;
    }
    .st-key-two_pane > div:first-child > div:first-child,
    .st-key-two_pane > div:nth-child(2) > div:first-child {
      margin-top:8px !important;
    }
    .st-key-kpi_row [data-testid="stHorizontalBlock"] {
      flex-wrap:wrap !important;
    }
    .st-key-kpi_row [data-testid="stHorizontalBlock"] > div {
      min-width:46% !important;
      flex:1 1 46% !important;
    }
    .st-key-sec_day [data-testid="stHorizontalBlock"],
    .st-key-sec_week [data-testid="stHorizontalBlock"],
    .st-key-sec_month [data-testid="stHorizontalBlock"] {
      flex-wrap:wrap !important;
    }
    [data-testid="stPlotlyChart"] { overflow-x:auto !important; }
  }

  /* ── Pointer tables (Day / Week / Month) — pricing-table style ── */
  .pt-wrap {
    overflow:auto; max-height:302px;
    border-radius:18px; background:linear-gradient(180deg, #FFFFFF 0%, #FCFDFE 100%);
    border:1px solid #E2E8F0;
    box-shadow:0 10px 26px rgba(15,23,42,0.07);
    scroll-behavior:smooth;
  }
  .pt-wrap::-webkit-scrollbar { width:7px; height:7px; }
  .pt-wrap::-webkit-scrollbar-thumb { background:#CBD5E1; border-radius:4px; }
  .pt-wrap::-webkit-scrollbar-thumb:hover { background:#94A3B8; }
  .pt-wrap::-webkit-scrollbar-track { background:transparent; }
  table.pt-table {
    --pt-accent:#276749;
    --pt-accent-dark:#1F7A52;
    --pt-accent-soft:#F0FDF4;
    --pt-accent-hover:#ECFDF3;
    --pt-accent-divider:#BFE8D0;
    --pt-name-grad-1:#2C7A57;
    --pt-name-grad-2:#276749;
    border-collapse:separate; border-spacing:0; width:100%;
    font-family:'Inter',sans-serif; font-size:11px; color:#0F172A;
    background:#FFFFFF;
  }
  .pt-table.pt-day {
    --pt-accent:#6366F1;
    --pt-accent-dark:#4F46E5;
    --pt-accent-soft:#EEF2FF;
    --pt-accent-hover:#E0E7FF;
    --pt-accent-divider:#C7D2FE;
    --pt-name-grad-1:#6366F1;
    --pt-name-grad-2:#4F46E5;
  }
  .pt-table.pt-week {
    --pt-accent:#0891B2;
    --pt-accent-dark:#0E7490;
    --pt-accent-soft:#ECFEFF;
    --pt-accent-hover:#CFFAFE;
    --pt-accent-divider:#A5F3FC;
    --pt-name-grad-1:#0891B2;
    --pt-name-grad-2:#0E7490;
  }
  .pt-table.pt-month {
    --pt-accent:#7C3AED;
    --pt-accent-dark:#6D28D9;
    --pt-accent-soft:#F5F3FF;
    --pt-accent-hover:#EDE9FE;
    --pt-accent-divider:#C4B5FD;
    --pt-name-grad-1:#8B5CF6;
    --pt-name-grad-2:#6D28D9;
  }
  .pt-table th, .pt-table td {
    padding:5px 10px; text-align:center; white-space:nowrap; border:none;
  }
  .pt-table tbody td { border-bottom:1px solid #EAF2EF; }
  .pt-table thead th { position:sticky; top:0; z-index:3; }
  .pt-table th.pt-h2 {
    background:linear-gradient(180deg, var(--pt-accent-dark) 0%, var(--pt-accent) 100%); color:#FFFFFF;
    font-weight:800; font-size:10px; text-transform:uppercase;
    letter-spacing:0.6px; border-bottom:none;
    box-shadow:inset 0 -1px 0 rgba(255,255,255,0.12);
  }
  .pt-table th.pt-corner {
    background:linear-gradient(180deg, var(--pt-accent-dark) 0%, var(--pt-accent) 100%); color:#FFFFFF; text-align:left;
    font-size:10px; font-weight:800; text-transform:uppercase;
    letter-spacing:0.6px; z-index:5; border-bottom:none;
    box-shadow:inset 0 -1px 0 rgba(255,255,255,0.12);
  }
  .pt-table td.pt-name {
    text-align:left; font-weight:700; font-size:11px; color:#F8FAFC;
    background:linear-gradient(180deg, var(--pt-name-grad-1) 0%, var(--pt-name-grad-2) 100%);
    vertical-align:middle; min-width:160px; max-width:220px;
    overflow:hidden; text-overflow:ellipsis; padding:7px 12px;
    border-right:1px solid rgba(255,255,255,0.08);
  }
  .pt-idx {
    display:inline-flex; align-items:center; justify-content:center;
    width:20px; height:20px; border-radius:7px; margin-right:8px;
    font-size:9.5px; font-weight:800; color:#14532D; vertical-align:middle;
    background:rgba(255,255,255,0.82);
  }
  .pt-table td.pt-pointer {
    text-align:left; color:#334155; font-weight:600; font-size:10.5px;
    min-width:160px; padding:5px 12px; background:#F8FAFC;
    border-right:1px solid #E2E8F0;
  }
  .pt-table td.pt-val {
    font-variant-numeric:tabular-nums;
    background:#FCFEFD;
    color:#0F172A;
  }
  /* Uniform value-cell background for every store block (no per-store striping). */
  .pt-chip {
    display:inline-block; min-width:28px; padding:1px 8px;
    border-radius:999px; font-weight:800; font-size:10px; line-height:1.35;
    box-shadow:inset 0 0 0 1px rgba(255,255,255,0.45);
  }
  .pt-r-alloc          .pt-chip { background:#DBEAFE; color:#1D4ED8; }
  .pt-r-contacted      .pt-chip { background:#DCFCE7; color:#15803D; }
  .pt-r-not_contacted  .pt-chip { background:#FEE2E2; color:#B91C1C; }
  .pt-r-interested     .pt-chip { background:#EDE9FE; color:#6D28D9; }
  .pt-r-not_interested .pt-chip { background:#FAE8FF; color:#A21CAF; }
  .pt-r-rnr            .pt-chip { background:#FEF3C7; color:#B45309; }
  .pt-table tbody tr:hover td.pt-val { background:var(--pt-accent-hover); }
  .pt-table tbody tr:hover td.pt-pointer { background:#F1F5F9; }
  .pt-table tbody tr:hover .pt-chip { transform:translateY(-1px); }
  .pt-table tbody tr.pt-first td { border-top:2px solid var(--pt-accent-divider); }
  .pt-table tbody tr.pt-first:first-child td { border-top:none; }

  /* ── Keep Day/Week/Month section wrappers, but hide their border visually ── */
  .st-key-pt_section_day,
  .st-key-pt_section_week,
  .st-key-pt_section_month {
    border-color:transparent !important;
    background:transparent !important;
    box-shadow:none !important;
  }
</style>
"""


# ── Data loader ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_df(db_path: str, allowed_codes_key: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Load dashboard lead columns once, scoped in SQL when user access is restricted."""
    sql = (
        "SELECT ifb_point, status, final_status, interested, follow_up, lead_date "
        "FROM api_leads"
    )
    params: list[str] = []
    if allowed_codes_key:
        placeholders = ",".join("?" for _ in allowed_codes_key)
        sql += f" WHERE ifb_point IN ({placeholders})"
        params.extend(allowed_codes_key)
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


# ── KPI card ───────────────────────────────────────────────────────────────────

def _kpi_card(col, label: str, value: int, pct: float | None = None,
              today_val: int | None = None, today_pct: float | None = None,
              sub_label: str = "Today", all_label: str = "All") -> None:
    color, _, icon = _KPI_STYLE.get(label, ("#6366F1", "#EEF2FF", "•"))
    pct_html = (
        f"<span style='font-size:10px;font-weight:700;color:{color};"
        f"margin-left:6px;opacity:0.9;'>{pct:.1f}%</span>"
        if pct is not None else ""
    )
    tint = _KPI_STYLE.get(label, ("#6366F1", "#EEF2FF", "•"))[1]
    if today_val is not None:
        today_pct_html = (
            f"<span style='font-size:9px;font-weight:700;color:{color};"
            f"margin-left:3px;opacity:0.9;'>{today_pct:.1f}%</span>"
            if today_pct is not None else ""
        )
        val_html = (
            f"<div style='display:grid;grid-template-columns:1fr auto 1fr;align-items:baseline;'>"
            f"<span style='font-size:22px;font-weight:800;color:#0F172A;line-height:1;text-align:center;'>{value:,}{pct_html}</span>"
            f"<span style='font-size:16px;font-weight:300;color:#CBD5E1;line-height:1;padding:0 6px;'>|</span>"
            f"<span style='font-size:18px;font-weight:800;color:{color};line-height:1;text-align:center;'>{today_val:,}{today_pct_html}</span>"
            f"</div>"
            f"<div style='display:grid;grid-template-columns:1fr auto 1fr;margin-top:1px;'>"
            f"<span style='font-size:7px;font-weight:700;color:#64748B;text-transform:uppercase;text-align:center;'>{all_label}</span>"
            f"<span style='font-size:7px;font-weight:700;color:#CBD5E1;padding:0 6px;'>|</span>"
            f"<span style='font-size:7px;font-weight:700;color:{color};text-transform:uppercase;text-align:center;'>{sub_label}</span>"
            f"</div>"
        )
    else:
        val_html = (
            f"<div style='display:flex;align-items:baseline;justify-content:center;'>"
            f"<span style='font-size:22px;font-weight:800;color:#0F172A;line-height:1;'>{value:,}</span>"
            f"{pct_html}</div>"
        )
    _align = "text-align:center;" if today_val is None else ""
    col.markdown(
        f"<div style='background:{tint};border:1px solid {color}30;"
        f"border-left:4px solid {color};border-radius:12px;"
        f"padding:9px 12px;height:76px;display:flex;flex-direction:column;"
        f"justify-content:space-between;{_align}"
        f"box-shadow:0 2px 10px {color}18;'>"
        f"<div style='display:flex;align-items:center;justify-content:center;gap:6px;'>"
        f"<span style='font-size:8.5px;font-weight:800;color:{color};text-transform:uppercase;"
        f"letter-spacing:0.6px;'>{label}</span>"
        f"<span style='font-size:13px;'>{icon}</span></div>"
        f"{val_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Time-bucket aggregation ────────────────────────────────────────────────────

def _bucket_aggregate(df: pd.DataFrame, freq: str, n_buckets: int = 7) -> pd.DataFrame:
    today_ts = pd.Timestamp(date.today())
    if freq == "D":
        idx    = pd.date_range(today_ts - pd.Timedelta(days=n_buckets - 1), today_ts, freq="D")
        labels = [d.strftime("%d %b") for d in idx]
        keys   = df["lead_dt"].dt.normalize() if not df.empty else idx
    elif freq == "W":
        ws  = today_ts - pd.Timedelta(days=today_ts.weekday())
        idx = pd.date_range(ws - pd.Timedelta(weeks=n_buckets - 1), ws, freq="W-MON")
        labels = [f"{d.strftime('%d')}-{(d + pd.Timedelta(days=6)).strftime('%d %b')}" for d in idx]
        keys   = ((df["lead_dt"] - pd.to_timedelta(df["lead_dt"].dt.weekday, unit="D"))
                  .dt.normalize() if not df.empty else idx)
    else:  # "M"
        ms  = today_ts.replace(day=1)
        idx = pd.date_range(ms - pd.DateOffset(months=n_buckets - 1), ms, freq="MS")
        labels = [d.strftime("%b %Y") for d in idx]
        keys   = (df["lead_dt"].dt.to_period("M").dt.to_timestamp()
                  if not df.empty else idx)

    out = pd.DataFrame({"bucket": idx, "label": labels})
    if df.empty:
        for s in _BAR_SERIES:
            out[s] = 0
        return out

    tmp = df.copy()
    tmp["_bk"] = keys
    counts = pd.DataFrame({
        "Total Customers Allocated": tmp.groupby("_bk").size(),
        "Calls Attempted":           tmp["status"].isin(["Contacted", "RnR", "Not Reachable"]).groupby(tmp["_bk"]).sum(),
        "Not Contacted": (tmp["status"] == "Not Contacted").groupby(tmp["_bk"]).sum(),
        "RnR":           (tmp["status"] == "RnR").groupby(tmp["_bk"]).sum(),
    }).reset_index().rename(columns={"_bk": "bucket"})

    out = out.merge(counts, on="bucket", how="left").fillna(0)
    for s in _BAR_SERIES:
        out[s] = out[s].astype(int)
    return out


# ── Clustered bar chart ────────────────────────────────────────────────────────

def _clustered_bar(agg: pd.DataFrame, height: int = 158) -> go.Figure:
    fig = go.Figure()
    for name, color in _BAR_SERIES.items():
        fig.add_trace(go.Bar(
            name=name, x=agg["label"], y=agg[name],
            marker_color=color,
            hovertemplate=f"{name}: %{{y}}<extra></extra>",
        ))
    fig.update_layout(
        barmode="group", height=height,
        margin=dict(l=8, r=8, t=28, b=4),
        plot_bgcolor="#FFFFFF", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickfont=dict(size=9, color="#475569"), type="category",
                   gridcolor="#F1F5F9", linecolor="#E2E8F0"),
        yaxis=dict(tickfont=dict(size=9, color="#475569"), gridcolor="#F1F5F9",
                   linecolor="#E2E8F0"),
        font=dict(size=9, color="#475569"),
        legend=dict(orientation="h", yanchor="top", y=1.1,
                    xanchor="center", x=0.5, font=dict(size=8.5, color="#475569"),
                    bgcolor="rgba(255,255,255,0)"),
        bargap=0.20, bargroupgap=0.03,
    )
    return fig


# ── Marimekko / Mosaic chart ───────────────────────────────────────────────────

# Must match _BUCKET_TO_STAGE values in streamlit_app.py exactly
_STAGE_ORDER = ["Post-Purchase", "1st 30 days call", "Pre-AMC", "8 Year Upgrade"]
_STAGE_SHORT = {  # shorter labels for the x-axis ticks
    "Post-Purchase":    "Post-Purchase",
    "1st 30 days call": "1st 30 Days",
    "Pre-AMC":          "Pre-AMC",
    "8 Year Upgrade":   "8 Yr Upgrade",
}

# Mutually-exclusive outcome segments (sum to each stage's total).
# Contacted is split into its interest sub-outcomes so all 7 metrics show.
_MK_SEGMENTS = [
    ("Interested",      "#16A34A"),   # contacted & interested  (the win path)
    ("Not Interested",  "#9333EA"),   # contacted & not interested
    ("Contacted",       "#86EFAC"),   # contacted, interest not logged yet
    ("Not Contacted",   "#DC2626"),
    ("Not Reachable",   "#F97316"),
    ("RnR",             "#D97706"),
    ("Untouched",       "#CBD5E1"),   # status = Pending
]


def _segments(sdf: pd.DataFrame) -> dict:
    """Mutually-exclusive segment counts for any subset of rows."""
    st_ = sdf["status"]
    it_ = sdf["interest"]
    contacted_mask = st_ == "Contacted"
    return {
        "Interested":     int((contacted_mask & (it_ == "Interested")).sum()),
        "Not Interested": int((contacted_mask & (it_ == "Not Interested")).sum()),
        "Contacted":      int((contacted_mask & (~it_.isin(["Interested", "Not Interested"]))).sum()),
        "Not Contacted":  int((st_ == "Not Contacted").sum()),
        "Not Reachable":  int((st_ == "Not Reachable").sum()),
        "RnR":            int((st_ == "RnR").sum()),
        "Untouched":      int((st_ == "Pending").sum()),
    }


def _time_buckets(df: pd.DataFrame, period: str, n: int) -> list[tuple]:
    """
    Split df into the last `n` time periods (oldest → today), in order.
    Returns a list of (label, total, segment_breakdown) per period.
    """
    today_ts = pd.Timestamp(date.today())
    if period == "day":
        idx    = pd.date_range(today_ts.normalize() - pd.Timedelta(days=n - 1),
                               today_ts.normalize(), freq="D")
        labels = [d.strftime("%d %b") for d in idx]
        keys   = df["lead_dt"].dt.normalize() if not df.empty else None
    elif period == "week":
        ws     = today_ts.normalize() - pd.Timedelta(days=today_ts.weekday())
        idx    = pd.date_range(ws - pd.Timedelta(weeks=n - 1), ws, freq="W-MON")
        labels = [f"{d.strftime('%d')}-{(d + pd.Timedelta(days=6)).strftime('%d %b')}" for d in idx]
        keys   = ((df["lead_dt"] - pd.to_timedelta(df["lead_dt"].dt.weekday, unit="D"))
                  .dt.normalize() if not df.empty else None)
    else:  # month
        ms     = today_ts.normalize().replace(day=1)
        idx    = pd.date_range(ms - pd.DateOffset(months=n - 1), ms, freq="MS")
        labels = [d.strftime("%b %y") for d in idx]
        keys   = df["lead_dt"].dt.to_period("M").dt.to_timestamp() if not df.empty else None

    buckets = []
    for i, b in enumerate(idx):
        sub = df[keys == b] if keys is not None else df.iloc[0:0]
        buckets.append((labels[i], len(sub), _segments(sub)))
    return buckets


# ── Pointer tabular view (Day / Week / Month) ─────────────────────────────────

def _period_labels_keys(period: str, n: int) -> list[tuple[pd.Timestamp, str]]:
    """Return ordered list of (bucket_key_ts, display_label) for the period.

    Day → chronological (oldest → newest, left→right).
    Week / Month → reverse chronological (newest → oldest, left→right).
    """
    today_ts = pd.Timestamp(date.today())
    if period == "day":
        idx    = pd.date_range(today_ts.normalize() - pd.Timedelta(days=n - 1),
                               today_ts.normalize(), freq="D")
        labels = [d.strftime("%d-%b") for d in idx]
        return list(zip(idx, labels))
    if period == "week":
        ws  = today_ts.normalize() - pd.Timedelta(days=today_ts.weekday())
        idx = pd.date_range(ws - pd.Timedelta(weeks=n - 1), ws, freq="W-MON")
        labels = [f"{d.strftime('%d')}-{(d + pd.Timedelta(days=6)).strftime('%d %b')}"
                  for d in idx]
        pairs = list(zip(idx, labels))
        pairs.reverse()
        return pairs
    # month
    ms  = today_ts.normalize().replace(day=1)
    idx = pd.date_range(ms - pd.DateOffset(months=n - 1), ms, freq="MS")
    labels = [d.strftime("%b-%y") for d in idx]
    pairs = list(zip(idx, labels))
    pairs.reverse()
    return pairs


def _bucket_keys_for(df: pd.DataFrame, period: str) -> pd.Series | None:
    """Compute per-row bucket-key timestamp so rows can be grouped by period."""
    if df.empty or "lead_dt" not in df.columns:
        return None
    dt = df["lead_dt"]
    if period == "day":
        return dt.dt.normalize()
    if period == "week":
        return (dt - pd.to_timedelta(dt.dt.weekday, unit="D")).dt.normalize()
    # month
    return dt.dt.to_period("M").dt.to_timestamp()


# (pointer_label, internal column key) — order matches the Excel reference
_POINTER_FIELDS = [
    ("Customers Allocated",    "alloc"),
    ("Contacted",              "contacted"),
    ("Not Contacted",          "not_contacted"),
    ("Interested",             "interested"),
    ("Not Interested",         "not_interested"),
    ("RnR (Ring No Response)", "rnr"),
]


def _pointer_table_html(
    scope_df: pd.DataFrame,
    scope_codes: set[str] | list[str],
    channel_names: dict[str, str],
    period: str,
    n: int,
    force_all: bool = False,
    limit: int | None = None,
) -> tuple[str, int, int]:
    """Build the IFB Point × 6 pointers × N periods table.

    Returns (html, stores_shown, stores_total). HTML is emitted as a single
    line — any newline + indentation would be re-parsed by Streamlit's
    markdown as a literal code block.
    By default only stores with ≥1 follow up inside the window are listed;
    force_all=True (explicit point selection) lists every scoped store.
    limit caps the number of stores rendered (busiest first) to keep the DOM
    light; None renders all.
    """
    col_pairs = _period_labels_keys(period, n)
    col_keys  = [k for k, _ in col_pairs]
    col_lbls  = [lbl for _, lbl in col_pairs]

    # Vectorized counts: one groupby over the whole scope instead of one
    # _segments()-style pass per (store, bucket) slice.
    lookup: dict[tuple, pd.Series] = {}
    window_totals: dict = {}
    bucket_keys = _bucket_keys_for(scope_df, period)
    if bucket_keys is not None:
        st_ = scope_df["status"]
        it_ = scope_df["interest"]
        tmp = pd.DataFrame({
            "code":           scope_df["ifb_point"].values,
            "bk":             bucket_keys.values,
            "alloc":          1,
            "contacted":      (st_ == "Contacted").astype(int).values,
            "not_contacted":  (~st_.isin(["Contacted", "RnR", "Not Reachable"])).astype(int).values,
            "interested":     (it_ == "Interested").astype(int).values,
            "not_interested": (it_ == "Not Interested").astype(int).values,
            "rnr":            (st_ == "RnR").astype(int).values,
        })
        tmp = tmp[tmp["bk"].isin(col_keys)]
        if not tmp.empty:
            grouped = tmp.groupby(["code", "bk"]).sum(numeric_only=True)
            for key, row in grouped.iterrows():
                lookup[key] = row
                window_totals[key[0]] = window_totals.get(key[0], 0) + int(row["alloc"])

    codes = sorted(
        set(scope_codes),
        key=lambda c: (channel_names.get(c, str(c)).lower(), str(c)),
    )
    if not force_all:
        codes = [c for c in codes if c in window_totals]
    total_stores = len(codes)
    if limit is not None and total_stores > limit:
        # Busiest stores first when truncating, so the visible slice matters
        codes = sorted(
            codes,
            key=lambda c: (-window_totals.get(c, 0),
                           channel_names.get(c, str(c)).lower(), str(c)),
        )[:limit]
    if not codes:
        return (
            "<div style='padding:16px;color:#94A3B8;font-style:italic;font-size:12px;"
            "background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;'>"
            "No follow ups in this window.</div>",
            0, 0,
        )

    ncols = len(col_lbls)

    parts: list[str] = [f"<div class='pt-wrap'><table class='pt-table pt-{period}'><thead>"]
    parts.append(
        "<tr>"
        "<th class='pt-corner'>IFB Point</th>"
        "<th class='pt-corner'>Pointers</th>"
        + "".join(f"<th class='pt-h2'>{lbl}</th>" for lbl in col_lbls) +
        "</tr>"
    )
    parts.append("</thead><tbody>")

    for idx_c, code in enumerate(codes, start=1):
        name = channel_names.get(code, str(code))
        for row_i, (pointer, field) in enumerate(_POINTER_FIELDS):
            cells: list[str] = []
            if row_i == 0:
                cells.append(
                    f"<td class='pt-name' rowspan='6' title='{name} ({code})'>"
                    f"<span class='pt-idx'>{idx_c}</span>{name}</td>"
                )
            cells.append(f"<td class='pt-pointer'>{pointer}</td>")
            for bk in col_keys:
                row = lookup.get((code, bk))
                val = int(row[field]) if row is not None else 0
                cell = f"<span class='pt-chip'>{val}</span>" if val else ""
                cells.append(f"<td class='pt-val'>{cell}</td>")
            row_cls = f" class='pt-r-{field}{' pt-first' if row_i == 0 else ''}'"
            parts.append(f"<tr{row_cls}>" + "".join(cells) + "</tr>")

    parts.append("</tbody></table></div>")
    return "".join(parts), len(codes), total_stores


def _marimekko(buckets: list[tuple], height: int = 158,
               visible_segs: set | None = None) -> go.Figure:
    """
    Time-based Marimekko: one column per time period (oldest → today),
    column WIDTH ∝ that period's lead volume, HEIGHT = status/interest mix.
    Empty periods keep a thin minimum width so they stay visible in order.
    """
    labels    = [b[0] for b in buckets]
    totals    = [b[1] for b in buckets]
    breakdown = [b[2] for b in buckets]
    grand     = sum(totals)

    fig = go.Figure()
    if grand == 0:
        fig.update_layout(
            height=height, margin=dict(l=8, r=8, t=8, b=8),
            plot_bgcolor="#FFFFFF", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            annotations=[dict(text="No follow ups in this window", showarrow=False,
                              font=dict(size=12, color="#94A3B8"), x=0.5, y=0.5,
                              xref="paper", yref="paper")],
        )
        return fig

    # Equal-width columns (categorical x) so every period is evenly spaced
    # and all 7 / 4 / 6 fit cleanly, regardless of volume.
    x_labels = [f"{lbl}<br><b>{t:,}</b>" for lbl, t in zip(labels, totals)]

    # Only draw segments that are checked; default = all visible
    active = visible_segs if visible_segs is not None else {s for s, _ in _MK_SEGMENTS}

    # Build the full column tooltip once per column — same content for every segment trace,
    # so hovering ANY bar in a column always shows the complete breakdown with circles.
    col_customs = []
    for i, t in enumerate(totals):
        b = breakdown[i]
        # Aggregate to 3 KPI lines — Untouched absorbed into Not Contacted
        contacted_sum = b["Interested"] + b["Not Interested"] + b["Contacted"]
        not_cont_sum  = b["Not Contacted"] + b["Untouched"]
        not_reach_sum = b["Not Reachable"]
        rnr_sum       = b["RnR"]

        def _pct(n): return f"{n/t*100:.1f}%" if t else "0%"

        kpi_rows = (
            f"<span style='color:#86EFAC;'>⬤</span>"
            f" <b style='color:#F1F5F9;'>Contacted</b>"
            f"<span style='color:#94A3B8;'>  {contacted_sum:,}  ({_pct(contacted_sum)})</span><br>"
            f"<span style='color:#16A34A;'>⬤</span>"
            f" <b style='color:#F1F5F9;'>Interested</b>"
            f"<span style='color:#94A3B8;'>  {b['Interested']:,}  ({_pct(b['Interested'])})</span><br>"
            f"<span style='color:#9333EA;'>⬤</span>"
            f" <b style='color:#F1F5F9;'>Not Interested</b>"
            f"<span style='color:#94A3B8;'>  {b['Not Interested']:,}  ({_pct(b['Not Interested'])})</span><br>"
            f"<span style='color:#DC2626;'>⬤</span>"
            f" <b style='color:#F1F5F9;'>Not Contacted</b>"
            f"<span style='color:#94A3B8;'>  {not_cont_sum:,}  ({_pct(not_cont_sum)})</span><br>"
            f"<span style='color:#F97316;'>⬤</span>"
            f" <b style='color:#F1F5F9;'>Not Reachable</b>"
            f"<span style='color:#94A3B8;'>  {not_reach_sum:,}  ({_pct(not_reach_sum)})</span><br>"
            f"<span style='color:#D97706;'>⬤</span>"
            f" <b style='color:#F1F5F9;'>RnR</b>"
            f"<span style='color:#94A3B8;'>  {rnr_sum:,}  ({_pct(rnr_sum)})</span><br>"
        )
        col_customs.append([labels[i].replace("<br>", " "), t, kpi_rows])

    for seg, color in _MK_SEGMENTS:
        if seg not in active:
            continue
        ys = [(breakdown[i][seg] / totals[i] * 100) if totals[i] else 0
              for i in range(len(totals))]
        fig.add_trace(go.Bar(
            name=seg, x=x_labels, y=ys,
            marker_color=color, marker_line=dict(color="#FFFFFF", width=1),
            customdata=col_customs,
            hovertemplate=(
                "<b style='color:#E2E8F0;font-size:12px;'>%{customdata[0]}</b>"
                "<span style='color:#64748B;'>  ·  %{customdata[1]:,} follow ups</span>"
                "<br><br>"
                "%{customdata[2]}"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        barmode="stack", height=height, bargap=0.18,
        margin=dict(l=8, r=8, t=26, b=22),
        plot_bgcolor="#FFFFFF", paper_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
        hoverdistance=50,
        hoverlabel=dict(
            bgcolor="#1E293B",
            bordercolor="#4F46E5",
            namelength=0,
            font=dict(size=11, color="#F1F5F9", family="Inter, sans-serif"),
        ),
        xaxis=dict(
            type="category", tickfont=dict(size=8, color="#475569"),
            showgrid=False, zeroline=False,
            showspikes=False,
        ),
        yaxis=dict(
            range=[0, 100], ticksuffix="%",
            tickfont=dict(size=8.5, color="#94A3B8"),
            gridcolor="#F1F5F9", zeroline=False,
        ),
        font=dict(size=9, color="#475569"),
        showlegend=False,
    )
    return fig


# ── Storytelling insights ──────────────────────────────────────────────────────

def _b(text: str, color: str = "#0F172A") -> str:
    """Inline bold with optional colour."""
    return f"<b style='color:{color};'>{text}</b>"


def _insights(buckets: list[tuple], period: str, scope_df=None) -> str:
    """
    Written narrative insights derived from bucket data.
    Tells the story: total, current vs avg, peak, low, dominant outcome, untouched, RnR.
    buckets = list of (label, total, {seg: count}) from _time_buckets().
    scope_df: optional DataFrame for per-IFB-point today breakdown.
    """
    _CUR_NOUN = {"day": "Today",     "week": "This week",  "month": "This month"}
    _UNIT     = {"day": "day",       "week": "week",       "month": "month"}

    grand_total = sum(b[1] for b in buckets)
    if grand_total == 0:
        return (
            "<div style='font-size:11px;color:#94A3B8;font-style:italic;"
            "padding-top:8px;'>No data for this period.</div>"
        )

    totals = [b[1] for b in buckets]
    labels = [b[0] for b in buckets]

    cur_lbl, cur_total, cur_segs = buckets[-1]
    prior   = totals[:-1]
    # Only include non-zero prior periods in avg so empty slots don't drag it down
    prior_nonzero = [v for v in prior if v > 0]
    avg_val = sum(prior_nonzero) / len(prior_nonzero) if prior_nonzero else 0.0

    # Peak and low among non-zero buckets only (zero = no data, not a real low)
    nonzero_buckets = [(i, labels[i], totals[i]) for i in range(len(totals)) if totals[i] > 0]
    if nonzero_buckets:
        peak_i, peak_lbl, peak_val = max(nonzero_buckets, key=lambda x: x[2])
        low_i,  low_lbl,  low_val  = min(nonzero_buckets, key=lambda x: x[2])
    else:
        peak_i = low_i = len(buckets) - 1
        peak_lbl = low_lbl = cur_lbl
        peak_val = low_val = cur_total

    # Aggregate segments across all buckets
    seg_totals: dict[str, int] = {s: 0 for s, _ in _MK_SEGMENTS}
    for _, _, segs in buckets:
        for s in seg_totals:
            seg_totals[s] += segs.get(s, 0)

    _SEG_CLR = {s: c for s, c in _MK_SEGMENTS}

    # Dominant outcome: highest-count segment excluding Untouched, must be > 0
    outcome_segs = {s: v for s, v in seg_totals.items() if s != "Untouched" and v > 0}
    dominant_seg = max(outcome_segs, key=lambda s: outcome_segs[s]) if outcome_segs else None
    dom_pct = (seg_totals[dominant_seg] / grand_total * 100) if dominant_seg else 0

    untouched_pct  = seg_totals["Untouched"]  / grand_total * 100 if grand_total else 0
    interested_pct = seg_totals["Interested"] / grand_total * 100 if grand_total else 0
    not_cont_pct   = seg_totals["Not Contacted"] / grand_total * 100 if grand_total else 0
    rnr_count      = seg_totals["RnR"]
    unit           = _UNIT.get(period, "period")
    cur_noun       = _CUR_NOUN.get(period, "Current")

    def hi(txt: str, color: str) -> str:
        return f"<span style='font-weight:700;color:{color};'>{txt}</span>"

    def lead_word(n: int) -> str:
        return "follow up" if n == 1 else "follow ups"

    sentences = []

    # 0. Total across the full window
    window_desc = {"day": "last 7 days", "week": "last 4 weeks", "month": "last 6 months"}
    sentences.append(
        f"{hi(f'{grand_total:,}', '#4F46E5')} follow ups across the "
        f"{window_desc.get(period, 'window')}."
    )

    # 1. Current period vs average (skip if today has 0 and avg > 0 — data not in yet)
    if cur_total == 0 and avg_val > 0:
        sentences.append(
            f"{hi(cur_noun, '#4F46E5')} has no follow ups yet "
            f"(avg is {hi(f'{avg_val:.0f}', '#475569')} per {unit})."
        )
    elif avg_val > 0:
        delta_pct = (cur_total - avg_val) / avg_val * 100
        if delta_pct >= 15:
            sentences.append(
                f"{hi(cur_noun, '#4F46E5')}: {hi(f'{cur_total:,}', '#16A34A')} follow ups — "
                f"{hi(f'+{delta_pct:.0f}%', '#16A34A')} above the avg of "
                f"{hi(f'{avg_val:.0f}', '#475569')}."
            )
        elif delta_pct <= -15:
            sentences.append(
                f"{hi(cur_noun, '#4F46E5')}: {hi(f'{cur_total:,}', '#DC2626')} follow ups — "
                f"{hi(f'{abs(delta_pct):.0f}%', '#DC2626')} below the avg of "
                f"{hi(f'{avg_val:.0f}', '#475569')}."
            )
        else:
            sentences.append(
                f"{hi(cur_noun, '#4F46E5')}: {hi(f'{cur_total:,}', '#475569')} follow ups — "
                f"on par with avg of {hi(f'{avg_val:.0f}', '#475569')}."
            )
    else:
        sentences.append(
            f"{hi(cur_noun, '#4F46E5')}: {hi(f'{cur_total:,}', '#4F46E5')} follow ups."
        )

    # 2. Peak and low (only when they differ and both are > 0)
    if peak_val > 0 and peak_i != low_i:
        if peak_i == len(buckets) - 1:
            sentences.append(
                f"Highest {unit} in the window with {hi(f'{peak_val:,}', '#16A34A')} follow ups; "
                f"lowest prior was {hi(low_lbl, '#0F172A')} ({hi(f'{low_val:,}', '#DC2626')})."
            )
        elif low_i == len(buckets) - 1:
            sentences.append(
                f"Lowest {unit} in the window; "
                f"peak was {hi(peak_lbl, '#16A34A')} at {hi(f'{peak_val:,}', '#16A34A')} follow ups."
            )
        else:
            sentences.append(
                f"Peak: {hi(peak_lbl, '#16A34A')} ({hi(f'{peak_val:,}', '#16A34A')} follow ups) · "
                f"Low: {hi(low_lbl, '#DC2626')} ({hi(f'{low_val:,}', '#DC2626')})."
            )

    # 3. Dominant actioned outcome
    if dominant_seg:
        sentences.append(
            f"{hi(dominant_seg, _SEG_CLR[dominant_seg])} is the leading outcome "
            f"at {hi(f'{dom_pct:.0f}%', _SEG_CLR[dominant_seg])} of total."
        )

    # 4. Not Contacted — if significant
    if not_cont_pct >= 20:
        sentences.append(
            f"{hi(f'{not_cont_pct:.0f}%', '#DC2626')} were "
            f"{hi('not contacted', '#DC2626')} — needs follow-up."
        )

    # 5. Untouched — contextual wording based on actual percentage
    if untouched_pct > 0:
        if untouched_pct >= 80:
            severity = "nearly all follow ups are sitting untouched"
        elif untouched_pct >= 50:
            severity = "more than half the follow ups are untouched"
        elif untouched_pct >= 30:
            severity = "over a third of follow ups are untouched"
        else:
            severity = f"{untouched_pct:.0f}% of follow ups remain untouched"
        sentences.append(
            f"{hi(f'{untouched_pct:.0f}%', '#94A3B8')} untouched — {severity}."
        )

    # 6. Interested rate — positive signal
    if interested_pct >= 10:
        sentences.append(
            f"{hi(f'{interested_pct:.0f}%', '#16A34A')} showed "
            f"{hi('interest', '#16A34A')} — a strong conversion signal."
        )

    # 7. RnR — grammar-correct
    if rnr_count > 0:
        sentences.append(
            f"{hi(f'{rnr_count:,}', '#D97706')} {lead_word(rnr_count)} pending "
            f"{hi('callback', '#D97706')} (RnR)."
        )

    # 8. Per-IFB-Point action summary for the current period
    if scope_df is not None and "lead_dt" in scope_df.columns:
        _today_d  = date.today()
        _today_ts = pd.Timestamp(_today_d)
        _period_noun = {"day": "today", "week": "this week", "month": "this month"}
        _pn = _period_noun.get(period, "this period")

        if period == "day":
            _pf = scope_df[scope_df["lead_dt"].dt.normalize() == _today_ts.normalize()]
        elif period == "week":
            _ws = _today_ts.normalize() - pd.Timedelta(days=_today_ts.weekday())
            _pf = scope_df[(scope_df["lead_dt"] >= _ws) & (scope_df["lead_dt"] < _ws + pd.Timedelta(days=7))]
        else:
            _ms = _today_ts.normalize().replace(day=1)
            _me = (_ms + pd.DateOffset(months=1))
            _pf = scope_df[(scope_df["lead_dt"] >= _ms) & (scope_df["lead_dt"] < _me)]

        _all_pts = len(scope_df["ifb_point"].unique()) if not scope_df.empty else 0
        if not _pf.empty:
            _live_pts = set(_pf[_pf["status"].isin(["Contacted", "RnR", "Not Reachable"])]["ifb_point"].unique())
            _n_live   = len(_live_pts)
            _n_no_act = _all_pts - _n_live
            _no_act_pct = round(_n_no_act / _all_pts * 100) if _all_pts else 0
            sentences.append(
                f"Out of total {hi(f'{_all_pts}', '#334155')} IFB Points, "
                f"{hi(f'{_n_no_act}', '#DC2626')} "
                f"({hi(f'{_no_act_pct}%', '#DC2626')}) IFB Points have taken no action {_pn}."
            )
        elif _all_pts:
            sentences.append(
                f"Out of total {hi(f'{_all_pts}', '#334155')} IFB Points, "
                f"{hi(f'{_all_pts}', '#DC2626')} "
                f"({hi('100%', '#DC2626')}) IFB Points have taken no action {_pn}."
            )

    # ── Render ────────────────────────────────────────────────────────────────
    items_html = "".join(
        f"<div style='padding:3px 0 3px 8px;border-left:2px solid #E2E8F0;"
        f"margin-bottom:4px;font-size:10px;color:#334155;line-height:1.45;'>"
        f"{s}</div>"
        for s in sentences
    )

    return f"<div style='font-size:10px;line-height:1.5;'>{items_html}</div>"


# ── Main render function ───────────────────────────────────────────────────────

def _load_hierarchy(
    mapping_db: str,
    email: str,
    allowed_codes: set[str] | None,
    valid_codes: set[str] | None = None,
) -> dict:
    """Load Region → Branch → IFB Point hierarchy for the logged-in user.

    If allowed_codes is empty/None (admin), loads ALL mappings.
    Otherwise restricts to the user's email rows + allowed codes.
    valid_codes (master list) drops any code no longer in IFB_Point_Master.txt.
    """
    result: dict[str, dict[str, list[str]]] = {}
    try:
        with sqlite3.connect(mapping_db) as conn:
            if not allowed_codes:
                rows = conn.execute(
                    'SELECT Region, Branch, IFBpoint_id FROM login_mapping',
                ).fetchall()
            else:
                _e = email.strip().lower()
                rows = []
                for _col in ('"Regional Email_ID"', '"Retail Email_ID"', "Email_ID"):
                    rows = conn.execute(
                        f'SELECT Region, Branch, IFBpoint_id FROM login_mapping '
                        f'WHERE LOWER({_col})=?',
                        (_e,),
                    ).fetchall()
                    if rows:
                        break
            for region, branch, code in rows:
                if not region or not branch or not code:
                    continue
                if allowed_codes and code not in allowed_codes:
                    continue
                if valid_codes and code not in valid_codes:
                    continue
                result.setdefault(region, {}).setdefault(branch, [])
                if code not in result[region][branch]:
                    result[region][branch].append(code)
    except Exception:
        pass
    return result


# ── RM Mapping (editable) ─────────────────────────────────────────────────────
# Column label (shown in the editor)  →  login_mapping.db column name.
# "IFB Point Name" is handled separately (persisted to IFB_Point_Master.txt).
_RM_COL_TO_DB = {
    "Branch":                   "Branch",
    "Region":                   "Region",
    "Cluster Manager Name":     "Name",
    "Cluster Manager Email ID": "Email_ID",
    "Retail Name":              "Retail Name",
    "Retail Email ID":          "Retail Email_ID",
    "Regional Manager Name":     "Regional Name",
    "Regional Manager Email ID": "Regional Email_ID",
}
_RM_DISPLAY_COLS = [
    "IFB Point ID", "IFB Point Name", "Branch", "Region",
    "Cluster Manager Name", "Cluster Manager Email ID",
    "Retail Name", "Retail Email ID",
    "Regional Manager Name", "Regional Manager Email ID",
]


def _read_master_names(master_file: str | Path) -> dict[str, str]:
    """Return {code: name} read raw from IFB_Point_Master.txt.
    Splits each line on the first run of whitespace, so it accepts both the
    tab-separated format (code\\tname) and the space-separated format the
    external sync currently produces (code name)."""
    names: dict[str, str] = {}
    p = Path(master_file)
    if not p.exists():
        return names
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        code = parts[0].strip()
        if code:
            names[code] = parts[1].strip() if len(parts) > 1 else ""
    return names


def _write_master_names(master_file: str | Path, updates: dict[str, str]) -> None:
    """Update names for the given codes in IFB_Point_Master.txt, preserving order.
    Appends a new `code\\tname` line for any code not already present."""
    p = Path(master_file)
    existing = p.read_text(encoding="utf-8", errors="replace").split("\n") if p.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in existing:
        raw = line.rstrip("\r")
        parts = raw.split(None, 1)
        code = parts[0].strip() if parts else ""
        if code and code in updates:
            out.append(f"{code}\t{updates[code]}")
            seen.add(code)
            continue
        out.append(raw)
    for code, name in updates.items():
        if code not in seen:
            out.append(f"{code}\t{name}")
    p.write_text("\n".join(out), encoding="utf-8")


def _load_rm_rows(mapping_db: str | Path, master_names: dict[str, str],
                  allowed_codes: set[str] | None,
                  channel_names: dict[str, str] | None = None) -> pd.DataFrame:
    """Build the RM-mapping table — one row per IFB Point ID **from
    IFB_Point_Master.txt** (the authoritative point list), left-joined with
    login_mapping.db for Region/Branch/Cluster/Retail fields. Row count therefore
    always matches the master file: delete/add a line there and RM Mapping follows."""
    with sqlite3.connect(str(mapping_db)) as conn:
        data = conn.execute(
            'SELECT IFBpoint_id, Region, Branch, Name, Email_ID, '
            '"Retail Name", "Retail Email_ID", "Regional Name", "Regional Email_ID" '
            'FROM login_mapping'
        ).fetchall()
    db_by_code: dict[str, tuple] = {}
    for code, region, branch, name, email, rname, remail, regmname, regmemail in data:
        code = (str(code).strip() if code is not None else "")
        if not code or code in db_by_code:
            continue
        db_by_code[code] = (region, branch, name, email, rname, remail, regmname, regmemail)

    rows: list[dict] = []
    for code, mname in master_names.items():
        code = code.strip()
        if not code:
            continue
        if allowed_codes and code not in allowed_codes:
            continue
        region, branch, name, email, rname, remail, regmname, regmemail = db_by_code.get(
            code, ("", "", "", "", "", "", "", ""))
        rows.append({
            "IFB Point ID":             code,
            "IFB Point Name":           mname or (channel_names or {}).get(code, ""),
            "Branch":                   branch or "",
            "Region":                   region or "",
            "Cluster Manager Name":     name or "",
            "Cluster Manager Email ID": email or "",
            "Retail Name":              rname or "",
            "Retail Email ID":          remail or "",
            "Regional Manager Name":     regmname or "",
            "Regional Manager Email ID": regmemail or "",
        })
    df = pd.DataFrame(rows, columns=_RM_DISPLAY_COLS)
    if not df.empty:
        df = df.sort_values("IFB Point Name", key=lambda s: s.str.lower()).reset_index(drop=True)
    return df


def _apply_rm_updates(master_updates: dict[str, str],
                      db_updates: list[tuple[str, str, str]],
                      mapping_db: str | Path, master_file: str | Path) -> int:
    """Write the collected changes: db_updates → login_mapping.db,
    master_updates → IFB_Point_Master.txt. Returns count of fields changed."""
    if db_updates:
        with sqlite3.connect(str(mapping_db)) as conn:
            # Row may not exist yet if this code only lives in the master file —
            # ensure it exists (once per code, not once per field: IFBpoint_id has
            # no UNIQUE constraint, so a naive INSERT OR IGNORE per field would
            # insert a fresh duplicate row for every edited field).
            codes = {code for code, _col, _val in db_updates}
            for code in codes:
                exists = conn.execute(
                    "SELECT 1 FROM login_mapping WHERE IFBpoint_id=? LIMIT 1", (code,)
                ).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO login_mapping (IFBpoint_id) VALUES (?)", (code,)
                    )
            for code, db_col, val in db_updates:
                conn.execute(
                    f'UPDATE login_mapping SET "{db_col}"=? WHERE IFBpoint_id=?',
                    (val if val != "" else None, code),
                )
            conn.commit()
    if master_updates:
        _write_master_names(master_file, master_updates)
        # Invalidate the cached channel-name / master-code lookups in the main app
        # so the Analytics view reflects renamed points without a restart.
        try:
            import streamlit_app as _sa
            _sa._load_channel_names.cache_clear()
            _sa._load_master_codes.cache_clear()
        except Exception:
            pass
    return len(db_updates) + len(master_updates)


def _save_rm_row(code: str, values: dict[str, str], original: dict[str, str],
                 mapping_db: str | Path, master_file: str | Path) -> int:
    """Persist edits for a single IFB Point row (from the edit dialog)."""
    master_updates: dict[str, str] = {}
    db_updates: list[tuple[str, str, str]] = []
    for col in _RM_DISPLAY_COLS:
        if col == "IFB Point ID":
            continue
        new_v = (values.get(col) or "").strip()
        old_v = (original.get(col) or "").strip()
        if new_v == old_v:
            continue
        if col == "IFB Point Name":
            master_updates[code] = new_v
        else:
            db_updates.append((code, _RM_COL_TO_DB[col], new_v))
    return _apply_rm_updates(master_updates, db_updates, mapping_db, master_file)


# Soft badge palette for the Region pill (echoes the DataTables Status/Priority look)
_RM_BADGE_PALETTE = [
    ("#DBEAFE", "#1E40AF"), ("#DCFCE7", "#166534"), ("#FEF9C3", "#854D0E"),
    ("#FCE7F3", "#9D174D"), ("#E0E7FF", "#3730A3"), ("#FFEDD5", "#9A3412"),
    ("#CCFBF1", "#115E59"), ("#F3E8FF", "#6B21A8"), ("#FEE2E2", "#991B1B"),
]


def _rm_badge(text: str) -> str:
    """Coloured pill for a Region value (stable colour per distinct value)."""
    text = (text or "").strip()
    if not text:
        return "<span class='rm-muted'>—</span>"
    idx = sum(ord(c) for c in text) % len(_RM_BADGE_PALETTE)
    bg, fg = _RM_BADGE_PALETTE[idx]
    return (f"<span class='rm-badge' style='background:{bg};color:{fg};'>"
            f"{html.escape(text)}</span>")


def _rm_cell(text: str, cls: str = "") -> str:
    """Ellipsised, hover-titled table cell."""
    text = "" if text is None else str(text)
    safe = html.escape(text)
    inner = safe if text.strip() else "<span class='rm-muted'>—</span>"
    return f"<div class='rm-cell {cls}' title='{safe}'>{inner}</div>"


# Column layout: (label, key, streamlit-column-ratio, css-class)
_RM_COLS = [
    ("Point ID",           "IFB Point ID",             1.25, "rm-mono"),
    ("Point Name",         "IFB Point Name",           2.20, "rm-strong"),
    ("Branch",             "Branch",                   1.40, ""),
    ("Region",             "Region",                   1.40, "rm-badgecol"),
    ("Cluster Mgr",        "Cluster Manager Name",     1.55, ""),
    ("Cluster Mgr Email",  "Cluster Manager Email ID", 2.05, "rm-email"),
    ("Retail Mgr",         "Retail Name",              1.50, ""),
    ("Retail Mgr Email",   "Retail Email ID",          2.05, "rm-email"),
    ("Regional Mgr",       "Regional Manager Name",     1.55, ""),
    ("Regional Mgr Email", "Regional Manager Email ID", 2.05, "rm-email"),
    ("Edit",               "__edit__",                 0.70, "rm-editcol"),
]
_RM_RATIOS = [c[2] for c in _RM_COLS]

_POPOVER_CSS = """
<style>
  /* ── LinkedIn-style topbar nav items (icon on top, label below) ── */
  .st-key-_nav_analytics button, .st-key-_nav_rmmap button, .st-key-_nav_signout button {
    background:transparent !important; border:none !important; box-shadow:none !important;
    white-space:pre-line !important; line-height:1.25 !important; padding:4px 6px 2px !important;
    font-size:11.5px !important; font-weight:600 !important; color:#64748B !important;
    border-radius:6px !important; border-bottom:2.5px solid transparent !important;
  }
  .st-key-_nav_analytics button p, .st-key-_nav_rmmap button p, .st-key-_nav_signout button p {
    white-space:pre-line !important; line-height:1.25 !important; font-size:11.5px !important;
  }
  .st-key-_nav_analytics button:hover, .st-key-_nav_rmmap button:hover,
  .st-key-_nav_signout button:hover {
    background:#F1F5F9 !important; color:#0F172A !important;
  }
  /* Active-tab indicator rendered as static markdown block (see _nav_item()) */
  .nav-item-active {
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    white-space:pre-line; line-height:1.25; padding:4px 6px 2px; font-size:11.5px;
    font-weight:700; color:#0F172A; border-bottom:2.5px solid #4F46E5;
    text-align:center; cursor:default;
  }
  /* Topbar "Search IFB Point ID" box (RM Mapping view only) — centred between the
     title and the Analytics tab, with an "✖" clear icon overlaid inside the bar. */
  .st-key-rm_search_wrap {
    position:relative; max-width:260px; margin:2px auto 0;
  }
  .st-key-rm_search_wrap input {
    min-height:30px !important; font-size:12px !important; padding-right:26px !important;
  }
  /* The button's own element-container is already position:relative (Streamlit
     default), which becomes a closer containing block than rm_search_wrap — so
     position the container itself, not the [data-testid="stButton"] div inside it. */
  .st-key-rm_search_wrap .st-key-_rm_search_x {
    position:absolute !important; top:50% !important; right:2px !important;
    transform:translateY(-50%) !important; z-index:5 !important;
  }
  .st-key-rm_search_wrap [data-testid="stButton"] > button {
    background:transparent !important; border:none !important; box-shadow:none !important;
    padding:0 !important; min-height:20px !important; height:20px !important;
    width:20px !important; font-size:11px !important; color:#94A3B8 !important;
    line-height:1 !important; border-radius:5px !important;
  }
  .st-key-rm_search_wrap [data-testid="stButton"] > button:hover {
    color:#475569 !important; background:#EEF2FF !important;
  }
</style>
"""

_RM_CSS = """
<style>
  /* ── RM Mapping table ── */
  .st-key-rm_head { margin-top:6px !important; }
  .st-key-rm_pager { margin-top:6px !important; }
  .st-key-rm_head [data-testid="stHorizontalBlock"],
  .st-key-rm_body [data-testid="stHorizontalBlock"] {
    gap:0 !important; align-items:center !important;
  }
  .st-key-rm_body [data-testid="stHorizontalBlock"] {
    border-bottom:1px solid #EEF1F5 !important; min-height:40px;
  }
  .st-key-rm_body [data-testid="stHorizontalBlock"]:hover { background:#F8FAFF !important; }
  .st-key-rm_head [data-testid="stColumn"],
  .st-key-rm_body [data-testid="stColumn"] { padding:0 6px !important; }

  /* Header sort buttons — flat, blue, DataTables-like */
  .st-key-rm_head [data-testid="stButton"] > button {
    background:transparent !important; border:none !important; box-shadow:none !important;
    color:#2F6FB0 !important; font-weight:700 !important; font-size:10.5px !important;
    padding:4px 0 !important; height:auto !important; min-height:0 !important;
    line-height:1.15 !important; width:100% !important; justify-content:flex-start !important;
    text-align:left !important; border-radius:0 !important; letter-spacing:.2px;
  }
  .st-key-rm_head [data-testid="stButton"] > button:hover {
    color:#1D4E8A !important; text-decoration:underline; background:transparent !important;
  }
  .st-key-rm_head [data-testid="stHorizontalBlock"] { border-bottom:2px solid #E2E8F0 !important; }

  /* Body cells */
  .rm-cell { font-size:13px; color:#334155; padding:9px 0; line-height:1.25;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .rm-strong { font-weight:600; color:#0F172A; }
  .rm-mono   { font-variant-numeric:tabular-nums; color:#0F172A; font-weight:600; }
  .rm-email  { color:#475569; }
  .rm-muted  { color:#CBD5E1; }
  .rm-badge  { display:inline-block; padding:2px 8px; border-radius:5px;
    font-size:10.5px; font-weight:700; white-space:nowrap; }

  /* Per-row edit button — small ghost icon */
  .st-key-rm_body [data-testid="stButton"] > button {
    background:transparent !important; border:1px solid transparent !important;
    box-shadow:none !important; padding:2px 6px !important; min-height:28px !important;
    font-size:14px !important; color:#64748B !important; border-radius:7px !important;
  }
  .st-key-rm_body [data-testid="stButton"] > button:hover {
    background:#EEF2FF !important; border-color:#C7D2FE !important; color:#4F46E5 !important;
  }

  /* Footer pager buttons */
  .st-key-rm_pager [data-testid="stButton"] > button {
    min-height:30px !important; padding:2px 11px !important; font-size:12px !important;
    border:1px solid #E2E8F0 !important; background:#FFFFFF !important;
    color:#475569 !important; box-shadow:none !important; border-radius:7px !important;
  }
  .st-key-rm_pager [data-testid="stButton"] > button:hover {
    border-color:#6366F1 !important; color:#4F46E5 !important; background:#EEF2FF !important; }
  .st-key-rm_pager [data-testid="stButton"] > button:disabled {
    color:#CBD5E1 !important; background:#F8FAFC !important; }
  .st-key-rm_pager [data-testid="stButton"] > button[kind="primary"] {
    background:#4F46E5 !important; border-color:#4F46E5 !important; color:#FFFFFF !important;
    font-weight:700 !important; }
  .st-key-rm_pager [data-testid="stButton"] > button[kind="primary"]:hover {
    background:#4338CA !important; color:#FFFFFF !important; }
</style>
"""


@st.dialog("✏️ Edit IFB Point")
def _rm_edit_dialog(row: dict, mapping_db: str | Path, master_file: str | Path) -> None:
    code = row["IFB Point ID"]
    st.markdown(
        f"<div style='font-size:12px;color:#64748B;margin:-6px 0 8px;'>"
        f"IFB Point ID <b style='color:#0F172A;'>{html.escape(str(code))}</b> "
        f"· reference key, not editable</div>",
        unsafe_allow_html=True,
    )
    name = st.text_input("IFB Point Name", value=row["IFB Point Name"],
                         help="Saved to IFB_Point_Master.txt")
    c1, c2 = st.columns(2)
    branch   = c1.text_input("Branch",   value=row["Branch"])
    region   = c2.text_input("Region",   value=row["Region"])
    cm_name  = c1.text_input("Cluster Manager Name",     value=row["Cluster Manager Name"])
    cm_email = c2.text_input("Cluster Manager Email ID", value=row["Cluster Manager Email ID"])
    r_name   = c1.text_input("Retail Name",     value=row["Retail Name"])
    r_email  = c2.text_input("Retail Email ID", value=row["Retail Email ID"])
    rm_name  = c1.text_input("Regional Manager Name",     value=row["Regional Manager Name"])
    rm_email = c2.text_input("Regional Manager Email ID", value=row["Regional Manager Email ID"])

    b1, b2 = st.columns([1, 1])
    if b1.button("💾 Save", type="primary", use_container_width=True):
        values = {
            "IFB Point Name": name, "Branch": branch, "Region": region,
            "Cluster Manager Name": cm_name, "Cluster Manager Email ID": cm_email,
            "Retail Name": r_name, "Retail Email ID": r_email,
            "Regional Manager Name": rm_name, "Regional Manager Email ID": rm_email,
        }
        n = _save_rm_row(str(code), values, row, mapping_db, master_file)
        st.session_state["_rm_flash"] = (
            f"Saved {n} change{'s' if n != 1 else ''} for {code}." if n
            else "No changes to save."
        )
        st.rerun()
    if b2.button("Cancel", use_container_width=True):
        st.rerun()


def _render_rm_mapping(mapping_db: str | Path, master_file: str | Path,
                       allowed_codes: set[str] | None,
                       channel_names: dict[str, str] | None = None) -> None:
    """RM Mapping screen — a DataTables-style, searchable, sortable, paginated table
    of login_mapping.db joined with IFB Point names from the master file.
    Each row has an ✏️ button that opens an edit dialog; IFB Point ID is the key."""
    st.markdown(_RM_CSS, unsafe_allow_html=True)

    _flash = st.session_state.pop("_rm_flash", None)
    if _flash:
        st.toast(_flash, icon="✅")

    master_names = _read_master_names(master_file)
    df = _load_rm_rows(mapping_db, master_names, allowed_codes, channel_names)
    if df.empty:
        st.info("No mapping rows available for your scope.")
        return

    ss = st.session_state
    ss.setdefault("_rm_page", 1)
    ss.setdefault("_rm_sort_col", "IFB Point Name")
    ss.setdefault("_rm_sort_asc", True)

    # ── Filter + sort ─────────────────────────────────────────────────────────
    q = ss.get("_rm_search", "").strip().lower()
    if q:
        mask = df.apply(
            lambda r: q in " ".join(str(v).lower() for v in r.values), axis=1)
        fdf = df[mask]
    else:
        fdf = df
    sort_col = ss["_rm_sort_col"] if ss["_rm_sort_col"] in df.columns else "IFB Point Name"
    fdf = fdf.sort_values(
        sort_col, ascending=ss["_rm_sort_asc"], kind="stable",
        key=lambda s: s.astype(str).str.lower(),
    ).reset_index(drop=True)

    psize = ss.get("_rm_psize", 12)
    total = len(fdf)
    npages = max(1, math.ceil(total / psize))
    page = min(max(1, ss["_rm_page"]), npages)
    ss["_rm_page"] = page
    start = (page - 1) * psize
    end = min(start + psize, total)
    page_df = fdf.iloc[start:end]

    # ── Header (sortable) ─────────────────────────────────────────────────────
    with st.container(key="rm_head"):
        hc = st.columns(_RM_RATIOS)
        for i, (label, key, _r, _cls) in enumerate(_RM_COLS):
            if key == "__edit__":
                continue
            arrow = ""
            if ss["_rm_sort_col"] == key:
                arrow = " ▲" if ss["_rm_sort_asc"] else " ▼"
            if hc[i].button(f"{label}{arrow}", key=f"_rm_h_{i}", use_container_width=True):
                if ss["_rm_sort_col"] == key:
                    ss["_rm_sort_asc"] = not ss["_rm_sort_asc"]
                else:
                    ss["_rm_sort_col"] = key
                    ss["_rm_sort_asc"] = True
                st.rerun()

    # ── Body ──────────────────────────────────────────────────────────────────
    with st.container(key="rm_body"):
        if page_df.empty:
            st.markdown(
                "<div style='padding:22px 4px;color:#94A3B8;font-size:13px;'>"
                "No matching rows.</div>", unsafe_allow_html=True)
        for _, row in page_df.iterrows():
            rc = st.columns(_RM_RATIOS)
            for i, (label, key, _r, cls) in enumerate(_RM_COLS):
                if key == "__edit__":
                    if rc[i].button("✏️", key=f"_rm_e_{row['IFB Point ID']}",
                                    help="Edit this row"):
                        _rm_edit_dialog(row.to_dict(), mapping_db, master_file)
                elif "rm-badgecol" in cls:
                    rc[i].markdown(_rm_badge(row[key]), unsafe_allow_html=True)
                else:
                    rc[i].markdown(_rm_cell(row[key], cls), unsafe_allow_html=True)

    # ── Footer: Prev / Next pagination (fixed 15 rows per page) ────────────────
    with st.container(key="rm_pager"):
        pc1, pc2, pc3 = st.columns([1, 2, 1])
        with pc1:
            if st.button("‹ Prev", key="_rm_prev", disabled=(page <= 1),
                        use_container_width=True):
                ss["_rm_page"] = page - 1
                st.rerun()
        with pc2:
            st.markdown(
                f"<div style='text-align:center;color:#64748B;font-size:12.5px;"
                f"padding-top:6px;'>Page <b style='color:#334155;'>{page}</b> of "
                f"<b style='color:#334155;'>{npages}</b></div>",
                unsafe_allow_html=True,
            )
        with pc3:
            if st.button("Next ›", key="_rm_next", disabled=(page >= npages),
                        use_container_width=True):
                ss["_rm_page"] = page + 1
                st.rerun()


def render_overview_dashboard(
    db_path: Path,
    channel_names: dict[str, str],
    bucket_to_stage: dict[str, str],
    allowed_codes: set[str] | None = None,
    login_mapping_db: Path | None = None,
    user_email: str = "",
    master_file: Path | None = None,
) -> None:
    """
    Render the Analytics Console overview screen.

    Args:
        db_path:        Path to ifb_point.db
        channel_names:  {code: friendly_name} mapping
        bucket_to_stage: {api_bucket_key: stage_label} mapping
        allowed_codes:  IFB point codes this user is permitted to see;
                        None or empty set means no restriction.
        login_mapping_db: Path to login_mapping.db (for Region/Branch hierarchy)
        user_email:     Logged-in user's email
        master_file:    Path to IFB_Point_Master.txt (for the RM Mapping editor)
    """
    if master_file is None:
        master_file = Path(db_path).parent / "IFB_Point_Master.txt"
    st.markdown(_OVERVIEW_CSS, unsafe_allow_html=True)
    st.markdown(_POPOVER_CSS, unsafe_allow_html=True)

    # ── JS: rounded tooltip corners + column highlight on hover ──────────────
    st.html("""
    <script>
    (function() {
      const obs = new MutationObserver(() => {
        // 1. Rounded corners on hoverlabel rects
        document.querySelectorAll('.hoverlabel rect').forEach(r => {
          r.setAttribute('rx', '8'); r.setAttribute('ry', '8');
        });
        // 2. Column highlight: add animated indigo border around hovered bar column
        document.querySelectorAll('.plot-container').forEach(pc => {
          if (pc._hoverInit) return;
          pc._hoverInit = true;
          pc.addEventListener('mousemove', e => {
            const bars = pc.querySelectorAll('.bars .point path');
            bars.forEach(b => {
              const bb = b.getBoundingClientRect();
              const inCol = e.clientX >= bb.left - 2 && e.clientX <= bb.right + 2;
              b.style.transition = 'stroke-width .15s ease, stroke .15s ease';
              if (inCol) {
                b.style.stroke = '#6366F1';
                b.style.strokeWidth = '2.5px';
              } else {
                b.style.stroke = '#FFFFFF';
                b.style.strokeWidth = '1px';
              }
            });
          });
          pc.addEventListener('mouseleave', () => {
            pc.querySelectorAll('.bars .point path').forEach(b => {
              b.style.stroke = '#FFFFFF'; b.style.strokeWidth = '1px';
            });
          });
        });
      });
      obs.observe(document.body, {childList: true, subtree: true});
    })();
    </script>
    """)

    # ── A TOPBAR: title · [search] · Analytics · RM Mapping · Sign Out ─────────
    # Clear-flag must be applied *before* the _rm_search widget is instantiated —
    # writing to a widget's session-state key after it's created raises in Streamlit.
    if st.session_state.pop("_rm_search_clear", False):
        st.session_state["_rm_search"] = ""

    cur_view = st.session_state.get("_ov_view", "analytics")
    if cur_view == "rm_mapping":
        # tb1 is deliberately narrow (title text is ~215px) so the search column
        # begins right after the title text — the search box then centres in the
        # visible whitespace between the title and the Analytics tab, not in a
        # column padded out to half the topbar width.
        tb1, tbs, tb2, tb3, tb4 = st.columns([1.95, 5.25, 0.85, 0.95, 0.75])
    else:
        tb1, tb2, tb3, tb4 = st.columns([7.2, 0.85, 0.95, 0.75])
    with tb1:
        # white-space:nowrap keeps the title on one line even when its column is
        # deliberately narrow (RM Mapping view) — the text ends well left of the
        # search box, so any overflow into the gap is harmless.
        st.markdown(
            "<div style='font-size:19px;font-weight:800;color:#0F172A;line-height:1.1;"
            "letter-spacing:-0.3px;padding-top:4px;white-space:nowrap;overflow:visible;'>"
            "🎯 Follow Up Control Tower</div>",
            unsafe_allow_html=True,
        )
    if cur_view == "rm_mapping":
        with tbs:
            with st.container(key="rm_search_wrap"):
                _rm_prev_q = st.session_state.get("_rm_search", "")
                st.text_input(
                    "Search IFB Point ID", placeholder="🔍  Search IFB Point ID…",
                    label_visibility="collapsed", key="_rm_search",
                )
                if st.session_state.get("_rm_search", "").strip():
                    if st.button("✖", key="_rm_search_x"):
                        st.session_state["_rm_search_clear"] = True
                        st.rerun()
                if st.session_state.get("_rm_search", "") != _rm_prev_q:
                    st.session_state["_rm_page"] = 1
    with tb2:
        if cur_view == "analytics":
            st.markdown("<div class='nav-item-active'>📊\nAnalytics</div>", unsafe_allow_html=True)
        else:
            # on_click callbacks run *before* Streamlit's single automatic rerun,
            # so the state flip is already in effect when the script body runs
            # top-to-bottom again — no need for an extra manual st.rerun(), which
            # would otherwise force the whole (expensive) script to execute twice
            # per click and make tab switching feel sluggish.
            st.button("📊\nAnalytics", use_container_width=True, key="_nav_analytics",
                      on_click=lambda: st.session_state.update({"_ov_view": "analytics"}))
    with tb3:
        if cur_view == "rm_mapping":
            st.markdown("<div class='nav-item-active'>🗺️\nRM Mapping</div>", unsafe_allow_html=True)
        else:
            st.button("🗺️\nRM Mapping", use_container_width=True, key="_nav_rmmap",
                      on_click=lambda: st.session_state.update({"_ov_view": "rm_mapping"}))
    with tb4:
        def _do_sign_out():
            st.session_state["_authed"] = False
            st.session_state.pop("_authed_email", None)
            st.query_params.clear()
        st.button("🚪\nSign Out", use_container_width=True, key="_nav_signout",
                  on_click=_do_sign_out)

    st.divider()

    # ── View routing ──────────────────────────────────────────────────────────
    if st.session_state.get("_ov_view", "analytics") == "rm_mapping":
        _render_rm_mapping(login_mapping_db or (Path(db_path).parent / "login_mapping.db"),
                           master_file, allowed_codes, channel_names)
        return

    allowed_codes_key = tuple(sorted(allowed_codes)) if allowed_codes else None
    df = _load_df(str(db_path), allowed_codes_key).copy()
    if df.empty:
        st.info("No data available yet.")
        return

    # Restrict to IFB points currently in the master list (IFB_Point_Master.txt) —
    # the leads DB can retain stale/old codes that are no longer valid points.
    if channel_names:
        df = df[df["ifb_point"].isin(channel_names.keys())]
        if df.empty:
            st.info("No data available yet.")
            return

    df["status"]     = df["status"].fillna("").replace("", "Pending")
    df["interest"]   = df["interested"].fillna("").replace("", "—")
    df["stage"]      = df["follow_up"].map(bucket_to_stage).fillna("Other")
    df["point_name"] = df["ifb_point"].map(channel_names).fillna(df["ifb_point"])
    df["lead_dt"]    = pd.to_datetime(df["lead_date"], format="%d-%m-%Y", errors="coerce")

    _codes = sorted(df["ifb_point"].unique(),
                    key=lambda c: channel_names.get(c, c).lower())

    # Restrict to only the IFB points this user is mapped to. The loader already
    # applies this in SQL; keep this guard for safety if cached data shape changes.
    if allowed_codes:
        df     = df[df["ifb_point"].isin(allowed_codes)]
        _codes = [c for c in _codes if c in allowed_codes]

    # ── Two-pane: C RAIL | main ────────────────────────────────────────────────
    with st.container(key="two_pane"):
        rail, main = st.columns([1.3, 8.7], gap="medium")

        with rail:
            _LIST_H = 634

            if "_ov_sel" not in st.session_state:
                st.session_state["_ov_sel"] = set()

            # ── Load hierarchy ────────────────────────────────────────────────
            _hierarchy: dict[str, dict[str, list[str]]] = {}
            if login_mapping_db and user_email:
                _hierarchy = _load_hierarchy(str(login_mapping_db), user_email, allowed_codes,
                                              set(channel_names.keys()) if channel_names else None)
            _all_regions  = sorted(_hierarchy.keys())
            _has_hierarchy = len(_all_regions) > 0

            # Search removed — Region/Branch/IFB Point cascade drives filtering now.
            _q = ""

            # ── All / Clear buttons ───────────────────────────────────────────
            # Precompute all branches and all points for "All" button
            _all_branches_list = sorted({
                b for r_data in _hierarchy.values() for b in r_data.keys()
            }) if _has_hierarchy else []
            _all_points_list = sorted({
                c for r_data in _hierarchy.values()
                for pts in r_data.values() for c in pts
            }) if _has_hierarchy else list(_codes)

            qa1, qa2 = st.columns(2, gap="small")
            with qa1:
                if st.button("✅ All", use_container_width=True, key="_ov_selall"):
                    st.session_state["_ov_sel_regions"]  = list(_all_regions)
                    st.session_state["_ov_sel_branches"] = list(_all_branches_list)
                    st.session_state["_ov_sel"]          = set(_all_points_list)
                    # Set widget keys directly so multiselects reflect selection visually
                    st.session_state["_ov_ms_region"]    = list(_all_regions)
                    st.session_state["_ov_ms_branch"]    = list(_all_branches_list)
                    st.session_state["_ov_ms_points"]    = list(_all_points_list)
                    st.rerun()
            with qa2:
                if st.button("✖ Clear", use_container_width=True, key="_ov_clr"):
                    st.session_state["_ov_sel"]            = set()
                    st.session_state["_ov_sel_regions"]    = []
                    st.session_state["_ov_sel_branches"]   = []
                    # Clear the widget keys directly so multiselects reset visually
                    st.session_state["_ov_ms_region"]      = []
                    st.session_state["_ov_ms_branch"]      = []
                    st.session_state["_ov_ms_points"]      = []
                    st.rerun()

            # ── Region / Branch / IFB Point cascade ───────────────────────────
            if _has_hierarchy:
                # Region multiselect
                sel_regions = st.multiselect(
                    "🌍 Region",
                    options=_all_regions,
                    default=st.session_state.get("_ov_sel_regions", []),
                    key="_ov_ms_region",
                    placeholder="All Regions",
                )
                st.session_state["_ov_sel_regions"] = sel_regions

                # Derive available branches from selected regions
                if sel_regions:
                    _avail_branches = sorted({
                        b for r in sel_regions
                        for b in _hierarchy.get(r, {}).keys()
                    })
                else:
                    _avail_branches = sorted({
                        b for r_data in _hierarchy.values()
                        for b in r_data.keys()
                    })

                # Clean stale branch selections
                _prev_branches = st.session_state.get("_ov_sel_branches", [])
                _valid_branches = [b for b in _prev_branches if b in _avail_branches]

                sel_branches = st.multiselect(
                    "🏢 Branch",
                    options=_avail_branches,
                    default=_valid_branches,
                    key="_ov_ms_branch",
                    placeholder="All Branches",
                )
                st.session_state["_ov_sel_branches"] = sel_branches

                # Derive available IFB points from selected regions + branches
                _avail_points: list[str] = []
                _src_regions = sel_regions if sel_regions else list(_hierarchy.keys())
                _src_branches_set = set(sel_branches) if sel_branches else None
                for _r in _src_regions:
                    for _b, _pts in _hierarchy.get(_r, {}).items():
                        if _src_branches_set and _b not in _src_branches_set:
                            continue
                        _avail_points.extend(_pts)
                _avail_points = sorted(set(_avail_points),
                                       key=lambda c: channel_names.get(c, c).lower())

                # Include codes that have DB data but are absent from login_mapping
                _hierarchy_codes = set(_avail_points)
                _unassigned = [c for c in _codes if c not in _hierarchy_codes]
                if _unassigned:
                    _avail_points = sorted(
                        set(_avail_points) | set(_unassigned),
                        key=lambda c: channel_names.get(c, c).lower(),
                    )

                # Apply search filter
                if _q:
                    _avail_points = [c for c in _avail_points
                                     if _q in channel_names.get(c, str(c)).lower()
                                     or _q in str(c).lower()]

                # IFB Points multiselect
                _prev_pts = [c for c in st.session_state.get("_ov_sel", set())
                             if c in _avail_points]
                sel_points = st.multiselect(
                    "🏪 IFB Points",
                    options=_avail_points,
                    default=_prev_pts,
                    format_func=lambda c: f"{channel_names.get(c, c)} ({c})",
                    key="_ov_ms_points",
                    placeholder="All IFB Points",
                )
                st.session_state["_ov_sel"] = set(sel_points)
            else:
                # Fallback: no hierarchy data — show flat multiselect
                _visible = [c for c in _codes
                            if not _q
                            or _q in channel_names.get(c, str(c)).lower()
                            or _q in str(c).lower()]
                _prev_pts = [c for c in st.session_state.get("_ov_sel", set())
                             if c in _visible]
                sel_points = st.multiselect(
                    "🏪 IFB Points",
                    options=_visible,
                    default=_prev_pts,
                    format_func=lambda c: f"{channel_names.get(c, c)} ({c})",
                    key="_ov_ms_points_flat",
                    placeholder="All IFB Points",
                )
                st.session_state["_ov_sel"] = set(sel_points)

            selected_set = st.session_state["_ov_sel"]

            # Master-list total for this user's scope (used for Total Stores KPI)
            _master_all = set(channel_names.keys())
            if allowed_codes:
                _master_all = _master_all & allowed_codes

            # Determine scope based on hierarchy selections (not just IFB point picks)
            if _has_hierarchy and not selected_set:
                # No specific IFB points picked — scope from region/branch cascade
                _cascade_pts: list[str] = []
                _src_r = sel_regions if sel_regions else list(_hierarchy.keys())
                _src_b = set(sel_branches) if sel_branches else None
                for _r in _src_r:
                    for _b, _pts in _hierarchy.get(_r, {}).items():
                        if _src_b and _b not in _src_b:
                            continue
                        _cascade_pts.extend(_pts)
                _cascade_set = set(_cascade_pts)
                if sel_regions or sel_branches:
                    scope_codes       = _cascade_set
                    scope_df          = df[df["ifb_point"].isin(scope_codes)]
                    _master_store_count = len(scope_codes)
                    scope_label       = f"{_master_store_count} point{'s' if _master_store_count != 1 else ''}"
                else:
                    scope_codes         = set(_codes)
                    scope_df            = df
                    _master_store_count = len(_master_all)
                    scope_label         = f"All {_master_store_count} points"
            elif selected_set:
                scope_codes         = selected_set
                scope_df            = df[df["ifb_point"].isin(scope_codes)]
                _master_store_count = len(selected_set)
                n = _master_store_count
                scope_label = f"{n} point{'s' if n != 1 else ''} selected"
            else:
                scope_codes         = set(_codes)
                scope_df            = df
                _master_store_count = len(_master_all)
                scope_label         = f"All {_master_store_count} points"

            st.markdown(
                f"<div class='scope-badge'>⚡ {scope_label}</div>",
                unsafe_allow_html=True,
            )

        # ── MAIN: F KPI + G charts ─────────────────────────────────────────────────
        with main:
            _section_colors = {
                "day":   ("#6366F1", "#EEF2FF"),   # indigo
                "week":  ("#0891B2", "#ECFEFF"),   # cyan
                "month": ("#7C3AED", "#F5F3FF"),   # violet
            }
            _force_all = bool(selected_set)
            _day_html, _day_shown, _day_total = _pointer_table_html(
                scope_df=scope_df,
                scope_codes=scope_codes,
                channel_names=channel_names,
                period="day",
                n=7,
                force_all=_force_all,
                limit=None,
            )
            total_leads = len(scope_df)
            contacted     = int((scope_df["status"] == "Contacted").sum())
            rnr           = int((scope_df["status"] == "RnR").sum())
            not_reachable = int((scope_df["status"] == "Not Reachable").sum())
            not_cont      = total_leads - contacted - rnr

            _today_ts = pd.Timestamp(date.today())
            _df_today = scope_df[scope_df["lead_dt"].dt.normalize() == _today_ts
            ] if "lead_dt" in scope_df.columns else pd.DataFrame()
            t_total         = len(_df_today)
            t_contacted     = int((_df_today["status"] == "Contacted").sum()) if not _df_today.empty else 0
            t_rnr           = int((_df_today["status"] == "RnR").sum()) if not _df_today.empty else 0
            t_not_reachable = int((_df_today["status"] == "Not Reachable").sum()) if not _df_today.empty else 0
            t_not_cont      = t_total - t_contacted - t_rnr

            def _pct(n: int) -> float:
                return (n / total_leads * 100) if total_leads else 0.0

            def _tpct(n: int) -> float:
                return (n / t_total * 100) if t_total else 0.0

            # F — KPI ROW  (bordered container kept for spacing; border hidden via CSS)
            with st.container(border=True, key="kpi_row"):
                kc1, kc2, kc3, kc4, kc5, kc6 = st.columns(6, gap="small")
                _active_pts = int(_df_today[_df_today["status"].isin(["Contacted", "RnR", "Not Reachable"])]["ifb_point"].nunique()) if not _df_today.empty else 0
                _active_pct = (_active_pts / _master_store_count * 100) if _master_store_count else 0.0
                _kpi_card(kc1, "Total Stores", _master_store_count, today_val=_active_pts, today_pct=_active_pct, sub_label="Active Calling Stores")
                _kpi_card(kc2, "Total Customers Allocated", total_leads, today_val=t_total)
                _calls_attempted   = contacted + rnr + not_reachable
                _t_calls_attempted = t_contacted + t_rnr + t_not_reachable
                _t_ca_pct = (_t_calls_attempted / t_total * 100) if t_total else 0.0
                _kpi_card(kc3, "Calls Attempted", _calls_attempted,
                          today_val=_t_calls_attempted, today_pct=_t_ca_pct,
                          sub_label="Today Calls Attempted", all_label="Total Calls Attempted")

                _kpi_card(kc4, "Calls Connected", contacted, today_val=t_contacted, today_pct=_tpct(t_contacted), sub_label="Todays Calls Connected")

                _interested     = int((scope_df["interest"] == "Interested").sum()) if not scope_df.empty else 0
                _t_interested   = int((_df_today["interested"] == "Interested").sum()) if not _df_today.empty else 0
                _t_int_pct      = (_t_interested / t_total * 100) if t_total else 0.0
                _kpi_card(kc5, "Interested Customers", _interested,
                          today_val=_t_interested, today_pct=_t_int_pct)

                _kpi_card(kc6, "Not Contacted", not_cont, today_val=t_not_cont, today_pct=_tpct(t_not_cont))

            # G — TABULAR ROWS  (Day / Week / Month) — IFB Point × 6 Pointers × N periods
            st.markdown(
                f"<div style='font-size:9.5px;font-weight:800;color:{_section_colors['day'][0]};"
                f"text-transform:uppercase;letter-spacing:0.7px;"
                f"padding-left:3px;margin-top:8px;margin-bottom:8px;'>📅  Day Wise — Last 7 Days"
                f"<span style='color:#94A3B8;font-weight:600;'> · {_day_shown} store{'s' if _day_shown != 1 else ''}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            for title, period, n in [
                ("📅  Day Wise — Last 7 Days",     "day",   7),
                ("📆  Week Wise — Last 4 Weeks",   "week",  4),
                ("🗓️  Month Wise — Last 6 Months", "month", 6),
            ]:
                accent, _ = _section_colors[period]
                if period == "day":
                    tbl_html, n_shown, n_total = _day_html, _day_shown, _day_total
                else:
                    tbl_html, n_shown, n_total = _pointer_table_html(
                        scope_df=scope_df,
                        scope_codes=scope_codes,
                        channel_names=channel_names,
                        period=period,
                        n=n,
                        force_all=_force_all,
                        limit=None,
                    )
                _count_note = f" · {n_shown} store{'s' if n_shown != 1 else ''}"
                if period != "day":
                    st.markdown(
                        f"<div style='font-size:9.5px;font-weight:800;color:{accent};"
                        f"text-transform:uppercase;letter-spacing:0.7px;"
                        f"padding-left:3px;margin-bottom:8px;'>{title}"
                        f"<span style='color:#94A3B8;font-weight:600;'>{_count_note}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with st.container(border=True, key=f"pt_section_{period}"):
                    tcol, icol = st.columns([6.8, 3.2], gap="medium")
                    with tcol:
                        st.markdown(tbl_html, unsafe_allow_html=True)
                    with icol:
                        buckets = _time_buckets(scope_df, period, n)
                        st.markdown(
                            f"<div style='background:#FFFFFF;border:1px solid #E2E8F0;"
                            f"border-left:4px solid {accent};"
                            f"border-radius:10px;padding:10px 12px;"
                            f"height:302px;overflow-y:auto;box-sizing:border-box;'>"
                            f"{_insights(buckets, period, scope_df=scope_df)}</div>",
                            unsafe_allow_html=True,
                        )
                st.markdown("<div style='height:18px;'></div>", unsafe_allow_html=True)
