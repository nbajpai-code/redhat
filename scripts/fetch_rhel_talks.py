#!/usr/bin/env python3
"""
fetch_rhel_talks.py
--------------------
Fetches YouTube videos covering Red Hat Enterprise Linux (RHEL 9/10),
RHCSA (EX200), RHCE (EX294), and Ansible Automation Platform — then
writes RHEL_TALKS.md in the redhat repo root.

Retention policy: talks are kept for 1 year from their first-fetch date.
If a YouTube run returns no results the existing list is preserved (not wiped).

Run with the agenticSOC venv which has youtubesearchpython installed:
    /path/to/agenticSOC/venv/bin/python fetch_rhel_talks.py
"""

import os
import re
from datetime import datetime, timezone, timedelta

import pytz
from youtubesearchpython import VideosSearch

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ONE_YEAR_AGO = datetime.now(timezone.utc) - timedelta(days=365)

# RHEL_TALKS.md lives in the redhat repo root (one level up from scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "..", "RHEL_TALKS.md")

QUERIES = [
    # RHCSA EX200
    "RHCSA EX200 exam prep 2024 2025",
    "Red Hat Certified System Administrator RHEL 9 tutorial",
    "RHCSA 9 practice lab hands-on",
    # RHCE EX294
    "RHCE EX294 Ansible exam prep 2025",
    "Red Hat Certified Engineer Ansible automation RHEL 9",
    "Ansible playbook tutorial RHCE 2024",
    # RHEL general / new features
    "RHEL 9 new features administration",
    "RHEL 10 preview features Red Hat",
    # Ansible Automation Platform
    "Ansible Automation Platform AAP enterprise 2024 2025",
    "Red Hat Ansible Tower AWX tutorial",
]

# Row regex matching the format written by write_markdown()
ROW_RE = re.compile(
    r"^\|\s*(?P<title>.+?)\s*\|\s*(?P<channel>.+?)\s*\|\s*(?P<duration>.+?)\s*\|"
    r"\s*(?P<views>.+?)\s*\|\s*\[Link\]\((?P<link>https?://[^\)]+)\)\s*\|"
    r"\s*(?P<fetched>\d{4}-\d{2}-\d{2})\s*\|$"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_existing_talks() -> list[dict]:
    """Read RHEL_TALKS.md and return entries whose Fetched date is within 1 year."""
    if not os.path.exists(OUTPUT_FILE):
        return []

    kept: list[dict] = []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            m = ROW_RE.match(line.rstrip())
            if not m:
                continue
            try:
                fetched_dt = datetime.strptime(m.group("fetched"), "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                fetched_dt = datetime.now(timezone.utc)  # keep if date is malformed

            if fetched_dt >= ONE_YEAR_AGO:
                kept.append(
                    {
                        "title": m.group("title"),
                        "link": m.group("link"),
                        "channel": m.group("channel"),
                        "duration": m.group("duration"),
                        "views": m.group("views"),
                        "fetched": m.group("fetched"),
                    }
                )

    print(f"Retained {len(kept)} existing talk(s) (within the last year).")
    return kept


def fetch_new_talks() -> list[dict]:
    """Search YouTube for fresh RHEL / RHCSA / RHCE / Ansible content."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fresh: list[dict] = []
    seen_urls: set[str] = set()

    print("Fetching RHEL / Ansible talks from YouTube...")
    for query in QUERIES:
        print(f"  Searching: {query}")
        try:
            results = VideosSearch(query, limit=10).result()
            for video in results.get("result", []):
                link = video["link"]
                if link not in seen_urls:
                    seen_urls.add(link)
                    fresh.append(
                        {
                            "title": video["title"],
                            "link": link,
                            "channel": video["channel"]["name"],
                            "duration": video["duration"],
                            "views": video["viewCount"]["short"],
                            "fetched": today,
                        }
                    )
        except Exception as exc:
            print(f"  Error for '{query}': {exc}")

    print(f"Found {len(fresh)} new talk(s) from YouTube this run.")
    return fresh


def merge_talks(existing: list[dict], new: list[dict]) -> list[dict]:
    """Combine new + existing, deduplicate by URL. New entries win on conflict."""
    seen: set[str] = set()
    merged: list[dict] = []
    for talk in new:
        if talk["link"] not in seen:
            seen.add(talk["link"])
            merged.append(talk)
    for talk in existing:
        if talk["link"] not in seen:
            seen.add(talk["link"])
            merged.append(talk)
    return merged


def write_markdown(talks: list[dict]) -> None:
    """Write RHEL_TALKS.md with the merged list, grouped by topic."""
    now_str = datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md = "# Red Hat / RHEL YouTube Talks & Tutorials\n\n"
    md += f"Last Updated: {now_str}\n\n"
    md += (
        "A curated list of YouTube talks, tutorials, and exam-prep videos covering "
        "**RHEL 9/10**, **RHCSA (EX200)**, **RHCE (EX294)**, and "
        "**Ansible Automation Platform**. Automatically updated weekly. "
        "Talks older than 1 year are automatically pruned.\n\n"
        "> See [YOUTUBE_CHANNELS.md](./YOUTUBE_CHANNELS.md) for the curated list of "
        "top channels to follow.\n\n"
    )

    if not talks:
        md += "No talks found.\n"
    else:
        md += "| Title | Channel | Duration | Views | Watch | Fetched |\n"
        md += "|-------|---------|----------|-------|-------|---------|\n"
        for v in talks:
            title = v["title"].replace("|", "-")
            channel = v["channel"].replace("|", "-")
            md += (
                f"| {title} | {channel} | {v['duration']} | {v['views']} "
                f"| [Link]({v['link']}) | {v['fetched']} |\n"
            )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Wrote {os.path.normpath(OUTPUT_FILE)} — {len(talks)} talk(s) total.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def fetch_talks() -> None:
    existing = load_existing_talks()
    new = fetch_new_talks()

    if not new:
        print("No new talks found — retaining existing list (up to 1 year old).")

    merged = merge_talks(existing, new)
    write_markdown(merged)


if __name__ == "__main__":
    fetch_talks()
