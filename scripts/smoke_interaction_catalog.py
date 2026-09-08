"""Browse every recorded step; prohibit requests beyond local static GETs."""
import asyncio
import json

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1400, "height": 1050})
        errors, blocked = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def static_only(route):
            request = route.request
            if request.method != "GET" or not request.url.startswith("http://127.0.0.1:8007/static/"):
                blocked.append(request.url)
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", static_only)
        await page.goto("http://127.0.0.1:8007/static/interaction-replay.html")
        await page.wait_for_function("window.interactionReplay?.view.canvas.dataset.ready==='true'")
        original = await page.evaluate("JSON.stringify(interactionReplay.catalog)")
        cases = await page.evaluate("interactionReplay.catalog.cases.map(c=>({id:c.id,frames:c.frames.length}))")
        checked = 0
        for case in cases:
            await page.locator(f'button[data-case="{case["id"]}"]').click()
            for index in range(case["frames"]):
                await page.evaluate("i=>interactionReplay.show(i)", index)
                await page.wait_for_function("i=>interactionReplay.view.lastState===interactionReplay.data.frames[i].state", arg=index)
                assert await page.evaluate("""() => {
                    const v=interactionReplay.view, order=v.drawOrder;
                    const first=order.findIndex(id=>id.startsWith('citizen:'));
                    return first>=0 && !order.slice(first).some(id=>id.startsWith('facility:'));
                }"""), case
                checked += 1
        assert await page.evaluate("JSON.stringify(interactionReplay.catalog)") == original
        await page.locator('button[data-case="street_accident"]').click()
        await page.get_by_role("button", name="Next step", exact=True).click()
        await page.wait_for_function("interactionReplay.view.presentedActions.get('yellow_01')?.pose==='relieve-2'")
        # Freeze and inspect the actual mid-squat; verify the pile has visible brown pixels.
        await page.evaluate("interactionReplay.view.setPaused(true)")
        assert await page.evaluate("""() => {
          const v=interactionReplay.view,o=v.lastState.objects.find(o=>o.kind==='waste'),p=v.project(o.position);
          const dpr=devicePixelRatio, a=v.ctx.getImageData((p.x-15)*dpr,(p.y-15)*dpr,30*dpr,30*dpr).data;
          let brown=0;for(let i=0;i<a.length;i+=4)if(a[i]>70&&a[i]<210&&a[i]>a[i+1]*1.2&&a[i+1]>a[i+2]*1.2)brown++;
          return brown>30;
        }""")
        await page.screenshot(path="/tmp/interaction-catalog-sanitation.png", full_page=True)
        await page.locator('button[data-case="fatal_collapse"]').click()
        await page.get_by_role("button", name="Next step", exact=True).click()
        await page.screenshot(path="/tmp/interaction-catalog-collapse.png", full_page=True)
        await page.locator('button[data-case="move"]').click()
        await page.get_by_role("button", name="▶ Play", exact=True).click()
        await page.wait_for_function("interactionReplay.index===1")
        await page.get_by_role("button", name="Ⅱ Pause", exact=True).click()
        frozen = await page.evaluate("({i:interactionReplay.index,pose:interactionReplay.view.presentedActions.get('yellow_01').pose})")
        await page.wait_for_timeout(450)
        assert await page.evaluate("interactionReplay.index") == frozen["i"]
        assert await page.evaluate("interactionReplay.view.presentedActions.get('yellow_01').pose") == frozen["pose"]
        await page.locator("#search").fill("waste")
        assert await page.locator("button.case").count() == 1
        assert not errors and not blocked, (errors, blocked)
        print(json.dumps({"passed": True, "scenes": len(cases), "frames": checked, "errors": errors,
                          "non_static_requests": blocked, "model_calls": 0}))
        await browser.close()


asyncio.run(asyncio.wait_for(main(), 90))
