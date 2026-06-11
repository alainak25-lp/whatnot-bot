import requests
import time
import re
import os
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
WHATNOT_USERNAME = "loosepacks"
DISCORD_WEBHOOK  = os.environ.get("DISCORD_WEBHOOK", "YOUR_DISCORD_WEBHOOK_URL_HERE")
CHECK_INTERVAL   = 60  # seconds between checks
TEST_MODE        = os.environ.get("TEST_MODE", "false").lower() == "true"
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.whatnot.com",
    "Origin": "https://www.whatnot.com",
}

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def send_discord_notification(live_url: str, stream_title: str):
    payload = {
        "content": "🔴 **loosepacks is LIVE!**",
        "embeds": [
            {
                "title": f"🎴 {stream_title}",
                "description": (
                    f"**Loose Packs Trading Co** just went live on Whatnot!\n\n"
                    f"[👉 Watch the stream now]({live_url})"
                ),
                "url": live_url,
                "color": 0xFF4500,
                "footer": {"text": f"whatnot.com/user/{WHATNOT_USERNAME}"},
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ],
    }
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        r.raise_for_status()
        log(f"✅ Discord notification sent! → {live_url}")
    except requests.RequestException as e:
        log(f"ERROR sending Discord notification: {e}")

def check_graphql() -> tuple[str | None, str]:
    """Query Whatnot's internal GraphQL API for live streams by username."""
    url = "https://www.whatnot.com/api/live/graphql"
    query = """
    query GetUserLivestream($username: String!) {
      userByUsername(username: $username) {
        activeLivestream {
          id
          title
          url
        }
      }
    }
    """
    try:
        resp = requests.post(
            url,
            json={"query": query, "variables": {"username": WHATNOT_USERNAME}},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        log(f"GraphQL response: {data}")
        livestream = (
            data.get("data", {})
                .get("userByUsername", {})
                .get("activeLivestream")
        )
        if livestream:
            live_id    = livestream.get("id", "")
            live_title = livestream.get("title", "Live Stream")
            live_url   = livestream.get("url") or f"https://www.whatnot.com/live/{live_id}"
            return live_url, live_title
    except Exception as e:
        log(f"GraphQL check failed: {e}")
    return None, ""

def check_search_api() -> tuple[str | None, str]:
    """Fall back to checking Whatnot's search/live API endpoint."""
    try:
        url = f"https://www.whatnot.com/api/live/streams?username={WHATNOT_USERNAME}&status=live"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        log(f"Search API response: {data}")
        streams = data.get("streams") or data.get("data") or []
        if streams:
            s     = streams[0]
            live_id    = s.get("id", "")
            live_title = s.get("title", "Live Stream")
            live_url   = s.get("url") or f"https://www.whatnot.com/live/{live_id}"
            return live_url, live_title
    except Exception as e:
        log(f"Search API check failed: {e}")
    return None, ""

def check_profile_page() -> tuple[str | None, str]:
    """Last resort — scrape the profile page HTML for a /live/ URL."""
    try:
        url  = f"https://www.whatnot.com/user/{WHATNOT_USERNAME}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text
        log(f"Profile page length: {len(html)} chars")
        match = re.search(r'https://www\.whatnot\.com/live/[a-f0-9\-]+', html)
        if match:
            live_url = match.group(0)
            # Try to get title from meta tags
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            title = "Live Stream"
            if title_match:
                raw = title_match.group(1).strip()
                cleaned = re.sub(r'\s*·\s*Whatnot.*$', '', raw, flags=re.IGNORECASE).strip()
                cleaned = re.sub(rf'^{re.escape(WHATNOT_USERNAME)}\s+is\s+live\s*·\s*', '', cleaned, flags=re.IGNORECASE).strip()
                title = cleaned or "Live Stream"
            return live_url, title
    except Exception as e:
        log(f"Profile page check failed: {e}")
    return None, ""

def check_if_live() -> tuple[str | None, str]:
    """Try multiple methods to detect a live stream."""
    # Method 1: GraphQL API
    live_url, title = check_graphql()
    if live_url:
        log("Detected via GraphQL API")
        return live_url, title

    # Method 2: Search/streams API
    live_url, title = check_search_api()
    if live_url:
        log("Detected via Search API")
        return live_url, title

    # Method 3: Profile page scrape
    live_url, title = check_profile_page()
    if live_url:
        log("Detected via profile page scrape")
        return live_url, title

    return None, ""

def main():
    if TEST_MODE:
        log("TEST MODE — sending a sample Discord notification...")
        send_discord_notification(
            "https://www.whatnot.com/live/test-1234",
            "EVOLVING SKIES w/ @Poke_AK47"
        )
        log("Test done. Check your Discord channel!")
        return

    log(f"Whatnot Live Notifier started — watching @{WHATNOT_USERNAME}")
    log(f"Checking every {CHECK_INTERVAL}s")
    log("─" * 55)

    last_live_url: str | None = None

    while True:
        live_url, stream_title = check_if_live()

        if live_url:
            if live_url != last_live_url:
                log(f"🔴 LIVE detected! {live_url}")
                log(f"   Stream title: {stream_title}")
                send_discord_notification(live_url, stream_title)
                last_live_url = live_url
            else:
                log("Still live. No new notification.")
        else:
            if last_live_url:
                log("Stream ended.")
                last_live_url = None
            else:
                log("Not live.")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
