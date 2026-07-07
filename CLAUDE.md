# IFB Point Dashboard — CLAUDE.md

Project memory for Claude. Keep this file updated after every significant change.

---

## Project Overview

**IFB Point Dashboard** is a Streamlit web app for IFB Industries franchise point owners to manage and track customer follow-ups. It has two screens:

1. **Login screen** — simple email/password gate (`/?` with no auth)
2. **Individual point view** — per-IFB-point lead management (`/?id=<code>`)
3. **Analytics Console (Overview Dashboard)** — admin analytics for all IFB points (`/?auth=ok`)

---

## File Structure

```
IFB point Dashboard/
├── streamlit_app.py          # Main app entry point — login, per-point lead view
├── overview_dashboard.py     # Analytics Console (/?auth=ok) — all IFB points overview
├── config.py                 # Shared API credentials (rarely changes)
├── refresh_data.py           # Manual data refresh script
├── IFB_Point_Master.txt      # Tab-separated: code\tname — 545 IFB points
├── ifb_point.db              # SQLite: lead/follow-up data (committed to git)
├── ifb_counter.db            # SQLite: counter/usage tracking (committed to git)
├── scripts/
│   └── sync_api.py           # API sync script
├── data/                     # Runtime-generated JSON (gitignored)
├── pyproject.toml
├── requirements.txt
└── uv.lock
```

**External reference file (not in repo):**
`C:\myfiles\IFB\Project\IT\IFB Point Dashboard - notes\Unique_ChannelCode_ChannelName (1).xlsx`
— 545 rows, columns: `Channel Code`, `Channel Name`. Used as primary source for channel name loading.

---

## Running the App

```bash
# Using uv (recommended)
uv run streamlit run streamlit_app.py

# Or with venv activated
streamlit run streamlit_app.py
```

App runs at `http://127.0.0.1:8501`

- `/?auth=ok` → Analytics Console (overview dashboard)
- `/?id=<IFB_POINT_CODE>` → Individual point follow-up view

---

## Authentication

**Login credentials (hardcoded, temporary):**
- Email: `s_aswin@ifbglobal.com`
- Password: `rpi12345`

Auth is persisted via `?auth=ok` query param in the URL.

---

## Database

### `ifb_point.db`
Main leads database. Table: `api_leads`
```sql
SELECT ifb_point, status, final_status, interested, follow_up, lead_date
FROM api_leads
```

### `ifb_counter.db`
Counter/usage tracking database. Both DBs are committed to GitHub.

---

## Key Data Sources

### Channel Names (`_load_channel_names()` in `streamlit_app.py`)
- **Primary source**: Excel file at `../IFB Point Dashboard - notes/Unique_ChannelCode_ChannelName (1).xlsx`
- **Fallback**: `IFB_Point_Master.txt` (tab-separated: `code\tname`)
- Names are cleaned by `_clean_channel_name()` which strips prefixes:
  - `"IFB Industries Limit- "`
  - `"IFB Industries Limited- "`
  - `"IFB Industries Ltd- "`
- Example: `"IFB Industries Limit- IFB Point City mall"` → `"IFB Point City mall"`

### Master Codes (`_load_master_codes()`)
- Loaded from `IFB_Point_Master.txt`
- Used to validate incoming IFB point codes

---

## Analytics Console (`overview_dashboard.py`)

### Navigation (☰ hamburger menu)
The topbar has a `☰` popover (left of the title) with two views, tracked in
`st.session_state["_ov_view"]` (default `"analytics"`). `_POPOVER_CSS` (emitted in
`render_overview_dashboard` for both views) hides Streamlit's trailing "expand_more"
chevron so the button is icon-only.
1. **📊 IFB Point Analytics** — the normal dashboard (KPIs + Day/Week/Month charts).
2. **🗺️ RM Mapping** — `_render_rm_mapping()`: a **DataTables-style** table (built from
   `st.columns`, not `st.data_editor`) of `login_mapping.db` joined with IFB Point names
   from `IFB_Point_Master.txt`. Styled via `_RM_CSS`.
   - Columns (`_RM_COLS`, ratio-based widths): `IFB Point ID` (key) · `IFB Point Name` ·
     `Branch` · `Region` (coloured pill via `_rm_badge`) · `Cluster Mgr` ·
     `Cluster Mgr Email` · `Retail Name` · `Retail Email` · **Edit** (✏️ per row).
   - **DataTables chrome**: "Showing X to Y of Z items" + Search box (top);
     clickable sortable headers (▲/▼, `_rm_sort_col`/`_rm_sort_asc`); footer pager
     (‹ Prev · page numbers · Next › with active page as `type="primary"`) +
     "Show N entries" selectbox (`_rm_psize`, options 10/25/50/100). Page = `_rm_page`.
   - **Editing**: click a row's ✏️ → `@st.dialog _rm_edit_dialog` opens a 7-field form
     (ID shown read-only). Save → `_save_rm_row` → `_apply_rm_updates`:
     - **IFB Point Name → `IFB_Point_Master.txt`** (`_write_master_names`, keyed by ID;
       clears `streamlit_app._load_channel_names`/`_load_master_codes` lru_caches).
     - **Other fields → `login_mapping.db`** via `UPDATE ... WHERE IFBpoint_id=?`
       (empty string writes `NULL`). `_RM_COL_TO_DB` maps labels → DB columns.
     - A `_rm_flash` session key carries the post-save toast across the rerun.
   - Scoped by `allowed_codes` (admin/empty = all ~550 points).
   - `render_overview_dashboard(..., master_file=MASTER_FILE)` param; falls back to
     `db_path.parent / "IFB_Point_Master.txt"` if not passed.

