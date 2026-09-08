import test from "node:test";
import assert from "node:assert/strict";
import {PhysicalEffects, citizenPose, wasteStamp, confirmedTrauma} from "../web/citizen-art.js";
const state = (objects, time=0, run="a") => ({world:{experiment_id:run,time},objects});
const pile = (metadata={}) => ({id:"w",kind:"waste",metadata});

test("blood requires explicit traumatic cause or authoritative earthquake casualty receipt", () => {
  const item={kind:"remains",metadata:{citizen_id:"a"}};
  assert.equal(confirmedTrauma(item,{agents:[{id:"a",alive:false}]}),false);
  assert.equal(confirmedTrauma(item,{agents:[{id:"a",death_cause:"earthquake"}]}),true);
  assert.equal(confirmedTrauma(item,{interventions:[{type:"earthquake",killed:["a"]}]}),true);
  assert.equal(confirmedTrauma(item,{interventions:[{type:"earthquake",injured:["a"],killed:["b"]}]}),false);
  assert.equal(confirmedTrauma({...item,metadata:{citizen_id:"a",death_cause:"health_failure"}},
    {interventions:[{type:"earthquake",killed:["a"]}]}),false);
});

test("confirmed contact compresses over time and persists across reload without replay", () => {
  const fx = new PhysicalEffects();
  fx.update(state([pile()]),0);
  const hit = pile({step_a:1, unrelated:200});
  const snapshot = state([hit],1), original=structuredClone(snapshot);
  fx.update(snapshot,100);
  assert.equal(fx.compression(hit,100),0);
  assert.equal(fx.compression(hit,250),.5);
  assert.equal(fx.compression(hit,500),1);
  fx.update(snapshot,700);
  assert.equal(fx.compression(hit,700),1);
  assert.equal(fx.compression(hit,100,true),1);
  const loaded = new PhysicalEffects(); loaded.update(snapshot,0);
  assert.equal(loaded.compression(hit,0),1);
  assert.equal(loaded.animating(0),false);
  assert.deepEqual(snapshot,original);
  assert.equal(wasteStamp(pile({step_a:null,step_b:"1"})),null);
  fx.update(state([],2),1000);
  assert.equal(fx.impacts.size,0);
});

test("new remains fall once, historical remains stay down, changing worlds clears effects", () => {
  const fx=new PhysicalEffects(), remains={id:"r",kind:"remains"};
  fx.update(state([]),0); fx.update(state([remains],1),100);
  assert.equal(fx.fall(remains,100),0);
  assert.equal(fx.fall(remains,500),3);
  assert.equal(fx.fall(remains,100,true),7);
  fx.update(state([remains],1),500);
  assert.equal(fx.fall(remains,1000),7);
  fx.update(state([remains],1,"b"),1100);
  assert.equal(fx.fall(remains,1100),7);
  assert.equal(fx.animating(1100),false);
});

test("body poses represent supplied actions and freeze voluntary motion while paused", () => {
  const agent={current_action:"walking",speech:"",alive:true};
  assert.equal(citizenPose(agent,{},0,false,false),"walk-0");
  assert.equal(citizenPose(agent,{},220,false,false),"walk-2");
  assert.equal(citizenPose(agent,{},220,true,false),"idle");
  assert.equal(citizenPose(agent,{phase:3,disgust:true},220,true,false),"contact-3");
  assert.equal(citizenPose(agent,{phase:3,disgust:true},220,true,true),"disgust");
  assert.equal(citizenPose({...agent,current_action:"reconsidering"},{},220,false,false),"idle");
  assert.equal(citizenPose({...agent,current_action:"idle",speech:"Hello"},{},220,false,false),"talk-1");
});
