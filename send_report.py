"""
IFB Follow-Up Daily Email Report — Central Login
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
RECIPIENTS     = ["vibhash_kumar@ifbglobal.com"]
DB_PATH        = "ifb_point.db"

# ── Load ──────────────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql("SELECT ifb_point, lead_date, status FROM api_leads", conn)
    conn.close()
    df["lead_dt"] = pd.to_datetime(df["lead_date"], format="%d-%m-%Y", errors="coerce")
    df["status"]  = df["status"].fillna("").replace("", "Pending")
    return df

# ── KPI helpers ───────────────────────────────────────────────────────────────

def kpis(df):
    total     = len(df)
    contacted = int((df["status"] == "Contacted").sum())
    rnr       = int((df["status"] == "RnR").sum())
    not_cont  = total - contacted - rnr
    return total, contacted, not_cont, rnr

def pct(n, total):
    return f"{round(n / total * 100)}%" if total else "0%"

# ── Insights ──────────────────────────────────────────────────────────────────

def day_insights(df, today):
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
    _, cont, nc, rnr = kpis(t_df)
    dir_w  = f"+{delta}% above" if delta >= 0 else f"{abs(delta)}% below"
    lines  = [
        (f"&#x1F4C8; <strong>{window:,}</strong> total follow ups over the last 7 days.",                          "#0369A1"),
        (f"&#x1F4CA; Today&#39;s <strong>{tc:,}</strong> follow ups is <strong>{dir_w}</strong> the 6-day average of <strong>{avg:,}</strong>.", "#334155"),
        (f"&#x1F3C6; <strong>Peak:</strong> {peak[0].strftime('%d %b')} with <strong>{peak[1]:,}</strong> follow ups.", "#334155"),
        (f"&#x1F4C9; <strong>Low:</strong> {low[0].strftime('%d %b')} with <strong>{low[1]:,}</strong> follow ups.",   "#334155"),
        (f"&#x2705; Contact rate today: <strong style='color:#16A34A'>{pct(cont, tc)}</strong> ({cont:,} Contacted).", "#16A34A"),
    ]
    if tc and (nc / tc * 100) >= 20:
        lines.append((f"&#x1F6AB; <strong style='color:#DC2626'>{nc:,} Not Contacted</strong> today &mdash; needs follow-up action.", "#DC2626"))
    if rnr:
        u = "follow up" if rnr == 1 else "follow ups"
        lines.append((f"&#x1F501; <strong style='color:#D97706'>{rnr} RnR</strong> {u} pending callback today.", "#D97706"))
    return lines

def week_insights(df, today):
    weeks = []
    for i in range(3, -1, -1):
        we = today - pd.Timedelta(weeks=i)
        ws = we - pd.Timedelta(days=6)
        sub = df[(df["lead_dt"].dt.normalize() >= ws) & (df["lead_dt"].dt.normalize() <= we)]
        weeks.append((ws.strftime("%d %b"), we.strftime("%d %b"), len(sub)))
    window   = sum(w[2] for w in weeks)
    prior    = [w[2] for w in weeks[:-1] if w[2] > 0]
    avg      = round(sum(prior) / len(prior)) if prior else 0
    this_w   = weeks[-1][2]
    delta    = round((this_w - avg) / avg * 100) if avg else 0
    peak     = max(weeks, key=lambda w: w[2])
    low      = min((w for w in weeks if w[2] > 0), key=lambda w: w[2], default=weeks[0])
    dir_w    = f"+{delta}% above" if delta >= 0 else f"{abs(delta)}% below"
    all_cont = int((df["status"] == "Contacted").sum())
    lines = [
        (f"&#x1F4C8; <strong>{window:,}</strong> total follow ups across the last 4 weeks.",                                            "#0369A1"),
        (f"&#x1F4CA; This week (<strong>{this_w:,}</strong>) is <strong>{dir_w}</strong> the 3-week average of <strong>{avg:,}</strong>.", "#334155"),
        (f"&#x1F3C6; <strong>Peak week:</strong> {peak[0]} &ndash; {peak[1]} with <strong>{peak[2]:,}</strong> follow ups.",             "#334155"),
        (f"&#x1F4C9; <strong>Low week:</strong> {low[0]} &ndash; {low[1]} with <strong>{low[2]:,}</strong> follow ups.",                 "#334155"),
        (f"&#x2705; Overall contact rate (4 weeks): <strong style='color:#16A34A'>{pct(all_cont, len(df))}</strong>.",                   "#16A34A"),
    ]
    all_rnr = int((df["status"] == "RnR").sum())
    if all_rnr:
        u = "follow up" if all_rnr == 1 else "follow ups"
        lines.append((f"&#x1F501; <strong style='color:#D97706'>{all_rnr} RnR</strong> {u} pending across 4 weeks.", "#D97706"))
    return lines

def month_insights(df, today):
    months = []
    for i in range(5, -1, -1):
        ms  = today.replace(day=1) - pd.DateOffset(months=i)
        me  = ms + pd.DateOffset(months=1)
        sub = df[(df["lead_dt"] >= ms) & (df["lead_dt"] < me)]
        months.append((ms.strftime("%b %Y"), len(sub)))
    window   = sum(m[1] for m in months)
    prior    = [m[1] for m in months[:-1] if m[1] > 0]
    avg      = round(sum(prior) / len(prior)) if prior else 0
    this_m   = months[-1][1]
    delta    = round((this_m - avg) / avg * 100) if avg else 0
    peak     = max(months, key=lambda m: m[1])
    low      = min((m for m in months if m[1] > 0), key=lambda m: m[1], default=months[0])
    dir_w    = f"+{delta}% above" if delta >= 0 else f"{abs(delta)}% below"
    all_cont = int((df["status"] == "Contacted").sum())
    lines = [
        (f"&#x1F4C8; <strong>{window:,}</strong> total follow ups over the last 6 months.",                                                    "#0369A1"),
        (f"&#x1F4CA; {months[-1][0]} (<strong>{this_m:,}</strong>) is <strong>{dir_w}</strong> the 5-month average of <strong>{avg:,}</strong>.", "#334155"),
        (f"&#x1F3C6; <strong>Peak month:</strong> {peak[0]} with <strong>{peak[1]:,}</strong> follow ups.",                                    "#334155"),
        (f"&#x1F4C9; <strong>Low month:</strong> {low[0]} with <strong>{low[1]:,}</strong> follow ups.",                                       "#334155"),
        (f"&#x2705; Overall contact rate (6 months): <strong style='color:#16A34A'>{pct(all_cont, len(df))}</strong>.",                        "#16A34A"),
    ]
    return lines

# ── HTML ──────────────────────────────────────────────────────────────────────

def kpi_card(label, icon, value, color, bg, border):
    return f"""<td width="25%" style="padding:0 5px 0 0;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"
    style="background:{bg};border:1px solid {border};border-top:3px solid {color};
           border-radius:8px;mso-border-alt:none;">
    <tr><td align="center" style="padding:14px 10px 12px;">
      <div style="font-size:22px;line-height:1;">{icon}</div>
      <div style="font-size:9px;font-weight:700;color:#64748B;text-transform:uppercase;
                  letter-spacing:0.6px;margin-top:7px;line-height:1.5;">{label}</div>
      <div style="font-size:28px;font-weight:800;color:{color};margin-top:7px;line-height:1;">{value:,}</div>
    </td></tr>
  </table>
