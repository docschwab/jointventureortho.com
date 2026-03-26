#!/usr/bin/env python3
"""
JVO Website Build Script
========================
Fetches episode data from Transistor API and generates a static
episodes.json file for the OrthoDigest episode browser.

Run this whenever new episodes are published:
    python build.py

Requires TRANSISTOR_API_KEY environment variable.
"""

import json
import os
import re
import sys

import requests

# Load .env from OrthoDigest project
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "OrthoDigest", ".env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("TRANSISTOR_API_KEY", "")
SHOW_ID = "76191"
SITE_DIR = os.path.dirname(os.path.abspath(__file__))

# Subspecialty rotation
SUBSPECIALTIES = ["Hip", "Knee", "Shoulder & Elbow", "Foot & Ankle", "Hand", "Trauma", "Sports Medicine"]


def fetch_all_episodes():
    """Fetch all episodes from Transistor API with pagination."""
    headers = {"x-api-key": API_KEY}
    episodes = []
    page = 1

    while True:
        r = requests.get(
            "https://api.transistor.fm/v1/episodes",
            headers=headers,
            params={"show_id": SHOW_ID, "pagination[per]": 25, "pagination[page]": page},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()

        for ep in data["data"]:
            attr = ep["attributes"]
            episodes.append({
                "id": ep["id"],
                "title": attr.get("title", ""),
                "number": attr.get("number"),
                "status": attr.get("status", ""),
                "description_html": attr.get("description", ""),
                "summary": attr.get("summary", ""),
                "media_url": attr.get("media_url", ""),
                "share_url": attr.get("share_url", ""),
                "duration": attr.get("duration_in_mmss", ""),
                "published_at": attr.get("published_at", ""),
            })

        # Check pagination
        total_pages = data.get("meta", {}).get("totalPages", 1)
        if page >= total_pages:
            break
        page += 1

    return episodes


def parse_episode(ep):
    """Transform a Transistor episode into the format needed by the website."""
    number = ep.get("number") or 0
    title = ep.get("title", "")

    # Extract subspecialty from title or rotation
    subspecialty = ""
    for sub in SUBSPECIALTIES:
        if sub.lower() in title.lower():
            subspecialty = sub
            break
    if not subspecialty and number > 0:
        subspecialty = SUBSPECIALTIES[(number - 1) % 7]

    # Extract volume/issue from title
    vol_match = re.search(r"Vol\.\s*(\d+)", title)
    issue_match = re.search(r"Issue\s*(\d+)", title)
    volume = int(vol_match.group(1)) if vol_match else 1
    issue = int(issue_match.group(1)) if issue_match else ((number - 1) // 7) + 1

    # Parse manuscripts from description HTML
    manuscripts = []
    desc_html = ep.get("description_html", "")

    # Normalize HTML entities and curly quotes
    normalized = desc_html.replace("&#x201C;", '"').replace("&#x201D;", '"')
    normalized = normalized.replace("\u201c", '"').replace("\u201d", '"')
    normalized = normalized.replace("&#x2014;", "—").replace("&#x2013;", "—")
    normalized = normalized.replace("\u2014", "—").replace("\u2013", "—")

    # Strategy 1: Parse <li> items containing manuscript citations
    for li_match in re.finditer(r'<li>(.*?)</li>', normalized, re.DOTALL):
        li_text = li_match.group(1).strip()
        # Strip remaining HTML tags for matching
        li_clean = re.sub(r'<[^>]+>', '', li_text)
        # Extract: "Title" — Author et al., Journal — DOI URL
        ms_match = re.match(
            r'["\u201c](.+?)["\u201d]\s*[—–-]+\s*(\S+(?:\s+\S+)?)\s+et\s+al\.,\s*(.+?)\s*[—–-]+\s*https?://doi\.org/(\S+)',
            li_clean,
        )
        if ms_match:
            manuscripts.append({
                "title": ms_match.group(1).strip(),
                "author": ms_match.group(2).strip(),
                "journal": ms_match.group(3).strip(),
                "doi": ms_match.group(4).strip().rstrip('.,;)'),
            })
            continue
        # Fallback: try extracting DOI from the HTML version (with <a> tags)
        doi_match = re.search(r'doi\.org/([^\s<"]+)', li_text)
        title_match = re.match(r'["\u201c](.+?)["\u201d]', li_clean)
        author_match = re.search(r'[—–-]\s*(\S+(?:\s+\S+)?)\s+et\s+al\.', li_clean)
        if title_match:
            manuscripts.append({
                "title": title_match.group(1).strip(),
                "author": author_match.group(1).strip() if author_match else "",
                "journal": "",
                "doi": doi_match.group(1).strip().rstrip('.,;)') if doi_match else "",
            })

    # Strategy 2: If no <li> items found, try plain-text numbered list
    if not manuscripts:
        for match in re.finditer(
            r'\d+\.\s*"([^"]+)"\s*[—–-]\s*(\S+(?:\s+\S+)?)\s+et\s+al\.,\s*(.+?)\s*[—–-]\s*https?://doi\.org/(\S+)',
            normalized,
        ):
            manuscripts.append({
                "title": match.group(1),
                "author": match.group(2),
                "journal": match.group(3),
                "doi": match.group(4).rstrip('"<.,;)'),
            })

    # Clean description to plain text summary
    desc_text = re.sub(r"<[^>]+>", "", desc_html)
    desc_text = re.sub(r"\d+\.\s*\".*", "", desc_text).strip()
    # Take first paragraph only
    desc_text = desc_text.split("\n")[0].strip() if desc_text else ""

    return {
        "id": ep["id"],
        "number": number,
        "title": title,
        "subspecialty": subspecialty,
        "volume": volume,
        "issue": issue,
        "description": desc_text,
        "manuscripts": manuscripts,
        "manuscript_count": len(manuscripts) or 6,
        "media_url": ep.get("media_url", ""),
        "share_url": ep.get("share_url", ""),
        "duration": ep.get("duration", ""),
        "published_at": ep.get("published_at", ""),
    }


def build():
    """Main build: fetch episodes and write static JSON."""
    if not API_KEY:
        print("ERROR: TRANSISTOR_API_KEY not set")
        sys.exit(1)

    print("Fetching episodes from Transistor...")
    raw_episodes = fetch_all_episodes()
    print(f"  Found {len(raw_episodes)} episodes")

    # Parse and sort by episode number (descending — newest first)
    episodes = [parse_episode(ep) for ep in raw_episodes if ep.get("status") == "published"]
    episodes.sort(key=lambda e: e["number"], reverse=True)

    print(f"  {len(episodes)} published episodes")

    # Write static JSON
    data_dir = os.path.join(SITE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    output_path = os.path.join(data_dir, "episodes.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(episodes, f, indent=2, ensure_ascii=False)

    print(f"  Written to: {output_path}")
    print(f"  Subspecialty breakdown:")
    for sub in SUBSPECIALTIES:
        count = sum(1 for e in episodes if e["subspecialty"] == sub)
        print(f"    {sub}: {count}")


if __name__ == "__main__":
    build()
