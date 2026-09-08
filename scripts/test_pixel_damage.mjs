import test from 'node:test';
import assert from 'node:assert/strict';
import {PixelDamage,damageState,drawDamagedBuilding} from '../web/pixel-damage.js';

const item=(phase='intact',stamp)=>({id:'site',kind:'home',position:{x:500,y:400},metadata:{damage_state:phase,quake_damage:stamp}});
const state=(objects,run='a')=>({world:{experiment_id:run},objects});
test('only new confirmed structural changes trigger collapse or dust',()=>{
  const effects=new PixelDamage(),intact=item(),collapsed=item('collapsed','quake1');
  effects.update(state([intact]),0);effects.update(state([collapsed]),100);
  assert.equal(effects.progress(collapsed,100,false),0);
  effects.update(state([collapsed]),300);
  assert.ok(effects.progress(collapsed,300,false)>0);
  assert.equal(effects.bursts.get('site').start,100);
  assert.equal(effects.progress(collapsed,300,true),1);
  effects.update(state([collapsed]),2000);assert.equal(effects.bursts.size,0);
});
test('loading damage does not replay, repairs and world changes clear dust',()=>{
  const effects=new PixelDamage();effects.update(state([item('collapsed','old')]),0);
  assert.equal(effects.bursts.size,0);
  effects.update(state([item('major','new')]),10);assert.equal(effects.bursts.size,1);
  effects.update(state([item('rebuilding','new')]),20);assert.equal(effects.bursts.size,0);
  effects.update(state([item('major','again')]),30);effects.update(state([item('collapsed','other')],'b'),40);
  assert.equal(effects.bursts.size,0);
  effects.update(state([],'b'),50);assert.equal(effects.previous.size,0);
});
test('all five structural states produce distinct art without mutating inputs',()=>{
  const outputs=[];
  for(const phase of ['intact','damaged','major','collapsed','rebuilding']){
    const calls=[],c=new Proxy({}, {get:(_,name)=>(...args)=>calls.push([name,...args]),set:(_,name,value)=>{calls.push([name,value]);return true;}});
    const site=item(phase),before=JSON.stringify(site);drawDamagedBuilding(c,site);
    assert.equal(JSON.stringify(site),before);outputs.push(JSON.stringify(calls));
    if(phase==='major')assert.ok(calls.some(call=>call[0]==='clip'&&call[1]==='evenodd'));
    if(phase==='collapsed')assert.ok(!calls.some(call=>call[0]==='fillRect'&&call[2]<370),'no intact upper floors remain');
  }
  assert.equal(new Set(outputs).size,5);
  assert.equal(damageState({metadata:{quake_damage:'legacy'}}),'damaged');
});
