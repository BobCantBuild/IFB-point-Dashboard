"""Fetch latest customer data from IFB BSE API and write to data/api_data.json.

Runs from GitHub Actions (Azure IPs — allowed by IFB) and also locally.
Streamlit Cloud (blocked by IFB firewall) reads this committed JSON file.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

API_BASE = "https://bseapi.ifbsupport.com/api"
USERNAME = os.environ.get("IFB_API_USER",   "IFBFollowUPAPP")
PASSWORD = os.environ.get("IFB_API_PASS",   "U29tZVJhbmRvbUJhc2U2NA==")
IFB_CODE = os.environ.get("IFB_POINT_CODE", "ADSF")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_FILE  = REPO_ROOT / "data" / "api_data.json"

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

    records, point_code, point_name = parse_payload(r2.json())
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
