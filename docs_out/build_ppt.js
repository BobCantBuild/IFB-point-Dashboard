// Follow Up Control Tower — IFB Points Dashboard User Guide (PPTX)
// Theme: Midnight Indigo (matches the live app's #4F46E5 / #6366F1 / #1E1B4B tones)

const path = require("path");
const PPTX = require("pptxgenjs");
const pres = new PPTX();

pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 inches
pres.title = "Follow Up Control Tower — User Guide";
pres.company = "IFB Industries";

// ── Brand palette ────────────────────────────────────────────────────────────
const C = {
  ink:      "0F172A",
  slate:    "475569",
  muted:    "94A3B8",
  bg:       "FFFFFF",
  bgSoft:   "F0F2FF",
  card:     "FFFFFF",
  line:     "E0E7FF",
  brand:    "4F46E5",   // indigo
  brandD:   "1E1B4B",   // deep indigo
  brandL:   "EEF2FF",
  accent:   "6366F1",
  good:     "16A34A",
  goodBg:   "DCFCE7",
  warn:     "D97706",
  warnBg:   "FEF3C7",
  bad:      "DC2626",
  badBg:    "FEE2E2",
  purple:   "9333EA",
  sky:      "0EA5E9",
  skyBg:    "F0F9FF",
};

const FONT_H = "Calibri";
const FONT_B = "Calibri";
const SW = 13.333;
const SH = 7.5;

// ── Reusable building blocks ────────────────────────────────────────────────
function bgSoft(slide) {
  slide.background = { color: C.bgSoft };
}
function bgDark(slide) {
  slide.background = { color: C.brandD };
}
function bgWhite(slide) {
  slide.background = { color: C.bg };
}

// Side rail (visual motif) — thin indigo bar on the left of every content slide
function sideRail(slide) {
  slide.addShape("rect", {
    x: 0, y: 0, w: 0.18, h: SH,
    fill: { color: C.brand }, line: { color: C.brand },
  });
}

function pageNumber(slide, n, total) {
  slide.addText(`${n} / ${total}`, {
    x: SW - 1.2, y: SH - 0.45, w: 1.0, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.muted, align: "right",
  });
}

function footerBrand(slide) {
  slide.addText("IFB Points · Follow Up Control Tower", {
    x: 0.45, y: SH - 0.45, w: 7, h: 0.3,
    fontFace: FONT_B, fontSize: 10, color: C.muted, italic: true,
  });
}

function chip(slide, x, y, text, color) {
  // tiny pill chip
  slide.addShape("roundRect", {
    x, y, w: 1.7, h: 0.32,
    fill: { color: color + "" }, line: { color: color },
    rectRadius: 0.14,
  });
  slide.addText(text, {
    x, y, w: 1.7, h: 0.32,
    fontFace: FONT_B, fontSize: 10, bold: true, color: "FFFFFF", align: "center",
  });
}

function titleBlock(slide, eyebrow, title) {
  slide.addText(eyebrow, {
    x: 0.6, y: 0.45, w: 12, h: 0.32,
    fontFace: FONT_B, fontSize: 11, bold: true, color: C.brand,
    charSpacing: 4,
  });
  slide.addText(title, {
    x: 0.6, y: 0.78, w: 12, h: 0.7,
    fontFace: FONT_H, fontSize: 30, bold: true, color: C.ink,
  });
}

function placeholderImage(slide, x, y, w, h, label) {
  slide.addShape("roundRect", {
    x, y, w, h,
    fill: { color: "F8FAFC" }, line: { color: C.line, width: 1.25, dashType: "dash" },
    rectRadius: 0.1,
  });
  slide.addText(
    [
      { text: "📷  ", options: { fontSize: 24, color: C.brand } },
      { text: "Insert screenshot\n", options: { fontSize: 14, bold: true, color: C.slate } },
      { text: label, options: { fontSize: 11, italic: true, color: C.muted } },
    ],
    { x, y, w, h, align: "center", valign: "middle", fontFace: FONT_B }
  );
}

// =========================================================================
// SLIDE 1 — Cover
// =========================================================================
{
  const s = pres.addSlide();
  bgDark(s);

  // big circle motif top-right
  s.addShape("ellipse", {
    x: SW - 4.2, y: -2.2, w: 6.5, h: 6.5,
    fill: { color: C.accent, transparency: 70 }, line: { color: C.accent, transparency: 70 },
  });
  s.addShape("ellipse", {
    x: SW - 2.8, y: -1.2, w: 4.5, h: 4.5,
    fill: { color: C.brand, transparency: 50 }, line: { color: C.brand, transparency: 50 },
  });

  s.addText("IFB POINTS", {
    x: 0.8, y: 1.0, w: 8, h: 0.5,
    fontFace: FONT_B, fontSize: 14, bold: true, color: "C7D2FE", charSpacing: 8,
  });
  s.addText("Follow Up\nControl Tower", {
    x: 0.8, y: 1.6, w: 9, h: 2.6,
    fontFace: FONT_H, fontSize: 64, bold: true, color: "FFFFFF",
    lineSpacingMultiple: 0.95,
  });
  s.addText("A complete, non-technical user guide", {
    x: 0.8, y: 4.5, w: 9, h: 0.5,
    fontFace: FONT_B, fontSize: 20, color: "CADCFC",
  });

  // tiny meta chips
  s.addShape("roundRect", {
    x: 0.8, y: 5.4, w: 3.2, h: 0.45,
    fill: { color: "FFFFFF", transparency: 88 }, line: { color: "FFFFFF", transparency: 70 },
    rectRadius: 0.2,
  });
  s.addText("✦  Sign In  ·  Regional Overview", {
    x: 0.8, y: 5.4, w: 3.2, h: 0.45,
    fontFace: FONT_B, fontSize: 11, color: "FFFFFF", align: "center", bold: true,
  });
  s.addShape("roundRect", {
    x: 4.15, y: 5.4, w: 3.2, h: 0.45,
    fill: { color: "FFFFFF", transparency: 88 }, line: { color: "FFFFFF", transparency: 70 },
    rectRadius: 0.2,
  });
  s.addText("✦  Per-Point Workspace", {
    x: 4.15, y: 5.4, w: 3.2, h: 0.45,
    fontFace: FONT_B, fontSize: 11, color: "FFFFFF", align: "center", bold: true,
  });

  s.addText("For IFB Point owners & regional managers", {
    x: 0.8, y: SH - 1.0, w: 9, h: 0.4,
    fontFace: FONT_B, fontSize: 12, italic: true, color: "94A3B8",
  });
}

