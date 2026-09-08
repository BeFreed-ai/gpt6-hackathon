import test from "node:test";
import assert from "node:assert/strict";
import {CitizenInteractions} from "../web/citizen-interactions.js";
const a={id:"a",alive:true,position:{x:100,y:100}},b={id:"b",alive:true,position:{x:130,y:100}},c={id:"c",alive:true,position:{x:200,y:100}};
const snapshot=(events=[],time=1,run="test",agents=[a,b,c])=>({world:{experiment_id:run,time},agents,events});
const event=(type="give",payload={})=>({id:type,type,world_time:1,actor_id:"a",target_ids:["b"],payload});

test("only confirmed participants animate, receipts are deduplicated and snapshots stay unchanged",()=>{
  const fx=new CitizenInteractions();fx.update(snapshot(),0);
  const next=snapshot([event()]),original=structuredClone(next);fx.update(next,100);
  assert.equal(fx.pose(a,550).pose,"give-2");
  assert.equal(fx.pose(b,550).pose,"receive-2");
  assert.equal(fx.pose(b,550).facing,-1);
  assert.equal(fx.pose(c,550),null);
  fx.update(next,600);assert.equal(fx.active.get("give").start,100);
  fx.update(next,2000);assert.equal(fx.pose(a,2000),null);
  assert.deepEqual(next,original);
});
test("speech and offers do not invent an accepting or speaking recipient",()=>{
  for(const type of ["speech","offer","help"]){
    const fx=new CitizenInteractions();fx.update(snapshot(),0);fx.update(snapshot([event(type)]),100);
    assert.equal(fx.pose(b,500).pose,null);
  }
  const fx=new CitizenInteractions();fx.update(snapshot(),0);fx.update(snapshot([event("agreement",{status:"rejected"})]),100);
  assert.equal(fx.pose(a,500,true).pose,"decline-2");
});
test("saved history, stale events, death and world changes cannot replay social actions",()=>{
  const fx=new CitizenInteractions();fx.update(snapshot([event()]),0);assert.equal(fx.active.size,0);
  fx.update(snapshot([event("help")],30),100);assert.equal(fx.active.size,0);
  fx.update(snapshot([event("attack")]),200);assert.equal(fx.pose(b,300).pose,"flinch-0");
  fx.update(snapshot([event("attack")],1,"test",[a,{...b,alive:false}]),400);assert.equal(fx.active.size,0);
  fx.update(snapshot([event("speech")],1,"other"),500);assert.equal(fx.active.size,0);
});
