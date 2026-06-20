"""
IFB Follow-Up Daily Email Report
- Personal reports → each user in login.db mapped to their IFB Points via login_mapping.db
- Central report   → all IFB Points → sent to fixed admin list
Run via cron: 30 2 * * * cd /path/to/dashboard && python send_report.py
"""

import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

MAIL_SERVER    = "smtp.cloudzimail.com"
MAIL_PORT      = 587
MAIL_USERNAME  = "s_aswin@ifbglobal.com"
MAIL_PASSWORD  = "#Ifb@2026"
MAIL_FROM      = "s_aswin@ifbglobal.com"
MAIL_FROM_NAME = "IFB Follow-Up Dashboard"

DB_PATH          = "ifb_point.db"
LOGIN_DB         = "login.db"
LOGIN_MAPPING_DB = "login_mapping.db"

# Central report recipients (all IFB Points scope)
CENTRAL_RECIPIENTS = [
    "rajat_paul@ifbglobal.com",
    "vibhash_kumar@ifbglobal.com",
    "s_aswin@ifbglobal.com",
    "prateek_bharadwaj@ifbglobal.com",
    "nayana_bhati@ifbglobal.com",
    "vijaykumar_khote@ifbglobal.com"
]

# ─────────────────────────────────────────────────────────────────────────────
# ROUTING MODE — single switch that controls who receives the mails
# ─────────────────────────────────────────────────────────────────────────────
#  TEST MODE  → TEST_REDIRECT_TO = "<your email>"
#               ALL 41 mails land in this one inbox. Nobody else is disturbed.
#               Use this while reviewing the content with your manager.
#
#  LIVE MODE  → TEST_REDIRECT_TO = None
#               Each of the 40 users gets their OWN personal report
#               and the 4 admins get the CENTRAL report.
#               Change this one line to switch over — no other code changes
#               needed.
# ─────────────────────────────────────────────────────────────────────────────
# TEST_REDIRECT_TO = "s_aswin@ifbglobal.com"     # ← TEST MODE (current)
TEST_REDIRECT_TO = None                       # ← LIVE MODE (uncomment to go live)

# ── Load ──────────────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql("SELECT ifb_point, lead_date, status, interested FROM api_leads", conn)
    conn.close()
    df["lead_dt"]    = pd.to_datetime(df["lead_date"], format="%d-%m-%Y", errors="coerce")
    df["status"]     = df["status"].fillna("").replace("", "Pending")
    df["interested"] = df["interested"].fillna("")
    df["ifb_point"]  = df["ifb_point"].astype(str)
    return df


def load_user_mappings() -> dict[str, dict]:
    """Return {email: {"name": str, "points": set[str]}} for every login.db user
    that has at least one IFB Point mapping.

    Mirrors streamlit_app._get_allowed_codes: checks Retail Email_ID first
    (per-point owner / store contact), falls back to Email_ID (territory manager).
    Both columns are queried — overlapping points get deduplicated via set union.
    centrallogin is excluded (not a real email)."""
    conn = sqlite3.connect(LOGIN_DB)
    emails = [r[0] for r in conn.execute("SELECT email FROM users").fetchall()
              if r[0] and "@" in r[0]]
    conn.close()

    mapping: dict[str, dict] = {}
    with sqlite3.connect(LOGIN_MAPPING_DB) as conn:
        for email in emails:
            e = email.strip().lower()

            # Retail Email_ID match — per-point retail contact
            retail_rows = conn.execute(
                'SELECT IFBpoint_id, Name FROM login_mapping '
                'WHERE LOWER("Retail Email_ID")=?',
                (e,),
            ).fetchall()

            # Email_ID match — territory manager
            mgr_rows = conn.execute(
                "SELECT IFBpoint_id, Name FROM login_mapping "
                "WHERE LOWER(Email_ID)=?",
                (e,),
            ).fetchall()

            points = {str(r[0]) for r in retail_rows + mgr_rows if r[0]}
            if not points:
                continue

            # Name column refers to the territory manager (Email_ID owner).
            # Use it only when this email matches via Email_ID; otherwise derive
            # a readable name from the email prefix.
            name = next((r[1] for r in mgr_rows if r[1]), "")
            if not name:
                name = email.split("@")[0].replace("_", " ").replace(".", " ").title()

            mapping[email] = {"name": name, "points": points}

    return mapping


# ── KPI helpers ───────────────────────────────────────────────────────────────

