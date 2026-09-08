"""Read-only pixel city checks; fixtures never send actions to the live world."""
import asyncio
import json
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto("http://127.0.0.1:8007")
        await page.locator('#world-canvas[data-ready="true"]').wait_for()
        await page.evaluate("async()=>{window.r=(await import('/static/app.js')).renderer}")
        initial = await (await page.request.get('http://127.0.0.1:8007/api/state')).json()
        assert initial['world']['paused']
        assert await page.evaluate("r.constructor.name") == 'PixelCity'
        assert await page.evaluate("r.positions.size") == 100
        assert await page.evaluate("Boolean(r.context)")
        assert await page.evaluate("(()=>{const p=r.context.point([-122.419,37.77]);return r.context.onLand(p.x,p.y)})()")
        assert await page.evaluate("(()=>{const p=r.context.point([-122.52,37.77]);return !r.context.onLand(p.x,p.y)})()")
        assert await page.evaluate("r.zoom<.4")
        await page.screenshot(path='/tmp/sf-pixel-overview.png')
        # Test the inset's former rectangle at medium zoom, not only the overview.
        await page.evaluate("()=>{r.focus={x:560,y:330};r.setZoom(.65)}")
        await page.wait_for_function("r.canvas.dataset.zoom==='0.65'")
        await page.locator('#world-canvas').screenshot(path='/tmp/sf-pixel-continuous-city.png')
        assert await page.evaluate('''()=>{
          const c=r.ground.getContext('2d'),source=r.context.canvas.getContext('2d');
          // Undisturbed edge pixels are an exact crop of the outer-city ground.
          return [80,160,240,320,440,560,700].every(y=>{
            const a=c.getImageData(0,y,1,1).data,b=source.getImageData(1250,550+Math.floor(y/2),1,1).data;
            return a.every((value,i)=>value===b[i]);
          });
        }''')
        assert await page.evaluate("agents=>agents.every(a=>{const p=r.positions.get(a.id);return p.x===a.position.x&&p.y===a.position.y})",initial['agents'])
        box=await page.locator('#world-canvas').bounding_box()
        await page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
        zoom=await page.evaluate('r.zoom')
        await page.mouse.wheel(0,-180)
        await page.wait_for_function('z=>r.zoom>z',arg=zoom)
        focus=await page.evaluate('({...r.focus})')
        await page.mouse.down()
        await page.mouse.move(box['x']+box['width']/2+80,box['y']+box['height']/2,steps=8)
        await page.mouse.up()
        assert await page.evaluate('x=>r.focus.x!==x',focus['x'])
        await page.locator('#map-mission').click()
        await page.wait_for_function("r.canvas.dataset.district==='mission'")
        await page.screenshot(path='/tmp/sf-pixel-mission.png')
        await page.locator('#map-soma').click()
        await page.wait_for_function("r.canvas.dataset.district==='soma'")
        await page.screenshot(path='/tmp/sf-pixel-soma.png')
        await page.locator('#map-mission_bay').click()
        await page.wait_for_function("r.canvas.dataset.district==='mission_bay'")
        await page.screenshot(path='/tmp/sf-pixel-mission-bay.png')
        geography=await page.evaluate('''async()=>{
          const {cityPlaces,geographicPoint}=await import('/static/pixel-landmarks.js');
          const s=r.lastState,places=cityPlaces(s);
          return places.filter(p=>p.scenery&&p.coordinates).every(p=>{
            const expected=geographicPoint(p.coordinates,s.terrain.map);
            return p.position.x===expected.x&&p.position.y===expected.y;
          })&&s.objects.filter(o=>o.metadata?.footprint_cell).every(o=>places.find(p=>p.id===o.id)===o);
        }''')
        assert geography
        openai = next(o for o in initial['objects'] if o['name']=='OpenAI')
        await page.locator('#map-places').select_option(openai['id'])
        await page.wait_for_function("id=>r.displayedPlaces.includes(id)",arg=openai['id'])
        await page.screenshot(path='/tmp/sf-pixel-openai.png')
        await page.locator('#map-residents').click()
        await page.wait_for_function("document.querySelector('#citizens-visible').textContent.startsWith('100 in view')")
        person = initial['agents'][0]
        await page.evaluate('a=>r.focusCitizen(a)',person)
        point=await page.evaluate("a=>{const p=r.screenPoint(a.position),b=r.canvas.getBoundingClientRect();return {x:p.x+b.left,y:p.y+b.top-40}}",person)
        await page.mouse.click(point['x'],point['y'])
        await page.wait_for_function("name=>document.querySelector('#agent-name').textContent===name",arg=person['name'])
        await page.locator('#visit-home').click()
        await page.wait_for_function("r.focusedPlace===r.selectedPlaces.home")
        await page.locator('#map-waste').click()
        await page.wait_for_function("r.zoom===5")
        await page.screenshot(path='/tmp/sf-pixel-waste.png')
        # Render controlled presentation fixtures offscreen, not fake live decisions.
        fixtures=await page.evaluate('''async state=>{
          const {PixelCity}=await import('/static/pixel-city.js');
          const c=document.createElement('canvas'); c.style.cssText='width:800px;height:600px';
          document.body.append(c); const v=new PixelCity(c);v.resize();
          const types=['going to OpenAI to work','work at OpenAI','clean at Street Waste','eat at Market'];
          const f=structuredClone(state);f.world.paused=false;
          f.agents=f.agents.slice(0,4).map((a,i)=>({...a,current_action:types[i],speech:null,reaction:'',is_thinking:false}));
          v.draw(f,null,null);const kinds=f.agents.map(a=>v.presentedActions.get(a.id).kind);
          c.remove();return kinds;
        }''',initial)
        assert fixtures == ['walking','working','cleaning','eating']
        await page.set_viewport_size({'width':390,'height':844})
        await page.screenshot(path='/tmp/sf-pixel-mobile.png',full_page=True)
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        final=await (await page.request.get('http://127.0.0.1:8007/api/state')).json()
        assert final['world']==initial['world']
        assert final['agents']==initial['agents']
        assert final['objects']==initial['objects']
        assert final['runtime']['requests']==initial['runtime']['requests']
        assert not errors, errors
        print(json.dumps({'passed':True,'citizens':100,'actions':fixtures,'model_calls':0,'browser_errors':errors}))
        await browser.close()

asyncio.run(asyncio.wait_for(main(),90))
