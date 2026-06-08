// Follow Up Control Tower — IFB Points Dashboard User Guide (DOCX)
// A complete, non-technical, user-perspective guide.

const path = require("path");
const fs = require("fs");

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  TabStopType, TabStopPosition,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber, PageBreak, ExternalHyperlink,
} = require("docx");

// ── helpers ─────────────────────────────────────────────────────────────────
const BRAND       = "4F46E5";
const BRAND_DARK  = "1E1B4B";
const BRAND_LIGHT = "EEF2FF";
const INK         = "0F172A";
const SLATE       = "475569";
const MUTED       = "94A3B8";
const LINE        = "E0E7FF";
const GOOD        = "16A34A";
const BAD         = "DC2626";
const WARN        = "D97706";
const PURPLE      = "9333EA";

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 100, ...(opts.spacing || {}) },
    alignment: opts.alignment,
    children: [new TextRun({
      text, font: "Calibri",
      size: opts.size || 22, // 11pt
      bold: opts.bold, italic: opts.italic, color: opts.color,
    })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 160 },
    children: [new TextRun({ text, font: "Calibri", size: 36, bold: true, color: BRAND_DARK })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 260, after: 120 },
    children: [new TextRun({ text, font: "Calibri", size: 28, bold: true, color: BRAND })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 80 },
    children: [new TextRun({ text, font: "Calibri", size: 24, bold: true, color: INK })],
  });
}

function body(parts, opts = {}) {
  // parts: string OR array of {text, bold/italic/color/size}
  const runs = (Array.isArray(parts) ? parts : [{ text: parts }])
    .map(r => new TextRun({
      text: r.text,
      font: "Calibri",
      size: r.size || 22,
      bold: r.bold, italic: r.italic, color: r.color,
    }));
  return new Paragraph({
    spacing: { after: 120, line: 320 },
    alignment: opts.alignment,
    children: runs,
  });
}

function bullet(parts, level = 0) {
  const runs = (Array.isArray(parts) ? parts : [{ text: parts }])
    .map(r => new TextRun({
      text: r.text, font: "Calibri", size: 22,
      bold: r.bold, italic: r.italic, color: r.color,
    }));
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 80, line: 300 },
    children: runs,
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun({ text: " ", font: "Calibri", size: 18 })] });
}

function callout(title, lines, color = BRAND, bgColor = BRAND_LIGHT) {
  // single-cell table = callout box
  const cellParas = [];
  cellParas.push(new Paragraph({
    spacing: { after: 80 },
    children: [new TextRun({ text: title, font: "Calibri", size: 22, bold: true, color })],
  }));
  const linesArr = Array.isArray(lines) ? lines : [lines];
  linesArr.forEach(line => {
    const runs = (Array.isArray(line) ? line : [{ text: line }])
      .map(r => new TextRun({
        text: r.text, font: "Calibri", size: 21,
        bold: r.bold, italic: r.italic, color: r.color || INK,
      }));
    cellParas.push(new Paragraph({
      spacing: { after: 60, line: 280 },
      children: runs,
    }));
  });

  const border = { style: BorderStyle.SINGLE, size: 6, color };
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: 9360, type: WidthType.DXA },
        shading: { fill: bgColor, type: ShadingType.CLEAR, color: "auto" },
        borders: { top: border, bottom: border, left: border, right: border },
        margins: { top: 180, bottom: 180, left: 240, right: 240 },
        children: cellParas,
      })],
    })],
  });
}

function imagePlaceholder(label) {
  // a tall bordered placeholder cell saying "[ Insert screenshot ]"
  const border = { style: BorderStyle.DASHED, size: 8, color: BRAND };
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({
      height: { value: 2200, rule: "atLeast" },
      children: [new TableCell({
        width: { size: 9360, type: WidthType.DXA },
        verticalAlign: VerticalAlign.CENTER,
        shading: { fill: "F8FAFC", type: ShadingType.CLEAR, color: "auto" },
        borders: { top: border, bottom: border, left: border, right: border },
        margins: { top: 220, bottom: 220, left: 240, right: 240 },
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: 80 },
            children: [new TextRun({ text: "📷  Insert screenshot here", font: "Calibri", size: 26, bold: true, color: BRAND })],
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: label, font: "Calibri", size: 20, italic: true, color: SLATE })],
          }),
        ],
      })],
    })],
  });
}

