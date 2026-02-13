import json
import os
import requests
from datetime import datetime

# All config from GitHub secrets/env
JSON_URL    = os.getenv("JSON_SOURCE_URL")
GIST_TOKEN  = os.getenv("GIST_TOKEN")
GIST_ID     = os.getenv("OUTPUT_GIST_ID")
GIST_FILE   = "playlist.m3u"   # must match the filename in your Gist

if not JSON_URL or not GIST_TOKEN or not GIST_ID:
    raise ValueError("Missing required env vars: JSON_SOURCE_URL, GIST_TOKEN, OUTPUT_GIST_ID")

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
        raise ValueError("No valid channels generated - check JSON format")

    return "\n".join(lines)

def update_gist(m3u_content):
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "files": {
            GIST_FILE: {"content": m3u_content}
        }
    }
    url = f"https://api.github.com/gists/{GIST_ID}"
    r = requests.patch(url, headers=headers, json=payload)
    r.raise_for_status()
    print(f"Gist updated: https://gist.github.com/{GIST_ID}")
    print(f"Raw URL: https://gist.githubusercontent.com/raw/{GIST_ID}/{GIST_FILE}")

def main():
    print(f"Fetching channels from: {JSON_URL}")
    resp = requests.get(JSON_URL, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    channels = data if isinstance(data, list) else data.get("channels", [])
    if not channels:
        raise ValueError("No channels list found in JSON")

    m3u_content = generate_m3u(channels)
    update_gist(m3u_content)

if __name__ == "__main__":
    main()
