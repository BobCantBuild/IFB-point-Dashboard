# IFB Point — Customer Follow-Up Dashboard

A Streamlit web dashboard for tracking and managing customer follow-ups for an IFB service point. Sales/support staff can see every installation's follow-up stage, log contact status, set next appointment dates, and record interest and remarks — all from a browser, with no local install needed.

Live app → **https://ifb-point-dashboard.streamlit.app/**

---

## How the data flows — end to end

```
IFB BSE API
(bseapi.ifbsupport.com)
        │
        │  POST /api/Auth/login  →  JWT token
        │  GET  /api/IFBPointFollowUp/GetInstallationAgeingDetails
        │
        ▼
GitHub Actions (runs every 30 min on Azure infra)
  scripts/sync_api.py
        │
        │  writes  ──►  data/api_data.json  (committed to repo)
        │
        ▼
GitHub Repository
  data/api_data.json   ← single source of truth for customer records
        │
        │  Streamlit Cloud reads this file at every page load
        ▼
streamlit_app.py
  load_all()
    ├── reads data/api_data.json          (customer base records)
    └── reads ifb_point.db / followups    (staff edits — status, remarks, etc.)
        │
        ▼
  Dashboard UI  (visible at ifb-point-dashboard.streamlit.app)
```

---

## Why GitHub Actions is in the middle

`bseapi.ifbsupport.com` is behind a corporate firewall that only allows connections from IFB's own network and from whitelisted cloud IPs.

| Environment | IPs | Can reach API? |
|---|---|---|
| Streamlit Cloud | Google Cloud Platform | ❌ Blocked |
| GitHub Actions | Microsoft Azure | ✅ Allowed |
| Your local machine (on IFB network) | IFB LAN | ✅ Allowed |

Because Streamlit Cloud cannot call the API directly, a **GitHub Actions relay** is used:

1. GitHub Actions runs `scripts/sync_api.py` every 30 minutes on Azure infrastructure.
2. The script logs in, fetches all installation records, and writes them to `data/api_data.json`.
3. The file is committed back to the repository with `[skip ci]` so it does not trigger another run.
4. Streamlit Cloud reads `data/api_data.json` from the repo on every page load — no outbound API call needed.

If the API is temporarily unreachable the step is skipped (`continue-on-error: true`), the previous `api_data.json` is kept, and no failure email is sent.

---

## What the dashboard shows

### Fixed header (always visible)
- **Hero bar** — app title, sync status badge (`API Synced` / `Sync failed`), timestamp of last successful sync.
- **Stats row** — Total follow-ups · Contact status (Contacted / Not Contacted / Empty) · Interest (Interested / Not Interested / Empty) · Follow-Up Stage breakdown.

### Filter bar (pinned below header)
| Control | Purpose |
|---|---|
| Open Followup's / Attempted's | Toggle between all leads and leads where contact was attempted |
| Follow-Up Stage dropdown | Filter by bucket (Post-Purchase / 1st 30 days / Pre-AMC / 8 Year Upgrade) |
| Date range picker | Filter by purchase date |
| Search box | Free-text search across name, phone, email, customer ID |
| ↻ Refresh | Clears Streamlit cache and reloads data |

### Data table
11 columns per row:

| Col | Field | Source |
|---|---|---|
| ✏️ | Edit button | — |
| Customer Follow-Up | Computed bucket (see below) | Calculated |
| Customer Name | `customer_name` | API |
| Purchase Date | `purchase_date` | API |
| Machine Type | `machine_type` | API |
| Phone | `phone_number` | API |
| Email | `email_id` | API |
| Status | Contacted / Not Contacted | Staff edit (SQLite) |
| Next Appt | Next appointment date | Staff edit (SQLite) |
| Interested? | Interested / Not Interested | Staff edit (SQLite) |
| Remarks | Free-text notes | Staff edit (SQLite) |

### Follow-Up bucket logic

| Days since purchase | Bucket |
|---|---|
| 0 – 2 | Post-Purchase |
| 3 – 30 | 1st 30 days call |
| 31 – 1460 (4 years) | Pre-AMC |
| 1461 + | 8 Year Upgrade |

### Edit dialog
Clicking ✏️ opens a modal where staff can set Status, Next Appointment, Interested?, and Remarks. On save the values are written to `ifb_point.db` (SQLite) on Streamlit Cloud's ephemeral disk. They persist for the life of the deployment but will reset if the app is redeployed (limitation of Streamlit's free tier — a persistent DB like Supabase or PlanetScale would be needed to keep edits long-term).

---

## File structure

```
IFB point Dashboard/
├── streamlit_app.py              # Main app — UI, data loading, edit dialog
├── requirements.txt              # Python dependencies
│
├── data/
│   └── api_data.json             # Snapshot of API records (auto-updated by Actions)
│
├── scripts/
│   └── sync_api.py               # GitHub Actions script: login → fetch → write JSON
│
├── .github/
│   └── workflows/
│       └── sync-api.yml          # Workflow: runs sync_api.py every 30 min
│
├── .streamlit/
│   └── secrets.toml              # Local dev secrets (gitignored — never committed)
│
└── ifb_point.db                  # SQLite DB for staff edits (created at runtime, gitignored)
```

