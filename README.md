# IFB Point — Customer Follow-Up Dashboard

A Streamlit web dashboard for tracking and managing customer follow-ups for an IFB Point franchise. Sales/support staff can see every installation's follow-up stage, log contact status, set next appointment dates, and record interest and remarks — all from a browser, with no local install needed.

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
            │  sync_api.py        │
            └──────────┬──────────┘
                       │
                       │  1. POST /api/Auth/login   →  JWT token
                       │  2. GET  /api/IFBPointFollowUp/GetInstallationAgeingDetails
                       │  3. Append new records into ifb_point.db (api_leads table)
                       │  4. Write data/api_data.json (Cloud fallback)
                       │  5. git add / commit / push
                       ▼
                GitHub Repository
                  data/api_data.json  ← committed snapshot for Cloud bootstrap
                       │
                       │  Streamlit Cloud auto-redeploys
                       │  on every push to main
                       ▼
                Streamlit Cloud
                  streamlit_app.py
                    ├── bootstraps ephemeral SQLite from data/api_data.json
                    ├── reads ALL display data from api_leads table
                    └── writes user edits back into api_leads + followups.json
                       │
                       ▼
                Dashboard UI
                (ifb-point-dashboard.streamlit.app)
```

---

## Switching IFB Point franchise — one line

All configuration lives in **`config.py`**. Both `streamlit_app.py` and `scripts/sync_api.py` import from here, so changing the code in one place updates both:

```python
# config.py
IFB_POINT_CODE = "1018638"   # ← change this when switching IFB Point franchise

