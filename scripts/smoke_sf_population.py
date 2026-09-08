"""Validate the SF preview in a browser; optionally run a bounded live LLM observation.

Use a disposable preview server. This script resumes then pauses that server only
when --seconds is positive. It never changes population, invents goals or intervenes.
"""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def main(url: str, seconds: int) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000}, base_url=url)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(url)
        await page.locator("#population-panel:not(.hidden)").wait_for()
        initial = await (await page.request.get("/api/state")).json()
        assert initial["world"]["scenario"] == "sf"
        if initial["stats"]["brain_mode"] == "novita":
            assert "DEEPSEEK / NOVITA" in await page.locator("#brain-mode").inner_text()
            assert "deepseek/" in await page.locator("#model-label").inner_text()
        assert initial["population"]["adult_population"] == 70568
        assert not await page.locator("#agent-background").is_visible()
        assert all("background" not in agent for agent in initial["agents"])
        await page.locator("#population-panel summary").click()
        text = await page.locator("#population-content").inner_text()
        assert "79,129" in text and "70,568" in text
        assert "2019" in text and "2023" in text
        assert "san francisco city" in text.lower()
        assert "Unknown" in text
        await page.screenshot(path="/tmp/sf-population-calibration.png")
        await page.locator("#population-panel summary").click()

        canvas = await page.locator("#world-canvas").bounding_box()
        position = initial["agents"][0]["position"]
        scale = min((canvas["width"] - 32) / 560, (canvas["height"] - 56) / 328)
        x = canvas["x"] + canvas["width"] / 2 - 280 * scale + position["x"] * 0.4 * scale
        y = canvas["y"] + canvas["height"] / 2 - 164 * scale + 8 + position["y"] * 0.4 * scale
        await page.mouse.click(x, y)
        await page.locator("#agent-background:not(.hidden)").wait_for()
        assert await page.locator("#agent-biography p").count() >= 4
        await page.screenshot(path="/tmp/sf-population-citizen.png")
        print(
            "PASS: calibrated counts, explicit employer scopes and click-only backgrounds.",
            flush=True,
        )

        state = initial
        if seconds:
            if initial["stats"]["brain_mode"] not in {"astra", "novita"}:
                raise AssertionError("LLM provider required for live observation; no rule fallback")
            await page.request.post("/api/control", data={"action": "play"})
            try:
                for elapsed in range(0, seconds, 5):
                    await asyncio.sleep(min(5, seconds - elapsed))
                    state = await (await page.request.get("/api/state")).json()
                    print(
                        json.dumps(
                            {
                                "seconds": min(elapsed + 5, seconds),
                                "world_time": state["world"]["time"],
                                "provider": state["stats"]["brain_mode"],
                                "llm_decisions": state["stats"]["llm_decisions"],
                                "provider_error": state["stats"]["brain_error"],
                            }
                        ),
                        flush=True,
                    )
            finally:
                await page.request.post("/api/control", data={"action": "pause"})
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path="/tmp/sf-population-mobile.png", full_page=True)
        assert not errors, errors
        Path(".data").mkdir(exist_ok=True)
        Path(".data/sf-population-smoke.json").write_text(
            json.dumps(
                {
                    "scenario": state["population"],
                    "stats": state["stats"],
                    "agents": state["agents"],
                    "browser_errors": errors,
                    "observation_seconds": seconds,
                    "claim": "Integration observation, not long-run or consciousness validation",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        await browser.close()
        if seconds:
            assert not state["stats"]["brain_error"], state["stats"]["brain_error"]
            assert state["world"]["time"] > initial["world"]["time"]
            assert state["stats"]["llm_decisions"] > initial["stats"]["llm_decisions"]
            print("PASS: unprompted LLM decisions in the SF resident scenario.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8003")
    parser.add_argument("--seconds", type=int, default=0)
    args = parser.parse_args()
    if not 0 <= args.seconds <= 120:
        parser.error("--seconds must be between 0 and 120")
    asyncio.run(main(args.url, args.seconds))
