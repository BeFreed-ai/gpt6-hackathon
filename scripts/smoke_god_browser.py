"""Exercise fatal tools through canvas clicks in a disposable local test world.

Kills two citizens, resumes the simulation and observes real decisions when Astra is configured.
"""

import argparse
import asyncio
import json

from playwright.async_api import async_playwright


async def run(url):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000}, base_url=url)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(url)
        await page.request.post("/api/control", data={"action": "pause"})
        await page.wait_for_timeout(700)
        first = await (await page.request.get("/api/state")).json()
        victims = [a for a in first["agents"] if a["alive"]][:2]
        assert len(victims) == 2
        canvas = page.locator("#world-canvas")

        async def click_citizen(agent):
            box = await canvas.bounding_box()
            scale = min((box["width"] - 32) / 560, (box["height"] - 56) / 328)
            x = round(box["width"] / 2 - 280 * scale) + agent["position"]["x"] * scale * 0.4
            y = round(box["height"] / 2 - 164 * scale + 8) + agent["position"]["y"] * scale * 0.4
            await canvas.click(position={"x": x, "y": y})

        for tool, victim in zip(("kill", "lightning"), victims, strict=True):
            await page.locator(f'[data-tool="{tool}"]').click()
            async with page.expect_response("**/api/intervene") as response:
                await click_citizen(victim)
            receipt = await (await response.value).json()
            assert victim["id"] in receipt["killed"], receipt
            state = await (await page.request.get("/api/state")).json()
            dead = next(a for a in state["agents"] if a["id"] == victim["id"])
            assert not dead["alive"] and dead["health"] == 0
            print(json.dumps({
                "tool": tool, "victim": victim["name"], "receipt": receipt
            }), flush=True)
            await page.wait_for_timeout(500)

        await click_citizen(victims[0])
        await page.locator("#agent-status").filter(has_text="dead").wait_for()
        await page.get_by_text("CITY LIFE", exact=True).click()
        await page.locator("#intervention-log").get_by_text("LIGHTNING", exact=True).wait_for()
        await page.request.post("/api/control", data={"action": "play"})
        for step in range(4):
            await page.wait_for_timeout(10000)
            state = await (await page.request.get("/api/state")).json()
            print(json.dumps({
                "seconds_observed": (step + 1) * 10,
                "population": state["stats"]["population"],
                "decisions": state["stats"]["astra_decisions"],
                "followups": sum(len(e["followups"]) for e in state["interventions"]),
                "player_messages": [e["public_text"] for e in state["player_messages"]],
            }), flush=True)
        await page.screenshot(path="/tmp/sf-god-desktop.png", full_page=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path="/tmp/sf-god-mobile.png", full_page=True)
        assert not errors, errors
        assert state["world"]["time"] > first["world"]["time"]
        if state["stats"]["brain_mode"] == "astra":
            assert state["stats"]["astra_decisions"] > first["stats"]["astra_decisions"]
            assert any(e["followups"] for e in state["interventions"])
            assert not state["stats"]["brain_error"]
        print("PASS: fatal tools, deceased inspector, live followups, no JS errors.", flush=True)
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8002")
    asyncio.run(run(parser.parse_args().url))
