import json
import os
import requests
from datetime import datetime

# Fetch from GitHub secret only
JSON_URL = os.getenv("JSON_SOURCE_URL")
if not JSON_URL:
    raise ValueError("JSON_SOURCE_URL not set in repo secrets!")

GIST_TOKEN = os.getenv("GIST_TOKEN")
if not GIST_TOKEN:
    raise ValueError("GIST_TOKEN not set in repo secrets!")

GIST_ID_FILE = ".gist_id"          # File in repo to persist the created gist ID
GIST_FILE_NAME = "playlist.m3u"    # Name of the file inside the Gist

M3U_HEADER = """#EXTM3U x-tvg-url=""
#EXTM3U
# Generated from {source} on {timestamp} UTC
# TiviMate compatible - ClearKey + __hdnea__ duplicated
"""

def parse_drm(drm_str):
    if not isinstance(drm_str, str) or ':' not in drm_str:
        return None, None
    kid, key = drm_str.split(':', 1)
    kid = kid.strip().replace('-', '')
    key = key.strip().replace('-', '')
    if len(kid) == 32 and len(key) == 32:
        return kid, key
    return None, None

def generate_m3u(channels):
    lines = [M3U_HEADER.format(source=JSON_URL, timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M"))]

    shared_cookie = None

    for ch in channels:
        name   = ch.get("name", "Unknown").strip()
        logo   = ch.get("logo", "")
        stream = ch.get("link", "")
        drm    = ch.get("drmLicense", "")
        cookie = ch.get("cookie", "")

        if not stream or not drm:
            continue

        kid, key = parse_drm(drm)
        if not kid or not key:
            continue

        if cookie and not shared_cookie:
            shared_cookie = cookie
        cookie = shared_cookie or cookie
        if not cookie:
            continue

        extinf = f'#EXTINF:-1 tvg-id="{name.replace(" ", "_")}" group-title="JioTV" tvg-logo="{logo}",{name}'
        kodiprop1 = "#KODIPROP:inputstream.adaptive.license_type=clearkey"
        kodiprop2 = f"#KODIPROP:inputstream.adaptive.license_key=https://aqfadtv.xyz/clearkey/results.php?keyid={kid}&key={key}"
        vlcopt    = "#EXTVLCOPT:http-user-agent=plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"
        exthttp   = f'#EXTHTTP:{{"cookie":"{cookie}"}}'

        token_value = cookie.split("=", 1)[1] if "=" in cookie else ""
        stream_url = f"{stream}?{token_value}"

        lines.extend([extinf, kodiprop1, kodiprop2, vlcopt, exthttp, stream_url, ""])

    if len(lines) < 5:
        raise ValueError("No valid channels generated")

    return "\n".join(lines)

def get_or_create_gist_id():
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Check if we already have a saved ID
    if os.path.exists(GIST_ID_FILE):
        with open(GIST_ID_FILE, "r") as f:
            gist_id = f.read().strip()
        if gist_id:
            # Quick validation: try to get the gist
            r = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers)
            if r.status_code == 200:
                print(f"Using existing Gist ID: {gist_id}")
                return gist_id

    # Create new private Gist
    print("Creating new private Gist...")
    payload = {
        "description": "Auto-generated JioTV M3U Playlist",
        "public": False,
        "files": {
            GIST_FILE_NAME: {"content": "# Placeholder - will be updated soon"}
        }
    }
    r = requests.post("https://api.github.com/gists", headers=headers, json=payload)
    r.raise_for_status()
    data = r.json()
    new_id = data["id"]
    print(f"Created new Gist: {new_id}")

    # Save ID to file for next runs
    with open(GIST_ID_FILE, "w") as f:
        f.write(new_id)

    return new_id

def update_gist(gist_id, m3u_content):
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "files": {
            GIST_FILE_NAME: {"content": m3u_content}
        }
    }
    r = requests.patch(f"https://api.github.com/gists/{gist_id}", headers=headers, json=payload)
    r.raise_for_status()
    print(f"Gist updated successfully: https://gist.github.com/{gist_id}")

def main():
    resp = requests.get(JSON_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    channels = data if isinstance(data, list) else data.get("channels", [])
    if not channels:
        raise ValueError("No channels found in JSON")

    m3u_content = generate_m3u(channels)

    gist_id = get_or_create_gist_id()
    update_gist(gist_id, m3u_content)

    # Optional: print raw URL for convenience
    raw_url = f"https://gist.githubusercontent.com/raw/{gist_id}/{GIST_FILE_NAME}"
    print(f"Raw playlist URL: {raw_url}")

if __name__ == "__main__":
    main()
