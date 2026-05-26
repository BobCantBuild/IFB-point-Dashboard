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
USERNAME = os.environ.get("IFB_API_USER", "IFBFollowUPAPP")
PASSWORD = os.environ.get("IFB_API_PASS", "U29tZVJhbmRvbUJhc2U2NA==")
IFB_CODE = os.environ.get("IFB_POINT_CODE", "ADSF")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_FILE  = REPO_ROOT / "data" / "api_data.json"


def main() -> int:
    print(f"[sync_api] Logging in as {USERNAME}...")
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
    payload = r2.json()

    # Flatten the 4 ageing buckets into a single list
    records: list[dict] = []
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list):
                records.extend(v)

    out = {
        "synced_at_utc":   datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ifb_point_code":  IFB_CODE,
        "record_count":    len(records),
        "records":         records,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[sync_api] Wrote {len(records)} records to {OUT_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
