#!/usr/bin/env python3
"""
Downloader for SEBI DRHP PDFs + uploader to Google Drive.
"""

import requests
from bs4 import BeautifulSoup
import os
import json
import hashlib
import time
from urllib.parse import urljoin, urlparse

# --- CONFIG ---
SEBI_URL = "https://www.sebi.gov.in/filings/public-issues.html"
OUT_DIR = "drhps"
STATE_FILE = "downloaded.json"
HEADERS = {"User-Agent": "drhp-downloader/1.0"}
KEYWORDS = ["draft", "drhp", "red-herring", "red herring", "offer document"]

# Google Drive
FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID"  # 🔴 replace with your folder ID
SERVICE_ACCOUNT_FILE = "service_account.json"  # 🔴 place JSON key in repo

os.makedirs(OUT_DIR, exist_ok=True)

# --- Drive Setup ---
from pydrive2.auth import ServiceAccountCredentials
from pydrive2.drive import GoogleDrive

def get_drive():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return GoogleDrive(creds)

# --- Helpers ---
def load_state():
    if os.path.exists(STATE_FILE):
        return set(json.load(open(STATE_FILE)))
    return set()

def save_state(state):
    json.dump(list(state), open(STATE_FILE, "w"), indent=2)

def is_pdf_link(href):
    return href and (href.lower().endswith(".pdf") or ".pdf?" in href.lower())

def likely_drhp_text(text):
    return text and any(k in text.lower() for k in KEYWORDS)

def pdf_filename(url):
    parsed = urlparse(url)
    name = os.path.basename(parsed.path) or "drhp.pdf"
    name = name.split("?")[0]
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f"{h}_{name}"

def download_file(url, outpath):
    print("Downloading:", url)
    r = requests.get(url, headers=HEADERS, stream=True, timeout=30)
    r.raise_for_status()
    with open(outpath, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
    print("Saved:", outpath)

def upload_to_drive(drive, filepath, filename):
    file = drive.CreateFile({"parents": [{"id": FOLDER_ID}], "title": filename})
    file.SetContentFile(filepath)
    file.Upload()
    print(f"Uploaded to Drive: {filename}")

# --- Main ---
def main():
    state = load_state()
    print("Loaded state:", len(state))

    r = requests.get(SEBI_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    candidates = []
    for a in soup.find_all("a", href=True):
        full = urljoin(SEBI_URL, a["href"])
        text = (a.get_text(" ", strip=True) or "") + " " + a["href"]
        if is_pdf_link(full) and likely_drhp_text(text):
            candidates.append(full)

    drive = get_drive()
    new_count = 0
    for url in candidates:
        if url in state:
            continue
        fname = pdf_filename(url)
        path = os.path.join(OUT_DIR, fname)
        try:
            download_file(url, path)
            upload_to_drive(drive, path, fname)
            state.add(url)
            new_count += 1
            time.sleep(1)
        except Exception as e:
            print("Error with", url, ":", e)

    save_state(state)
    print("New PDFs:", new_count)

if __name__ == "__main__":
    main()