---

## API details

**Base URL:** `https://bseapi.ifbsupport.com/api`

| Step | Method | Endpoint | Purpose |
|---|---|---|---|
| 1 | POST | `/Auth/login` | Authenticate, get JWT token |
| 2 | GET | `/IFBPointFollowUp/GetInstallationAgeingDetails?IFBPointCode=ADSF` | Fetch all customer records |

The API response is a JSON object with four ageing-bucket keys:

```json
{
  "twoDays_details":         [...],
  "oneMonth_details":        [...],
  "fortySevenMonthDetails":  [...],
  "eightyFourMonthDetails":  [...]
}
```

`sync_api.py` flattens all four lists into a single `records` array in `api_data.json`.

**Key API fields → dashboard columns:**

| API field | Dashboard column |
|---|---|
| `customer_id` | (primary key, not shown) |
| `customer_name` | Customer Name |
| `purchase_date` | Purchase Date |
| `machine_type` | Machine Type |
| `phone_number` | Phone |
| `email_id` | Email |

---

## Refreshing data (manual — from IFB network)

Run this one command from any PC on the IFB office network:

```bash
python refresh_data.py
```

That's it. The script will:
1. Login to the IFB BSE API and fetch all customer records
2. Write `data/api_data.json`
3. Commit and push to GitHub
4. Streamlit Cloud updates automatically within ~30 seconds

Sample output:
```
  IFB Point Dashboard — Data Refresh
  API  : https://bseapi.ifbsupport.com/api
  Point: ADSF
  User : IFBFollowUPAPP

  ───────────────────────────────────────────────────────
    Step 1 — Login as IFBFollowUPAPP
  ───────────────────────────────────────────────────────
    ✓ Login successful — token received

  ───────────────────────────────────────────────────────
    Step 2 — Fetch records for IFB Point 'ADSF'
  ───────────────────────────────────────────────────────
    · twoDays_details: 3 record(s)
    · oneMonth_details: 12 record(s)
    · fortySevenMonthDetails: 25 record(s)
    · eightyFourMonthDetails: 8 record(s)
    ✓ 48 total records fetched

  ───────────────────────────────────────────────────────
    Step 3 — Write data/api_data.json
  ───────────────────────────────────────────────────────
    ✓ Written → data/api_data.json

  ───────────────────────────────────────────────────────
    Step 4 — Commit & push to GitHub
  ───────────────────────────────────────────────────────
    ✓ git add
    ✓ git commit
    ✓ git push

    🚀 Pushed! Streamlit Cloud will update within ~30 seconds.

  ───────────────────────────────────────────────────────
    Done
  ───────────────────────────────────────────────────────
    48 records are now live on Streamlit Cloud.
    URL: https://ifb-point-dashboard.streamlit.app/
```

---

## Local development

```bash
# 1. Clone
git clone https://github.com/IFB-Analytics/ifbpoint-followup.git
cd ifbpoint-followup

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app (reads existing data/api_data.json)
streamlit run streamlit_app.py
```

---

## GitHub Actions workflow

**File:** `.github/workflows/sync-api.yml`
**Trigger:** Manual only — *Actions → Sync IFB BSE API data → Run workflow*

> **Note:** The cron schedule is disabled. GitHub Actions runs on Azure infrastructure, and `bseapi.ifbsupport.com` does not allow connections from Azure IPs. Use `python refresh_data.py` from the IFB office network instead.

The workflow is kept for future use (e.g. if IFB IT whitelists GitHub's IP ranges, re-enabling the cron will make syncing fully automatic).

---

## Deployment (Streamlit Cloud)

1. Push code to the GitHub repo connected to Streamlit Cloud.
2. Streamlit Cloud auto-deploys on every push to `main`.
3. In Streamlit Cloud app settings → **Secrets**, add:

```toml
[api]
username       = "IFBFollowUPAPP"
password       = "U29tZVJhbmRvbUJhc2U2NA=="
ifb_point_code = "ADSF"
```

*(These are only used by the live API fallback path — normally the app reads `data/api_data.json` and never calls the API directly.)*

---

## Known limitations

| Limitation | Detail |
|---|---|
| Staff edits are ephemeral | SQLite lives on Streamlit Cloud's temporary disk. Edits survive re-runs but are lost on redeployment. Use a hosted DB for persistence. |
| Data freshness | `api_data.json` is at most 30 minutes stale (GitHub Actions cron cadence). |
| API firewall | Only Azure IPs (GitHub Actions) can reach the IFB API. Direct calls from Streamlit Cloud or other GCP-based services will time out. |
