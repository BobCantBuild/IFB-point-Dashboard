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

## Local development

```bash
# 1. Clone
git clone https://github.com/IFB-Analytics/ifbpoint-followup.git
cd ifbpoint-followup

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run streamlit_app.py
```

The app reads `data/api_data.json` (already in the repo). To pull fresh data from the API while on the IFB network:

```bash
python scripts/sync_api.py
```

---

## GitHub Actions workflow

**File:** `.github/workflows/sync-api.yml`
**Schedule:** Every 30 minutes (`*/30 * * * *`) + manual trigger via *Actions → Run workflow*

Steps:
1. Check out the repository
2. Set up Python 3.12
3. `pip install httpx`
4. Run `scripts/sync_api.py` *(continue-on-error — a network failure skips this step without failing the job)*
5. If `data/api_data.json` changed, commit and push with `[skip ci]`

**Credentials** are read from GitHub repository secrets (`IFB_API_USER`, `IFB_API_PASS`, `IFB_POINT_CODE`). If secrets are not set, the defaults hardcoded in the workflow are used as fallback.

To set secrets: GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

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