API_BASE = "https://bseapi.ifbsupport.com/api"
API_USER = "IFBFollowUPAPP"
API_PASS = "U29tZVJhbmRvbUJhc2U2NA=="
```

Then refresh data:

```bash
uv run python scripts/sync_api.py     # fetches API, appends to SQLite + JSON
git add config.py data/api_data.json
git commit -m "switch to franchise XXXXXXX"
git push origin main                  # Streamlit auto-redeploys
```

The IFB API is firewalled — `sync_api.py` only works from a machine on the IFB office network.

| Environment | Can reach the IFB API? |
|---|---|
| Your PC on IFB office LAN | ✅ Yes |
| Streamlit Cloud (GCP) | ❌ Blocked |
| GitHub Actions (Azure) | ❌ Blocked |

---

## SQLite — the source of truth

**Table:** `api_leads` in `ifb_point.db`

| Column | Source | Notes |
|---|---|---|
| `id` | Auto | Primary key |
| `ifb_point` | sync | IFB Point Code |
| `key` | sync | `ifb_point-customer_id-serialNo` (unique row identifier) |
| `lead_date` | sync | DD-MM-YYYY of first capture |
| `follow_up` | sync | Raw API bucket name (`twoDays_details`, `oneMonth_details`, …) |
| `customer_id` | API | |
| `customer_name` | API | |
| `purchase_date` | API | |
| `installationdate` | API | (original field name preserved) |
| `machine_type` | API | |
| `phone_number` | API | |
| `alt_number` | API | |
| `email_id` | API | |
| `pinCode` | API | (original) |
| `serialNo` | API | (original) |
| `status` | **User save** | Contacted / Not Contacted |
| `next_appointment` | **User save** | YYYY-MM-DD |
| `interested` | **User save** | Interested / Not Interested |
| `remarks` | **User save** | Free text |

### Sync rules (`sync_api.py`)

- Builds `key = ifb_point-customer_id-serialNo` for each API record.
- **If key already exists** → leaves the row untouched (no UPDATE, no re-INSERT). User-edited columns are preserved.
- **If key is new** → INSERT all API fields; user columns start NULL.
- Switching `IFB_POINT_CODE` and re-running appends new rows; previous franchises stay intact.

### Display rules (`streamlit_app.py`)

- On startup, if `api_leads` has no rows for the active IFB Point → bootstrap from `data/api_data.json` (handles Streamlit Cloud cold-starts where SQLite is wiped).
- Reads all 18 columns of `api_leads` for the current IFB Point and renders them.
- User saves are written to `api_leads` (UPDATE WHERE customer_id = ? AND ifb_point = ?) AND `data/followups.json` (Cloud-survivable JSON if `github_token` is set in Streamlit secrets).

---

## What the dashboard shows

### Hero header
- App title + IFB Point name (read from snapshot)
- Sync status badge + UTC timestamp + total record count

### Stats row
- 🏪 **IFB Point Code** — current franchise (mirrors `config.py`)
- 👥 **Total Follow-Ups**
- 📞 **Contact Status** breakdown — Contacted / Not Contacted / Empty
- 💬 **Interest** breakdown — Interested / Not Interested / Empty
- 🎯 **Follow-Up Stage** breakdown — Post Purchase / 1st 30 Days / Pre-AMC / 8 Year Upgrade

### Filter bar

| Row | Controls |
|---|---|
| 1 | 📅 Today Leads · ⚠️ Missed Leads · Date range picker |
| 2 | 📋 Open Followup's · 📞 Attempted's · 🌐 Stage filter · 🔍 Search |

### Data table — 11 columns

| Column | Source | Editable |
|---|---|---|
| ✏️ Edit | — | — |
| Customer Follow-Up | API bucket → stage | — |
| Customer Name | API (falls back to `(unnamed <machine>)` if blank) | — |
| Purchase Date | API | — |
| Machine Type | API | — |
| Phone | API | — |
| Email | API | — |
| Status | SQLite `api_leads.status` | ✅ |
| Next Appt | SQLite `api_leads.next_appointment` | ✅ |
| Interested? | SQLite `api_leads.interested` | ✅ |
| Remarks | SQLite `api_leads.remarks` | ✅ |

### Follow-Up bucket logic

Driven by the API bucket — `customer_follow_up` is set from the bucket the record arrived in:

| API bucket key | Dashboard label |
|---|---|
| `twoDays_details` | Post-Purchase |
| `oneMonth_details` | 1st 30 days call |
| `fortySevenMonthDetails` | Pre-AMC |
| `eightyFourMonthDetails` | 8 Year Upgrade |

For records lacking a bucket, the dashboard falls back to a `purchase_date → bucket` computation (0–2 days = Post-Purchase, 3–30 = 1st 30 days call, 31–1460 = Pre-AMC, 1461+ = 8 Year Upgrade).

### Edit dialog

Clicking ✏️ opens a modal with the 4 editable fields. **Save** writes to:

1. `data/followups.json` (local + GitHub commit if `github_token` set)
2. `api_leads.{status, next_appointment, interested, remarks}` (UPDATE WHERE customer_id AND ifb_point)

A toast confirms: `✅ Saved — followups.json + SQLite (N row(s) updated)`. If the SQLite write fails, a yellow warning shows the exception.

---

## File structure

```
IFB point Dashboard/
│
├── config.py                  ← Single source of truth (IFB_POINT_CODE, API creds)
├── streamlit_app.py           ← Main app (UI, SQLite read/write, edit dialog)
├── refresh_data.py            ← Convenience: run sync + git push in one go
├── pyproject.toml             ← Dependency source of truth (uv)
├── uv.lock                    ← Pinned versions (committed)
├── requirements.txt           ← Auto-generated for Streamlit Cloud
├── README.md                  ← This file
│
├── data/
│   ├── api_data.json          ← API snapshot (committed — Cloud bootstrap source)
│   └── followups.json         ← User edits (committed if github_token set)
│
├── scripts/
│   └── sync_api.py            ← API fetch + SQLite append (key-based idempotency)
│
├── .github/workflows/
│   └── sync-api.yml           ← Manual workflow (dormant — Azure IPs blocked)
│
├── .streamlit/
│   ├── config.toml            ← Streamlit theme
│   └── secrets.toml           ← Local-only secrets (gitignored)
│
└── ifb_point.db               ← SQLite (gitignored, local-only persistence)
```

---

## API details

**Base URL:** `https://bseapi.ifbsupport.com/api`

| Step | Method | Endpoint | Purpose |
|---|---|---|---|
| 1 | `POST` | `/Auth/login` | Authenticate → returns JWT token |
| 2 | `GET` | `/IFBPointFollowUp/GetInstallationAgeingDetails?IFBPointCode={code}` | Fetch all customer records for the franchise |

Response shape (bucket-list format):

```json
{
  "ifbPointCode":            "1018638",
  "ifbPointName":            "IFB Industries Limited - IFB Point ST.Inez Panjim",
  "twoDays_details":         [...],
  "oneMonth_details":        [...],
  "fortySevenMonthDetails":  [...],
  "eightyFourMonthDetails":  [...]
}
```

**Field normalization (API → SQLite / dashboard):**

