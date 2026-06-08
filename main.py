import requests
import time
import re
import os
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIGURATION — edit these two values only
# ─────────────────────────────────────────────
WHATNOT_USERNAME  = "loosepacks"
DISCORD_WEBHOOK   = os.environ.get("DISCORD_WEBHOOK", "YOUR_DISCORD_WEBHOOK_URL_HERE")

# How often to check (in seconds). 60 = every 1 minute.
CHECK_INTERVAL    = 60
# ─────────────────────────────────────────────

PROFILE_URL = f"https://www.whatnot.com/user/{WHATNOT_USERNAME}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Pattern to detect a live stream URL on the profile page
LIVE_URL_PATTERN = re.compile(
    r'href=["\']?(https://www\.whatnot\.com/live/[a-f0-9\-]+)["\']?',
    re.IGNORECASE,
)

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def fetch_profile() -> str | None:
    """Fetch the Whatnot profile page HTML. Returns None on error."""
    try:
        resp = requests.get(PROFILE_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        log(f"ERROR fetching profile: {e}")
        return None

def find_live_url(html: str) -> str | None:
    """Return the first /live/ URL found in the page, or None."""
    match = LIVE_URL_PATTERN.search(html)
    return match.group(1) if match else None

def send_discord_notification(live_url: str):
    """Post a rich embed to the Discord webhook."""
    payload = {
        "content": "@everyone",          # remove this line if you don't want a ping
        "embeds": [
            {
                "title": f"🔴 {WHATNOT_USERNAME} is LIVE on Whatnot!",
                "description": (
                    f"**Loose Packs Trading Co** just went live!\n\n"
                    f"🎴 High-End Boutique for Sealed, Vintage & Pokémon\n\n"
                    f"[👉 Watch Now]({live_url})"
                ),
                "url": live_url,
                "color": 0xFF4500,        # orange-red
                "footer": {"text": "Whatnot Live Notifier"},
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ],
    }
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        r.raise_for_status()
        log(f"Discord notification sent! → {live_url}")
    except requests.RequestException as e:
        log(f"ERROR sending Discord notification: {e}")

def main():
    log(f"Whatnot Live Notifier started — watching @{WHATNOT_USERNAME}")
    log(f"Checking every {CHECK_INTERVAL}s  |  Profile: {PROFILE_URL}")
    log("─" * 55)

    last_live_url: str | None = None   # tracks the current/last live stream URL

    while True:
        html = fetch_profile()

        if html:
            live_url = find_live_url(html)

            if live_url:
                # Found a live stream
                if live_url != last_live_url:
                    # It's a NEW stream (different URL = new session)
                    log(f"🔴 LIVE detected! {live_url}")
                    send_discord_notification(live_url)
                    last_live_url = live_url
                else:
                    log(f"Still live (same stream). No new notification.")
            else:
                # No live stream found
                if last_live_url:
                    log("Stream ended (no /live/ URL found on profile).")
                    last_live_url = None
                else:
                    log("Not live.")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