> The old rail **"🔍 Search IFB Point or Code…"** box was removed; the
> Region/Branch/IFB Point multiselect cascade is now the only rail filter (`_q = ""`).

### Layout Structure
```
Fixed header (sticky): IFB Point name + 5 stat badges + API sync status
─────────────────────────────────────────────────────────────────────
Two-pane layout:
  Left Rail (1.85)          │  Main (8.15)
  ────────────────────────  │  ──────────────────────────────────
  🔍 Search box             │  [Stores][Cust Alloc][Attempted][Connected][Interested][Not Cont]  ← KPIs
  [✅ All]  [✖ Clear]       │  ← horizontally parallel with search+buttons
  ────────────────────────  │  ──────────────────────────────────
  Scrollable checkbox list  │  📅 Day Wise — Last 7 Days
  (all IFB points)          │    [7 segment circles] | 👆 Click a circle...
                            │    [Marimekko chart]   | [Insights panel]
                            │
                            │  📆 Week Wise — Last 4 Weeks
                            │    [7 segment circles] | 👆 Click a circle...
                            │    [Marimekko chart]   | [Insights panel]
                            │
                            │  🗓️ Month Wise — Last 6 Months
                            │    [7 segment circles] | 👆 Click a circle...
                            │    [Marimekko chart]   | [Insights panel]
```