def kpis(df):
    total           = len(df)
    contacted       = int((df["status"] == "Contacted").sum())
    rnr             = int((df["status"] == "RnR").sum())
    not_reachable   = int((df["status"] == "Not Reachable").sum())
    not_cont        = total - contacted - rnr - not_reachable
    calls_attempted = contacted + rnr + not_reachable
    interested_cnt  = int((df["interested"] == "Interested").sum()) if "interested" in df.columns else 0
    return total, contacted, not_cont, rnr, not_reachable, calls_attempted, interested_cnt

def pct(n, total):
    return f"{round(n / total * 100)}%" if total else "0%"

# ── Insights ──────────────────────────────────────────────────────────────────

def day_insights(df, today, total_pts=0):
    days   = [today - pd.Timedelta(days=i) for i in range(6, -1, -1)]
    totals = [len(df[df["lead_dt"].dt.normalize() == d]) for d in days]
    window = sum(totals)
    prior  = [t for t in totals[:-1] if t > 0]
    avg    = round(sum(prior) / len(prior)) if prior else 0
    tc     = totals[-1]
    delta  = round((tc - avg) / avg * 100) if avg else 0
    nz     = [(d, t) for d, t in zip(days, totals) if t > 0]
    peak   = max(nz, key=lambda x: x[1], default=(today, 0))
    low    = min(nz, key=lambda x: x[1], default=(today, 0))
    t_df   = df[df["lead_dt"].dt.normalize() == today]
    _, cont, nc, rnr, not_reach, t_ca, _ = kpis(t_df)
    dir_w  = f"+{delta}% above" if delta >= 0 else f"{abs(delta)}% below"
    lines  = [
        (f"&#x2197; <strong>{window:,}</strong> total follow ups over the last 7 days.",                          "#0369A1"),
        (f"&#x25BA; Today&#39;s <strong>{tc:,}</strong> follow ups is <strong>{dir_w}</strong> the 6-day average of <strong>{avg:,}</strong>.", "#334155"),
        (f"&#x25B2; <strong>Peak:</strong> {peak[0].strftime('%d %b')} with <strong>{peak[1]:,}</strong> follow ups.", "#334155"),
        (f"&#x25BC; <strong>Low:</strong> {low[0].strftime('%d %b')} with <strong>{low[1]:,}</strong> follow ups.",   "#334155"),
        (f"&#x2714; Calls Connected today: <strong style='color:#16A34A'>{pct(cont, tc)}</strong> ({cont:,} calls connected).", "#16A34A"),
        (f"&#x260E; Calls Attempted today: <strong style='color:#D97706'>{t_ca:,} ({pct(t_ca, tc)})</strong> "
         f"(Connected {cont:,} + RnR {rnr:,} + Not Reachable {not_reach:,}).", "#D97706"),
    ]
    if tc and (nc / tc * 100) >= 20:
        lines.append((f"&#x2716; <strong style='color:#DC2626'>{nc:,} ({pct(nc, tc)})</strong> Not Contacted today &mdash; needs follow-up action.", "#DC2626"))
    if rnr:
        u = "follow up" if rnr == 1 else "follow ups"
        lines.append((f"&#x21BA; <strong style='color:#D97706'>{rnr} RnR</strong> {u} pending callback today.", "#D97706"))
    if total_pts:
        active_pts = len(set(t_df[t_df["status"].isin(["Contacted", "RnR", "Not Reachable"])]["ifb_point"].unique()))
        no_act     = total_pts - active_pts
        no_act_pct = round(no_act / total_pts * 100) if total_pts else 0
        lines.append((
            f"&#x25A0; Out of total <strong>{total_pts}</strong> IFB Points, "
            f"<strong style='color:#DC2626'>{no_act}</strong> "
            f"(<strong style='color:#DC2626'>{no_act_pct}%</strong>) "
            f"IFB Points have taken no action today.",
            "#DC2626",
        ))
    return lines

