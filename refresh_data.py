"""
IFB Point Dashboard — Manual Data Refresh
==========================================
Run this script from any machine on the IFB office network:

    python refresh_data.py

What it does:
  1. Logs in to the IFB BSE API and fetches all customer records
  2. Writes the result to data/api_data.json
  3. Commits the file and pushes to GitHub
  4. Streamlit Cloud picks up the new data automatically (within ~30 sec)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ── API credentials ──────────────────────────────────────────────────────────
API_BASE = "https://bseapi.ifbsupport.com/api"
USERNAME = os.environ.get("IFB_API_USER", "IFBFollowUPAPP")
PASSWORD = os.environ.get("IFB_API_PASS", "U29tZVJhbmRvbUJhc2U2NA==")
IFB_CODE = os.environ.get("IFB_POINT_CODE", "ADSF")

REPO_ROOT = Path(__file__).resolve().parent
OUT_FILE  = REPO_ROOT / "data" / "api_data.json"


def _banner(msg: str) -> None:
    print(f"\n{'─' * 55}")
    print(f"  {msg}")
    print(f"{'─' * 55}")


def fetch_records() -> list[dict]:
    """Login → fetch installation ageing details → return flat record list."""
    _banner(f"Step 1 — Login as {USERNAME}")
    with httpx.Client(timeout=30) as client:
        r1 = client.post(
            f"{API_BASE}/Auth/login",
            json={"userName": USERNAME, "password": PASSWORD},
            headers={"Content-Type": "application/json"},
        )

    if r1.status_code != 200:
        print(f"  ✗ Login failed — HTTP {r1.status_code}", file=sys.stderr)
        print(f"    {r1.text[:300]}", file=sys.stderr)
        sys.exit(1)

    token = r1.json().get("token")
    if not token:
        print(f"  ✗ Login OK but no token in response: {list(r1.json().keys())}", file=sys.stderr)
        sys.exit(1)

    print(f"  ✓ Login successful — token received")

    _banner(f"Step 2 — Fetch records for IFB Point '{IFB_CODE}'")
    with httpx.Client(timeout=30) as client:
        r2 = client.get(
            f"{API_BASE}/IFBPointFollowUp/GetInstallationAgeingDetails",
            params={"IFBPointCode": IFB_CODE},
            headers={"Authorization": f"Bearer {token}"},
        )

    if r2.status_code != 200:
        print(f"  ✗ Fetch failed — HTTP {r2.status_code}", file=sys.stderr)
        print(f"    {r2.text[:300]}", file=sys.stderr)
        sys.exit(1)

    payload = r2.json()

    # Flatten the 4 ageing buckets into one list
    records: list[dict] = []
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key, val in payload.items():
            if isinstance(val, list):
                print(f"  · {key}: {len(val)} record(s)")
                records.extend(val)

    print(f"  ✓ {len(records)} total records fetched")
    return records


def write_json(records: list[dict]) -> None:
    """Write records to data/api_data.json."""
    _banner("Step 3 — Write data/api_data.json")
    out = {
        "synced_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ifb_point_code": IFB_CODE,
        "record_count": len(records),
        "records": records,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ Written → {OUT_FILE.relative_to(REPO_ROOT)}")


def git_push() -> None:
    """Stage, commit (only if changed), and push api_data.json."""
    _banner("Step 4 — Commit & push to GitHub")

    def run(cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)

    # Check if there is actually a change worth committing
    diff = run(["git", "diff", "--quiet", "data/api_data.json"])
    if diff.returncode == 0:
        print("  · No changes detected — api_data.json is already up to date.")
        print("  ✓ Nothing to push.")
        return

    ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = f"chore(data): manual refresh {ts} [skip ci]"

    cmds = [
        (["git", "add", "data/api_data.json"],    "git add"),
        (["git", "commit", "-m", msg],            "git commit"),
        (["git", "push"],                          "git push"),
    ]

    for cmd, label in cmds:
        result = run(cmd)
        if result.returncode != 0:
            print(f"  ✗ {label} failed:", file=sys.stderr)
            print(f"    {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        print(f"  ✓ {label}")

    print("\n  🚀 Pushed! Streamlit Cloud will update within ~30 seconds.")


def main() -> None:
    print("\n  IFB Point Dashboard — Data Refresh")
    print(f"  API  : {API_BASE}")
    print(f"  Point: {IFB_CODE}")
    print(f"  User : {USERNAME}")

    records = fetch_records()
    write_json(records)
    git_push()

    _banner("Done")
    print(f"  {len(records)} records are now live on Streamlit Cloud.")
    print(f"  URL: https://ifb-point-dashboard.streamlit.app/\n")


if __name__ == "__main__":
    main()