function tableRow(cells, isHeader = false) {
  const headFill = BRAND;
  const headColor = "FFFFFF";
  return new TableRow({
    tableHeader: isHeader,
    children: cells.map(c => {
      const text = typeof c === "string" ? c : c.text;
      const width = typeof c === "object" && c.width ? c.width : null;
      const cellPara = new Paragraph({
        spacing: { after: 0, line: 280 },
        children: [new TextRun({
          text,
          font: "Calibri",
          size: isHeader ? 22 : 21,
          bold: isHeader || (typeof c === "object" && c.bold),
          color: isHeader ? headColor : INK,
        })],
      });
      return new TableCell({
        width: { size: width || 3120, type: WidthType.DXA },
        shading: isHeader
          ? { fill: headFill, type: ShadingType.CLEAR, color: "auto" }
          : { fill: "FFFFFF", type: ShadingType.CLEAR, color: "auto" },
        borders: {
          top:    { style: BorderStyle.SINGLE, size: 4, color: LINE },
          bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE },
          left:   { style: BorderStyle.SINGLE, size: 4, color: LINE },
          right:  { style: BorderStyle.SINGLE, size: 4, color: LINE },
        },
        margins: { top: 90, bottom: 90, left: 140, right: 140 },
        children: [cellPara],
      });
    }),
  });
}

function dataTable(headers, rows, widths) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      tableRow(headers.map((h, i) => ({ text: h, width: widths[i] })), true),
      ...rows.map(r => tableRow(r.map((c, i) => ({ text: c, width: widths[i] }))))
    ],
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

// ── Content ──────────────────────────────────────────────────────────────────
const children = [];

// ─── Cover ───
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 2400, after: 200 },
  children: [new TextRun({ text: "IFB POINTS", font: "Calibri", size: 28, bold: true, color: BRAND, characterSpacing: 60 })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [new TextRun({ text: "Follow Up Control Tower", font: "Calibri", size: 72, bold: true, color: BRAND_DARK })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 600 },
  children: [new TextRun({ text: "A complete, non-technical user guide", font: "Calibri", size: 32, italic: true, color: SLATE })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [new TextRun({ text: "Two views ·  One purpose", font: "Calibri", size: 24, bold: true, color: BRAND })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Sign In + Regional Overview     |     IFB Point Workspace", font: "Calibri", size: 22, color: SLATE })],
}));
children.push(spacer(), spacer(), spacer());
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Prepared for IFB Point owners & regional managers", font: "Calibri", size: 20, italic: true, color: MUTED })],
}));

children.push(pageBreak());

// ─── 1. Welcome / What this is ───
children.push(h1("1.  Welcome"));
children.push(body("This guide walks you through the IFB Points Follow-Up Dashboard from a user's point of view. It does not assume any technical background — only that you spend your day managing follow-ups for one or many IFB Points and want to be efficient about it."));
children.push(body([
  { text: "Two screens. ", bold: true },
  { text: "Sign in once, and you'll spend your time in just two screens — the " },
  { text: "Regional Overview", bold: true },
  { text: " (your home base) and the " },
  { text: "IFB Point Workspace", bold: true },
  { text: " (where you actually log calls). Everything else is a quiet helper." },
]));

children.push(h2("Why this dashboard exists"));
children.push(bullet([
  { text: "Nothing falls through the cracks.  ", bold: true, color: BRAND },
  { text: "Every customer due for a follow-up is automatically surfaced — today's, missed ones, and upcoming ones — without you having to chase a spreadsheet." },
]));
children.push(bullet([
  { text: "Your region in one glance.  ", bold: true, color: BRAND },
  { text: "Open the page and see how all your mapped IFB Points are doing — a single screen replaces three separate reports." },
]));
children.push(bullet([
  { text: "Faster updates.  ", bold: true, color: BRAND },
  { text: "Logging the outcome of a call is three clicks. The dialog only asks what's actually relevant." },
]));
children.push(bullet([
  { text: "Discipline, built in.  ", bold: true, color: BRAND },
  { text: "The system itself closes out customers who've stopped answering — so your worklist stays clean." },
]));
children.push(bullet([
  { text: "Plain-English explanations.  ", bold: true, color: BRAND },
  { text: "Charts come with auto-generated insights — no need to interpret a graph; the dashboard tells you what's going on." },
]));

children.push(pageBreak());

// ─── 2. How it's organised ───
children.push(h1("2.  How it's organised"));
children.push(body("The dashboard has two screens. You'll move between them naturally based on what you're doing right now."));

children.push(h2("Screen 1 — Sign In  +  Regional Overview"));
children.push(body("Your daily landing page. After signing in, you immediately see the health of every IFB Point in your scope — KPIs, a visual mix chart, three time lenses (Day / Week / Month), and an insights panel that explains what's happening."));

children.push(h2("Screen 2 — The IFB Point Workspace"));
children.push(body("Click on a specific IFB Point (or open the link with its code) and you land here. This is where the actual follow-up work happens — filter the customers, search for one, log a call outcome, see customer details."));

children.push(callout(
  "A clarifying note on terminology",
  [
    [
      { text: "Throughout this guide we say  ", italic: true },
      { text: "“IFB Points”", bold: true },
      { text: "  — not  ", italic: true },
      { text: "“franchise”", italic: true },
      { text: ", not  ", italic: true },
      { text: "“dealer”", italic: true },
      { text: ". Each IFB Point has its own unique code (e.g. 1014154) and its own name (e.g. ", italic: true },
      { text: "IFB Point City Mall", bold: true },
      { text: "). The system keeps these mapped to your login automatically.", italic: true },
    ]
  ],
  BRAND, BRAND_LIGHT
));

