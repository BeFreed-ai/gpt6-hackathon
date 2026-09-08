import test from 'node:test';
import assert from 'node:assert/strict';
import {EarthquakeReactions,disasterEvents} from '../web/earthquake-reactions.js';

test('all delivered living citizens show a reflex, not a scripted decision',()=>{
  const r=new EarthquakeReactions();
  const agents=Array.from({length:100},(_,i)=>({id:`a${i}`,alive:true,current_action:'reconsidering'}));
  const state={world:{experiment_id:'test',time:1},events:[]};
  r.update(state,0);
  state.events.push({id:'quake',type:'earthquake',world_time:1,payload:{delivered_to:agents.map(a=>a.id)}});
  r.update(state,100);
  assert.equal(agents.filter(a=>r.pose(a)==='flinch-0').length,100);
  assert.equal(r.pose({...agents[0],alive:false}),null);
  assert.equal(r.pose({...agents[0],id:'unaware'}),null);
  assert.equal(r.pose({...agents[0],current_action:'going to shelter'}),null);
  state.world.time=9;r.update(state,200);
  assert.equal(r.pose(agents[0]),null);
});

test('reload does not replay flashing and a new world clears the reaction',()=>{
  const r=new EarthquakeReactions();
  r.update({world:{experiment_id:'one',time:1},events:[{id:'e',type:'earthquake',world_time:1,target_ids:['a']}]},300);
  assert.equal(r.start,-Infinity);
  assert.equal(r.pose({id:'a',alive:true,current_action:'reconsidering'}),'flinch-0');
  r.update({world:{experiment_id:'two',time:0},events:[]},400);
  assert.equal(r.pose({id:'a',alive:true,current_action:'reconsidering'}),null);
});

test('a mass casualty event cannot hide the quake behind the 35-event feed limit',()=>{
  const r=new EarthquakeReactions();
  const state={world:{experiment_id:'city',time:1},events:[],interventions:[]};
  r.update(state,0);
  state.interventions.push({type:'earthquake',event_id:'quake',world_time:1,delivered_to:['a']});
  state.events=Array.from({length:35},(_,i)=>({id:`injury${i}`,type:'injury',world_time:1}));
  r.update(state,100);
  assert.equal(r.pose({id:'a',alive:true,current_action:'reconsidering'}),'flinch-0');
  assert.equal(disasterEvents(state).filter(e=>e.type==='earthquake').length,1);
  state.events.push({id:'quake',type:'earthquake',world_time:1,target_ids:['a']});
  assert.equal(disasterEvents(state).filter(e=>e.type==='earthquake').length,1);
});
