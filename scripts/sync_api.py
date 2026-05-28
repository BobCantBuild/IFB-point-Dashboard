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

OUT_FILE    = REPO_ROOT / "data" / "api_data.json"
DB_FILE     = REPO_ROOT / "ifb_point.db"
MASTER_FILE = REPO_ROOT / "IFB_Point_Master.txt"

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
    """Create the api_leads table if missing, then run idempotent migrations."""
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
            status            TEXT,
            next_appointment  TEXT,
            interested        TEXT,
            remarks           TEXT,
            UNIQUE (ifb_point, customer_id, lead_date, follow_up)
        )
    """)
    # Migration for DBs created before the 4 user-input columns existed
    existing = {r[1] for r in conn.execute("PRAGMA table_info(api_leads)").fetchall()}
    for new_col in ("status", "next_appointment", "interested", "remarks"):
        if new_col not in existing:
            conn.execute(f"ALTER TABLE api_leads ADD COLUMN {new_col} TEXT")
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
    skipped   = 0

    with sqlite3.connect(DB_FILE) as conn:
        _ensure_api_leads_table(conn)

        # Backfill any pre-existing rows that have an empty key (one-time)
        conn.execute("""
            UPDATE api_leads
               SET key = ifb_point || '-' || customer_id || '-' || "serialNo"
             WHERE key IS NULL OR key = ''
        """)

        for bucket_key, _stage in BUCKET_STAGE.items():
            for raw in payload.get(bucket_key, []):
                if not isinstance(raw, dict):
                    continue
                cust_id = str(raw.get("customer_id", "") or "").strip()
                serial  = str(raw.get("serialNo",    "") or "").strip()
                key_val = f"{point_code}-{cust_id}-{serial}"

                # Key-based idempotency: if key already exists, leave the row
                # alone — don't modify, don't re-insert. (User-edited columns
                # status/next_appointment/interested/remarks are preserved.)
                exists = conn.execute(
                    "SELECT 1 FROM api_leads WHERE key = ? LIMIT 1", (key_val,)
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

                values = [str(raw.get(c, "") or "").strip() for c in _API_COLS]
                conn.execute(
                    """
                    INSERT INTO api_leads
                      (ifb_point, key, lead_date, follow_up,
                       customer_id, customer_name, purchase_date, installationdate,
                       machine_type, phone_number, alt_number, email_id,
                       "pinCode", "serialNo")
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (point_code, key_val, lead_date, bucket_key, *values),
                )
                inserted += 1

        conn.commit()

    print(f"[sync_api] SQLite: {inserted} new, {skipped} skipped (key exists)")
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


def load_master_codes() -> list[str]:
    """
    Read IFB_Point_Master.txt and return every IFB Point Code in it.

    Format is permissive: codes may be separated by commas, whitespace, or
    newlines — anything non-empty after splitting on those delimiters is
    treated as a code. Duplicates are removed but original order is preserved
    (so the configured IFB_POINT_CODE keeps its position if it's in the file).
    """
    if not MASTER_FILE.exists():
        print(f"[sync_api] Master file not found at {MASTER_FILE} — "
              f"falling back to single code {IFB_CODE}", file=sys.stderr)
        return [IFB_CODE]

    raw = MASTER_FILE.read_text(encoding="utf-8")
    # Treat commas, whitespace and newlines as separators
    tokens = (
        raw.replace("\r", " ")
           .replace("\n", " ")
           .replace("\t", " ")
           .replace(",", " ")
           .split()
    )
    seen: set[str] = set()
    codes: list[str] = []
    for t in tokens:
        c = t.strip()
        if not c or c in seen:
            continue
        seen.add(c)
        codes.append(c)
    return codes


def _login(client: httpx.Client) -> str | None:
    """POST /Auth/login → JWT token (None on failure)."""
    r = client.post(
        f"{API_BASE}/Auth/login",
        json={"userName": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/json"},
    )
    if r.status_code != 200:
        print(f"[sync_api] LOGIN FAILED — HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return None
    tok = r.json().get("token")
    if not tok:
        print(f"[sync_api] LOGIN OK but no token: {r.json()}", file=sys.stderr)
        return None
    return tok


def _fetch_one(client: httpx.Client, token: str, code: str) -> dict | None:
    """
    GET /GetInstallationAgeingDetails?IFBPointCode=<code>.
    Returns the raw JSON payload, or None if the call failed.
    """
    try:
        r = client.get(
            f"{API_BASE}/IFBPointFollowUp/GetInstallationAgeingDetails",
            params={"IFBPointCode": code},
            headers={"Authorization": f"Bearer {token}"},
        )
    except Exception as exc:
        print(f"[sync_api]   {code}: HTTP exception — {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    if r.status_code != 200:
        print(f"[sync_api]   {code}: HTTP {r.status_code} — {r.text[:200]}", file=sys.stderr)
        return None
    try:
        return r.json()
    except Exception as exc:
        print(f"[sync_api]   {code}: bad JSON — {exc}", file=sys.stderr)
        return None


def main() -> int:
    codes = load_master_codes()
    print(f"[sync_api] Loaded {len(codes)} IFB Point code(s) from "
          f"{MASTER_FILE.name if MASTER_FILE.exists() else 'fallback config'}")
    print(f"[sync_api] Logging in as {USERNAME}...")

    with httpx.Client(timeout=30) as client:
        token = _login(client)
        if not token:
            return 1
        print("[sync_api] Login OK, token received.")

        # Per-franchise stats so the summary tells you exactly what flowed in
        total_inserted = 0
        total_records  = 0
        success_codes: list[str] = []
        empty_codes:   list[str] = []
        failed_codes:  list[str] = []

        for i, code in enumerate(codes, 1):
            print(f"[sync_api] ({i}/{len(codes)}) fetching {code}...", flush=True)
            payload = _fetch_one(client, token, code)
            if payload is None:
                failed_codes.append(code)
                continue

            records, _parsed_code, _parsed_name = parse_payload(payload)
            total_records += len(records)

            # SQLite append (idempotent by key — re-runs are safe)
            try:
                inserted = append_to_sqlite(payload, code)
                total_inserted += inserted
            except Exception as exc:
                print(f"[sync_api]   {code}: SQLite append failed — {exc}", file=sys.stderr)
                failed_codes.append(code)
                continue

            if records:
                success_codes.append(code)
            else:
                empty_codes.append(code)

    # ── Summary ────────────────────────────────────────────────────────────
    print("")
    print(f"[sync_api] ═══ SUMMARY ═══")
    print(f"[sync_api]   Codes processed : {len(codes)}")
    print(f"[sync_api]   With records    : {len(success_codes)}")
    print(f"[sync_api]   Empty responses : {len(empty_codes)}")
    print(f"[sync_api]   Failed          : {len(failed_codes)}")
    print(f"[sync_api]   API records seen: {total_records}")
    print(f"[sync_api]   New DB rows     : {total_inserted}")
    if failed_codes:
        print(f"[sync_api]   Failed codes    : {', '.join(failed_codes[:20])}"
              f"{' ...' if len(failed_codes) > 20 else ''}")

    return 0 if not failed_codes else 0  # non-fatal — partial syncs are fine


if __name__ == "__main__":
    sys.exit(main())
