"""Mutating browser smoke for a disposable LOCAL-provider server on port 8008 only."""

import asyncio
import json

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--enable-unsafe-swiftshader"])
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto("http://127.0.0.1:8008")
        await page.locator('#geo-map[data-ready="true"]').wait_for(timeout=45000)
        await page.evaluate(
            "async () => { window.smokeRenderer = (await import('/static/app.js')).renderer; }"
        )
        initial = await (await page.request.get("http://127.0.0.1:8008/api/state")).json()
        assert initial["world"]["paused"] and initial["stats"]["brain_mode"] == "local"
        assert len(initial["agents"]) == 100
        living_before = sum(a["alive"] for a in initial["agents"])
        remains_before = sum(o["kind"] == "remains" for o in initial["objects"])
        site = next(
            o
            for o in initial["objects"]
            if o["kind"] == "home" and not o["metadata"].get("quake_damage")
        )
        await page.locator("#map-residents").click()
        await page.wait_for_function(
            "() => !window.smokeRenderer.map.isMoving() && window.smokeRenderer.effectsInitialized"
        )
        await page.evaluate(
            """async site => {
          const {renderer:r} = await import('/static/app.js');
          const {toLngLat} = await import('/static/geo-world.js');
          r.map.jumpTo({center: toLngLat(site.position, r.bounds),
            zoom: 17, pitch: 55, bearing: -18});
        }""",
            site,
        )
        await page.screenshot(path="/tmp/sf-building-before.png")
        await page.evaluate("""() => {
          window.quakeDustSeen = false;
          new MutationObserver(records => {
            for (const record of records) for (const node of record.addedNodes) {
              if (node.classList?.contains('quake-dust')) window.quakeDustSeen = true;
            }
          }).observe(document.querySelector('#geo-map'), {childList:true, subtree:true});
        }""")
        response = await page.request.post(
            "http://127.0.0.1:8008/api/intervene",
            data={
                "type": "earthquake",
                "position": site["position"],
            },
        )
        assert response.ok, await response.text()
        receipt = await response.json()
        await page.wait_for_function(
            """eventId => {
          const r = window.smokeRenderer;
          const sites = JSON.parse(r.sourceData.get('sites')).features;
          return r.seenEffects.has(eventId) && sites.some(f => f.properties.damaged);
        }""",
            arg=receipt["event_id"],
        )
        await page.wait_for_function("""() => {
          const r = window.smokeRenderer;
          return performance.now() - r.collapseStarted > 2400;
        }""")
        result = await page.evaluate("""async () => {
          const {renderer:r} = await import('/static/app.js');
          const people = JSON.parse(r.sourceData.get('citizens')).features;
          const sites = JSON.parse(r.sourceData.get('sites')).features;
          const damaged = sites.find(f => f.properties.damaged);
          const meshes = JSON.parse(r.sourceData.get('building-meshes')).features;
          return {
            damaged: sites.filter(f => f.properties.damaged).length,
            reacting: people.filter(f => f.properties.public_label).length,
            damageLayer: Boolean(r.map.getLayer('damage-labels')),
            dust: window.quakeDustSeen,
            rubbleMeshes: meshes.filter(f => f.properties.part === 'rubble').length,
            collapsedMeshes: meshes.filter(f => f.properties.state === 'collapsed').length,
            meshLayer: r.map.getLayer('simulation-buildings-3d').type,
            fallenCitizens: sites.filter(f => f.properties.kind === 'remains').length,
          };
        }""")
        print(
            json.dumps(
                {
                    "phase": "rendered",
                    "living_before": living_before,
                    "killed": len(receipt["killed"]),
                    "browser_errors": errors,
                    **result,
                }
            )
        )
        assert result["damaged"] > 0 and result["reacting"] == living_before - len(
            receipt["killed"]
        )
        assert result["damageLayer"] and result["dust"]
        assert result["rubbleMeshes"] > 0 and result["collapsedMeshes"] > 0
        assert result["meshLayer"] == "fill-extrusion"
        assert result["fallenCitizens"] == remains_before + len(receipt["killed"])
        await page.wait_for_function("() => window.smokeRenderer.map.areTilesLoaded()")
        await page.screenshot(path="/tmp/sf-earthquake-damage.png")
        await page.reload()
        await page.locator('#geo-map[data-ready="true"]').wait_for(timeout=45000)
        await page.evaluate(
            "async () => { window.smokeRenderer = (await import('/static/app.js')).renderer; }"
        )
        await page.wait_for_function("""() => {
          const r = window.smokeRenderer;
          if (!r?.sourceData) return false;
          const data = JSON.parse(r.sourceData.get('building-meshes') || '{"features":[]}');
          return r.ready && data.features.some(f => f.properties.state === 'collapsed');
        }""")
        assert await page.locator(".quake-dust").count() == 0
        await page.locator("#map-offline").click()
        await page.screenshot(path="/tmp/sf-earthquake-offline.png")
        final = await (await page.request.get("http://127.0.0.1:8008/api/state")).json()
        assert final["runtime"]["requests"] == 0
        assert not errors, errors
        print(
            json.dumps(
                {
                    "passed": True,
                    **result,
                    "killed": len(receipt["killed"]),
                    "model_calls": 0,
                    "errors": errors,
                }
            )
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), 90))
