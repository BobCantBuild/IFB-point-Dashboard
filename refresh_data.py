"""
IFB Point Dashboard — Manual Data Refresh
==========================================
Run this from any PC on the IFB office network:

    python refresh_data.py

What it does:
  1. Runs scripts/sync_api.py to fetch records → data/api_data.json
  2. If api_data.json changed, commits and pushes to GitHub
  3. Streamlit Cloud picks up the new data automatically (~30 sec)

API credentials are read from environment variables (or fall back to the
defaults defined in scripts/sync_api.py):
  IFB_API_USER, IFB_API_PASS, IFB_POINT_CODE
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_api.py"
DATA_FILE = REPO_ROOT / "data" / "api_data.json"


def _section(msg: str) -> None:
    print(f"\n── {msg} " + "─" * (50 - len(msg)))


def _run(cmd: list[str], label: str) -> subprocess.CompletedProcess:
    """Run a command in the repo root and stream output to console."""
    result = subprocess.run(cmd, cwd=REPO_ROOT, text=True)
    if result.returncode != 0:
        print(f"  ✗ {label} failed (exit code {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def _git(args: list[str], label: str, *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command capturing output (so we can decide on next step)."""
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        print(f"  ✗ {label} failed:", file=sys.stderr)
        print(f"    {result.stderr.strip()}", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def fetch_from_api() -> None:
    """Delegate to scripts/sync_api.py — the canonical fetch logic."""
    _section("Fetching from IFB BSE API")
    _run([sys.executable, str(SYNC_SCRIPT)], "API sync")


def commit_and_push() -> None:
    """Stage api_data.json and push only if the file actually changed."""
    _section("Committing & pushing")

    # Check if api_data.json is dirty relative to HEAD
    diff = _git(["diff", "--quiet", "data/api_data.json"], "diff", check=False)
    if diff.returncode == 0:
        print("  · api_data.json is already up to date — nothing to push.")
        return

    # Show what changed
    record_count = "?"
    try:
        blob = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        record_count = blob.get("record_count", "?")
    except Exception:
        pass

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = f"chore(data): refresh api_data.json — {record_count} records @ {ts} [skip ci]"

    _git(["add", "data/api_data.json"],     "git add")
    print("  ✓ git add")
    _git(["commit", "-m", msg],             "git commit")
    print("  ✓ git commit")
    _git(["push"],                          "git push")
    print("  ✓ git push")

    print("\n  🚀 Pushed! Streamlit Cloud will update within ~30 seconds.")
    print(f"     URL: https://ifb-point-dashboard.streamlit.app/")


def main() -> None:
    print("\n  IFB Point Dashboard — Manual Data Refresh")
    print(f"  Repo: {REPO_ROOT}")

    if not SYNC_SCRIPT.exists():
        print(f"  ✗ Missing {SYNC_SCRIPT.relative_to(REPO_ROOT)}", file=sys.stderr)
        sys.exit(1)

    fetch_from_api()
    commit_and_push()

    _section("Done")


if __name__ == "__main__":
    main()
