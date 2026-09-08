"""Actual-engine earthquake fixtures in a temporary DB; live preview stays untouched."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import ActionIntent, ActionType, Vec2
from app.store import EventStore
from app.world import World
from playwright.async_api import async_playwright


async def main():
    with tempfile.TemporaryDirectory(prefix='sf-pixel-quake-') as directory:
        store=EventStore(str(Path(directory)/'fixture.db'))
        try:
            city=World(store,agent_count=100,scenario='sf');city.paused=True
            sites=[o for o in city.objects.values() if o.kind=='home'][:3]
            for site,x in zip(sites,[500,630,710]):
                site.position=Vec2(x=x,y=400);site.metadata['entrance']={'x':x,'y':420}
            for agent in city.agents.values():agent.position=Vec2(x=1390,y=800)
            victim,repairer=list(city.agents.values())[:2];victim.position=sites[0].position.model_copy()
            before=city.snapshot('local')
            receipt=city.intervene('earthquake',sites[0].position,None)
            after=city.snapshot('local')
            assert len(receipt['delivered_to'])==100 and victim.id in receipt['killed']
            phases=[o.metadata['damage_state'] for o in sites]
            assert phases==['collapsed','major','damaged'],phases
            repairer.position=Vec2(**sites[0].metadata['entrance'])
            repairer.credits=1000
            for step in range(4):
                assert city.urban.execute(repairer,ActionIntent(action=ActionType.REPAIR,target_id=sites[0].id))
                city.time=repairer.activity.ends_at;city.urban.tick()
                if step==0:rebuilding=city.snapshot('local')
            repaired=city.snapshot('local');assert sites[0].metadata['damage_state']=='intact'
            async with async_playwright() as p:
                browser=await p.chromium.launch();page=await browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                await page.goto('http://127.0.0.1:8007')
                await page.locator('#world-canvas[data-ready="true"]').wait_for()
                live_before=await (await page.request.get('http://127.0.0.1:8007/api/state')).json()
                result=await page.evaluate('''async fixture=>{
                  const {PixelCity}=await import('/static/pixel-city.js');
                  const {drawDamagedBuilding}=await import('/static/pixel-damage.js');
                  const holder=document.createElement('div');holder.style.cssText='position:fixed;inset:0;z-index:99999;background:#e8dabb;padding:28px';document.body.append(holder);
                  const title=document.createElement('h2');title.textContent='EARTHQUAKE · ACTUAL ENGINE TEST · NOT THE LIVE CITY';holder.append(title);
                  const canvas=document.createElement('canvas');canvas.width=1250;canvas.height=500;canvas.style.width='1250px';holder.append(canvas);
                  const c=canvas.getContext('2d');c.imageSmoothingEnabled=false;
                  const rows=[fixture.before.objects.find(o=>o.id===fixture.ids[0]),fixture.after.objects.find(o=>o.id===fixture.ids[2]),fixture.after.objects.find(o=>o.id===fixture.ids[1]),fixture.after.objects.find(o=>o.id===fixture.ids[0]),fixture.rebuilding.objects.find(o=>o.id===fixture.ids[0]),fixture.repaired.objects.find(o=>o.id===fixture.ids[0])];
                  const names=['INTACT','CRACKED','MAJOR DAMAGE','COLLAPSED','REBUILDING','REPAIRED'];
                  rows.forEach((o,i)=>{c.save();c.translate(100+i*205,350);c.scale(5,5);drawDamagedBuilding(c,{...o,position:{x:0,y:0}});c.restore();c.font='15px monospace';c.textAlign='center';c.fillStyle='#4d574a';c.fillText(names[i],100+i*205,455);});
                  const hidden=document.createElement('canvas');hidden.style.cssText='width:800px;height:600px';holder.append(hidden);
                  const r=new PixelCity(hidden);r.resize();r.lastFrame=-100;r.draw(fixture.before,null,null);r.lastFrame=-100;r.draw(fixture.after,null,null);
                  const dust=r.damage.bursts.size;const dead=!r.positions.has(fixture.victim);
                  const reacting=[...r.presentedActions.values()].filter(a=>a.kind==='startled').length;
                  const reload=new PixelCity(hidden);reload.resize();reload.lastFrame=-100;reload.draw(fixture.after,null,null);
                  hidden.remove();return {dust,dead,reacting,reloadDust:reload.damage.bursts.size,states:rows.map(o=>o.structure.state)};
                }''',{'before':before,'after':after,'rebuilding':rebuilding,'repaired':repaired,'ids':[o.id for o in sites],'victim':victim.id})
                assert result['dust']>0 and result['dead'] and result['reloadDust']==0,result
                assert result['reacting']==99,result
                await page.screenshot(path='/tmp/sf-pixel-damage-stages.png')
                live_after=await (await page.request.get('http://127.0.0.1:8007/api/state')).json()
                for key in ['world','agents','objects']:assert live_before[key]==live_after[key]
                assert live_before['runtime']['requests']==live_after['runtime']['requests']
                assert not errors,errors
                await browser.close();print(json.dumps({'passed':True,'delivered':100,'killed':len(receipt['killed']),'model_calls':0,**result}))
        finally:store.close()


if __name__=='__main__':asyncio.run(asyncio.wait_for(main(),90))