children.push(pageBreak());

// ─── 3. PART 1: Sign In + Regional Overview ───
children.push(new Paragraph({
  spacing: { before: 200, after: 60 },
  children: [new TextRun({ text: "PART ONE", font: "Calibri", size: 22, bold: true, color: BRAND, characterSpacing: 60 })],
}));
children.push(h1("3.  Sign In  &  Regional Overview"));

children.push(h2("3.1  Signing in"));
children.push(body("The very first screen you see when you open the dashboard."));
children.push(imagePlaceholder("01_login.png — the Sign In screen"));
children.push(spacer());

children.push(h3("What you do"));
children.push(body("Enter your IFB email and password and click  Sign In. The eye icon next to the password lets you peek at what you've typed — useful when the keyboard is misbehaving."));

children.push(h3("What happens behind it (the bit you don't need to think about)"));
children.push(body("The dashboard looks you up and figures out which IFB Points belong to your region, branch, and assignment. From that moment, only those points show up for you. You don't have to remember codes, set filters, or scope anything manually."));

children.push(h3("Why this matters"));
children.push(body([
  { text: "Your scope travels with you. ", bold: true },
  { text: "Whether you manage 4 IFB Points or 40, the system knows. You just see your slice — nothing else clutters the view." },
]));

children.push(callout(
  "If sign-in fails",
  [
    "A red banner appears just under the form: “Invalid email or password.” Re-check the email exactly as IT has it on record (including any dot). If it still won't work, IT can re-issue your credentials. Nothing in the dashboard is locked behind sign-in attempts — there's no lockout penalty."
  ],
  BAD, "FEE2E2"
));

children.push(pageBreak());

// ─── 3.2  Overview ───
children.push(h2("3.2  The Regional Overview Dashboard"));
children.push(body("Right after sign-in (and any time you click the dashboard title) you land here. It's a single screen that answers “how are my IFB Points doing right now?”"));

children.push(imagePlaceholder("Overview Dashboard — post-login landing"));
children.push(spacer());

children.push(h3("The four things on this screen"));
children.push(bullet([{ text: "Top:  ", bold: true }, { text: "Five KPI cards summarising your whole region." }]));
children.push(bullet([{ text: "Left:  ", bold: true }, { text: "A scrollable list of every IFB Point you manage, with a search box and All / Clear buttons." }]));
children.push(bullet([{ text: "Right (main area):  ", bold: true }, { text: "Three stacked sections — Day Wise (last 7 days), Week Wise (last 4 weeks), Month Wise (last 6 months). Each section has a chart + an insights panel." }]));
children.push(bullet([{ text: "Bottom edge:  ", bold: true }, { text: "A small line confirming the API sync — when the data was last refreshed and how many records loaded." }]));

children.push(pageBreak());

// 3.3 KPI strip
children.push(h2("3.3  The KPI strip — five numbers, one pulse"));
children.push(body("These five cards run across the top. They cover everything in your scope — i.e. all your mapped IFB Points, all stages, the full date range you've loaded."));

children.push(dataTable(
  ["KPI", "What it counts", "Why it matters"],
  [
    ["IFB Points",      "How many IFB Points fall under you",          "Your scope at a glance. If this number ever drops unexpectedly, IT has changed your mapping."],
    ["Total Follow Up", "Every open customer follow-up combined",      "The size of your book of work. Watch this trend — slow rise = healthy intake, sharp drop = something's wrong with sync."],
    ["Contacted",       "Customers your team has reached",             "Your productivity number. A higher count here means more conversations were had."],
    ["Not Contacted",   "Customers tried but couldn't be reached",     "If this climbs, your team is dialing but customers aren't picking up. Try different call windows."],
    ["RnR",             "Ring-no-Response — picked up but no answer",  "Customers screening calls. Each RnR is a soft no — schedule a different time."],
  ],
  [1800, 3360, 4200]
));

children.push(spacer());
children.push(callout(
  "Reading them together",
  [
    "Total Follow Up = Contacted + Not Contacted + RnR + still-untouched.",
    [
      { text: "If Not Contacted ", color: BAD, bold: true },
      { text: "is high, customers aren't picking up at all — adjust calling windows." },
    ],
    [
      { text: "If RnR ", color: WARN, bold: true },
      { text: "is high, customers are picking up but not engaging — try a different day or a shorter pitch." },
    ],
    [
      { text: "If Contacted ", color: GOOD, bold: true },
      { text: "is dominant but Interested is low (see per-Point view), the conversation works but the value isn't landing — review the script." },
    ],
  ],
  BRAND, BRAND_LIGHT
));

children.push(pageBreak());

