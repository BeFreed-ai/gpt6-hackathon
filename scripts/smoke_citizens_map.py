"""Read-only preview checks; the one placement request is intercepted, never sent."""

import asyncio
import json

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--enable-unsafe-swiftshader"])
        page = await browser.new_page(
            viewport={"width": 1440, "height": 1000}, base_url="http://127.0.0.1:8007"
        )
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto("http://127.0.0.1:8007")
        await page.locator('#geo-map[data-ready="true"]').wait_for(timeout=45000)
        await page.evaluate("async () => {window.r = (await import('/static/app.js')).renderer;}")
        await page.wait_for_function("() => !r.map.isMoving() && r.positions.size === 100")
        initial = await (await page.request.get("/api/state")).json()
        assert initial["world"]["paused"]
        assert "100 / 100" in await page.locator("#citizens-visible").inner_text()
        result = await page.evaluate("""() => {
          const points = [...r.positions].map(([id,p]) => ({id, ...r.screenPoint(p)}));
          let minDistance = Infinity;
          for (let i=0;i<points.length;i++) for (let j=i+1;j<points.length;j++) {
            const distance = Math.hypot(points[i].x-points[j].x, points[i].y-points[j].y);
            minDistance = Math.min(minDistance, distance);
          }
          return {minDistance, sprites: JSON.parse(r.sourceData.get('citizens')).features.length};
        }""")
        assert result["minDistance"] > 0 and result["sprites"] == 100
        assert len({(a["position"]["x"], a["position"]["y"]) for a in initial["agents"]}) == 100
        for zoom in (13, 16.5, 18):
            await page.evaluate("zoom => {r.map.jumpTo({zoom}); r.cameraDirty=true;}", zoom)
            await page.wait_for_function("() => !r.cameraDirty")
            assert await page.evaluate("""agents => agents.every(a => {
              const p = r.positions.get(a.id);
              return p.x === a.position.x && p.y === a.position.y;
            })""", initial["agents"])
        await page.locator('#map-residents').click()
        await page.wait_for_function("() => !r.map.isMoving() && !r.cameraDirty")
        await page.screenshot(path="/tmp/sf-100-citizens.png")
        citizens = initial["agents"][:3]
        for person in citizens:
            await page.evaluate("""pos => {
              const p = r.screenPoint(pos);
              r.map.jumpTo({center:r.map.unproject(p),zoom:17,pitch:0});
              r.cameraDirty=true;
            }""", person["position"])
            await page.wait_for_function("() => !r.cameraDirty")
            point = await page.evaluate(
                """id => {
              const p=r.screenPoint(r.positions.get(id));
              const b=document.querySelector('#canvas-wrap').getBoundingClientRect();
              return {x:p.x+b.left,y:p.y+b.top};
            }""",
                person["id"],
            )
            await page.mouse.click(point["x"], point["y"])
            await page.wait_for_function(
                "name => document.querySelector('#agent-name').textContent === name",
                arg=person["name"],
            )
        intercepted = []

        async def intercept(route):
            intercepted.append(route.request.post_data_json)
            await route.fulfill(status=200, json={"accepted": True, "killed": [], "injured": []})

        await page.route("**/api/intervene", intercept)
        await page.locator('[data-tool="waste"]').click()
        await page.mouse.click(point["x"], point["y"])
        await page.wait_for_function(
            "() => !document.querySelector('[data-tool=waste]').classList.contains('active')"
        )
        assert intercepted[0]["position"] == citizens[-1]["position"]
        final = await (await page.request.get("/api/state")).json()
        assert final["runtime"]["requests"] == initial["runtime"]["requests"]
        assert final["world"]["time"] == initial["world"]["time"]
        assert final["objects"] == initial["objects"]
        assert not errors, errors
        print(
            json.dumps(
                {
                    "passed": True,
                    **result,
                    "individual_clicks": len(citizens),
                    "placement_snapped_to_real_feet": True,
                    "model_calls": 0,
                }
            )
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), 90))