### 6 KPI Cards
`Total Stores` · `Total Customers Allocated` · `Calls Attempted` · `Calls Connected` · `Interested Customers` · `Not Contacted`
- Height: `76px` each
- Horizontally aligned with the rail's search + All/Clear buttons (both have `margin-top:14px`)
- **Total Stores**: main = count of scope codes; sub = "Active Calling Stores" (today's distinct IFB points with status Contacted/RnR/Not Reachable)
- **Calls Attempted**: `Contacted + RnR + Not Reachable` (any call attempt made)
- **Calls Connected**: `Contacted` only (call actually picked up)

### 7 Segment Options (Marimekko chart)
```python
_MK_SEGMENTS = [
    ("Interested",      "#16A34A"),
    ("Not Interested",  "#9333EA"),
    ("Contacted",       "#86EFAC"),
    ("Not Contacted",   "#DC2626"),
    ("Not Reachable",   "#F97316"),
    ("RnR",             "#D97706"),
    ("Untouched",       "#CBD5E1"),
]
```
- Rendered as circle checkboxes above each chart section
- Clicking toggles segment visibility on the Marimekko chart
- Hint text `"👆 Click a circle to filter the chart view"` shown in the right column of the checkbox row

### Marimekko Chart
- Column WIDTH ∝ lead volume per period; HEIGHT = segment mix %
- No vertical spike line on hover (`showspikes=False`)
- Full-column tooltip shows all 7 segment counts + % on hover
- Chart height: `158px`

### Insights Panel (right of each chart, `height:158px`)
Written narrative — NOT a visual duplicate of the chart. Shows:
1. Total follow ups across the window
2. Current period vs average (with % delta)
3. Peak and low periods (excludes zero-data periods)
4. Dominant outcome segment
5. Not Contacted % (if ≥ 20%)
6. Untouched % with contextual wording (nearly all / more than half / over a third / exact %)
7. Interested rate (if ≥ 10%)
8. RnR callbacks (grammar-correct: "1 follow up" vs "N follow ups")

All "Leads" terminology replaced with "Follow Up" / "follow ups" throughout the UI.

### Rail Search Behaviour
- Search matches by **channel name** OR **channel code** (partial match, case-insensitive)
- Typing resets all selections (prevents "All" state contaminating search results)
- **✅ All** button:
  - With active search → selects only the filtered results, ticks those checkboxes
  - No search → resets to default (no ticks, all points in background data)
- **✖ Clear** button → clears search text + deselects all checkboxes + resets to all points
- `_ov_sel = set()` (empty) = all IFB points shown (default state, no ticks)
- `_ov_sel = {code1, ...}` = only those codes shown (ticked)

### Session State Keys (Rail)
| Key | Purpose |
|-----|---------|
| `_ov_sel` | Set of selected IFB point codes |
| `_ov_search` | Text input widget value |
| `_ov_search_clear` | Flag: clear search on next run (before widget instantiation) |
| `_ov_prev_q` | Previous query — detects changes to reset selections |
| `cb_{code}` | Individual checkbox state per IFB point |

---

## Per-Point View (`streamlit_app.py`)

Accessed via `/?id=<code>`. Shows leads for a single IFB point with:
- Filter bar: Today Follow Up / Missed Follow Up / Follow Up Date buttons
- Date range picker
- Stage filter (Post-Purchase / 1st 30 days call / Pre-AMC / 8 Year Upgrade / Greetings)
- Search box (Name · Phone · Email · ID)
- Leads table with eye icon (👁) for detailed customer lookup via API
- Status update modal: Contacted / RnR / Not Reachable + Interest + Remarks

---

## API Integration

```
Base URL: https://bseapi.ifbsupport.com/api
User: IFBFollowUPAPP
Pass: U29tZVJhbmRvbUJhc2U2NA==  (base64)
```

JWT token cached in `st.session_state["_api_jwt_token"]` for the session.

Eye icon (`👁`) fetches customer detail from `/api/...` using the composite key `{ifb_point_code}-{customer_id}`.

---

## Terminology

| Old term | Current term (UI) |
|----------|-------------------|
| Leads | Follow Up / Follow Ups |
| Total Leads (KPI) | Total Follow Up |

Variable names in code (`total_leads`, `api_leads` table) remain unchanged — internal only.

---

## Git / GitHub

- Remote: `ifbfollowup` → `https://github.com/IFB-Analytics/ifbpoint-followup.git`
- Branch: `main`
- Both `ifb_point.db` and `ifb_counter.db` are committed and tracked (whitelisted in `.gitignore`)
- `.venv/` and `data/` are gitignored

```bash
git push ifbfollowup main
```

---

## CSS Architecture (`_OVERVIEW_CSS` in `overview_dashboard.py`)

Key CSS rules and what they control:

| Selector | Purpose |
|----------|---------|
| `.block-container` | Page padding: `10px 20px 6px` |
| `stVerticalBlock` gap | `0.28rem` — controls spacing between stacked elements |
| `stVerticalBlockBorderWrapper > div > div` | Inner container padding: `7px 10px` |
| `.st-key-two_pane > div:first-child > div:first-child` | Rail margin-top: `14px` |
| `.st-key-two_pane > div:nth-child(2) > div:first-child` | Main col margin-top: `14px` (aligns KPIs with rail) |
| `.st-key-kpi_row` | KPI row: `padding:0`, `margin-bottom:14px` |
| `.st-key-c_container` | Scrollable rail list: white bg, `1.5px solid #E0E7FF` border |
| `[data-testid="stTextInput"] [data-baseweb="input"]` | Removes outer BaseWeb border (prevents double border) |

---

## Known Patterns & Gotchas

1. **Widget state timing**: Never write to a widget's session state key after it's been instantiated in the same run. Use a flag (`_ov_search_clear`) set on button click, read and applied **before** the widget renders on the next run.

2. **Checkbox state**: Individual `cb_{code}` keys must be explicitly set to `False` (not just popped) when clearing, because the button renders **before** the checkboxes in the script — so Streamlit allows the write.

3. **Channel name loading**: Always try Excel first (`openpyxl`/`pandas`), fall back to txt. The txt file has 1 entry with a corrupted character (`Vanasthalipuram\x00`); the Excel is clean.

4. **Zero-data periods**: When finding peak/low in insights, filter out buckets with `total == 0` — they represent no-data periods, not genuine lows.

5. **Avg calculation**: Use only non-zero prior periods in average so empty slots don't drag the avg down.

6. **`_q in str(c).lower()`**: Channel codes from the DB may be non-string types; always cast with `str(c)` before the `in` check.
