import asyncio
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright
import requests

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
WHATNOT_USERNAME = "loosepacks"
DISCORD_WEBHOOK  = os.environ.get("DISCORD_WEBHOOK", "YOUR_DISCORD_WEBHOOK_URL_HERE")
CHECK_INTERVAL   = 60  # seconds between checks
TEST_MODE        = os.environ.get("TEST_MODE", "false").lower() == "true"
DEBUG_MODE       = os.environ.get("DEBUG_MODE", "false").lower() == "true"
# ─────────────────────────────────────────────

PROFILE_URL      = f"https://www.whatnot.com/user/{WHATNOT_USERNAME}"
LIVE_URL_PATTERN = re.compile(r'https://www\.whatnot\.com/live/[a-f0-9\-]+', re.IGNORECASE)

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

async def check_if_live(browser) -> tuple[str | None, str]:
    page = await browser.new_page()
    try:
        log(f"Fetching {PROFILE_URL} ...")
        await page.goto(PROFILE_URL, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)

        content = await page.content()
        page_title = await page.title()
        log(f"Page title: {page_title}")
        log(f"Page content length: {len(content)} chars")

        # Search for any /live/ URL
        all_live_urls = LIVE_URL_PATTERN.findall(content)
        log(f"Live URLs found on page: {all_live_urls}")

        if DEBUG_MODE:
            # Log a snippet of the page around 'live' mentions
            idx = content.lower().find('/live/')
            if idx != -1:
                log(f"Context around /live/: ...{content[max(0,idx-100):idx+200]}...")
            else:
                log("No /live/ string found anywhere in page content")
                # Log first 500 chars to see what the page looks like
                log(f"Page start: {content[:500]}")

        if not all_live_urls:
            return None, ""

        live_url = all_live_urls[0]

        # Try to grab the stream title
        stream_title = "Live Stream"
        try:
            live_page = await browser.new_page()
            await live_page.goto(live_url, wait_until="domcontentloaded", timeout=20000)
            title = await live_page.title()
            log(f"Stream page title: {title}")
            cleaned = re.sub(r'\s*·\s*Whatnot.*$', '', title, flags=re.IGNORECASE).strip()
            cleaned = re.sub(
                rf'^{re.escape(WHATNOT_USERNAME)}\s+is\s+live\s*·\s*',
                '', cleaned, flags=re.IGNORECASE
            ).strip()
            if cleaned:
                stream_title = cleaned
            await live_page.close()
        except Exception as e:
            log(f"Could not fetch stream title: {e}")

        return live_url, stream_title

    except Exception as e:
        log(f"ERROR checking profile: {e}")
        return None, ""
    finally:
        await page.close()

async def main():
    if TEST_MODE:
        log("TEST MODE — sending a sample Discord notification...")
        send_discord_notification(
            "https://www.whatnot.com/live/test-1234",
            "EVOLVING SKIES w/ @Poke_AK47"
        )
        log("Test done. Check your Discord channel!")
        return

    log(f"Whatnot Live Notifier started — watching @{WHATNOT_USERNAME}")
    log(f"Checking every {CHECK_INTERVAL}s using headless browser")
    if DEBUG_MODE:
        log("DEBUG MODE enabled — extra logging active")
    log("─" * 55)

    last_live_url: str | None = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        while True:
            live_url, stream_title = await check_if_live(browser)

            if live_url:
                if live_url != last_live_url:
                    log(f"🔴 LIVE detected! {live_url}")
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

            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