// 3.4 IFB Points rail
children.push(h2("3.4  The IFB Points rail (left side)"));
children.push(body("This is your list of IFB Points. It's vertical, scrollable, and ticked-by-default to none — meaning by default the charts on the right show data for ALL your points combined."));

children.push(h3("Four controls, all you need to know"));
children.push(dataTable(
  ["Control", "What it does", "Impact on the charts"],
  [
    ["Search box (🔍)",   "Type any part of an IFB Point name OR its code (partial match, case-insensitive).", "Narrows the visible list. Typing also clears any current ticks — so you start the next selection fresh."],
    ["All  (✅)",          "If you've typed a search, ticks every result. If the search is empty, clears all ticks.", "Either focuses you onto the search results OR resets to “show everything in the charts”."],
    ["Clear  (✖)",        "Empties the search box AND unticks everything.",                                     "Quickest way back to a clean slate — charts go back to showing every point."],
    ["Checkboxes",         "Tick one or many IFB Points individually.",                                          "Charts and KPIs on the right re-compute for only the ticked points. Untick all = show everything again."],
  ],
  [1800, 4200, 3360]
));

children.push(pageBreak());

// 3.5 Marimekko / Mix Chart
children.push(h2("3.5  The Mix Chart"));
children.push(body("This is the headline visual on the right. Each column is a time period (a day, a week, or a month). The column's width shows how many follow-ups landed in that period; the colours inside show how those follow-ups ended up."));

children.push(imagePlaceholder("Marimekko / Mix chart from Day-Wise section"));
children.push(spacer());

children.push(h3("Reading the chart"));
children.push(bullet([{ text: "Width  ", bold: true }, { text: "(of a column) — the more follow-ups in that period, the fatter the column." }]));
children.push(bullet([{ text: "Height of each colour band  ", bold: true }, { text: "— the percentage of that period's follow-ups that ended in that outcome." }]));
children.push(bullet([{ text: "Hover  ", bold: true }, { text: "— mouse over any column to see the exact counts and percentages for all six outcomes." }]));
children.push(bullet([{ text: "Circles above the chart  ", bold: true }, { text: "— click any colour circle to hide or show that outcome on the chart. The chart re-balances in real time." }]));

children.push(h3("The six outcomes (and their colours)"));
children.push(dataTable(
  ["Colour", "Outcome", "Meaning"],
  [
    ["Green (dark)",  "Interested",     "Customer picked up AND was interested. The win path."],
    ["Purple",        "Not Interested", "Customer picked up but didn't want the product/service right now."],
    ["Green (light)", "Contacted",      "Customer picked up — but the caller hasn't yet logged whether they were interested."],
    ["Red",           "Not Contacted",  "We tried; customer didn't pick up."],
    ["Amber",         "RnR",            "Ring-no-Response — customer answered but didn't engage."],
    ["Grey",          "Untouched",      "Customer is still on the list but we haven't called yet."],
  ],
  [1800, 2100, 5460]
));

children.push(pageBreak());

// 3.6 Insights panel
children.push(h2("3.6  The Insights panel"));
children.push(body("To the right of each chart sits a small text box that reads like a colleague summarising what they see. It updates automatically based on the chart's data."));

children.push(imagePlaceholder("Insights panel — last 7 days"));
children.push(spacer());

children.push(h3("What the panel covers"));
children.push(bullet("Total follow-ups across the visible window."));
children.push(bullet("How today / this week / this month compares to the period's average (with a percentage delta)."));
children.push(bullet("Peak and low periods — automatically ignoring days with zero data, so a Sunday with no calls won't pretend to be the low."));
children.push(bullet("The dominant outcome — what most calls ended as."));
children.push(bullet("A warning if Not Contacted is above 20% — “worth a callback push”."));
children.push(bullet("Untouched share with friendly wording: “nearly all”, “more than half”, “over a third”."));
children.push(bullet("Interested rate, but only when it's healthy (≥10%) — otherwise the panel stays quiet."));
children.push(bullet("RnR callbacks still pending, with grammar-correct phrasing (“1 follow up” vs “8 follow ups”)."));

children.push(callout(
  "Why a written panel and not just another chart?",
  [
    "Charts show what changed; written sentences explain why it matters. The panel is meant for the 30-second “glance and act” moment — it's the difference between “Tuesday is shorter” and “Tuesday's call rate dropped 18%, mostly because RnR doubled.”"
  ],
  BRAND, BRAND_LIGHT
));

children.push(pageBreak());

// 3.7 Time lenses
children.push(h2("3.7  Three time lenses — Day, Week, Month"));
children.push(body("The same data is shown in three different zoom levels, stacked top-to-bottom on the page."));

children.push(dataTable(
  ["Lens", "Window", "What it's good for"],
  [
    ["Day Wise",   "Last 7 days",   "Today's energy. Spot the dip from yesterday. React to what's happening now."],
    ["Week Wise",  "Last 4 weeks",  "Trends. Is this week beating last? Are RnRs creeping up week-over-week?"],
    ["Month Wise", "Last 6 months", "Strategy. Seasonal peaks. The long arc of interest rate. Slow months."],
  ],
  [1600, 2160, 5600]
));

