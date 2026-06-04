"""IFB Point — Analytics Console (Overview Dashboard).

Renders the admin analytics screen shown at /?auth=ok.
Called from streamlit_app.py; receives shared state as arguments
to avoid circular imports.

Usage (from streamlit_app.py):
    from overview_dashboard import render_overview_dashboard
    render_overview_dashboard(DB_PATH, _CHANNEL_NAMES, _BUCKET_TO_STAGE)
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Constants ─────────────────────────────────────────────────────────────────

_KPI_STYLE = {
    "IFB Points":    ("#4F46E5", "#EEF2FF", "🏪"),
    "Total Leads":   ("#0EA5E9", "#F0F9FF", "👥"),
    "Contacted":     ("#16A34A", "#F0FDF4", "✅"),
    "Not Contacted": ("#DC2626", "#FEF2F2", "🚫"),
    "RnR":           ("#D97706", "#FFFBEB", "🔁"),
}

_BAR_SERIES = {
    "Total Leads":   "#4F46E5",
    "Contacted":     "#16A34A",
    "Not Contacted": "#DC2626",
    "RnR":           "#D97706",
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

  /* ── C container: the whole left rail, same height as right content ── */
  .st-key-c_container {
    background:#FFFFFF !important;
    border:1.5px solid #E0E7FF !important;
    border-radius:14px !important;
    box-shadow:0 2px 10px rgba(99,102,241,0.08) !important;
  }
  /* Force all checkbox labels visible — overrides global margin:0 rules */
  .st-key-c_container * { visibility:visible !important; opacity:1 !important; }
  .st-key-c_container p, .st-key-c_container span {
    font-size:12px !important; color:#374151 !important;
    line-height:1.3 !important; display:inline !important;
    white-space:normal !important; word-break:break-word !important;
  }
  .st-key-c_container [data-testid="stCheckbox"] {
    padding:2px 6px !important; margin:1px 0 !important;
    border-radius:7px !important; transition:background .12s !important;
  }
  .st-key-c_container [data-testid="stCheckbox"]:hover { background:#EEF2FF !important; }
  .st-key-c_container [data-testid="stCheckbox"]:hover p { color:#4F46E5 !important; }
  .st-key-c_container [data-testid="stCheckbox"]:has(input:checked) {
    background:#EEF2FF !important; border-left:3px solid #6366F1 !important;
  }
  .st-key-c_container [data-testid="stCheckbox"]:has(input:checked) p {
    color:#4F46E5 !important; font-weight:700 !important;
  }
  .st-key-c_container .element-container { margin:0 !important; padding:0 !important; }
  /* Scrollbar for C container */
  .st-key-c_container::-webkit-scrollbar { width:4px; }
  .st-key-c_container::-webkit-scrollbar-thumb { background:#C7D2FE; border-radius:4px; }
  .st-key-c_container::-webkit-scrollbar-track { background:transparent; }
</style>
"""


# ── Data loader ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_df(db_path: str) -> pd.DataFrame:
    """Load all leads once (cached 60s)."""
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            "SELECT ifb_point, status, final_status, interested, follow_up, lead_date "
            "FROM api_leads",
            conn,
        )


# ── KPI card ───────────────────────────────────────────────────────────────────

