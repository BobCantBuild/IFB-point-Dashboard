"""Shared configuration for the IFB Point Dashboard.

Single source of truth for the IFB Point Code and API credentials.
Both streamlit_app.py and scripts/sync_api.py import from here.

To switch IFB Point franchise, change IFB_POINT_CODE below — that's it.
"""
from __future__ import annotations

# ─── Change this when switching IFB Point franchise ──────────────────────────
IFB_POINT_CODE = "1017061"

# ─── API credentials (rarely change) ─────────────────────────────────────────
API_BASE = "https://bseapi.ifbsupport.com/api"
API_USER = "IFBFollowUPAPP"
API_PASS = "U29tZVJhbmRvbUJhc2U2NA=="