def week_insights(df, today, total_pts=0):
    weeks = []
    for i in range(3, -1, -1):
        we = today - pd.Timedelta(weeks=i)
        ws = we - pd.Timedelta(days=6)
        sub = df[(df["lead_dt"].dt.normalize() >= ws) & (df["lead_dt"].dt.normalize() <= we)]
        weeks.append((ws, we, ws.strftime("%d %b"), we.strftime("%d %b"), len(sub)))
    window   = sum(w[4] for w in weeks)
    prior    = [w[4] for w in weeks[:-1] if w[4] > 0]
    avg      = round(sum(prior) / len(prior)) if prior else 0
    this_w   = weeks[-1][4]
    delta    = round((this_w - avg) / avg * 100) if avg else 0
    peak     = max(weeks, key=lambda w: w[4])
    low      = min((w for w in weeks if w[4] > 0), key=lambda w: w[4], default=weeks[0])
    dir_w    = f"+{delta}% above" if delta >= 0 else f"{abs(delta)}% below"
    all_cont = int((df["status"] == "Contacted").sum())
    lines = [
        (f"&#x2197; <strong>{window:,}</strong> total follow ups across the last 4 weeks.",                                              "#0369A1"),
        (f"&#x25BA; This week (<strong>{this_w:,}</strong>) is <strong>{dir_w}</strong> the 3-week average of <strong>{avg:,}</strong>.", "#334155"),
        (f"&#x25B2; <strong>Peak week:</strong> {peak[2]} &ndash; {peak[3]} with <strong>{peak[4]:,}</strong> follow ups.",              "#334155"),
        (f"&#x25BC; <strong>Low week:</strong> {low[2]} &ndash; {low[3]} with <strong>{low[4]:,}</strong> follow ups.",                  "#334155"),
        (f"&#x2714; Overall calls connected rate (4 weeks): <strong style='color:#16A34A'>{pct(all_cont, len(df))}</strong>.",           "#16A34A"),
    ]
    all_rnr = int((df["status"] == "RnR").sum())
    if all_rnr:
        u = "follow up" if all_rnr == 1 else "follow ups"
        lines.append((f"&#x21BA; <strong style='color:#D97706'>{all_rnr} RnR</strong> {u} pending across 4 weeks.", "#D97706"))
    if total_pts:
        cw_start, cw_end = weeks[-1][0], weeks[-1][1]
        cw_df = df[(df["lead_dt"].dt.normalize() >= cw_start) & (df["lead_dt"].dt.normalize() <= cw_end)]
        active_pts = len(set(cw_df[cw_df["status"].isin(["Contacted", "RnR", "Not Reachable"])]["ifb_point"].unique()))
        no_act     = total_pts - active_pts
        no_act_pct = round(no_act / total_pts * 100) if total_pts else 0
        lines.append((
            f"&#x25A0; Out of total <strong>{total_pts}</strong> IFB Points, "
            f"<strong style='color:#DC2626'>{no_act}</strong> "
            f"(<strong style='color:#DC2626'>{no_act_pct}%</strong>) "
            f"IFB Points have taken no action this week.",
            "#DC2626",
        ))
    return lines

def month_insights(df, today, total_pts=0):
    months = []
    for i in range(5, -1, -1):
        ms  = today.replace(day=1) - pd.DateOffset(months=i)
        me  = ms + pd.DateOffset(months=1)
        sub = df[(df["lead_dt"] >= ms) & (df["lead_dt"] < me)]
        months.append((ms, me, ms.strftime("%b %Y"), len(sub)))
    window   = sum(m[3] for m in months)
    prior    = [m[3] for m in months[:-1] if m[3] > 0]
    avg      = round(sum(prior) / len(prior)) if prior else 0
    this_m   = months[-1][3]
    delta    = round((this_m - avg) / avg * 100) if avg else 0
    peak     = max(months, key=lambda m: m[3])
    low      = min((m for m in months if m[3] > 0), key=lambda m: m[3], default=months[0])
    dir_w    = f"+{delta}% above" if delta >= 0 else f"{abs(delta)}% below"
    all_cont = int((df["status"] == "Contacted").sum())
    lines = [
        (f"&#x2197; <strong>{window:,}</strong> total follow ups over the last 6 months.",                                                       "#0369A1"),
        (f"&#x25BA; {months[-1][2]} (<strong>{this_m:,}</strong>) is <strong>{dir_w}</strong> the 5-month average of <strong>{avg:,}</strong>.", "#334155"),
        (f"&#x25B2; <strong>Peak month:</strong> {peak[2]} with <strong>{peak[3]:,}</strong> follow ups.",                                       "#334155"),
        (f"&#x25BC; <strong>Low month:</strong> {low[2]} with <strong>{low[3]:,}</strong> follow ups.",                                          "#334155"),
        (f"&#x2714; Overall calls connected rate (6 months): <strong style='color:#16A34A'>{pct(all_cont, len(df))}</strong>.",                  "#16A34A"),
    ]
    if total_pts:
        cm_start, cm_end = months[-1][0], months[-1][1]
        cm_df = df[(df["lead_dt"] >= cm_start) & (df["lead_dt"] < cm_end)]
        active_pts = len(set(cm_df[cm_df["status"].isin(["Contacted", "RnR", "Not Reachable"])]["ifb_point"].unique()))
        no_act     = total_pts - active_pts
        no_act_pct = round(no_act / total_pts * 100) if total_pts else 0
        lines.append((
            f"&#x25A0; Out of total <strong>{total_pts}</strong> IFB Points, "
            f"<strong style='color:#DC2626'>{no_act}</strong> "
            f"(<strong style='color:#DC2626'>{no_act_pct}%</strong>) "
            f"IFB Points have taken no action this month.",
            "#DC2626",
        ))
    return lines

