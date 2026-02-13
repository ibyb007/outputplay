import json
import os
import requests
import re
from datetime import datetime

# Fetch JSON source URL from GitHub secret (environment variable)
JSON_URL = os.getenv("JSON_SOURCE_URL")
if not JSON_URL:
    raise ValueError("JSON_SOURCE_URL environment variable is not set! Set it in GitHub repo secrets.")

M3U_HEADER = """#EXTM3U x-tvg-url=""
#EXTM3U
# Generated from {source} on {timestamp} UTC
# TiviMate-compatible format: ClearKey DRM + __hdnea__ token duplicated (cookie header + query param)
"""

def parse_drm(drm_str):
    """
    Expects drmLicense as "kid:key" (32-char hex each, colon separated).
    Returns (kid, key) cleaned, or (None, None) if invalid.
    """
    if not isinstance(drm_str, str) or ':' not in drm_str:
        return None, None
    parts = drm_str.split(':', 1)
    if len(parts) != 2:
        return None, None
    kid = parts[0].strip().replace('-', '')
    key = parts[1].strip().replace('-', '')
    if len(kid) == 32 and len(key) == 32:
        return kid, key
    return None, None

def main():
    print(f"Fetching JSON from: {JSON_URL}")
    try:
        resp = requests.get(JSON_URL, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching or parsing JSON: {e}")
        return 1

    # Handle if wrapped (some proxies return {"channels": [...]})
    if isinstance(data, dict) and "channels" in data:
        channels = data["channels"]
    elif isinstance(data, list):
        channels = data
    else:
        print("Unexpected JSON format - expected list or dict with 'channels' key")
        return 1

    lines = [M3U_HEADER.format(
        source=JSON_URL,
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    )]

    shared_cookie = None

    for ch in channels:
        if not isinstance(ch, dict):
            continue

        name   = ch.get("name", "Unknown").strip()
        logo   = ch.get("logo", "")
        stream = ch.get("link", "")
        drm    = ch.get("drmLicense", "")
        cookie = ch.get("cookie", "")

        if not stream or not drm:
            print(f"Skipping {name} - missing link or drmLicense")
            continue

        kid, key = parse_drm(drm)
        if not kid or not key:
            print(f"Skipping {name} - invalid drmLicense format: {drm}")
            continue

        # Use first valid cookie found (they are shared/identical across channels)
        if cookie and not shared_cookie:
            shared_cookie = cookie
        if shared_cookie:
            cookie = shared_cookie
        else:
            print(f"Warning: No cookie available for {name}")
            continue

        # Build M3U entry exactly matching your working example
        extinf = f'#EXTINF:-1 tvg-id="{name.replace(" ", "_")}" group-title="JioTV" tvg-logo="{logo}",{name}'
        kodiprop1 = "#KODIPROP:inputstream.adaptive.license_type=clearkey"
        kodiprop2 = f"#KODIPROP:inputstream.adaptive.license_key=https://aqfadtv.xyz/clearkey/results.php?keyid={kid}&key={key}"
        vlcopt    = "#EXTVLCOPT:http-user-agent=plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"
        exthttp   = f'#EXTHTTP:{{"cookie":"{cookie}"}}'

        # Duplicate token: append ?__hdnea__=... to URL
        token_value = cookie.split("=", 1)[1] if "=" in cookie else ""
        stream_url = f"{stream}?{token_value}"

        lines.extend([
            extinf,
            kodiprop1,
            kodiprop2,
            vlcopt,
            exthttp,
            stream_url,
            ""   # blank line separator
        ])

    if len(lines) < 5:
        print("No valid channels were processed")
        return 1

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Successfully generated playlist.m3u with {len(lines)//7} channels")
    return 0

if __name__ == "__main__":
    exit(main())