children.push(callout(
  "Note  ·  segment toggles are per-section",
  [
    "Each of the three sections has its own row of six coloured circles above the chart. Toggling “Untouched” off in Day Wise won't affect Week Wise — you can compare apples to apples (all outcomes) AND apples to apples filtered (e.g. only Contacted vs Not Contacted) without one section's setting bleeding into another."
  ],
  WARN, "FEF3C7"
));

children.push(pageBreak());

// ─── 4. PART 2 — Per-Point view ───
children.push(new Paragraph({
  spacing: { before: 200, after: 60 },
  children: [new TextRun({ text: "PART TWO", font: "Calibri", size: 22, bold: true, color: WARN, characterSpacing: 60 })],
}));
children.push(h1("4.  The IFB Point Workspace"));

children.push(body("When you click on a point name in the rail (or open a link like /?id=1014154), the dashboard hands you the workspace for that specific point. This is where the actual follow-up work happens."));

children.push(h2("4.1  The top strip (header + 5 KPIs)"));
children.push(imagePlaceholder("Per-IFB-Point top header — name, code, KPIs, stages"));
children.push(spacer());

children.push(body("The header is sticky — it stays put even when you scroll the table below. Five tiles run across:"));
children.push(dataTable(
  ["Tile", "What it tells you"],
  [
    ["IFB Point + Code",   "The exact point you're looking at — name and 7-digit code. Useful when sharing screenshots."],
    ["Total Follow Up's",  "Every customer this point has on its book."],
    ["Contact Status",     "Contacted / Not Contacted / RnR / Empty — colour-coded counts."],
    ["Interest",           "Interested / Not Interested / Empty — only counts those who were contacted."],
    ["Follow-Up Stage",    "Post-Purchase, 1st 30 days, Pre-AMC, 8-Year Upgrade — counts per stage."],
  ],
  [2400, 6960]
));

children.push(pageBreak());

// 4.2 Filter bar
children.push(h2("4.2  Filter buttons — the heart of the workspace"));
children.push(body("Five one-tap filters sit just below the header. They are the fastest way to slice your book of work."));

children.push(imagePlaceholder("Filter buttons — Today / Missed / Date / Open / Attempted"));
children.push(spacer());

children.push(dataTable(
  ["Button", "What you get", "When to use it"],
  [
    ["📅  Today Follow Up",   "Only customers due TODAY.",                              "Your call list for the next 8 hours. Click it first thing in the morning."],
    ["⚠  Missed Follow Up",  "Calls that were due in the past but never closed.",     "Use mid-morning to catch anything that slipped from yesterday or before."],
    ["📆  Follow Up Date",     "Opens a calendar — pick any date or a range.",          "When auditing, doing a monthly review, or focusing on a specific push window."],
    ["📋  Open Followup",     "Anything not yet closed — Pending, RnR, Not Contacted.","Your one-click “what's still left to do?” view."],
    ["📞  Attempted",          "Customers already tried — Contacted, Not Contacted, RnR.","Audit view — confirm what has been worked on this period."],
  ],
  [2200, 3700, 3460]
));

children.push(callout(
  "How the buttons interact with each other",
  [
    [
      { text: "Today Follow Up", bold: true },
      { text: " and " },
      { text: "Missed Follow Up", bold: true },
      { text: " are mutually exclusive — clicking one turns the other off. " },
      { text: "Follow Up Date", bold: true },
      { text: " gives you a custom date window and overrides both. " },
      { text: "Open Followup", bold: true },
      { text: " and " },
      { text: "Attempted", bold: true },
      { text: " are status filters — they layer on top of whatever date filter is active." },
    ],
  ],
  BRAND, BRAND_LIGHT
));

children.push(pageBreak());

// 4.3 Stage + Search + Date Range
children.push(h2("4.3  Narrow further — Stage, Search, Date range"));
children.push(body("These three controls sit on the same row as the filter buttons and can be used in any combination."));

children.push(h3("Follow-Up Stage"));
children.push(body("A dropdown — pick a stage of the customer journey:"));
children.push(bullet([{ text: "Post-Purchase  ", bold: true }, { text: "— immediately after the customer bought the product." }]));
children.push(bullet([{ text: "1st 30 days call  ", bold: true }, { text: "— the early-relationship check-in." }]));
children.push(bullet([{ text: "Pre-AMC  ", bold: true }, { text: "— due for an Annual Maintenance Contract pitch." }]));
children.push(bullet([{ text: "8 Year Upgrade  ", bold: true }, { text: "— machine is old enough that an upgrade conversation makes sense." }]));
children.push(bullet([{ text: "Greetings  ", bold: true }, { text: "— birthday / anniversary / milestone touchpoints." }]));
children.push(body([
  { text: "Why this matters: ", bold: true },
  { text: "each stage carries a different script and a different value proposition. Handling them as a batch keeps the caller in flow." },
]));