# ── HTML ──────────────────────────────────────────────────────────────────────

def kpi_card(label, icon_html, value, color, bg, border):
    return f"""<td width="20%" style="padding:0 4px 0 0;vertical-align:top;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
    style="background:{bg};border:1px solid {border};border-top:3px solid {color};
           border-radius:8px;mso-border-alt:none;">
    <tr><td align="center" height="96"
      style="padding:10px 6px;vertical-align:middle;height:96px;">
      <div style="line-height:1;">{icon_html}</div>
      <div style="font-size:8px;font-weight:700;color:#64748B;text-transform:uppercase;
                  letter-spacing:0.4px;margin-top:6px;line-height:1.35;">{label}</div>
      <div style="font-size:24px;font-weight:800;color:{color};margin-top:6px;line-height:1;">{value:,}</div>
    </td></tr>
  </table>
</td>"""

def insight_block(lines):
    rows = ""
    for text, _ in lines:
        rows += f"""<tr>
  <td style="padding:7px 0;font-size:12px;color:#334155;line-height:1.65;
             border-bottom:1px solid #F1F5F9;
             font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',Arial,sans-serif;">{text}</td>
</tr>"""
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>"""

def section_header(icon_entity, title, date_range, color):
    return f"""<table width="100%" cellpadding="0" cellspacing="0" border="0"
  style="margin:20px 0 10px;border-left:4px solid {color};">
  <tr>
    <td style="padding-left:12px;">
      <span style="font-size:13px;font-weight:700;color:#0F172A;">{icon_entity}&nbsp;{title}</span>
      <span style="font-size:11px;color:#94A3B8;margin-left:8px;">{date_range}</span>
    </td>
  </tr>
