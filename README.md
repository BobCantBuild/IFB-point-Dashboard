# IFB Point — Customer Follow-Up Dashboard

A Streamlit web dashboard for tracking and managing customer follow-ups for an IFB service point. Sales/support staff can see every installation's follow-up stage, log contact status, set next appointment dates, and record interest and remarks — all from a browser, with no local install needed.

Live app → **https://ifb-point-dashboard.streamlit.app/**

---

## How the data flows — end to end

```
                IFB BSE API
                (bseapi.ifbsupport.com)
                       ▲
                       │  reachable only from
                       │  IFB office network
                       │
            ┌──────────┴──────────┐
            │  Your PC on IFB LAN │
            │   refresh_data.py   │
            └──────────┬──────────┘
                       │  1. POST /api/Auth/login  →  JWT token
                       │  2. GET  /api/IFBPointFollowUp/GetInstallationAgeingDetails
                       │  3. Write data/api_data.json
                       │  4. git add / commit / push
                       ▼
                GitHub Repository
                  data/api_data.json  ← single source of truth
                       │
                       │  Streamlit Cloud auto-redeploys
                       │  on every push to main
                       ▼
                Streamlit Cloud
                  streamlit_app.py
                    ├── reads data/api_data.json     (customer records)
                    └── reads ifb_point.db           (staff edits)
                       │
                       ▼
                Dashboard UI
                (ifb-point-dashboard.streamlit.app)
```

---

## Refreshing data — the manual workflow

The IFB API (`bseapi.ifbsupport.com`) is behind a firewall that only accepts connections from the IFB office network. Streamlit Cloud (Google Cloud) and GitHub Actions (Microsoft Azure) are both blocked. So data has to be refreshed from a machine inside the IFB office:

```bash
python refresh_data.py
```

That single command:
1. Calls `scripts/sync_api.py` — logs in, fetches records, writes `data/api_data.json`
2. Detects whether the file actually changed
3. If changed → commits and pushes to GitHub with `[skip ci]`
4. Streamlit Cloud picks up the new data within ~30 seconds

If `api_data.json` hasn't changed, no commit is made — safe to run as often as you like.

| Environment | Can reach the IFB API? |
|---|---|
| Your PC on IFB office LAN | ✅ Yes |
| Streamlit Cloud (GCP) | ❌ Blocked |
| GitHub Actions (Azure) | ❌ Blocked |

---

## What the dashboard shows

### Fixed header (always visible)
- **Hero bar** — app title, sync status badge, timestamp of last successful sync, snapshot record count.
- **Stats row** — Total follow-ups · Contact status (Contacted / Not Contacted / Empty) · Interest (Interested / Not Interested / Empty) · Follow-Up Stage breakdown.

### Filter bar (pinned below header)

| Control | Purpose |
|---|---|
| Open Followup's / Attempted's | Toggle between all leads vs. leads where contact was already attempted |
| Follow-Up Stage dropdown | Filter by bucket (Post-Purchase / 1st 30 days / Pre-AMC / 8 Year Upgrade) |
| Date range picker | Filter by purchase date |
| Search box | Free-text search across name, phone, email, customer ID |
| ↻ Refresh | Clears Streamlit cache and reloads from `api_data.json` |

### Data table — 11 columns

| Column | Source | Editable |
|---|---|---|
| ✏️ Edit | — | — |
| Customer Follow-Up | Computed bucket | — |
| Customer Name | API | — |
| Purchase Date | API | — |
| Machine Type | API | — |
| Phone | API | — |
| Email | API | — |
| Status | SQLite (`followups`) | ✅ |
| Next Appt | SQLite (`followups`) | ✅ |
| Interested? | SQLite (`followups`) | ✅ |
| Remarks | SQLite (`followups`) | ✅ |

### Follow-Up bucket logic

| Days since purchase | Bucket |
|---|---|
| 0 – 2 | Post-Purchase |
| 3 – 30 | 1st 30 days call |
| 31 – 1460 (≈ 4 years) | Pre-AMC |
| 1461 + | 8 Year Upgrade |

### Edit dialog
Clicking ✏️ opens a modal where staff can set Status, Next Appointment, Interested?, and Remarks. Saved values go to `ifb_point.db` (SQLite) on Streamlit Cloud's local disk. They persist between app runs but reset on full redeployment (Streamlit Cloud free-tier limitation — use a hosted DB like Supabase if long-term persistence is required).

---

## File structure