</td>"""

def insight_block(lines):
    rows = ""
    for text, _ in lines:
        rows += f"""<tr>
  <td style="padding:7px 0;font-size:12px;color:#334155;line-height:1.65;
             border-bottom:1px solid #F1F5F9;">{text}</td>
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

def build_html(df):
    today     = pd.Timestamp(date.today())
    today_str = date.today().strftime("%d %b %Y")
    today_day = date.today().strftime("%A")

    t_df = df[df["lead_dt"].dt.normalize() == today]
    t_total, t_cont, t_nc, t_rnr = kpis(t_df)
    total_pts  = df["ifb_point"].nunique()
    active_pts = df[df["status"].isin(["Contacted", "RnR"])]["ifb_point"].nunique()

    day7_start  = today - pd.Timedelta(days=6)
    wk4_start   = today - pd.Timedelta(weeks=4)
    mo6_start   = today.replace(day=1) - pd.DateOffset(months=5)

    df_7d = df[df["lead_dt"].dt.normalize() >= day7_start]
    df_4w = df[df["lead_dt"].dt.normalize() >= wk4_start]
    df_6m = df[df["lead_dt"] >= mo6_start]

    d_lines = day_insights(df_7d, today)
    w_lines = week_insights(df_4w, today)
    m_lines = month_insights(df_6m, today)

    d_range = f"{day7_start.strftime('%d %b')} &ndash; {today_str}"
    w_range = f"{(today - pd.Timedelta(weeks=4)).strftime('%d %b')} &ndash; {today_str}"
    m_range = f"{mo6_start.strftime('%b %Y')} &ndash; {today.strftime('%b %Y')}"

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