children.push(h3("Search"));
children.push(body("Type any fragment of a customer's name, phone number, email address, or customer ID. The table re-filters instantly. Particularly useful when a customer rings YOU back and you need their record in two seconds."));

children.push(h3("Date range"));
children.push(body("By default the table shows today onwards. Open the date pickers to define a custom window — perfect for monthly reviews, auditing a specific campaign, or going back to find a particular customer's last call."));

children.push(pageBreak());

// 4.4 Customer table
children.push(h2("4.4  The customer table — your worklist"));
children.push(body("Every row is one customer. The table sits below the filters and scrolls if there's more than a page-worth of customers."));

children.push(imagePlaceholder("Customer table — rows + columns"));
children.push(spacer());

children.push(h3("Every column, decoded"));
children.push(dataTable(
  ["Column", "What it shows"],
  [
    ["✏  Edit",      "Pencil button — opens the Edit Lead dialog for that row. The main way you log call outcomes."],
    ["👁  Eye",       "Pulls the customer's full IFB profile (address, serial number, installation date) live from the API. Doesn't make any changes — read-only."],
    ["Stage",         "Which follow-up stage this customer is at (Post-Purchase, etc.)."],
    ["Name",          "Customer name + machine model (washing machine / microwave / cook top, etc.) in one line."],
    ["Contact",       "Phone (primary + alternate if available) and email address."],
    ["Next Appt",     "When you've promised to call back. Blank if no promise has been made yet."],
    ["Call Status",   "Coloured chip: green = Contacted, red = Not Contacted, amber = RnR."],
    ["Interested?",   "Coloured chip — only filled for Contacted rows. Green = Interested, red = Not Interested."],
    ["Remarks",       "Up to 60 characters of free-text notes from the last caller."],
    ["Final Status",  "WON / LOST — the closing decision. Blank for rows still in play."],
  ],
  [2000, 7360]
));

children.push(pageBreak());

// 4.5 Edit dialog
children.push(h2("4.5  Logging a call — the Edit Lead dialog"));
children.push(body([
  { text: "Click the  " }, { text: "✏  ", bold: true },
  { text: "pencil on any row and a dialog slides in. This is where you log what happened on the call. The dialog is " },
  { text: "adaptive", bold: true },
  { text: " — it only asks for what's relevant to the call status you've picked." },
]));

children.push(imagePlaceholder("Edit Lead dialog — Call Status flow"));
children.push(spacer());

children.push(h3("Step 1 — Pick Call Status"));
children.push(body("The first dropdown. Three options:"));
children.push(bullet([{ text: "Contacted  ", bold: true, color: GOOD }, { text: "— customer picked up and you spoke to them." }]));
children.push(bullet([{ text: "Not Contacted  ", bold: true, color: BAD }, { text: "— you tried but couldn't reach them at all." }]));
children.push(bullet([{ text: "RnR  ", bold: true, color: WARN }, { text: "— Ring-no-Response. Phone rang, they didn't pick up or engage." }]));

children.push(spacer());

children.push(h3("Step 2A — If you picked Contacted"));
children.push(body("Two more questions appear:"));
children.push(bullet([
  { text: "Interested?  ", bold: true },
  { text: "— Interested OR Not Interested." },
]));
children.push(body([
  { text: "If Interested  ", bold: true, color: GOOD },
  { text: "→ pick a Next Appointment date (anything from tomorrow onwards). The system schedules the callback for you." },
]));
children.push(body([
  { text: "If Not Interested  ", bold: true, color: PURPLE },
  { text: "→ a new dropdown appears: " },
  { text: "Reason", bold: true, color: BRAND },
  { text: " — choose either " },
  { text: "Service issue", bold: true },
  { text: " or " },
  { text: "Others", bold: true },
  { text: ". The system then automatically marks the customer's Final Status as " },
  { text: "LOST", bold: true, color: BAD },
  { text: " — you don't need to remember to do it." },
]));

children.push(callout(
  "Why the “Reason” dropdown matters",
  [
    [
      { text: "Knowing that a customer said no isn't enough — you need to know " },
      { text: "why", bold: true, italic: true },
      { text: ". The Reason field flags genuine product complaints (“Service issue”) separately from general churn (“Others”), so your service team can spot patterns across IFB Points. A spike in Service issues is something you'd want to investigate." },
    ],
  ],
  BRAND, BRAND_LIGHT
));

children.push(h3("Step 2B — If you picked Not Contacted or RnR"));
children.push(body("Two simple fields:"));
children.push(bullet("Next Appointment — pick a date for the next attempt."));
children.push(bullet("Remarks — what you observed (e.g. “Phone switched off”, “Customer asked us to call after 6pm”)."));