// =========================================================================
// SLIDE 2 — Why this page exists (Benefits)
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "WHY THIS DASHBOARD", "Built so every follow-up is seen, owned, and closed.");

  // four benefit cards, 2x2
  const cards = [
    { ico: "👁", t: "Nothing falls through",
      d: "Every customer due for a call is surfaced — today, missed, or upcoming." },
    { ico: "🧭", t: "Region in one glance",
      d: "Open the app and see how your mapped IFB Points are doing — no spreadsheets, no filters to set." },
    { ico: "⚡", t: "Faster updates",
      d: "Mark a call outcome in three clicks — Contacted, interested, reason, done." },
    { ico: "🛡", t: "Discipline, built in",
      d: "Three unanswered RnRs and the lead is auto-closed as LOST. No lingering tasks." },
  ];
  const startX = 0.6, startY = 1.95, w = 5.95, h = 2.4, gap = 0.25;
  cards.forEach((c, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = startX + col * (w + gap);
    const y = startY + row * (h + gap);
    s.addShape("roundRect", {
      x, y, w, h,
      fill: { color: C.brandL }, line: { color: C.line, width: 1 },
      rectRadius: 0.12,
    });
    // colored left accent
    s.addShape("rect", { x, y, w: 0.12, h, fill: { color: C.brand }, line: { color: C.brand } });
    // icon circle
    s.addShape("ellipse", {
      x: x + 0.35, y: y + 0.35, w: 0.75, h: 0.75,
      fill: { color: C.brand }, line: { color: C.brand },
    });
    s.addText(c.ico, {
      x: x + 0.35, y: y + 0.35, w: 0.75, h: 0.75,
      fontFace: FONT_B, fontSize: 22, color: "FFFFFF", align: "center", valign: "middle",
    });
    s.addText(c.t, {
      x: x + 1.3, y: y + 0.32, w: w - 1.5, h: 0.5,
      fontFace: FONT_H, fontSize: 18, bold: true, color: C.ink,
    });
    s.addText(c.d, {
      x: x + 1.3, y: y + 0.85, w: w - 1.5, h: h - 1,
      fontFace: FONT_B, fontSize: 13, color: C.slate, lineSpacingMultiple: 1.25,
    });
  });

  pageNumber(s, 2, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 3 — Two sides of the app (overview)
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "HOW IT'S ORGANISED", "Two screens, one purpose.");

  // Left card — Regional Overview
  s.addShape("roundRect", {
    x: 0.6, y: 1.95, w: 5.95, h: 4.6,
    fill: { color: C.brandL }, line: { color: C.brand, width: 1.5 },
    rectRadius: 0.16,
  });
  s.addText("1", {
    x: 0.85, y: 2.15, w: 0.9, h: 0.9,
    fontFace: FONT_H, fontSize: 56, bold: true, color: C.brand,
  });
  s.addText("Sign In + Regional Overview", {
    x: 1.85, y: 2.25, w: 4.5, h: 0.5,
    fontFace: FONT_H, fontSize: 18, bold: true, color: C.brandD,
  });
  s.addText("Your mapped IFB Points, at a glance.", {
    x: 1.85, y: 2.7, w: 4.5, h: 0.4,
    fontFace: FONT_B, fontSize: 12, italic: true, color: C.slate,
  });
  s.addText(
    [
      { text: "● ", options: { color: C.brand, bold: true } },
      { text: "Sign-in scoped to your region\n", options: {} },
      { text: "● ", options: { color: C.brand, bold: true } },
      { text: "5 KPI cards (Points, Total, Contacted, Not Contacted, RnR)\n", options: {} },
      { text: "● ", options: { color: C.brand, bold: true } },
      { text: "Visual mix chart — Day / Week / Month\n", options: {} },
      { text: "● ", options: { color: C.brand, bold: true } },
      { text: "Plain-English insights panel\n", options: {} },
      { text: "● ", options: { color: C.brand, bold: true } },
      { text: "Searchable list of every IFB Point you manage", options: {} },
    ],
    { x: 1.0, y: 3.2, w: 5.4, h: 3.2,
      fontFace: FONT_B, fontSize: 13, color: C.ink, lineSpacingMultiple: 1.4 }
  );

  // Right card — IFB Point View
  s.addShape("roundRect", {
    x: 6.8, y: 1.95, w: 5.95, h: 4.6,
    fill: { color: "FFF7ED" }, line: { color: C.warn, width: 1.5 },
    rectRadius: 0.16,
  });
  s.addText("2", {
    x: 7.05, y: 2.15, w: 0.9, h: 0.9,
    fontFace: FONT_H, fontSize: 56, bold: true, color: C.warn,
  });
  s.addText("IFB Point Workspace", {
    x: 8.05, y: 2.25, w: 4.5, h: 0.5,
    fontFace: FONT_H, fontSize: 18, bold: true, color: "7C2D12",
  });
  s.addText("Where the actual follow-up work gets done.", {
    x: 8.05, y: 2.7, w: 4.5, h: 0.4,
    fontFace: FONT_B, fontSize: 12, italic: true, color: C.slate,
  });
  s.addText(
    [
      { text: "● ", options: { color: C.warn, bold: true } },
      { text: "Header KPIs for that point\n", options: {} },
      { text: "● ", options: { color: C.warn, bold: true } },
      { text: "Filter buttons — Today / Missed / Date / Open / Attempted\n", options: {} },
      { text: "● ", options: { color: C.warn, bold: true } },
      { text: "Stage + search + date range\n", options: {} },
      { text: "● ", options: { color: C.warn, bold: true } },
      { text: "Customer table with eye (👁) for full details\n", options: {} },
      { text: "● ", options: { color: C.warn, bold: true } },
      { text: "Edit Lead (✏) dialog to log the outcome", options: {} },
    ],
    { x: 7.2, y: 3.2, w: 5.4, h: 3.2,
      fontFace: FONT_B, fontSize: 13, color: C.ink, lineSpacingMultiple: 1.4 }
  );

  pageNumber(s, 3, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 4 — Part 1 divider
// =========================================================================
{
  const s = pres.addSlide();
  bgDark(s);
  s.addShape("ellipse", {
    x: -3, y: 4, w: 7, h: 7,
    fill: { color: C.brand, transparency: 60 }, line: { color: C.brand, transparency: 60 },
  });
  s.addShape("ellipse", {
    x: SW - 3, y: -4, w: 7, h: 7,
    fill: { color: C.accent, transparency: 70 }, line: { color: C.accent, transparency: 70 },
  });

  s.addText("PART  ONE", {
    x: 0.8, y: 2.2, w: 12, h: 0.5,
    fontFace: FONT_B, fontSize: 16, bold: true, color: "C7D2FE", charSpacing: 12,
  });
  s.addText("Sign In  &  Regional Overview", {
    x: 0.8, y: 2.8, w: 12, h: 1.4,
    fontFace: FONT_H, fontSize: 54, bold: true, color: "FFFFFF",
  });
  s.addText("Your daily landing screen — built for managers who own many IFB Points.", {
    x: 0.8, y: 4.4, w: 11.5, h: 0.6,
    fontFace: FONT_B, fontSize: 18, italic: true, color: "CADCFC",
  });
}

// =========================================================================
// SLIDE 5 — Sign In
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "STEP 1  ·  SIGN IN", "One screen. Your region travels with you.");

  // left: explanation
  s.addText(
    [
      { text: "What you do\n", options: { bold: true, fontSize: 14, color: C.brand } },
      { text: "Enter your IFB email and password. Hit Sign In.\n\n", options: { fontSize: 13, color: C.ink } },
      { text: "What happens behind it\n", options: { bold: true, fontSize: 14, color: C.brand } },
      { text: "The system looks you up and figures out which IFB Points belong to your region, branch, and assignment — only those will show up for you. ", options: { fontSize: 13, color: C.ink } },
      { text: "Nobody else's points clutter your view.\n\n", options: { fontSize: 13, color: C.ink, italic: true } },
      { text: "Why this matters\n", options: { bold: true, fontSize: 14, color: C.brand } },
      { text: "No filters to set, no codes to remember. Your scope is decided the moment you sign in.", options: { fontSize: 13, color: C.ink } },
    ],
    { x: 0.6, y: 1.95, w: 6.0, h: 5, valign: "top", lineSpacingMultiple: 1.35 }
  );

  // right: image placeholder
  placeholderImage(s, 7.0, 1.95, 5.7, 4.6, "01_login.png — the Sign In screen");

  // small note strip
  s.addShape("roundRect", {
    x: 0.6, y: 6.6, w: 12.2, h: 0.45,
    fill: { color: C.brandL }, line: { color: C.line }, rectRadius: 0.1,
  });
  s.addText(
    [
      { text: "Tip:  ", options: { bold: true, color: C.brand } },
      { text: "Trouble signing in? The dashboard shows a friendly red banner — re-check the email exactly as IT has it, including the dot.", options: { color: C.slate } },
    ],
    { x: 0.8, y: 6.6, w: 11.8, h: 0.45, fontFace: FONT_B, fontSize: 11 }
  );

  pageNumber(s, 5, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 6 — Regional Overview Dashboard (landing)
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "STEP 2  ·  THE LANDING SCREEN", "Regional Overview — your home base after sign-in.");

  placeholderImage(s, 0.6, 1.95, 7.6, 4.85, "Overview Dashboard (post-login landing)");

  // right side — labels/callouts
  s.addText("What you see on day one", {
    x: 8.4, y: 1.95, w: 4.4, h: 0.45,
    fontFace: FONT_H, fontSize: 16, bold: true, color: C.brandD,
  });
  s.addText(
    [
      { text: "①  ", options: { color: C.brand, bold: true } },
      { text: "Five KPI cards on top.\n", options: { bold: true } },
      { text: "   Quick pulse on your whole region.\n\n", options: { color: C.slate, fontSize: 11 } },
      { text: "②  ", options: { color: C.brand, bold: true } },
      { text: "Left rail — your IFB Points.\n", options: { bold: true } },
      { text: "   Search by name or code, tick to focus.\n\n", options: { color: C.slate, fontSize: 11 } },
      { text: "③  ", options: { color: C.brand, bold: true } },
      { text: "Three time lenses.\n", options: { bold: true } },
      { text: "   Day · Week · Month — same data, different zoom.\n\n", options: { color: C.slate, fontSize: 11 } },
      { text: "④  ", options: { color: C.brand, bold: true } },
      { text: "Insights panel.\n", options: { bold: true } },
      { text: "   Plain-English commentary, auto-generated.", options: { color: C.slate, fontSize: 11 } },
    ],
    { x: 8.4, y: 2.5, w: 4.4, h: 4.4,
      fontFace: FONT_B, fontSize: 12, color: C.ink, lineSpacingMultiple: 1.3 }
  );

  pageNumber(s, 6, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 7 — KPI strip explained
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "THE  KPI  STRIP", "Five numbers that tell you if the day is on track.");

  const kpis = [
    { lbl: "IFB POINTS",     val: "247",  ic: "🏪", color: C.brand,  bg: C.brandL,
      d: "How many IFB Points fall under your scope today." },
    { lbl: "TOTAL FOLLOW UP", val: "3,418", ic: "👥", color: C.sky,    bg: C.skyBg,
      d: "Every customer waiting for a call — across all your points." },
    { lbl: "CONTACTED",       val: "1,820", ic: "✅", color: C.good,   bg: C.goodBg,
      d: "Calls already made and logged." },
    { lbl: "NOT CONTACTED",   val: "924",   ic: "🚫", color: C.bad,    bg: C.badBg,
      d: "Customers tried but couldn't be reached." },
    { lbl: "RnR",             val: "163",   ic: "🔁", color: C.warn,   bg: C.warnBg,
      d: "Ring-no-Response — needs another attempt." },
  ];
  const W = 2.4, H = 1.45, gap = 0.12;
  const total = 5 * W + 4 * gap;
  const startX = (SW - total) / 2;
  kpis.forEach((k, i) => {
    const x = startX + i * (W + gap);
    s.addShape("roundRect", {
      x, y: 1.95, w: W, h: H,
      fill: { color: k.bg }, line: { color: k.color, width: 1 }, rectRadius: 0.1,
    });
    s.addShape("rect", {
      x, y: 1.95, w: 0.08, h: H,
      fill: { color: k.color }, line: { color: k.color },
    });
    s.addText(k.lbl, {
      x: x + 0.18, y: 2.05, w: W - 0.55, h: 0.3,
      fontFace: FONT_B, fontSize: 9, bold: true, color: k.color, charSpacing: 4,
    });
    s.addText(k.ic, {
      x: x + W - 0.55, y: 2.0, w: 0.4, h: 0.4,
      fontSize: 16, align: "right",
    });
    s.addText(k.val, {
      x: x + 0.18, y: 2.45, w: W - 0.35, h: 0.7,
      fontFace: FONT_H, fontSize: 28, bold: true, color: C.ink,
    });
    s.addText(k.d, {
      x: x, y: 3.55, w: W, h: 1.5,
      fontFace: FONT_B, fontSize: 11, color: C.slate, align: "left",
      lineSpacingMultiple: 1.25,
    });
  });

  // bottom strip
  s.addShape("roundRect", {
    x: 0.6, y: 5.4, w: 12.2, h: 1.35,
    fill: { color: C.brandL }, line: { color: C.line }, rectRadius: 0.12,
  });
  s.addText("How to read them together", {
    x: 0.85, y: 5.5, w: 11.5, h: 0.4,
    fontFace: FONT_H, fontSize: 14, bold: true, color: C.brandD,
  });
  s.addText(
    "Total = Contacted + Not Contacted + RnR + (anything still untouched).\n"
    + "If Not Contacted creeps high, your callers are reaching voicemails — change the calling window.\n"
    + "If RnR is creeping up, customers are picking up but not answering — schedule a fresh callback.",
    { x: 0.85, y: 5.85, w: 11.5, h: 0.85, fontFace: FONT_B, fontSize: 11.5, color: C.slate, lineSpacingMultiple: 1.3 }
  );

  pageNumber(s, 7, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 8 — IFB Points rail
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "LEFT RAIL  ·  YOUR IFB POINTS", "Search, tick, focus.");

  // Mock rail visual
  s.addShape("roundRect", {
    x: 0.6, y: 1.95, w: 4.0, h: 4.85,
    fill: { color: "FFFFFF" }, line: { color: C.line, width: 1.5 }, rectRadius: 0.14,
  });
  // search input
  s.addShape("roundRect", {
    x: 0.85, y: 2.15, w: 3.5, h: 0.42,
    fill: { color: "FFFFFF" }, line: { color: C.accent, width: 1.5 }, rectRadius: 0.1,
  });
  s.addText("🔍   City mall", {
    x: 0.95, y: 2.15, w: 3.3, h: 0.42, fontFace: FONT_B, fontSize: 11, color: C.ink,
  });
  // All / Clear buttons
  s.addShape("roundRect", {
    x: 0.85, y: 2.7, w: 1.65, h: 0.4,
    fill: { color: "FFFFFF" }, line: { color: C.accent }, rectRadius: 0.08,
  });
  s.addText("✅  All", {
    x: 0.85, y: 2.7, w: 1.65, h: 0.4,
    fontFace: FONT_B, fontSize: 11, bold: true, color: C.brand, align: "center",
  });
  s.addShape("roundRect", {
    x: 2.7, y: 2.7, w: 1.65, h: 0.4,
    fill: { color: "FFFFFF" }, line: { color: C.accent }, rectRadius: 0.08,
  });
  s.addText("✖  Clear", {
    x: 2.7, y: 2.7, w: 1.65, h: 0.4,
    fontFace: FONT_B, fontSize: 11, bold: true, color: C.brand, align: "center",
  });
  // list items
  const items = [
    { n: "IFB Point City Mall",      on: true },
    { n: "IFB Point Anand Vihar",    on: true },
    { n: "IFB Point Banjara Hills",  on: false },
    { n: "IFB Point Sector 18",      on: false },
    { n: "IFB Point Andheri West",   on: true },
    { n: "IFB Point Jubilee Hills",  on: false },
    { n: "IFB Point Park Street",    on: false },
  ];
  items.forEach((it, i) => {
    const y = 3.25 + i * 0.45;
    if (it.on) {
      s.addShape("roundRect", {
        x: 0.85, y, w: 3.5, h: 0.38,
        fill: { color: C.brandL }, line: { color: C.brandL }, rectRadius: 0.06,
      });
      s.addShape("rect", { x: 0.85, y, w: 0.06, h: 0.38, fill: { color: C.brand }, line: { color: C.brand } });
    }
    s.addShape("roundRect", {
      x: 1.0, y: y + 0.08, w: 0.22, h: 0.22,
      fill: { color: it.on ? C.brand : "FFFFFF" }, line: { color: it.on ? C.brand : C.muted },
      rectRadius: 0.04,
    });
    if (it.on) s.addText("✓", { x: 1.0, y: y + 0.04, w: 0.22, h: 0.28, fontSize: 11, bold: true, color: "FFFFFF", align: "center" });
    s.addText(it.n, {
      x: 1.3, y, w: 3.0, h: 0.38,
      fontFace: FONT_B, fontSize: 11, bold: it.on, color: it.on ? C.brand : C.ink, valign: "middle",
    });
  });

  // right: explanation
  s.addText(
    [
      { text: "🔍  Search\n", options: { bold: true, fontSize: 14, color: C.brand } },
      { text: "Type any part of an IFB Point name OR its code. The list narrows down live as you type.\n\n",
        options: { fontSize: 12, color: C.ink } },
      { text: "✅  All\n", options: { bold: true, fontSize: 14, color: C.brand } },
      { text: "If you've searched, this ticks every result. With no search, it clears all ticks (= shows every point in the charts).\n\n",
        options: { fontSize: 12, color: C.ink } },
      { text: "✖  Clear\n", options: { bold: true, fontSize: 14, color: C.brand } },
      { text: "Empties the search box AND unticks everything — quickest way back to a clean slate.\n\n",
        options: { fontSize: 12, color: C.ink } },
      { text: "☑  Checkboxes\n", options: { bold: true, fontSize: 14, color: C.brand } },
      { text: "Tick one or many. The charts and KPIs on the right update only for the ticked points.",
        options: { fontSize: 12, color: C.ink } },
    ],
    { x: 4.9, y: 1.95, w: 7.9, h: 5.0, valign: "top", lineSpacingMultiple: 1.3 }
  );

  pageNumber(s, 8, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 9 — Marimekko chart
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "THE  MIX  CHART", "Each column is a day. Its width is volume, its colours are outcomes.");

  // Legend / colour key
  const segs = [
    { n: "Interested",     c: C.good },
    { n: "Not Interested", c: C.purple },
    { n: "Contacted",      c: "86EFAC" },
    { n: "Not Contacted",  c: C.bad },
    { n: "RnR",            c: C.warn },
    { n: "Untouched",      c: "CBD5E1" },
  ];
  let lx = 0.6;
  segs.forEach(g => {
    s.addShape("ellipse", { x: lx, y: 1.95, w: 0.2, h: 0.2, fill: { color: g.c }, line: { color: g.c } });
    s.addText(g.n, {
      x: lx + 0.25, y: 1.88, w: 1.6, h: 0.36,
      fontFace: FONT_B, fontSize: 11, bold: true, color: C.ink, valign: "middle",
    });
    lx += 1.95;
  });

  // Placeholder for chart screenshot
  placeholderImage(s, 0.6, 2.55, 8.2, 3.2, "Marimekko chart from Overview Dashboard");

  // right column: what it tells you
  s.addText("How to read it", {
    x: 9.0, y: 2.55, w: 3.7, h: 0.4,
    fontFace: FONT_H, fontSize: 16, bold: true, color: C.brandD,
  });
  s.addText(
    [
      { text: "▣  WIDTH\n", options: { bold: true, color: C.brand } },
      { text: "Fatter column = more follow-ups landed in that period.\n\n", options: { color: C.slate, fontSize: 11.5 } },
      { text: "▣  HEIGHT\n", options: { bold: true, color: C.brand } },
      { text: "Each colour's share = how many calls ended that way.\n\n", options: { color: C.slate, fontSize: 11.5 } },
      { text: "▣  HOVER\n", options: { bold: true, color: C.brand } },
      { text: "Mouse over a column for the exact counts & %.\n\n", options: { color: C.slate, fontSize: 11.5 } },
      { text: "▣  CIRCLES ABOVE\n", options: { bold: true, color: C.brand } },
      { text: "Click any colour circle to toggle that outcome on/off in the chart.", options: { color: C.slate, fontSize: 11.5 } },
    ],
    { x: 9.0, y: 3.0, w: 3.85, h: 3.5, valign: "top", fontFace: FONT_B, fontSize: 12, lineSpacingMultiple: 1.3 }
  );

  // small notes strip
  s.addShape("roundRect", {
    x: 0.6, y: 6.0, w: 8.2, h: 0.85,
    fill: { color: C.brandL }, line: { color: C.line }, rectRadius: 0.1,
  });
  s.addText(
    [
      { text: "Quick read:  ", options: { bold: true, color: C.brand } },
      { text: "Lots of dark-red (Not Contacted)? Customers aren't picking up at all. ", options: {} },
      { text: "Lots of amber (RnR)? They pick up but don't answer your call — try a different time slot.", options: {} },
    ],
    { x: 0.85, y: 6.0, w: 7.9, h: 0.85, fontFace: FONT_B, fontSize: 11, color: C.slate, valign: "middle", lineSpacingMultiple: 1.3 }
  );

  pageNumber(s, 9, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 10 — Insights panel
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "AUTO  INSIGHTS", "The chart explains itself, in plain English.");

  // Mock insights panel
  s.addShape("roundRect", {
    x: 0.6, y: 1.95, w: 6.5, h: 5,
    fill: { color: "FFFFFF" }, line: { color: C.line, width: 1.5 }, rectRadius: 0.14,
  });
  s.addShape("rect", { x: 0.6, y: 1.95, w: 6.5, h: 0.5, fill: { color: C.brand }, line: { color: C.brand } });
  s.addText("👆  Insights — Last 7 Days", {
    x: 0.85, y: 1.95, w: 6.0, h: 0.5,
    fontFace: FONT_B, fontSize: 13, bold: true, color: "FFFFFF", valign: "middle",
  });
  s.addText(
    [
      { text: "342 follow ups logged this week.\n\n", options: { bold: true, color: C.ink, fontSize: 13 } },
      { text: "Today is up 18% vs the week's average.\n\n", options: { color: C.good, bold: true } },
      { text: "Peak day: Wednesday with 71 follow ups.\nLow day: Sunday with 12 follow ups.\n\n", options: { color: C.slate } },
      { text: "Dominant outcome: Contacted (54%).\n", options: { color: C.slate } },
      { text: "Not Contacted is over a third of the volume — worth a callback push.\n\n", options: { color: C.bad, italic: true } },
      { text: "8 RnR follow ups still need a fresh attempt.", options: { color: C.warn, bold: true } },
    ],
    { x: 0.85, y: 2.65, w: 6.0, h: 4.0, fontFace: FONT_B, fontSize: 12, lineSpacingMultiple: 1.4, valign: "top" }
  );

  // Right side — what's in it
  s.addText("What the panel covers", {
    x: 7.4, y: 1.95, w: 5.3, h: 0.4,
    fontFace: FONT_H, fontSize: 16, bold: true, color: C.brandD,
  });
  const items = [
    "Total follow-ups in the window",
    "How today / this week / this month compares to the average",
    "Peak and low periods (ignoring days with no data)",
    "The dominant outcome — what most calls ended as",
    "Warning if Not Contacted is over 20%",
    "Untouched share, with context (\"nearly all\", \"more than half\", \"over a third\")",
    "Interested rate when it's healthy (>10%)",
    "RnR callbacks still pending, grammar-correct",
  ];
  items.forEach((t, i) => {
    s.addShape("ellipse", {
      x: 7.4, y: 2.5 + i * 0.5, w: 0.18, h: 0.18,
      fill: { color: C.brand }, line: { color: C.brand },
    });
    s.addText(t, {
      x: 7.7, y: 2.4 + i * 0.5, w: 5.0, h: 0.45,
      fontFace: FONT_B, fontSize: 12, color: C.ink,
    });
  });

  pageNumber(s, 10, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 11 — Three time lenses (Day / Week / Month)
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "THREE  TIME  LENSES", "Same region, three zoom levels — stacked on one screen.");

  const lenses = [
    { ico: "📅", t: "Day Wise",  sub: "Last 7 Days",
      d: "Spot today's energy. Are calls landing right now? Where's yesterday's dip?",
      color: C.brand },
    { ico: "📆", t: "Week Wise", sub: "Last 4 Weeks",
      d: "Catch trends — is this week beating last? Are RnRs creeping up week-on-week?",
      color: C.accent },
    { ico: "🗓",  t: "Month Wise", sub: "Last 6 Months",
      d: "Strategic view — seasonal peaks, the long arc of interest rate, slow months.",
      color: "8B5CF6" },
  ];
  const w = 4.0, gap = 0.3;
  const startX = (SW - (3 * w + 2 * gap)) / 2;
  lenses.forEach((l, i) => {
    const x = startX + i * (w + gap);
    s.addShape("roundRect", {
      x, y: 2.05, w, h: 4.8,
      fill: { color: "FFFFFF" }, line: { color: l.color, width: 1.5 }, rectRadius: 0.14,
    });
    s.addShape("rect", { x, y: 2.05, w, h: 0.7, fill: { color: l.color }, line: { color: l.color } });
    s.addText(`${l.ico}  ${l.t}`, {
      x: x + 0.2, y: 2.05, w: w - 0.4, h: 0.7,
      fontFace: FONT_H, fontSize: 18, bold: true, color: "FFFFFF", valign: "middle",
    });
    s.addText(l.sub, {
      x, y: 2.9, w, h: 0.4,
      fontFace: FONT_B, fontSize: 12, italic: true, color: l.color, align: "center", bold: true,
    });
    s.addText(l.d, {
      x: x + 0.25, y: 3.4, w: w - 0.5, h: 3.0,
      fontFace: FONT_B, fontSize: 13, color: C.slate, lineSpacingMultiple: 1.4,
    });
  });

  pageNumber(s, 11, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 12 — Part 2 divider
// =========================================================================
{
  const s = pres.addSlide();
  bgDark(s);
  s.addShape("ellipse", {
    x: SW - 4, y: 3.5, w: 7, h: 7,
    fill: { color: C.warn, transparency: 65 }, line: { color: C.warn, transparency: 65 },
  });
  s.addShape("ellipse", {
    x: -3.5, y: -3.5, w: 7, h: 7,
    fill: { color: C.brand, transparency: 60 }, line: { color: C.brand, transparency: 60 },
  });

  s.addText("PART  TWO", {
    x: 0.8, y: 2.2, w: 12, h: 0.5,
    fontFace: FONT_B, fontSize: 16, bold: true, color: "FDE68A", charSpacing: 12,
  });
  s.addText("The  IFB Point  Workspace", {
    x: 0.8, y: 2.8, w: 12, h: 1.4,
    fontFace: FONT_H, fontSize: 54, bold: true, color: "FFFFFF",
  });
  s.addText("Where each customer becomes a closed loop.", {
    x: 0.8, y: 4.4, w: 11.5, h: 0.6,
    fontFace: FONT_B, fontSize: 18, italic: true, color: "FED7AA",
  });
}

// =========================================================================
// SLIDE 13 — IFB Point view top (header + KPIs)
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "OPENING  AN  IFB  POINT", "Click a point name in the rail — or open the link with its code.");

  placeholderImage(s, 0.6, 1.95, 12.2, 2.2, "Per-IFB-Point header — name, code, 5 KPIs, follow-up stages");

  s.addShape("roundRect", {
    x: 0.6, y: 4.35, w: 12.2, h: 2.5,
    fill: { color: C.brandL }, line: { color: C.line }, rectRadius: 0.12,
  });
  s.addText("What the top strip tells you", {
    x: 0.85, y: 4.45, w: 11.5, h: 0.4,
    fontFace: FONT_H, fontSize: 15, bold: true, color: C.brandD,
  });
  s.addText(
    [
      { text: "●  IFB Point name + code  ", options: { bold: true, color: C.brand } },
      { text: "— exactly which point you're looking at.\n", options: { color: C.slate } },
      { text: "●  Total Follow Ups  ", options: { bold: true, color: C.brand } },
      { text: "— the open book of customers for this point.\n", options: { color: C.slate } },
      { text: "●  Contact Status  ", options: { bold: true, color: C.brand } },
      { text: "— Contacted / Not Contacted / RnR + Empty (untouched) split.\n", options: { color: C.slate } },
      { text: "●  Interest  ", options: { bold: true, color: C.brand } },
      { text: "— how many of those who picked up actually wanted the product.\n", options: { color: C.slate } },
      { text: "●  Follow-Up Stage  ", options: { bold: true, color: C.brand } },
      { text: "— Post-Purchase, 1st 30 days, Pre-AMC, 8-Year Upgrade.", options: { color: C.slate } },
    ],
    { x: 0.85, y: 4.85, w: 11.5, h: 1.85, fontFace: FONT_B, fontSize: 12, lineSpacingMultiple: 1.4 }
  );

  pageNumber(s, 13, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 14 — Filter buttons (the big one)
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "FILTER  BUTTONS", "Five one-tap filters — the heart of the workspace.");

  const filters = [
    { ico: "📅", t: "Today Follow Up", c: C.brand,
      d: "Shows only customers due TODAY. Your call list for the next 8 hours.",
      impact: "All other date/stage filters reset to honour this." },
    { ico: "⚠", t: "Missed Follow Up", c: C.bad,
      d: "Calls that were due in the past but never closed.",
      impact: "Catches anything that slipped — sorted by oldest first." },
    { ico: "📆", t: "Follow Up Date", c: C.warn,
      d: "Open a calendar and pick any date or range you want to focus on.",
      impact: "Combines with Stage + Search so you can drill down precisely." },
    { ico: "📋", t: "Open Followup", c: "8B5CF6",
      d: "Anything not yet closed — Pending, RnR, Not Contacted, all open work.",
      impact: "Your one-click 'what's left to do?'" },
    { ico: "📞", t: "Attempted", c: C.good,
      d: "Customers you've already tried — Contacted, Not Contacted, or RnR.",
      impact: "Audit view — verify what's been worked on this period." },
  ];
  const colW = 2.4, colH = 4.85, gap = 0.13;
  const totalW = 5 * colW + 4 * gap;
  const startX = (SW - totalW) / 2;
  filters.forEach((f, i) => {
    const x = startX + i * (colW + gap);
    s.addShape("roundRect", {
      x, y: 1.95, w: colW, h: colH,
      fill: { color: "FFFFFF" }, line: { color: f.c, width: 1.5 }, rectRadius: 0.12,
    });
    s.addShape("rect", { x, y: 1.95, w: colW, h: 0.85, fill: { color: f.c }, line: { color: f.c } });
    s.addText(f.ico, {
      x, y: 2.0, w: colW, h: 0.5,
      fontFace: FONT_B, fontSize: 22, color: "FFFFFF", align: "center",
    });
    s.addText(f.t, {
      x, y: 2.45, w: colW, h: 0.4,
      fontFace: FONT_H, fontSize: 12, bold: true, color: "FFFFFF", align: "center",
    });
    s.addText(f.d, {
      x: x + 0.15, y: 3.0, w: colW - 0.3, h: 2.3,
      fontFace: FONT_B, fontSize: 11, color: C.ink, lineSpacingMultiple: 1.3,
    });
    // impact pill at bottom
    s.addShape("roundRect", {
      x: x + 0.12, y: 5.45, w: colW - 0.24, h: 1.3,
      fill: { color: C.brandL }, line: { color: C.line }, rectRadius: 0.06,
    });
    s.addText(
      [
        { text: "Impact:\n", options: { bold: true, color: C.brand, fontSize: 9.5, charSpacing: 2 } },
        { text: f.impact, options: { color: C.slate, fontSize: 10 } },
      ],
      { x: x + 0.2, y: 5.5, w: colW - 0.4, h: 1.2, fontFace: FONT_B, lineSpacingMultiple: 1.25 }
    );
  });

  pageNumber(s, 14, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 15 — Stage filter + Search + Date range
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "NARROW  IT  DOWN", "Stage · Search · Date range — used together with the filter buttons.");

  // three columns
  const cards = [
    { ico: "🏷", t: "Follow-Up Stage", c: C.brand,
      l1: "Post-Purchase",
      l2: "1st 30 days call",
      l3: "Pre-AMC",
      l4: "8 Year Upgrade",
      l5: "Greetings",
      d: "Pick the stage of the customer journey. Each stage carries a different script — handle them as a batch." },
    { ico: "🔎", t: "Search Box", c: C.accent,
      l1: "Customer name",
      l2: "Phone number",
      l3: "Email address",
      l4: "Customer ID",
      l5: "(partial match works)",
      d: "Type any fragment. The table filters instantly — useful when a customer rings YOU and you need their record in two seconds." },
    { ico: "📆", t: "Date Range", c: C.warn,
      l1: "Default: today onwards",
      l2: "Pick start + end date",
      l3: "Plays nice with all buttons",
      l4: "Resets when you tap Today/Missed",
      l5: " ",
      d: "Limit the table to a specific date window — perfect for monthly reviews or auditing a campaign push." },
  ];
  const w = 4.0, gap = 0.3;
  const startX = (SW - (3 * w + 2 * gap)) / 2;
  cards.forEach((c, i) => {
    const x = startX + i * (w + gap);
    s.addShape("roundRect", {
      x, y: 1.95, w, h: 4.85,
      fill: { color: "FFFFFF" }, line: { color: c.c, width: 1.5 }, rectRadius: 0.14,
    });
    s.addShape("ellipse", {
      x: x + 0.25, y: 2.15, w: 0.7, h: 0.7,
      fill: { color: c.c }, line: { color: c.c },
    });
    s.addText(c.ico, {
      x: x + 0.25, y: 2.15, w: 0.7, h: 0.7,
      fontSize: 20, color: "FFFFFF", align: "center", valign: "middle",
    });
    s.addText(c.t, {
      x: x + 1.0, y: 2.18, w: w - 1.1, h: 0.65,
      fontFace: FONT_H, fontSize: 18, bold: true, color: C.ink, valign: "middle",
    });
    // bullets
    const bullets = [c.l1, c.l2, c.l3, c.l4, c.l5].filter(x => x && x.trim());
    bullets.forEach((b, j) => {
      s.addText("•  " + b, {
        x: x + 0.3, y: 3.0 + j * 0.35, w: w - 0.5, h: 0.32,
        fontFace: FONT_B, fontSize: 11.5, color: C.slate,
      });
    });
    // description box at bottom
    s.addShape("roundRect", {
      x: x + 0.18, y: 5.05, w: w - 0.36, h: 1.65,
      fill: { color: C.brandL }, line: { color: C.line }, rectRadius: 0.08,
    });
    s.addText(c.d, {
      x: x + 0.32, y: 5.15, w: w - 0.64, h: 1.45,
      fontFace: FONT_B, fontSize: 11, color: C.ink, lineSpacingMultiple: 1.3,
    });
  });

  pageNumber(s, 15, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 16 — The customer table
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "THE  CUSTOMER  TABLE", "Your daily worklist. Every row is one customer.");

  placeholderImage(s, 0.6, 1.95, 7.5, 4.85, "Customer table — rows + columns");

  // right: column-by-column callouts
  s.addText("Every column, decoded", {
    x: 8.3, y: 1.95, w: 4.4, h: 0.4,
    fontFace: FONT_H, fontSize: 16, bold: true, color: C.brandD,
  });
  const cols = [
    ["✏",  "Edit",        "Opens the Edit Lead dialog for that row."],
    ["👁",  "Eye",         "Pulls the customer's full IFB profile from the live API."],
    ["📋", "Stage",       "What follow-up stage the customer is at."],
    ["🙍", "Name",        "Customer + machine model in one line."],
    ["☎", "Contact",     "Phone (primary + alternate) and email."],
    ["📅", "Next Appt",   "When you've promised to call again."],
    ["🟢", "Call Status", "Coloured chip: Contacted (green), Not Contacted (red), RnR (amber)."],
    ["💬", "Remarks",     "Up to 60 characters of context for the next caller."],
    ["🏁", "Final Status","WON / LOST / open — the closing decision."],
  ];
  cols.forEach((row, i) => {
    const y = 2.45 + i * 0.48;
    s.addText(row[0], {
      x: 8.3, y, w: 0.4, h: 0.4,
      fontSize: 14, valign: "middle",
    });
    s.addText(row[1], {
      x: 8.75, y, w: 1.3, h: 0.4,
      fontFace: FONT_B, fontSize: 11, bold: true, color: C.brand, valign: "middle",
    });
    s.addText(row[2], {
      x: 10.0, y, w: 2.85, h: 0.4,
      fontFace: FONT_B, fontSize: 10.5, color: C.slate, valign: "middle",
    });
  });

  pageNumber(s, 16, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 17 — Edit Lead dialog (the big one)
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "EDIT  LEAD  (✏)", "Three clicks to log a call — the dialog adapts as you go.");

  // flow diagram — three branches from "Call Status"
  // Center node
  s.addShape("roundRect", {
    x: 0.6, y: 2.0, w: 3.2, h: 0.85,
    fill: { color: C.brandD }, line: { color: C.brandD }, rectRadius: 0.1,
  });
  s.addText("CALL STATUS", {
    x: 0.6, y: 2.0, w: 3.2, h: 0.35,
    fontFace: FONT_B, fontSize: 9, bold: true, color: "C7D2FE", charSpacing: 4, align: "center",
  });
  s.addText("Contacted  /  Not Contacted  /  RnR", {
    x: 0.6, y: 2.3, w: 3.2, h: 0.5,
    fontFace: FONT_B, fontSize: 12, bold: true, color: "FFFFFF", align: "center",
  });

  // Branch 1 — Contacted
  s.addShape("rect", { x: 4.0, y: 2.4, w: 0.5, h: 0.04, fill: { color: C.good }, line: { color: C.good } });
  s.addShape("roundRect", {
    x: 4.55, y: 1.95, w: 8.2, h: 1.95,
    fill: { color: C.goodBg }, line: { color: C.good, width: 1.5 }, rectRadius: 0.12,
  });
  s.addText("🟢  If Contacted", {
    x: 4.75, y: 2.05, w: 7.8, h: 0.4,
    fontFace: FONT_H, fontSize: 14, bold: true, color: "166534",
  });
  s.addText(
    [
      { text: "Interested?  →  Interested  ", options: { bold: true } },
      { text: "leads to a Next Appointment date.\n", options: {} },
      { text: "Interested?  →  Not Interested  ", options: { bold: true } },
      { text: "leads to a ", options: {} },
      { text: "Reason  ", options: { bold: true, color: C.brand } },
      { text: "dropdown (Service issue / Others) and auto-marks Final Status as LOST.\n", options: {} },
      { text: "Remarks", options: { bold: true } },
      { text: " — up to 60 characters. Required to enable Save.", options: {} },
    ],
    { x: 4.75, y: 2.45, w: 7.8, h: 1.45, fontFace: FONT_B, fontSize: 11.5, color: C.ink, lineSpacingMultiple: 1.35 }
  );

  // Branch 2 — Not Contacted
  s.addShape("rect", { x: 2.2, y: 2.85, w: 0.04, h: 0.6, fill: { color: C.bad }, line: { color: C.bad } });
  s.addShape("rect", { x: 2.2, y: 3.45, w: 2.35, h: 0.04, fill: { color: C.bad }, line: { color: C.bad } });
  s.addShape("roundRect", {
    x: 4.55, y: 3.95, w: 8.2, h: 1.4,
    fill: { color: C.badBg }, line: { color: C.bad, width: 1.5 }, rectRadius: 0.12,
  });
  s.addText("🔴  If Not Contacted", {
    x: 4.75, y: 4.05, w: 7.8, h: 0.4,
    fontFace: FONT_H, fontSize: 14, bold: true, color: "991B1B",
  });
  s.addText(
    "Pick a Next Appointment date (anything from tomorrow onwards) and a Remark. That's it — the row updates and a fresh callback is scheduled.",
    { x: 4.75, y: 4.45, w: 7.8, h: 0.85, fontFace: FONT_B, fontSize: 11.5, color: C.ink, lineSpacingMultiple: 1.35 }
  );

  // Branch 3 — RnR
  s.addShape("rect", { x: 2.2, y: 4.4, w: 0.04, h: 1.05, fill: { color: C.warn }, line: { color: C.warn } });
  s.addShape("rect", { x: 2.2, y: 5.45, w: 2.35, h: 0.04, fill: { color: C.warn }, line: { color: C.warn } });
  s.addShape("roundRect", {
    x: 4.55, y: 5.4, w: 8.2, h: 1.4,
    fill: { color: C.warnBg }, line: { color: C.warn, width: 1.5 }, rectRadius: 0.12,
  });
  s.addText("🟠  If RnR  (Ring-no-Response)", {
    x: 4.75, y: 5.5, w: 7.8, h: 0.4,
    fontFace: FONT_H, fontSize: 14, bold: true, color: "92400E",
  });
  s.addText(
    "Same as Not Contacted — pick the next attempt date and add a remark. The system silently counts your RnRs (see next slide).",
    { x: 4.75, y: 5.9, w: 7.8, h: 0.85, fontFace: FONT_B, fontSize: 11.5, color: C.ink, lineSpacingMultiple: 1.35 }
  );

  pageNumber(s, 17, 18);
  footerBrand(s);
}