| API field | SQLite column | Display column |
|---|---|---|
| `customer_id` | `customer_id` | (hidden — used as edit key) |
| `customer_name` | `customer_name` | Customer Name |
| `purchase_date` | `purchase_date` | Purchase Date |
| `installationdate` | `installationdate` | (hidden) |
| `machine_type` | `machine_type` | Machine Type |
| `phone_number` | `phone_number` | Phone |
| `alt_number` | `alt_number` | (hidden) |
| `email_id` | `email_id` | Email |
| `pinCode` | `pinCode` | (hidden) |
| `serialNo` | `serialNo` | (hidden — part of `key`) |

---

## Local development

This project uses **[uv](https://docs.astral.sh/uv/)** for dependency management.

```bash
# 0. Install uv (once)
pip install uv          # or: winget install astral-sh.uv

# 1. Clone the repo
git clone https://github.com/IFB-Analytics/ifbpoint-followup.git
cd ifbpoint-followup

# 2. Create venv and install all dependencies from uv.lock
uv sync

# 3. (Optional) Refresh data — must run from IFB office network
uv run python scripts/sync_api.py

# 4. Run the dashboard locally — saves go straight to local SQLite
uv run streamlit run streamlit_app.py
```

The dashboard opens at `http://localhost:8501`. The JSON snapshot in the repo is enough to view data without an API connection.

### Dependency management

| File | Purpose |
|---|---|
| `pyproject.toml` | Source of truth — add/remove packages here |
| `uv.lock` | Exact pinned versions — committed, ensures reproducible installs |
| `requirements.txt` | Auto-generated from `pyproject.toml` — used by Streamlit Cloud |

```bash
uv add <package>          # add a dependency
uv remove <package>       # remove a dependency
uv export --no-hashes -o requirements.txt   # regenerate after dep changes
```

---

## Deployment (Streamlit Cloud)

The app is deployed at https://ifb-point-dashboard.streamlit.app/ and auto-redeploys on every push to `main`.

### Streamlit Cloud secrets (optional)

```toml
[api]
username = "IFBFollowUPAPP"
password = "U29tZVJhbmRvbUJhc2U2NA=="

# Optional — enables auto-commit of followups.json back to GitHub
# so user edits survive Cloud redeploys
github_token = "github_pat_xxxxxxxxxxxxxxxxx"
github_repo  = "BobCantBuild/IFB-point-Dashboard"
```

### Save persistence options

| Option | Save persistence | Setup |
|---|---|---|
| **Run Streamlit locally** | ✅ Direct to local SQLite | None — `uv run streamlit run streamlit_app.py` |
| **Online Streamlit + `github_token`** | ✅ Commits `followups.json` to repo on every save | 2 min — create GitHub PAT, paste into secrets |
| **Online Streamlit, no token** | ⚠️ Lasts only until next Cloud redeploy | None |

---

## Architecture decisions

| Decision | Rationale |
|---|---|
| `config.py` is the single source of truth | Avoid drift between `streamlit_app.py` and `sync_api.py` |
| SQLite (`api_leads`) is the source for display | Allows accumulating leads from multiple syncs and IFB Points; preserves user edits across re-syncs |
| `api_data.json` is committed | Streamlit Cloud bootstraps SQLite from JSON on cold-start (Cloud filesystem is ephemeral) |
| `key = ifb_point-customer_id-serialNo` | Stable across re-syncs; uniquely identifies a customer's machine at a franchise |
| Sync is key-based idempotent (no UPSERT) | Re-running `sync_api.py` never overwrites an in-place user edit |
| `followups.json` mirrors user saves | Cloud-survivable persistence layer when `github_token` is set |

---

## Known limitations

| Limitation | Detail |
|---|---|
| Cloud SQLite is ephemeral | Streamlit Cloud rebuilds the container on every git push — local SQLite writes are lost. Use `followups.json` + `github_token` for cross-restart persistence, or run locally for direct SQLite saves. |
| Data freshness is manual | `api_data.json` and SQLite update only when someone runs `sync_api.py`. There is no automated sync until IFB IT whitelists Azure/GCP IPs. |
| API firewall | Only the IFB office network can reach `bseapi.ifbsupport.com`. Streamlit Cloud and GitHub Actions are both blocked. |
| One franchise per deploy | The active franchise is whichever `IFB_POINT_CODE` is in `config.py`. The SQLite stores rows for all franchises ever synced, but the UI shows one at a time. |
