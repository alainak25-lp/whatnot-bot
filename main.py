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

CHECK_INTERVAL = 60  # seconds

TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
# ─────────────────────────────────────────────

# Pages to check for loosepacks appearing live
CHECK_URLS = [
    "https://www.whatnot.com/category/trading-cards",
    "https://www.whatnot.com/category/pokemon-cards",
    f"https://www.whatnot.com/user/{WHATNOT_USERNAME}",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Matches a /live/ URL near the username
LIVE_BLOCK_PATTERN = re.compile(
    r'(https://www\.whatnot\.com/live/[a-f0-9\-]+)[^\n]{0,300}?' + re.escape(WHATNOT_USERNAME) +
    r'|' +
    re.escape(WHATNOT_USERNAME) + r'[^\n]{0,300}?(https://www\.whatnot\.com/live/[a-f0-9\-]+)',
    re.IGNORECASE | re.DOTALL,
)

TITLE_PATTERN = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def fetch_page(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        log(f"ERROR fetching {url}: {e}")
        return None

def find_live_url_on_page(html: str) -> str | None:
    """Look for a /live/ URL near the username on the page."""
    match = LIVE_BLOCK_PATTERN.search(html)
    if match:
        return match.group(1) or match.group(2)
    return None

def check_all_pages() -> str | None:
    """Check each page in order, return live URL if found."""
    for url in CHECK_URLS:
        html = fetch_page(url)
        if html:
            live_url = find_live_url_on_page(html)
            if live_url:
                log(f"Found live URL on {url}")
                return live_url
    return None

def fetch_stream_title(live_url: str) -> str:
    html = fetch_page(live_url)
    if not html:
        return "Live Stream"
    match = TITLE_PATTERN.search(html)
    if not match:
        return "Live Stream"
    raw = match.group(1).strip()
    cleaned = re.sub(r'\s*·\s*Whatnot.*$', '', raw, flags=re.IGNORECASE).strip()
    cleaned = re.sub(
        rf'^{re.escape(WHATNOT_USERNAME)}\s+is\s+live\s*·\s*',
        '', cleaned, flags=re.IGNORECASE,
    ).strip()
    return cleaned or "Live Stream"

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

def run_test():
    log("TEST MODE — sending a sample Discord notification...")
    send_discord_notification(
        "https://www.whatnot.com/live/test-1234",
        "EVOLVING SKIES w/ @Poke_AK47"
    )
    log("Test done. Check your Discord channel!")

def main():
    if TEST_MODE:
        run_test()
        return

    log(f"Whatnot Live Notifier started — watching @{WHATNOT_USERNAME}")
    log(f"Checking every {CHECK_INTERVAL}s across {len(CHECK_URLS)} pages")
    log("─" * 55)

    last_live_url: str | None = None

    while True:
        live_url = check_all_pages()

        if live_url:
            if live_url != last_live_url:
                log(f"🔴 LIVE detected! {live_url}")
                stream_title = fetch_stream_title(live_url)
                log(f"   Stream title: {stream_title}")
                send_discord_notification(live_url, stream_title)
                last_live_url = live_url
            else:
                log("Still live (same stream). No new notification.")
        else:
            if last_live_url:
                log("Stream ended.")
                last_live_url = None
            else:
                log("Not live.")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
