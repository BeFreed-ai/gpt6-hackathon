import test from 'node:test';
import assert from 'node:assert/strict';
import {StreetSanitation} from '../web/street-sanitation.js';
const person={id:'a',alive:true,has_home:false};
const waste={id:'w',kind:'waste',position:{x:100,y:100},metadata:{created_at:1}};
const event={id:'event',type:'waste',actor_id:'a',world_time:1,position:waste.position,payload:{object_id:'w'}};
const state=(events=[],objects=[],run='test')=>({world:{experiment_id:run,time:1},agents:[person],events,objects});

test('a recorded bodily event produces a squat and growing persistent waste, without deciding a follow-up',()=>{
 const fx=new StreetSanitation();fx.update(state(),0);
 const next=state([event],[waste]),original=structuredClone(next);fx.update(next,100);
 assert.equal(fx.pose(person,900),'relieve-2');assert.equal(fx.pose(person,900,true),'relieve-2');
 assert.ok(fx.growth(waste,100)<fx.growth(waste,700));
 fx.update(next,500);assert.equal(fx.active.get('a').start,100);
 fx.update(next,2600);assert.equal(fx.pose(person,2600),null);assert.equal(fx.growth(waste,2600),1);
 assert.deepEqual(next,original);
});
test('poverty, housing status, player-placed waste and initial saves do not invent defecation',()=>{
 const fx=new StreetSanitation();fx.update(state([event],[waste]),0);assert.equal(fx.active.size,0);
 fx.update(state([{...event,id:'player',actor_id:null}],[waste]),100);assert.equal(fx.active.size,0);
 fx.update(state([{...event,id:'new'}],[waste]),200);assert.equal(fx.active.size,1);
 fx.update(state([event],[]),300);assert.equal(fx.active.size,0);
 fx.update(state([event],[waste],'other'),400);assert.equal(fx.active.size,0);
});