<!-- ── OUTER CARD ── -->
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
            <div style="font-size:11px;color:#7BADD8;margin-top:3px;">
              Follow-Up Control Tower &mdash; Central Report
            </div>
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
                       padding:3px 8px;border-radius:3px;letter-spacing:0.5px;">CENTRAL</span>
          &nbsp;&nbsp;
          <span style="font-size:13px;font-weight:700;color:#0D3567;">All IFB Points</span>
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
      Hi, here is the central follow-up summary for
      <strong style="color:#0D3567;">today, {today_str}</strong> across all IFB Points.
    </p>

    <!-- TODAY SECTION TITLE -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
      style="margin-bottom:12px;border-left:4px solid #0D3567;">
      <tr><td style="padding-left:12px;font-size:10px;font-weight:700;color:#0D3567;
                     text-transform:uppercase;letter-spacing:0.8px;">
        &#x1F4C5;&nbsp; Today&#39;s Performance
      </td></tr>
    </table>

    <!-- KPI CARDS -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
      <tr>
        {kpi_card("Total Follow Up",  "&#x1F465;", t_total, "#0EA5E9", "#F0F9FF", "#BAE6FD")}
        {kpi_card("Contacted",        "&#x2705;",  t_cont,  "#16A34A", "#F0FDF4", "#BBF7D0")}
        {kpi_card("Not Contacted",    "&#x1F6AB;", t_nc,    "#DC2626", "#FEF2F2", "#FECACA")}
        {kpi_card("RnR",              "&#x1F501;", t_rnr,   "#D97706", "#FFFBEB", "#FDE68A")}
      </tr>
    </table>

    <!-- DIVIDER -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:4px;">
      <tr><td style="height:1px;background:#E2E8F0;font-size:0;">&nbsp;</td></tr>
    </table>

    <!-- DAY WISE -->
    {section_header("&#x1F4C5;", "Day Wise &mdash; Last 7 Days", d_range, "#0EA5E9")}
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:14px 16px;">
        {insight_block(d_lines)}
      </td></tr>
    </table>

    <!-- WEEK WISE -->
    {section_header("&#x1F4C6;", "Week Wise &mdash; Last 4 Weeks", w_range, "#16A34A")}
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;padding:14px 16px;">
        {insight_block(w_lines)}
      </td></tr>
    </table>

    <!-- MONTH WISE -->
    {section_header("&#x1F5D3;", "Month Wise &mdash; Last 6 Months", m_range, "#D97706")}
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">
      <tr><td style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:8px;padding:14px 16px;">
        {insight_block(m_lines)}
      </td></tr>
    </table>

  </td></tr>

  <!-- FOOTER -->
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
<!-- /OUTER CARD -->

</td></tr></table>
</body>
</html>"""

# ── Send ──────────────────────────────────────────────────────────────────────

def send_report():
    df      = load_data()
    html    = build_html(df)
    subject = f"IFB Follow-Up Daily Report — {date.today().strftime('%d %b %Y')}"

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{MAIL_FROM_NAME} <{MAIL_FROM}>"
    msg["To"]      = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_FROM, RECIPIENTS, msg.as_string())

    print(f"[OK] Report sent to {RECIPIENTS} — {date.today().strftime('%d %b %Y')}")


if __name__ == "__main__":
    send_report()