children.push(h3("Step 3 — Remarks (always required)"));
children.push(body([
  { text: "A free-text box, capped at 60 characters. A small counter in the bottom-right shows how many you've used (it goes green → amber → red as you run out). " },
  { text: "Remarks are required to enable Save", bold: true },
  { text: " — leaving the field empty keeps the Save button greyed out." },
]));

children.push(h3("Step 4 — Save"));
children.push(body("Click Save. The row updates immediately, the table refreshes, and a toast pops up confirming what was saved. Click Cancel to discard everything."));

children.push(pageBreak());

// 4.6 The 3-RnR rule
children.push(h2("4.6  The 3-RnR Auto-LOST Rule"));
children.push(callout(
  "The rule, in one line",
  [
    [
      { text: "If the same customer has been marked  " },
      { text: "RnR ", bold: true, color: WARN },
      { text: "three times already, the  ", },
      { text: "next ", bold: true, italic: true },
      { text: "save (regardless of what status you choose) automatically marks their Final Status as  " },
      { text: "LOST.", bold: true, color: BAD },
    ],
  ],
  BAD, "FEE2E2"
));

children.push(body("This is on purpose. The system makes the judgement call for you — three Ring-no-Responses is enough evidence that the customer isn't engaging. A toast appears confirming the auto-LOST so you know what happened."));

children.push(h3("Why this is in the system, not left to the caller"));
children.push(bullet("Removes a daily judgement call from the caller's plate."));
children.push(bullet("Keeps the worklist clean — no infinite chasing of dead leads."));
children.push(bullet("Standardises the data across all IFB Points — one rule for everyone."));
children.push(bullet("The full history is preserved — the 3 RnR attempts are still visible if you click into the customer."));

children.push(pageBreak());

// 4.7 Eye icon + pagination + tips
children.push(h2("4.7  The Eye icon  (👁)"));
children.push(body([
  { text: "Click  " }, { text: "👁  ", bold: true },
  { text: "on any row and the dashboard pulls that customer's full IFB record live from the API — address, serial number, installation date, machine model, last service, anything IFB has on file. This is read-only; nothing you do here changes the customer's record. " },
  { text: "Use it when a customer rings you and you need their full picture in 5 seconds.", italic: true },
]));

children.push(h2("4.8  Pagination"));
children.push(body("If the filtered list is longer than a page, page controls appear at the bottom: Previous / Next, current page, and a page-size selector (25, 50, or 100 rows per page). The header and filters stay frozen so context is never lost while you scroll."));

children.push(pageBreak());

// 5. Best practices
children.push(h1("5.  Best practices  &  tips"));

children.push(h2("Daily rhythm"));
children.push(bullet([{ text: "First thing:  ", bold: true, color: BRAND }, { text: "open Today Follow Up. That's your call list for the next 8 hours." }]));
children.push(bullet([{ text: "Mid-morning:  ", bold: true, color: BRAND }, { text: "sweep Missed Follow Up. Catches anything that slipped." }]));
children.push(bullet([{ text: "End of day:  ", bold: true, color: BRAND }, { text: "scan Open Followup with the Stage filter set to whichever stage you've been working on." }]));

children.push(h2("Writing remarks people will thank you for"));
children.push(bullet("Always note the time customer asked to be called back (“call after 6pm”)."));
children.push(bullet("Mention any service complaint the customer raised — even a passing one."));
children.push(bullet("Avoid generic notes like “Customer busy” — what made them busy? Will they be free tomorrow?"));
children.push(bullet("If the customer requested a different channel (WhatsApp, email), note it — your next colleague picks up where you left off."));

children.push(h2("Reading the Regional Overview"));
children.push(bullet([{ text: "Daily check:  ", bold: true, color: BRAND }, { text: "glance at the 5 KPI cards. If Not Contacted has jumped overnight, something changed (call rotor, staffing, etc.)." }]));
children.push(bullet([{ text: "Weekly check:  ", bold: true, color: BRAND }, { text: "scroll to Week Wise and check the insights panel — it'll flag the obvious issues." }]));
children.push(bullet([{ text: "Monthly check:  ", bold: true, color: BRAND }, { text: "use Month Wise to spot seasonal patterns. Cooking-related products always peak before Diwali, for instance — staff accordingly." }]));

children.push(callout(
  "One golden rule",
  [
    [
      { text: "Every call deserves a save. ", bold: true },
      { text: "Even if the customer didn't pick up, log it as Not Contacted with a date for the next attempt. An untouched row is invisible to your colleagues; a logged Not Contacted is a paper trail." },
    ],
  ],
  BRAND, BRAND_LIGHT
));

children.push(pageBreak());

// 6. Quick reference
children.push(h1("6.  Quick reference  ·  button map"));
children.push(body("All the buttons and icons across the dashboard, on one page."));

children.push(h2("Sign In screen"));
children.push(dataTable(
  ["Element", "What it does"],
  [
    ["Email field",         "Your registered IFB email address."],
    ["Password field",      "Your password. Eye icon toggles visibility."],
    ["Sign In button",      "Logs you in. Loads your mapped IFB Points."],
  ],
  [2400, 6960]
));

