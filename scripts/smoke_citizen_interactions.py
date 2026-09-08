"""Exercise the recorded engine interactions in a browser; never send simulation commands."""
import asyncio
import json
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 900})
        errors, requests = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def allow_static(route):
            request = route.request
            requests.append({"method": request.method, "url": request.url})
            if request.method != "GET" or not request.url.startswith("http://127.0.0.1:8007/static/"):
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", allow_static)
        await page.goto("http://127.0.0.1:8007/static/interaction-replay.html?scene=peer")
        await page.wait_for_function("window.interactionReplay?.view.canvas.dataset.ready==='true'")
        original = await page.evaluate("JSON.stringify(interactionReplay.data)")
        poses = []
        for index in range(1, 9):
            await page.get_by_role("button", name="Next step", exact=True).click()
            await page.wait_for_function("i=>interactionReplay.index===i && interactionReplay.view.lastState===interactionReplay.data.frames[i].state", arg=index)
            result = await page.evaluate("[...interactionReplay.view.presentedActions.values()]")
            poses.append(result)
            if index == 4:
                assert result[0]["pose"].startswith("give-") and result[1]["pose"].startswith("receive-"), result
                await page.wait_for_function("interactionReplay.view.presentedActions.get('yellow_01')?.pose==='give-2'")
                await page.screenshot(path="/tmp/citizen-giving.png")
            if index == 5:
                assert result[0]["pose"].startswith("help-"), result
            if index == 6:
                assert result[0]["pose"].startswith("offer-") and not result[1]["pose"].startswith("agree-"), result
            if index == 7:
                assert result[1]["pose"].startswith("decline-"), result
            if index == 8:
                assert result[0]["pose"].startswith("strike-") and result[1]["pose"].startswith("flinch-"), result
        assert await page.evaluate("JSON.stringify(interactionReplay.data)") == original
        await page.goto("http://127.0.0.1:8007/static/interaction-replay.html?scene=sanitation")
        await page.wait_for_function("window.interactionReplay?.view.canvas.dataset.ready==='true'")
        await page.get_by_role("button", name="Next step", exact=True).click()
        await page.wait_for_function("interactionReplay.index===1")
        assert await page.evaluate("interactionReplay.data.frames[1].state.agents[0].has_home") is False
        await page.get_by_role("button", name="Next step", exact=True).click()
        await page.wait_for_function("interactionReplay.view.presentedActions.get(interactionReplay.data.frames[2].state.agents[0].id)?.pose==='relieve-2'")
        await page.screenshot(path="/tmp/citizen-street-sanitation.png")
        waste_id = await page.evaluate("[...interactionReplay.view.sanitation.active.values()][0].wasteId")
        assert await page.evaluate("id=>interactionReplay.view.physicalEffects.compression(interactionReplay.view.lastState.objects.find(o=>o.id===id),performance.now())",waste_id) == 0
        await page.get_by_role("button", name="Next step", exact=True).click()
        await page.wait_for_function("interactionReplay.index===3 && interactionReplay.view.lastState===interactionReplay.data.frames[3].state")
        assert await page.evaluate("id=>interactionReplay.view.lastState.objects.some(o=>o.id===id)",waste_id)
        assert await page.evaluate("interactionReplay.view.sanitation.active.size") == 0
        await page.screenshot(path="/tmp/citizen-waste-left-behind.png")
        assert not errors, errors
        assert all(r["method"] == "GET" and "/static/" in r["url"] for r in requests)
        print(json.dumps({"passed": True, "peer_steps": 8, "sanitation_steps": 3, "browser_errors": errors, "model_calls": 0, "simulation_commands": 0}))
        await browser.close()


asyncio.run(asyncio.wait_for(main(), 60))