// =========================================================================
// SLIDE 18 — The 3-RnR rule, Eye icon, pagination + closing
// =========================================================================
{
  const s = pres.addSlide();
  bgWhite(s);
  sideRail(s);
  titleBlock(s, "ADDITIONAL  RULES  &  TOOLS", "Discipline built in, plus the helpers around the workspace.");

  // Top row: 3 cards
  const cards = [
    { ico: "⛔", t: "The 3-RnR Auto-LOST Rule",
      d: "If the same customer has been RnR three times already, the next save (regardless of status) automatically marks their Final Status as LOST. No human judgement call needed.",
      c: C.bad },
    { ico: "👁", t: "The Eye Icon",
      d: "Need the customer's full IFB record — address, serial number, installation date? Click 👁 and it pulls live from the IFB API. No need to leave the dashboard.",
      c: C.brand },
    { ico: "↔", t: "Pagination & Page Size",
      d: "Pages of 25, 50, or 100 customers. Use Previous / Next to step through. The table stays compact so the filters stay visible.",
      c: C.warn },
  ];
  const cw = 4.0, gap = 0.15;
  const startX = (SW - (3 * cw + 2 * gap)) / 2;
  cards.forEach((c, i) => {
    const x = startX + i * (cw + gap);
    s.addShape("roundRect", {
      x, y: 1.95, w: cw, h: 2.7,
      fill: { color: "FFFFFF" }, line: { color: c.c, width: 1.5 }, rectRadius: 0.12,
    });
    s.addShape("ellipse", {
      x: x + 0.25, y: 2.1, w: 0.65, h: 0.65,
      fill: { color: c.c }, line: { color: c.c },
    });
    s.addText(c.ico, {
      x: x + 0.25, y: 2.1, w: 0.65, h: 0.65,
      fontSize: 18, color: "FFFFFF", align: "center", valign: "middle",
    });
    s.addText(c.t, {
      x: x + 0.95, y: 2.08, w: cw - 1.1, h: 0.7,
      fontFace: FONT_H, fontSize: 13.5, bold: true, color: C.ink, valign: "middle",
    });
    s.addText(c.d, {
      x: x + 0.25, y: 2.9, w: cw - 0.5, h: 1.7,
      fontFace: FONT_B, fontSize: 11.5, color: C.slate, lineSpacingMultiple: 1.35,
    });
  });

  // Bottom: best practices box
  s.addShape("roundRect", {
    x: 0.6, y: 4.9, w: 12.2, h: 1.95,
    fill: { color: C.brandD }, line: { color: C.brandD }, rectRadius: 0.14,
  });
  s.addText("BEST  PRACTICES", {
    x: 0.85, y: 5.0, w: 11.5, h: 0.4,
    fontFace: FONT_B, fontSize: 12, bold: true, color: "C7D2FE", charSpacing: 6,
  });
  s.addText(
    [
      { text: "✓  ", options: { color: C.good, bold: true } },
      { text: "Start your day on Today Follow Up — it's your built-in call list.\n", options: { color: "FFFFFF" } },
      { text: "✓  ", options: { color: C.good, bold: true } },
      { text: "Sweep Missed Follow Up at midday to catch anything that slipped.\n", options: { color: "FFFFFF" } },
      { text: "✓  ", options: { color: C.good, bold: true } },
      { text: "Always fill Remarks — the next caller (or you tomorrow) will thank you.\n", options: { color: "FFFFFF" } },
      { text: "✓  ", options: { color: C.good, bold: true } },
      { text: "Use Reason = 'Service issue' faithfully — it flags genuine product problems, not just churn.", options: { color: "FFFFFF" } },
    ],
    { x: 0.85, y: 5.4, w: 11.5, h: 1.4, fontFace: FONT_B, fontSize: 12, lineSpacingMultiple: 1.3 }
  );

  pageNumber(s, 18, 18);
  footerBrand(s);
}

// =========================================================================
// SAVE
// =========================================================================
const out = path.join(__dirname, "IFB_Points_Dashboard_User_Guide.pptx");
pres.writeFile({ fileName: out }).then(name => {
  console.log("wrote", name);
});
