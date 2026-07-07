"""
IFB Point Master Refresh
========================
Fetches fresh IFB Point codes from the BSE API every morning and updates
IFB_Point_Master.txt with the latest list.

Rules:
  - Existing codes  → keep their current name (preserve manual edits)
  - New codes       → named "Unnamed" (for manual update later)
  - Codes removed from API → dropped from the file

Schedule (server cron example):
  0 7 * * * cd /path/to/dashboard && python refresh_master.py
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE   = "https://bseapi.ifbsupport.com/api"
API_USER   = "IFBFollowUPAPP"
API_PASS   = "U29tZVJhbmRvbUJhc2U2NA=="

MASTER_TXT = Path(__file__).resolve().parent / "IFB_Point_Master.txt"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login(session: requests.Session) -> str:
    r = session.post(
        f"{API_BASE}/Auth/login",
        json={"userName": API_USER, "password": API_PASS},
        timeout=30,
    )
    r.raise_for_status()
    token = r.json().get("token")
    if not token:
        raise RuntimeError(f"Login succeeded but no token returned: {r.text[:200]}")
    return token


def _fetch_codes(session: requests.Session, token: str) -> list[str]:
    r = session.get(
        f"{API_BASE}/IFBPointFollowUp/GetAllIFBPointPinCodesMapping",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    seen, codes = set(), []
    for row in data:
        code = str(row.get("channel_Code", "")).strip()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return sorted(codes)


def _load_existing() -> dict[str, str]:
    """Return {code: name} from the current master txt.
    Splits each line on the first run of whitespace, so it accepts both the
    tab-separated format (code\\tname) and the space-separated format the
    external sync currently produces (code name) — same parsing as
    overview_dashboard._read_master_names / streamlit_app._load_master_codes."""
    mapping: dict[str, str] = {}
    if not MASTER_TXT.exists():
        return mapping
    for line in MASTER_TXT.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        code = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else ""
        if code:
            mapping[code] = name
    return mapping


def _write(codes: list[str], mapping: dict[str, str]) -> None:
    lines = [f"{code}\t{mapping.get(code, 'Unnamed')}" for code in codes]
    MASTER_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] refresh_master starting")

    existing = _load_existing()
    print(f"  Existing codes in master: {len(existing)}")

    with requests.Session() as s:
        s.verify = False
        print("  Logging in to BSE API...")
        token = _login(s)
        print("  Fetching IFB Point codes...")
        api_codes = _fetch_codes(s, token)

    print(f"  API returned {len(api_codes)} unique codes")

    new_codes  = [c for c in api_codes if c not in existing]
    gone_codes = [c for c in existing  if c not in set(api_codes)]

    # Build updated mapping: preserve existing names, default new ones to "Unnamed"
    updated: dict[str, str] = {}
    for code in api_codes:
        updated[code] = existing.get(code, "Unnamed")

    _write(api_codes, updated)

    print(f"  New codes added  : {len(new_codes)}  {new_codes if new_codes else ''}")
    print(f"  Codes removed    : {len(gone_codes)} {gone_codes if gone_codes else ''}")
    print(f"  Total written    : {len(api_codes)}")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done — {MASTER_TXT.name} updated")


if __name__ == "__main__":
    main()