def _kpi_card(col, label: str, value: int, pct: float | None = None) -> None:
    color, _, icon = _KPI_STYLE.get(label, ("#6366F1", "#EEF2FF", "•"))
    pct_html = (
        f"<span style='font-size:10px;font-weight:700;color:{color};"
        f"margin-left:6px;opacity:0.9;'>{pct:.1f}%</span>"
        if pct is not None else ""
    )
    tint = _KPI_STYLE.get(label, ("#6366F1", "#EEF2FF", "•"))[1]
    col.markdown(
        f"<div style='background:{tint};border:1px solid {color}30;"
        f"border-left:4px solid {color};border-radius:12px;"
        f"padding:9px 12px;height:76px;display:flex;flex-direction:column;"
        f"justify-content:space-between;"
        f"box-shadow:0 2px 10px {color}18;'>"
        f"<div style='display:flex;align-items:center;justify-content:space-between;'>"
        f"<span style='font-size:8.5px;font-weight:800;color:{color};text-transform:uppercase;"
        f"letter-spacing:0.6px;'>{label}</span>"
        f"<span style='font-size:13px;'>{icon}</span></div>"
        f"<div style='display:flex;align-items:baseline;'>"
        f"<span style='font-size:22px;font-weight:800;color:#0F172A;line-height:1;'>{value:,}</span>"
        f"{pct_html}</div>"
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
        "Total Leads":   tmp.groupby("_bk").size(),
        "Contacted":     (tmp["status"] == "Contacted").groupby(tmp["_bk"]).sum(),
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
            annotations=[dict(text="No leads in this window", showarrow=False,
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
        circle_rows = "".join(
            f"<span style='color:{c};'>⬤</span>"
            f" <b style='color:#F1F5F9;'>{s}</b>"
            f"<span style='color:#94A3B8;'>"
            f"  {breakdown[i][s]:,}  ({(breakdown[i][s]/t*100) if t else 0:.1f}%)"
            f"</span><br>"
            for s, c in _MK_SEGMENTS if s in active
        )
        col_customs.append([labels[i].replace("<br>", " "), t, circle_rows])

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
                "<span style='color:#64748B;'>  ·  %{customdata[1]:,} leads</span>"
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


def _insights(buckets: list[tuple], period: str) -> str:
    """
    Written narrative insights derived from bucket data.
    Tells the story: total, current vs avg, peak, low, dominant outcome, untouched, RnR.
    buckets = list of (label, total, {seg: count}) from _time_buckets().
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
        return "lead" if n == 1 else "leads"

    sentences = []

    # 0. Total across the full window
    window_desc = {"day": "last 7 days", "week": "last 4 weeks", "month": "last 6 months"}
    sentences.append(
        f"{hi(f'{grand_total:,}', '#4F46E5')} leads across the "
        f"{window_desc.get(period, 'window')}."
    )

    # 1. Current period vs average (skip if today has 0 and avg > 0 — data not in yet)
    if cur_total == 0 and avg_val > 0:
        sentences.append(
            f"{hi(cur_noun, '#4F46E5')} has no leads yet "
            f"(avg is {hi(f'{avg_val:.0f}', '#475569')} per {unit})."
        )
    elif avg_val > 0:
        delta_pct = (cur_total - avg_val) / avg_val * 100
        if delta_pct >= 15:
            sentences.append(
                f"{hi(cur_noun, '#4F46E5')}: {hi(f'{cur_total:,}', '#16A34A')} leads — "
                f"{hi(f'+{delta_pct:.0f}%', '#16A34A')} above the avg of "
                f"{hi(f'{avg_val:.0f}', '#475569')}."
            )
        elif delta_pct <= -15:
            sentences.append(
                f"{hi(cur_noun, '#4F46E5')}: {hi(f'{cur_total:,}', '#DC2626')} leads — "
                f"{hi(f'{abs(delta_pct):.0f}%', '#DC2626')} below the avg of "
                f"{hi(f'{avg_val:.0f}', '#475569')}."
            )
        else:
            sentences.append(
                f"{hi(cur_noun, '#4F46E5')}: {hi(f'{cur_total:,}', '#475569')} leads — "
                f"on par with avg of {hi(f'{avg_val:.0f}', '#475569')}."
            )
    else:
        sentences.append(
            f"{hi(cur_noun, '#4F46E5')}: {hi(f'{cur_total:,}', '#4F46E5')} leads."
        )

    # 2. Peak and low (only when they differ and both are > 0)
    if peak_val > 0 and peak_i != low_i:
        if peak_i == len(buckets) - 1:
            sentences.append(
                f"Highest {unit} in the window with {hi(f'{peak_val:,}', '#16A34A')} leads; "
                f"lowest prior was {hi(low_lbl, '#0F172A')} ({hi(f'{low_val:,}', '#DC2626')})."
            )
        elif low_i == len(buckets) - 1:
            sentences.append(
                f"Lowest {unit} in the window; "
                f"peak was {hi(peak_lbl, '#16A34A')} at {hi(f'{peak_val:,}', '#16A34A')} leads."
            )
        else:
            sentences.append(
                f"Peak: {hi(peak_lbl, '#16A34A')} ({hi(f'{peak_val:,}', '#16A34A')} leads) · "
                f"Low: {hi(low_lbl, '#DC2626')} ({hi(f'{low_val:,}', '#DC2626')})."
            )

    # 3. Dominant actioned outcome
    if dominant_seg:
        sentences.append(
            f"{hi(dominant_seg, _SEG_CLR[dominant_seg])} leads the outcomes "
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
            severity = "nearly all leads are sitting untouched"
        elif untouched_pct >= 50:
            severity = "more than half the leads are untouched"
        elif untouched_pct >= 30:
            severity = "over a third of leads are untouched"
        else:
            severity = f"{untouched_pct:.0f}% of leads remain untouched"
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

    # ── Render ────────────────────────────────────────────────────────────────
    items_html = "".join(
        f"<div style='padding:3px 0 3px 8px;border-left:2px solid #E2E8F0;"
        f"margin-bottom:4px;font-size:10px;color:#334155;line-height:1.45;'>"
        f"{s}</div>"
        for s in sentences
    )

    return f"<div style='font-size:10px;line-height:1.5;'>{items_html}</div>"


# ── Main render function ───────────────────────────────────────────────────────

def render_overview_dashboard(
    db_path: Path,
    channel_names: dict[str, str],
    bucket_to_stage: dict[str, str],
) -> None:
    """
    Render the Analytics Console overview screen.

    Args:
        db_path:        Path to ifb_point.db
        channel_names:  {code: friendly_name} mapping
        bucket_to_stage: {api_bucket_key: stage_label} mapping
    """
    st.markdown(_OVERVIEW_CSS, unsafe_allow_html=True)

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

    df = _load_df(str(db_path)).copy()
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

    # ── A TOPBAR ──────────────────────────────────────────────────────────────
    tb1, tb2 = st.columns([8, 1.1])
    with tb1:
        st.markdown(
            "<div style='font-size:19px;font-weight:800;color:#0F172A;line-height:1.1;"
            "letter-spacing:-0.3px;'>📊 IFB Points "
            "<span style='color:#6366F1;'>·</span> Analytics Console</div>",
            unsafe_allow_html=True,
        )
    with tb2:
        if st.button("Sign Out", use_container_width=True):
            st.session_state["_authed"] = False
            st.query_params.clear()
            st.rerun()

    st.divider()

    # ── Two-pane: C RAIL | main ────────────────────────────────────────────────
    with st.container(key="two_pane"):
        rail, main = st.columns([1.85, 8.15], gap="medium")

        with rail:
            # ── Search + buttons sit OUTSIDE the scroll area so they align
            # horizontally with the KPI row in the main column.
            # Scroll list height = total right-side height minus the header area.
            # Right side: KPI(≈78) + 3×section(198) + gaps(≈30) ≈ 672px
            # Rail header (search + buttons): ≈78px → list height ≈ 634px
            _LIST_H = 634

            if "_ov_sel" not in st.session_state:
                st.session_state["_ov_sel"] = set()

            # Clear flag must be applied before the widget is instantiated
            if st.session_state.pop("_ov_search_clear", False):
                st.session_state["_ov_search"] = ""

            _prev_q = st.session_state.get("_ov_prev_q", "")

            # ── Search box (aligns with KPI row) ──────────────────────────────
            _q = st.text_input(
                "s", placeholder="🔍 Search IFB Point or Code…",
                label_visibility="collapsed", key="_ov_search",
            ).strip().lower()

            if _q != _prev_q:
                st.session_state["_ov_prev_q"] = _q
                st.session_state["_ov_sel"] = set()
                for _c in _codes:
                    st.session_state[f"cb_{_c}"] = False

            # ── All / Clear buttons (aligns with KPI row) ─────────────────────
            qa1, qa2 = st.columns(2, gap="small")
            with qa1:
                if st.button("✅ All", use_container_width=True, key="_ov_selall"):
                    _visible_now = [c for c in _codes
                                    if not _q
                                    or _q in channel_names.get(c, str(c)).lower()
                                    or _q in str(c).lower()]
                    if _q:
                        st.session_state["_ov_sel"] = set(_visible_now)
                        for _c in _codes:
                            st.session_state[f"cb_{_c}"] = _c in st.session_state["_ov_sel"]
                    else:
                        st.session_state["_ov_sel"]    = set()
                        st.session_state["_ov_prev_q"] = ""
                        for _c in _codes:
                            st.session_state[f"cb_{_c}"] = False
                    st.rerun()
            with qa2:
                if st.button("✖ Clear", use_container_width=True, key="_ov_clr"):
                    st.session_state["_ov_search_clear"] = True
                    st.session_state["_ov_prev_q"] = ""
                    st.session_state["_ov_sel"] = set()
                    for _c in _codes:
                        st.session_state[f"cb_{_c}"] = False
                    st.rerun()

            # ── Scrollable checkbox list ───────────────────────────────────────
            _visible = [c for c in _codes
                        if not _q
                        or _q in channel_names.get(c, str(c)).lower()
                        or _q in str(c).lower()]

            with st.container(height=_LIST_H, border=False, key="c_container"):
                for code in _visible:
                    name = channel_names.get(code, code)
                    was = code in st.session_state["_ov_sel"]
                    now = st.checkbox(name, value=was, key=f"cb_{code}")
                    if now != was:
                        if now:
                            st.session_state["_ov_sel"].add(code)
                        else:
                            st.session_state["_ov_sel"].discard(code)

            selected_set = st.session_state["_ov_sel"]

            if selected_set:
                scope_codes = selected_set
                scope_df    = df[df["ifb_point"].isin(scope_codes)]
                n = len(selected_set)
                scope_label = f"{n} point{'s' if n != 1 else ''} selected"
            else:
                scope_codes = set(_codes)
                scope_df    = df
                scope_label = f"All {len(_codes)} points"

            st.markdown(
                f"<div class='scope-badge'>⚡ {scope_label}</div>",
                unsafe_allow_html=True,
            )

        # ── MAIN: F KPI + G charts ─────────────────────────────────────────────────
        with main:
            total_leads = len(scope_df)
            contacted   = int((scope_df["status"] == "Contacted").sum())
            not_cont    = int((scope_df["status"] == "Not Contacted").sum())
            rnr         = int((scope_df["status"] == "RnR").sum())

            def _pct(n: int) -> float:
                return (n / total_leads * 100) if total_leads else 0.0

            # F — KPI ROW  (bordered container kept for spacing; border hidden via CSS)
            with st.container(border=True, key="kpi_row"):
                kc1, kc2, kc3, kc4, kc5 = st.columns(5, gap="small")
                _kpi_card(kc1, "IFB Points",    len(scope_codes))
                _kpi_card(kc2, "Total Leads",   total_leads)
                _kpi_card(kc3, "Contacted",     contacted, pct=_pct(contacted))
                _kpi_card(kc4, "Not Contacted", not_cont,  pct=_pct(not_cont))
                _kpi_card(kc5, "RnR",           rnr,       pct=_pct(rnr))

            # G — CHART ROWS  (colour-coded per time bucket)
            #   Day  → last 7 days · Week → last 4 weeks · Month → last 6 months
            _section_colors = {
                "day":   ("#6366F1", "#EEF2FF"),   # indigo
                "week":  ("#0891B2", "#ECFEFF"),   # cyan
                "month": ("#7C3AED", "#F5F3FF"),   # violet
            }
            _freq = {"day": "D", "week": "W", "month": "M"}

            # Inject per-segment circle CSS (once, before the loop)
            def _seg_css_key(period: str, seg: str) -> str:
                return f"cb_{period}_{seg.lower().replace(' ', '_')}"

            _circle_css = "<style>"
            for period_name in ("day", "week", "month"):
                for seg, color in _MK_SEGMENTS:
                    k = _seg_css_key(period_name, seg)
                    _circle_css += f"""
  .st-key-{k} [data-baseweb="checkbox"] > span:first-child {{
    border-radius:50% !important;
    border-color:{color} !important;
    width:13px !important; height:13px !important;
  }}
  .st-key-{k}:has(input:checked) [data-baseweb="checkbox"] > span:first-child {{
    background:{color} !important;
    border-color:{color} !important;
  }}"""
            _circle_css += "</style>"
            st.markdown(_circle_css, unsafe_allow_html=True)

            for title, period, n in [
                ("📅  Day Wise — Last 7 Days",    "day",   7),
                ("📆  Week Wise — Last 4 Weeks",  "week",  4),
                ("🗓️  Month Wise — Last 6 Months","month", 6),
            ]:
                accent, _ = _section_colors[period]
                agg = _bucket_aggregate(scope_df, _freq[period], n)
                st.markdown(
                    f"<div style='font-size:9.5px;font-weight:800;color:{accent};"
                    f"text-transform:uppercase;letter-spacing:0.7px;"
                    f"padding-left:3px;margin-bottom:1px;'>{title}</div>",
                    unsafe_allow_html=True,
                )
                buckets = _time_buckets(scope_df, period, n)
                # Pre-compute visible_segs before entering the container
                visible_segs = set()
                for seg, _ in _MK_SEGMENTS:
                    _key = _seg_css_key(period, seg)
                    if _key not in st.session_state:
                        st.session_state[_key] = True
                    if st.session_state[_key]:
                        visible_segs.add(seg)

                with st.container(border=True, key=f"sec_{period}"):
                    cb_wrap, cb_hint = st.columns([6.5, 3.5], gap="small")
                    with cb_wrap:
                        cb_cols = st.columns(len(_MK_SEGMENTS), gap="small")
                        for (seg, color), cb_col in zip(_MK_SEGMENTS, cb_cols):
                            _key = _seg_css_key(period, seg)
                            checked = cb_col.checkbox(
                                seg, value=st.session_state.get(_key, True), key=_key
                            )
                            if checked:
                                visible_segs.add(seg)
                            else:
                                visible_segs.discard(seg)

                    with cb_hint:
                        st.markdown(
                            "<div style='display:flex;align-items:center;height:100%;"
                            "padding-top:2px;'>"
                            "<span style='font-size:9.5px;color:#94A3B8;font-style:italic;"
                            "line-height:1.4;'>"
                            "👈 Click a circle to filter the chart view"
                            "</span></div>",
                            unsafe_allow_html=True,
                        )

                    # Chart and insights now start at the same vertical position
                    cg1, cg2 = st.columns([6.5, 3.5], gap="small")
                    with cg1:
                        st.plotly_chart(
                            _marimekko(buckets, visible_segs=visible_segs),
                            use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"mk3_{period}",
                        )
                    with cg2:
                        st.markdown(
                            f"<div style='background:#FFFFFF;border-left:4px solid {accent};"
                            f"border-radius:8px;padding:8px 11px;"
                            f"height:158px;overflow-y:auto;box-sizing:border-box;'>"
                            f"{_insights(buckets, period)}</div>",
                            unsafe_allow_html=True,
                        )