</table>"""


def build_html(df: pd.DataFrame,
               recipient_name: str,
               scope_label: str,
               scope_sub_label: str,
               sub_header: str) -> str:
    today     = pd.Timestamp(date.today())
    today_str = date.today().strftime("%d %b %Y")
    today_day = date.today().strftime("%A")

    t_df = df[df["lead_dt"].dt.normalize() == today]
    t_total, t_cont, t_nc, t_rnr, t_not_reach, t_calls_attempted, t_interested = kpis(t_df)
    total_pts  = df["ifb_point"].nunique()
    active_pts = df[df["status"].isin(["Contacted", "RnR", "Not Reachable"])]["ifb_point"].nunique()

    day7_start  = today - pd.Timedelta(days=6)
    wk4_start   = today - pd.Timedelta(weeks=4)
    mo6_start   = today.replace(day=1) - pd.DateOffset(months=5)

    df_7d = df[df["lead_dt"].dt.normalize() >= day7_start]
    df_4w = df[df["lead_dt"].dt.normalize() >= wk4_start]
    df_6m = df[df["lead_dt"] >= mo6_start]

    d_lines = day_insights(df_7d, today, total_pts=total_pts)
    w_lines = week_insights(df_4w, today, total_pts=total_pts)
    m_lines = month_insights(df_6m, today, total_pts=total_pts)

    d_range = f"{day7_start.strftime('%d %b')} &ndash; {today_str}"
    w_range = f"{(today - pd.Timedelta(weeks=4)).strftime('%d %b')} &ndash; {today_str}"
    m_range = f"{mo6_start.strftime('%b %Y')} &ndash; {today.strftime('%b %Y')}"

    greet = f"Hi <strong style='color:#0D3567;'>{recipient_name}</strong>," if recipient_name else "Hi,"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IFB Follow-Up Daily Report</title>
</head>
<body style="margin:0;padding:0;background:#F1F5F9;">

<table width="100%" cellpadding="0" cellspacing="0" border="0"
  style="background:#F1F5F9;padding:24px 0;">
<tr><td align="center">

<table width="600" cellpadding="0" cellspacing="0" border="0"
  style="background:#FFFFFF;border-radius:10px;border:1px solid #E2E8F0;
         font-family:Arial,Helvetica,sans-serif;">

  <!-- HEADER -->
  <tr>
    <td style="background:#0D3567;border-radius:10px 10px 0 0;padding:20px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="vertical-align:middle;">
            <div style="font-size:16px;font-weight:700;color:#FFFFFF;line-height:1.3;">
              IFB Follow-Up Daily Report
            </div>
            <div style="font-size:11px;color:#7BADD8;margin-top:3px;">{sub_header}</div>
          </td>
          <td align="right" style="vertical-align:middle;">
            <div style="font-size:13px;font-weight:700;color:#DCE8F7;">{today_day}, {today_str}</div>
            <div style="font-size:10px;color:#7BADD8;margin-top:3px;">8:00 AM IST</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- BANNER -->
  <tr>
    <td style="background:#EBF2FB;padding:10px 28px;border-bottom:1px solid #C8DCF4;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="vertical-align:middle;">
          <span style="background:#0D3567;color:#FFFFFF;font-size:9px;font-weight:700;
                       padding:3px 8px;border-radius:3px;letter-spacing:0.5px;">{scope_label}</span>
          &nbsp;&nbsp;
          <span style="font-size:13px;font-weight:700;color:#0D3567;">{scope_sub_label}</span>
        </td>
        <td align="right" style="vertical-align:middle;font-size:11px;color:#5A7A9F;">
          {total_pts} Total &nbsp;&#124;&nbsp; {active_pts} Active Points
        </td>
      </tr></table>
    </td>
  </tr>

  <!-- BODY -->
  <tr><td style="padding:22px 28px 6px;">

    <p style="margin:0 0 20px;font-size:13px;color:#475569;line-height:1.7;">
      {greet} here is the follow-up summary for
      <strong style="color:#0D3567;">today, {today_str}</strong>.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0"
      style="margin-bottom:12px;border-left:4px solid #0D3567;">
      <tr><td style="padding-left:12px;font-size:10px;font-weight:700;color:#0D3567;
                     text-transform:uppercase;letter-spacing:0.8px;">
        &#x25A0;&nbsp; Today&#39;s Performance
      </td></tr>
    </table>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
      <tr>
        {kpi_card("Total Customers Allocated",
                  '<span style="font-size:20px;color:#0EA5E9;">&#x25CF;</span>',
                  t_total, "#0EA5E9", "#F0F9FF", "#BAE6FD")}
        {kpi_card("Calls Attempted",
                  '<span style="font-size:18px;color:#16A34A;">&#x2714;</span>',
                  t_calls_attempted, "#16A34A", "#F0FDF4", "#BBF7D0")}
        {kpi_card("Calls Connected",
                  '<span style="font-size:18px;color:#D97706;">&#x260E;</span>',
                  t_cont, "#D97706", "#FFFBEB", "#FDE68A")}
        {kpi_card("Interested Customers",
                  '<span style="font-size:18px;color:#7C3AED;">&#x2605;</span>',
                  t_interested, "#7C3AED", "#F5F3FF", "#DDD6FE")}
        {kpi_card("Not Contacted",
                  '<span style="font-size:18px;color:#DC2626;">&#x2716;</span>',
                  t_nc, "#DC2626", "#FEF2F2", "#FECACA")}
      </tr>
    </table>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:4px;">
      <tr><td style="height:1px;background:#E2E8F0;font-size:0;">&nbsp;</td></tr>
    </table>

    {section_header("&#x25C6;", "Day Wise &mdash; Last 7 Days", d_range, "#0EA5E9")}
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:14px 16px;">
        {insight_block(d_lines)}
      </td></tr>
    </table>

    {section_header("&#x25C6;", "Week Wise &mdash; Last 4 Weeks", w_range, "#16A34A")}
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:14px 16px;">
        {insight_block(w_lines)}
      </td></tr>
    </table>

    {section_header("&#x25C6;", "Month Wise &mdash; Last 6 Months", m_range, "#D97706")}
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">
      <tr><td style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;padding:14px 16px;">
        {insight_block(m_lines)}
      </td></tr>
    </table>

  </td></tr>

  <tr>
    <td style="background:#F8FAFC;border-top:1px solid #E2E8F0;
               border-radius:0 0 10px 10px;padding:16px 28px;text-align:center;">
      <p style="margin:0;font-size:10px;color:#94A3B8;line-height:1.9;">
        <strong style="color:#0D3567;">IFB Industries</strong>
        &mdash; Follow-Up Control Tower<br>
        This is an automated daily report. Please do not reply to this email.<br>
        <span style="color:#CBD5E1;">
          Generated by IFB Point Dashboard &bull; IT Team &bull; IFB Industries Ltd.
        </span>
      </p>
    </td>
  </tr>

</table>
</td></tr></table>
</body>
</html>"""


