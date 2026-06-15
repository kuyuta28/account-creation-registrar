import asyncio
import sys
from camoufox.async_api import AsyncCamoufox

URL = sys.argv[1] if len(sys.argv) > 1 else 'about:blank'
PREFS = {'dom.min_background_timeout_value': 0, 'dom.suspend_inactive_tabs': False}

async def main():
    async with AsyncCamoufox(headless=False, os='windows', firefox_user_prefs=PREFS) as browser:
        page = await browser.new_page()
        await page.goto(URL)
        print('Opened:', URL)
        print('Ctrl+C to close...')
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

asyncio.run(main())