children.push(h2("Regional Overview"));
children.push(dataTable(
  ["Element", "What it does"],
  [
    ["🔍 Search box",       "Search the IFB Points rail by name OR code."],
    ["✅ All",              "If search active: tick all results. If no search: clear all ticks."],
    ["✖ Clear",            "Empty the search and untick everything."],
    ["Checkbox ☑",          "Tick / untick an IFB Point to include/exclude it from the charts."],
    ["Colour circles",      "Above each chart — click to toggle a segment colour on/off."],
    ["Day / Week / Month",  "Three sections, each with its own chart + insights panel."],
  ],
  [2400, 6960]
));

children.push(h2("IFB Point workspace"));
children.push(dataTable(
  ["Element", "What it does"],
  [
    ["📅 Today Follow Up",  "Show only customers due today."],
    ["⚠ Missed Follow Up", "Show customers who were due in the past."],
    ["📆 Follow Up Date",    "Open the calendar; pick a date range."],
    ["📋 Open Followup",    "Show all not-yet-closed customers."],
    ["📞 Attempted",         "Show only customers already tried."],
    ["Stage dropdown",       "Filter by follow-up stage."],
    ["Search box",           "Search by name / phone / email / customer ID."],
    ["Date range",           "Custom start + end date."],
    ["✏  Edit",             "Open Edit Lead dialog for a row."],
    ["👁  Eye",              "Pull live customer detail from the API (read-only)."],
    ["Previous / Next",      "Page through long lists."],
    ["Page size selector",   "25 / 50 / 100 rows per page."],
  ],
  [2400, 6960]
));

children.push(h2("Edit Lead dialog"));
children.push(dataTable(
  ["Field", "Behaviour"],
  [
    ["Call Status",           "Contacted / Not Contacted / RnR. Required first choice."],
    ["Interested?",           "Appears only if Call Status = Contacted."],
    ["Reason",                "Appears only if Interested? = Not Interested. Options: Service issue / Others."],
    ["Next Appointment",      "Appears for Contacted+Interested, Not Contacted, RnR. Minimum date = tomorrow."],
    ["Remarks",               "Always required. Max 60 chars. Live counter shows characters left."],
    ["Final Status",          "Auto-derived: Not Interested → LOST; 3rd RnR → LOST."],
    ["💾 Save",               "Greyed out until all required fields are filled."],
    ["Cancel",                "Discard changes; close the dialog."],
  ],
  [2400, 6960]
));

children.push(pageBreak());

// 7. Notes for IT / admins (light)
children.push(h1("7.  Notes you might find useful"));

children.push(h2("Your mapping is owned by IT"));
children.push(body("Which IFB Points you see is determined by a mapping IT manages. If a point is missing, IT can add it; if you've been moved between regions, IT updates the mapping and your scope changes automatically on your next sign-in."));

children.push(h2("Data freshness"));
children.push(body("The dashboard syncs from the live IFB API every time you open or refresh the page. There's no “refresh” button to remember — every page load fetches the latest. A small line at the bottom of the screen confirms the sync, with timestamp and record count."));

children.push(h2("Counter & audit log"));
children.push(body("Every save you make is also recorded in an immutable counter log — including the time, the previous values, and the new values. So if you ever wonder “did I save that?” or “what did the row look like yesterday?”, IT can reconstruct it."));

children.push(h2("Mobile / smaller screens"));
children.push(body("The dashboard is built for desktop / laptop screens. It will work on a tablet in landscape, but the per-Point workspace was designed to be used at a desk while you have a phone in the other hand."));

children.push(spacer(), spacer(), spacer());

children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "— End of user guide —", font: "Calibri", size: 22, italic: true, color: MUTED })],
}));

// ── Build the document ────────────────────────────────────────────────────────
const doc = new Document({
  creator: "IFB Industries",
  title: "IFB Points Dashboard — User Guide",
  description: "Complete non-technical user guide for the Follow Up Control Tower",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Calibri", color: BRAND_DARK },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Calibri", color: BRAND },
        paragraph: { spacing: { before: 260, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Calibri", color: INK },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 900, hanging: 270 } } } },
        ] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({
          text: "IFB Points · Follow Up Control Tower — User Guide",
          font: "Calibri", size: 18, italic: true, color: MUTED,
        })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Page ", font: "Calibri", size: 18, color: MUTED }),
          new TextRun({ children: [PageNumber.CURRENT], font: "Calibri", size: 18, color: MUTED }),
          new TextRun({ text: " of ", font: "Calibri", size: 18, color: MUTED }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Calibri", size: 18, color: MUTED }),
        ],
      })] }),
    },
    children,
  }],
});

const out = path.join(__dirname, "IFB_Points_Dashboard_User_Guide.docx");
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(out, buf);
  console.log("wrote", out);
});
