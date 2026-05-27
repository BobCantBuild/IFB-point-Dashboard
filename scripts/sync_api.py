"""Fetch latest customer data from IFB BSE API and write to data/api_data.json.

Runs from GitHub Actions (Azure IPs — allowed by IFB) and also locally.
Streamlit Cloud (blocked by IFB firewall) reads this committed JSON file.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Import shared config (single source of truth — change IFB_POINT_CODE in config.py)
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from config import IFB_POINT_CODE, API_BASE as _API_BASE, API_USER, API_PASS  # noqa: E402

API_BASE = _API_BASE
USERNAME = os.environ.get("IFB_API_USER",   API_USER)
PASSWORD = os.environ.get("IFB_API_PASS",   API_PASS)
IFB_CODE = os.environ.get("IFB_POINT_CODE", IFB_POINT_CODE)  # env var still overrides for CI

OUT_FILE = REPO_ROOT / "data" / "api_data.json"
DB_FILE  = REPO_ROOT / "ifb_point.db"

# Maps API bucket keys → customer_follow_up stage label shown in the dashboard
BUCKET_STAGE = {
    "twoDays_details":        "Post-Purchase",
    "twoDaysDetails":         "Post-Purchase",
    "oneMonth_details":       "1st 30 days call",
    "oneMonthDetails":        "1st 30 days call",
    "fortySevenMonthDetails": "Pre-AMC",
    "fortySevenMonth_details":"Pre-AMC",
    "eightyFourMonthDetails": "8 Year Upgrade",
    "eightyFourMonth_details":"8 Year Upgrade",
}


def _parse_date(val: str | None) -> str | None:
    """Normalise any date string to YYYY-MM-DD; return None if unparseable."""
    if not val:
        return None
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(val).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(val).strip() or None


def _normalise_record(rec: dict, stage: str, point_code: str, point_name: str) -> dict:
    """Flatten one API record into a standard dict ready for api_data.json."""
    return {
        "customer_id":       str(rec.get("customer_id", "") or "").strip(),
        "customer_name":     (rec.get("customer_name") or "").strip(),
        "purchase_date":     _parse_date(rec.get("purchase_date")),
        "installation_date": _parse_date(rec.get("installationdate")),
        "machine_type":      (rec.get("machine_type") or "").strip(),
        "phone_number":      str(rec.get("phone_number") or "").strip(),
        "alt_number":        str(rec.get("alt_number")   or "").strip(),
        "email_id":          (rec.get("email_id") or "").strip(),
        "pin_code":          str(rec.get("pinCode") or "").strip(),
        "serial_no":         str(rec.get("serialNo") or "").strip(),
        "ifb_point_code":    point_code,
        "ifb_point_name":    point_name,
        "customer_follow_up": stage,
    }


# Columns that mirror the raw API field names (so the DB matches the source 1:1).
_API_COLS = (
    "customer_id", "customer_name", "purchase_date", "installationdate",
    "machine_type", "phone_number", "alt_number", "email_id",
    "pinCode", "serialNo",
)


def _ensure_api_leads_table(conn: sqlite3.Connection) -> None:
    """Create the api_leads table if missing. Hyphenated column quoted in SQL."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_leads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ifb_point       TEXT,
            key             TEXT,
            lead_date       TEXT,
            follow_up       TEXT,
            customer_id     TEXT,
            customer_name   TEXT,
            purchase_date   TEXT,
            installationdate TEXT,
            machine_type    TEXT,
            phone_number    TEXT,
            alt_number      TEXT,
            email_id        TEXT,
            "pinCode"       TEXT,
            "serialNo"      TEXT,
            UNIQUE (ifb_point, customer_id, lead_date, follow_up)
        )
    """)
    conn.commit()


def append_to_sqlite(payload: dict | list, point_code: str) -> int:
    """
    Walk the raw API payload (bucket → list of customer dicts) and append each
    record to the api_leads table. Returns the number of rows actually inserted.

    Rules:
      • lead_date = today in DD-MM-YYYY (per user spec)
      • follow_up = the API bucket key (twoDays_details, oneMonth_details, ...)
      • Same (ifb_point, customer_id, lead_date, follow_up) re-runs are no-ops
        → so running sync twice on the same day doesn't duplicate rows
      • Different days append historical lead snapshots
      • Existing rows for OTHER ifb_points are NEVER deleted (append-only)
    """
    if not isinstance(payload, dict):
        return 0

    lead_date = datetime.now().strftime("%d-%m-%Y")
    inserted  = 0

    with sqlite3.connect(DB_FILE) as conn:
        _ensure_api_leads_table(conn)
        for bucket_key, _stage in BUCKET_STAGE.items():
            for raw in payload.get(bucket_key, []):
                if not isinstance(raw, dict):
                    continue
                values = [str(raw.get(c, "") or "").strip() for c in _API_COLS]
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO api_leads
                      (ifb_point, key, lead_date, follow_up,
                       customer_id, customer_name, purchase_date, installationdate,
                       machine_type, phone_number, alt_number, email_id,
                       "pinCode", "serialNo")
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (point_code, "", lead_date, bucket_key, *values),
                )
                inserted += cur.rowcount if cur.rowcount > 0 else 0
        conn.commit()

    return inserted


def parse_payload(payload: dict | list) -> tuple[list[dict], str, str]:
    """
    Parse the raw API response into a flat normalised record list.
    Returns (records, ifb_point_code, ifb_point_name).
    """
    if isinstance(payload, list):
        # Older flat-list format — no bucket info, no point code
        return [dict(r) for r in payload if isinstance(r, dict)], IFB_CODE, ""

    point_code = str(payload.get("ifbPointCode") or IFB_CODE).strip()
    point_name = str(payload.get("ifbPointName") or "").strip()

    records: list[dict] = []
    for key, stage in BUCKET_STAGE.items():
        for raw in payload.get(key, []):
            if isinstance(raw, dict):
                records.append(_normalise_record(raw, stage, point_code, point_name))

    # Fallback: dict had no recognised bucket keys — flatten all lists
    if not records:
        for k, v in payload.items():
            if isinstance(v, list):
                for raw in v:
                    if isinstance(raw, dict):
                        records.append(dict(raw))

    return records, point_code, point_name


def main() -> int:
    print(f"[sync_api] Logging in as {USERNAME} for point code {IFB_CODE}...")
    with httpx.Client(timeout=30) as client:
        r1 = client.post(
            f"{API_BASE}/Auth/login",
            json={"userName": USERNAME, "password": PASSWORD},
            headers={"Content-Type": "application/json"},
        )
    if r1.status_code != 200:
        print(f"[sync_api] LOGIN FAILED — HTTP {r1.status_code}: {r1.text[:300]}", file=sys.stderr)
        return 1
    token = r1.json().get("token")
    if not token:
        print(f"[sync_api] LOGIN OK but no token: {r1.json()}", file=sys.stderr)
        return 1
    print("[sync_api] Login OK, token received.")

    print(f"[sync_api] Fetching GetInstallationAgeingDetails for {IFB_CODE}...")
    with httpx.Client(timeout=30) as client:
        r2 = client.get(
            f"{API_BASE}/IFBPointFollowUp/GetInstallationAgeingDetails",
            params={"IFBPointCode": IFB_CODE},
            headers={"Authorization": f"Bearer {token}"},
        )
    if r2.status_code != 200:
        print(f"[sync_api] FETCH FAILED — HTTP {r2.status_code}: {r2.text[:300]}", file=sys.stderr)
        return 1

    raw_payload = r2.json()
    records, point_code, point_name = parse_payload(raw_payload)
    print(f"[sync_api] Parsed {len(records)} records — code={point_code}, name={point_name!r}")

    out = {
        "synced_at_utc":  datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ifb_point_code": point_code,
        "ifb_point_name": point_name,
        "record_count":   len(records),
        "records":        records,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[sync_api] Wrote {len(records)} records to {OUT_FILE.relative_to(REPO_ROOT)}")

    # Append raw API records to SQLite (cumulative, never deletes anything)
    try:
        inserted = append_to_sqlite(raw_payload, point_code)
        print(f"[sync_api] SQLite: appended {inserted} new row(s) to api_leads "
              f"(table: {DB_FILE.name})")
    except Exception as exc:
        print(f"[sync_api] SQLite append failed (non-fatal): {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
