"""Run against a local server. Resumes simulation and makes real calls if configured."""

import argparse
import asyncio
import json

from playwright.async_api import async_playwright


async def run(url: str, seconds: int, pause_after: bool) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000}, base_url=url)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(url)
        await page.get_by_text("CITY LIFE", exact=True).click()
        await page.get_by_text("Golden Gate Community Meals", exact=True).wait_for(timeout=10000)
        await page.request.post("/api/control", data={"action": "play"})
        first = await (await page.request.get("/api/state")).json()
        print(f"Browser ready; observing {len(first['agents'])} citizens.", flush=True)
        for _ in range(max(1, seconds // 10)):
            await page.wait_for_timeout(10000)
            state = await (await page.request.get("/api/state")).json()
            print(
                json.dumps(
                    {
                        "time": state["world"]["time"],
                        "decisions": state["stats"]["astra_decisions"],
                        "companies": len(state["economy"]["companies"]),
                        "raised": state["stats"]["capital_raised"],
                        "provider_error": state["stats"]["brain_error"],
                        "actions": {a["name"]: a["current_action"] for a in state["agents"]},
                    }
                ),
                flush=True,
            )
        if pause_after:
            await page.request.post("/api/control", data={"action": "pause"})
        await page.screenshot(path="/tmp/sf-economy-live.png")
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path="/tmp/sf-economy-mobile.png", full_page=True)
        assert state["world"]["time"] > first["world"]["time"], "World clock did not advance"
        if state["stats"]["brain_mode"] == "astra":
            assert state["stats"]["astra_decisions"] > first["stats"]["astra_decisions"]
            assert not state["stats"]["brain_error"], "Provider error during live test"
        assert not errors, errors
        print("PASS: UI, advancing world, new decisions, no browser errors.", flush=True)
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--pause-after", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.url, args.seconds, args.pause_after))
