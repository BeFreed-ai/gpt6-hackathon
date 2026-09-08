"""Read-only browser checks. Never resume the simulation or make model requests."""

import asyncio
import json
import os

from playwright.async_api import async_playwright

CAMERA_SETTLED = """async () => {
    const {renderer:r} = await import('/static/app.js');
    return !r.map.isMoving() && r.map.areTilesLoaded();
}"""


async def main():
    base_url = os.environ.get("SOCIETY_PREVIEW_URL", "http://127.0.0.1:8006")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--enable-unsafe-swiftshader"])
        page = await browser.new_page(
            viewport={"width": 1440, "height": 1000}, base_url=base_url
        )
        page.set_default_timeout(15000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(base_url)
        await page.locator('#geo-map[data-ready="true"]').wait_for(timeout=45000)
        print("Map loaded", flush=True)
        initial = await (await page.request.get("/api/state")).json()
        assert initial["world"]["paused"], "Keep paid simulation paused during map tests"
        await page.wait_for_function(CAMERA_SETTLED)
        await page.screenshot(path="/tmp/sf-geographic-overview.png")
        print("Overview captured", flush=True)
        canvas = page.locator(".maplibregl-canvas")
        box = await canvas.bounding_box()
        await page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        before = float(await page.locator("#geo-map").get_attribute("data-zoom"))
        await page.mouse.wheel(0, -450)
        await page.wait_for_function(
            "before => Number(document.querySelector('#geo-map').dataset.zoom) > before + 0.2",
            arg=before,
        )
        await page.locator("#map-residents").click()
        await page.wait_for_function(CAMERA_SETTLED)
        citizen = initial["agents"][0]

        async def click_citizen():
            point = await page.evaluate(
                "async pos => { const {renderer:r} = await import('/static/app.js');"
                "return r.screenPoint(pos); }",
                citizen["position"],
            )
            await page.mouse.click(box["x"] + point["x"], box["y"] + point["y"])
            await page.locator("#agent-inspector:not(.hidden)").wait_for()
            assert await page.locator("#agent-name").inner_text() == citizen["name"]

        await click_citizen()
        print("Zoom and 2D selection passed", flush=True)
        await page.locator("#map-3d").click()
        await page.wait_for_function(
            "Number(document.querySelector('#geo-map').dataset.pitch) > 50"
        )
        await page.wait_for_function(CAMERA_SETTLED)
        await page.screenshot(path="/tmp/sf-geographic-3d.png")
        await click_citizen()
        print("3D selection passed", flush=True)
        # Intercept interventions: tests must not mutate the saved world.
        interventions = []

        async def intercept(route):
            interventions.append(route.request.post_data_json)
            await route.fulfill(json={"ok": True})

        await page.route("**/api/intervene", intercept)
        await page.locator('[data-tool="kill"]').click()
        await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await page.mouse.down()
        await page.mouse.move(
            box["x"] + box["width"] / 2 + 110, box["y"] + box["height"] / 2 + 60, steps=10
        )
        await page.mouse.up()
        assert not interventions, "Dragging an armed tool must not trigger an intervention"
        await page.keyboard.press("Escape")
        # A round trip must remain precise at nonzero pitch and bearing.
        error = await page.evaluate(
            """async pos => {
          const {renderer:r} = await import('/static/app.js');
          const screen = r.screenPoint(pos), world = r.worldPoint(screen.x, screen.y);
          return Math.hypot(world.x-pos.x, world.y-pos.y);
        }""",
            citizen["position"],
        )
        assert error < 0.001, error
        await page.locator("#map-pixel").click()
        await page.wait_for_function(
            "document.querySelector('.pixel-map') !== null && "
            "Number(document.querySelector('#geo-map').dataset.pitch) < 1"
        )
        await page.screenshot(path="/tmp/sf-geographic-pixel.png")
        print("Drag safety, projection and pixel mode passed", flush=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.locator("#zoom-fit").click()
        await page.screenshot(path="/tmp/sf-geographic-mobile.png", full_page=True)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.locator("#map-offline").click()
        assert not await page.locator("#geo-map").is_visible()
        assert await page.locator("#world-canvas").is_visible()
        final = await (await page.request.get("/api/state")).json()
        assert final["runtime"]["requests"] == initial["runtime"]["requests"]
        assert final["world"]["paused"]
        assert not errors, errors
        print(
            json.dumps(
                {
                    "passed": True,
                    "projection_error": error,
                    "model_calls": 0,
                    "browser_errors": errors,
                }
            )
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=100))