```
IFB point Dashboard/
│
├── streamlit_app.py          ← Main app (UI, data loading, edit dialog)
├── refresh_data.py           ← Run this from IFB network to refresh data
├── requirements.txt          ← Python dependencies
├── README.md                 ← This file
│
├── data/
│   └── api_data.json         ← API snapshot (committed to repo, updated by refresh_data.py)
│
├── scripts/
│   └── sync_api.py           ← Pure fetch-and-write logic (used by refresh_data.py)
│
├── .github/workflows/
│   └── sync-api.yml          ← Manual-only workflow (dormant — Azure IPs blocked)
│
├── .streamlit/
│   ├── config.toml           ← Streamlit theme
│   └── secrets.toml          ← Local-only secrets (gitignored)
│
└── ifb_point.db              ← SQLite for staff edits (runtime, gitignored)
```

---

## API details

**Base URL:** `https://bseapi.ifbsupport.com/api`

| Step | Method | Endpoint | Purpose |
|---|---|---|---|
| 1 | `POST` | `/Auth/login` | Authenticate → returns JWT token |
| 2 | `GET` | `/IFBPointFollowUp/GetInstallationAgeingDetails?IFBPointCode=ADSF` | Fetch all customer records |

The response is a JSON object with four ageing-bucket keys, flattened into one array:

```json
{
  "twoDays_details":         [...],
  "oneMonth_details":        [...],
  "fortySevenMonthDetails":  [...],
  "eightyFourMonthDetails":  [...]
}
```

**Field mapping (API → dashboard):**

| API field | Dashboard column |
|---|---|
| `customer_id` | (primary key, hidden) |
| `customer_name` | Customer Name |
| `purchase_date` | Purchase Date |
| `machine_type` | Machine Type |
| `phone_number` | Phone |
| `email_id` | Email |

---

## Local development

```bash
# 1. Clone the repo
git clone https://github.com/IFB-Analytics/ifbpoint-followup.git
cd ifbpoint-followup

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the dashboard (reads the existing api_data.json)
streamlit run streamlit_app.py
```

The dashboard will open at `http://localhost:8501` and use the JSON snapshot already in the repo. You don't need API access to develop locally.

---

## Deployment (Streamlit Cloud)

The app is already deployed at https://ifb-point-dashboard.streamlit.app/. Auto-redeploys happen on every push to `main`.

Streamlit Cloud secrets (already configured) — *only used by the live-API fallback path, which never fires in normal operation since the JSON file is the primary source*:

```toml
[api]
username       = "IFBFollowUPAPP"
password       = "U29tZVJhbmRvbUJhc2U2NA=="
ifb_point_code = "ADSF"
```

---

## GitHub Actions workflow

**File:** `.github/workflows/sync-api.yml`
**Trigger:** Manual only — *Actions → Sync IFB BSE API data → Run workflow*

The cron schedule is **disabled** because GitHub Actions runs on Azure IPs which the IFB firewall blocks. The workflow stays in the repo for future use — if IFB IT ever whitelists GitHub's IP ranges (see https://api.github.com/meta), re-enabling the cron will make syncing fully automatic.

For now, **use `python refresh_data.py` from the IFB office network**.

---

## Architecture decisions

| Decision | Rationale |
|---|---|
| API data lives in `data/api_data.json` (committed to repo) | Streamlit Cloud can't reach the IFB API directly. Reading a committed JSON file eliminates the network hop. |
| Staff edits live in SQLite (`followups` table) | API records change with every sync; staff edits must survive that. Keyed by `customer_id`. |
| `refresh_data.py` is the single entry-point for refreshing | Combines API fetch + git push so users have one command to remember. |
| `scripts/sync_api.py` is kept as the canonical fetch logic | Used by both `refresh_data.py` (local) and the GitHub Actions workflow (dormant). |
| No CSV / Excel seed files | All customer data comes from the API. Removed `data.csv` and `seed_db.py` after migration. |

---

## Known limitations

| Limitation | Detail |
|---|---|
| Staff edits are ephemeral | SQLite lives on Streamlit Cloud's local disk. Edits survive between sessions but may reset on a full redeploy. Use Supabase / PlanetScale / similar for long-term persistence. |
| Data freshness is manual | `api_data.json` updates only when someone runs `refresh_data.py`. There is no automated sync until IFB IT whitelists Azure/GCP IPs. |
| API firewall | Only the IFB office network can reach `bseapi.ifbsupport.com`. Streamlit Cloud and GitHub Actions are both blocked. |