# ── Send ──────────────────────────────────────────────────────────────────────

def _send(server: smtplib.SMTP, html: str, to_addrs: list[str]) -> None:
    subject        = f"IFB Follow-Up Daily Report — {date.today().strftime('%d %b %Y')}"
    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg["To"]      = ", ".join(to_addrs)
    msg.attach(MIMEText(html, "html", "utf-8"))
    server.sendmail(MAIL_FROM, to_addrs, msg.as_string())


def send_report():
    df       = load_data()                # 5,925 follow-up rows from ifb_point.db
    mappings = load_user_mappings()       # 40 users  →  their assigned IFB Points

    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)

        sent, skipped = 0, 0

        # ═════════════════════════════════════════════════════════════════════
        # 1. PERSONAL REPORTS  →  one mail per user (40 in total)
        # ═════════════════════════════════════════════════════════════════════
        for email, info in mappings.items():
            points = info["points"]
            if not points:
                skipped += 1
                print(f"[SKIP] {email} — no IFB Points mapped")
                continue

            # Filter the master dataset down to just THIS user's IFB Points
            scoped = df[df["ifb_point"].isin(points)]

            # Build a personalised HTML body — addressed by name, scoped data
            html = build_html(
                scoped,
                recipient_name=info["name"] or email.split("@")[0].replace("_", " ").title(),
                scope_label="YOUR POINTS",
                scope_sub_label=f"{len(points)} IFB Point" + ("s" if len(points) != 1 else "") + " assigned to you",
                sub_header="Follow-Up Control Tower &mdash; Personal Report",
            )

            # ─── RECIPIENT ROUTING ────────────────────────────────────────────
            # In TEST mode  → redirect to TEST_REDIRECT_TO (s_aswin only)
            # In LIVE mode  → send to the actual user's email
            target = [TEST_REDIRECT_TO] if TEST_REDIRECT_TO else [email]
            # ──────────────────────────────────────────────────────────────────

            try:
                _send(server, html, target)
                sent += 1
                print(f"[OK]   {email} → {target[0]}  ({len(points)} points, {len(scoped)} leads)")
            except Exception as e:
                print(f"[FAIL] {email}: {e}")

        # ═════════════════════════════════════════════════════════════════════
        # 2. CENTRAL REPORT  →  one mail with ALL IFB Points
        #    Recipients in live mode: rajat_paul, vibhash_kumar, s_aswin,
        #                             prateek_bharadwaj  (CENTRAL_RECIPIENTS)
        # ═════════════════════════════════════════════════════════════════════
        html = build_html(
            df,
            recipient_name="Team",
            scope_label="CENTRAL",
            scope_sub_label="All IFB Points",
            sub_header="Follow-Up Control Tower &mdash; Central Report",
        )

        # ─── RECIPIENT ROUTING ────────────────────────────────────────────────
        # In TEST mode  → redirect to TEST_REDIRECT_TO (s_aswin only)
        # In LIVE mode  → broadcast to all 4 admins in CENTRAL_RECIPIENTS
        target = [TEST_REDIRECT_TO] if TEST_REDIRECT_TO else CENTRAL_RECIPIENTS
        # ──────────────────────────────────────────────────────────────────────

        try:
            _send(server, html, target)
            sent += 1
            print(f"[OK]   CENTRAL → {target}  ({df['ifb_point'].nunique()} points, {len(df)} leads)")
        except Exception as e:
            print(f"[FAIL] CENTRAL: {e}")

    print(f"\nSummary: {sent} sent, {skipped} skipped — {date.today().strftime('%d %b %Y')}")


if __name__ == "__main__":
    send_report()
