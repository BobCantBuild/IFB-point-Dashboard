"""Capture screenshots of the IFB Point Dashboard for documentation.

Per-point view bypasses login (it accepts ?id=<code> directly), so we
capture login + per-point screens without needing real user credentials.
"""
from playwright.sync_api import sync_playwright
from pathlib import Path
import time

OUT = Path(__file__).parent
URL = "http://127.0.0.1:8501"

def settle(page, t=2.0):
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    time.sleep(t)

def shot(page, name):
    p = OUT / f"{name}.png"
    page.screenshot(path=str(p), full_page=False)
    print("saved", p)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              device_scale_factor=1.5)
    page = ctx.new_page()

    # 1. Login screen
    page.goto(URL, wait_until="networkidle")
    settle(page, 2.5)
    shot(page, "01_login")

    # 2. Per-point view (login is bypassed when ?id=... is in URL)
    page.goto(URL + "/?id=1014154", wait_until="networkidle")
    settle(page, 5.0)
    shot(page, "02_perpoint_top")

    # capture full page too
    page.screenshot(path=str(OUT / "02_perpoint_full.png"), full_page=True)
    print("saved full perpoint")

    # Scroll to show the table
    page.evaluate("window.scrollTo(0, 400)")
    time.sleep(1.0)
    shot(page, "03_perpoint_table")

    page.evaluate("window.scrollTo(0, 800)")
    time.sleep(1.0)
    shot(page, "04_perpoint_table_more")

    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.6)

    # Click the first ✏️ edit button to surface the Edit Lead dialog
    try:
        # find a button whose text contains the pencil emoji
        page.wait_for_selector("button:has-text('✏')", timeout=5000)
        page.locator("button:has-text('✏')").first.click()
        time.sleep(2.5)
        shot(page, "05_edit_dialog_default")

        # Choose "Contacted" in the Call Status selectbox
        # Streamlit selectbox is a [role=combobox]
        boxes = page.locator("[role='combobox']")
        if boxes.count() > 0:
            boxes.first.click()
            time.sleep(0.6)
            page.get_by_role("option", name="Contacted").first.click()
            time.sleep(1.5)
            shot(page, "06_edit_dialog_contacted")

            # Pick Interested -> Not Interested to surface Reason dropdown
            boxes2 = page.locator("[role='combobox']")
            if boxes2.count() > 1:
                boxes2.nth(1).click()
                time.sleep(0.5)
                page.get_by_role("option", name="Not Interested").first.click()
                time.sleep(1.8)
                shot(page, "07_edit_dialog_reason")
    except Exception as e:
        print("dialog capture skipped:", e)

    # 3. Filter buttons — click Today Follow Up to show filtered table
    try:
        # Close any open dialog first
        page.keyboard.press("Escape")
        time.sleep(0.8)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
        btn = page.locator("button:has-text('Today Follow Up')").first
        if btn.count():
            btn.click()
            settle(page, 2.5)
            shot(page, "08_filter_today")
    except Exception as e:
        print("filter today skipped:", e)

    browser.close()
print("done")
