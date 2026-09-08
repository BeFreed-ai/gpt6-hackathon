// A flat inspection stage for recorded engine snapshots. No simulation writes.
import {drawCitizen, citizenPose, PhysicalEffects, drawImpact, confirmedTrauma} from './citizen-art.js';
import {CitizenInteractions} from './citizen-interactions.js';
import {StreetSanitation} from './street-sanitation.js';
import {WasteReactions, drawWaste, drawWasteSplash} from './waste-reactions.js';

export class InteractionStage {
  constructor(canvas) {
    this.canvas=canvas; this.ctx=canvas.getContext('2d'); this.focus={x:730,y:385}; this.zoom=4;
    this.interactions=new CitizenInteractions(); this.sanitation=new StreetSanitation();
    this.reactions=new WasteReactions(); this.physicalEffects=new PhysicalEffects();
    this.presentedActions=new Map(); this.drawOrder=[]; this.lastState=null;
    this.reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.paused=false; this.started=performance.now(); this.heldTime=this.started;
  }
  resize() {
    const box=this.canvas.getBoundingClientRect(), dpr=devicePixelRatio||1;
    this.width=box.width; this.height=box.height;
    this.canvas.width=Math.round(box.width*dpr); this.canvas.height=Math.round(box.height*dpr);
    this.ctx.setTransform(dpr,0,0,dpr,0,0); this.ctx.imageSmoothingEnabled=false;
  }
  setZoom(zoom) { this.zoom=Math.max(2,Math.min(6,zoom)); }
  project(p) { return {x:this.width/2+(p.x-this.focus.x)*this.zoom,y:this.height*.62+(p.y-this.focus.y)*this.zoom}; }
  prime(previous) {
    this.previous=previous;
    this.paused=false; this.offset=0; this.started=performance.now(); this.heldTime=this.started;
    for (const effect of [this.interactions,this.sanitation,this.reactions,this.physicalEffects]) {
      effect.run=null; effect.update(previous,this.started);
    }
  }
  setPaused(value) {
    if (value===this.paused) return;
    if (value) this.heldTime=performance.now()-this.offset;
    else this.offset=performance.now()-this.heldTime;
    this.paused=value;
  }
  get offset() { return this._offset||0; }
  set offset(value) { this._offset=value; }
  label(text,x,y,color='#33433f',size=12) {
    const c=this.ctx; c.font=`600 ${size}px system-ui`; c.textAlign='center';
    const width=c.measureText(text).width+12;
    c.fillStyle='#faf6e8ed'; c.fillRect(x-width/2,y-size,width,size+7);
    c.fillStyle=color; c.fillText(text,x,y);
  }
  draw(state, selectedId) {
    this.lastState=state;
    const now=this.paused?this.heldTime:performance.now()-this.offset;
    const c=this.ctx, z=this.zoom, s=z*.55;
    for (const effect of [this.interactions,this.sanitation,this.reactions,this.physicalEffects]) effect.update(state,now);
    this.drawOrder=[]; this.presentedActions.clear();
    c.clearRect(0,0,this.width,this.height);
    c.fillStyle='#d9e2c9';c.fillRect(0,0,this.width,this.height);
    c.fillStyle='#d8d4c5';c.fillRect(0,this.height*.31,this.width,this.height*.51);
    c.fillStyle='#eee6d1';c.fillRect(0,this.height*.30,this.width,9);c.fillRect(0,this.height*.82,this.width,9);
    c.strokeStyle='#b8bdac';c.lineWidth=1;
    for(let x=0;x<this.width;x+=60){c.beginPath();c.moveTo(x,this.height*.31);c.lineTo(x,this.height*.82);c.stroke();}
    // Facilities are shallow footprints, always below bodies: no roof can occlude a person.
    for(const tile of state.terrain?.tiles||[]) if(tile.kind==='wall') {
      const cell=state.terrain.cell_size||20,p=this.project({x:(tile.cell[0]+.5)*cell,y:(tile.cell[1]+.5)*cell});
      c.fillStyle='#7b8879';c.fillRect(p.x-cell*z/2,p.y-cell*z/2,cell*z,cell*z);
      this.label('Wall',p.x,p.y+4);this.drawOrder.push('tile:wall');
    }
    const loose=new Set(['waste','remains','food','material','coat','route_guide']);
    for(const object of state.objects||[]) {
      if(loose.has(object.kind)) continue;
      const p=this.project(object.position), w=Math.min(50,object.width)*z,h=Math.min(30,object.height)*z;
      if(p.x+w<0||p.x-w>this.width||p.y+h<0||p.y-h>this.height)continue;
      const collapsed=object.metadata?.damage_state==='collapsed';
      c.fillStyle=collapsed?'#b0a18b':'#afc0ae';c.fillRect(p.x-w/2,p.y-h/2,w,h);
      c.strokeStyle=collapsed?'#8c725b':'#698579';c.lineWidth=2;c.strokeRect(p.x-w/2,p.y-h/2,w,h);
      if(collapsed)for(let i=0;i<8;i++){c.fillStyle=i%2?'#897c6a':'#d0c0a6';c.fillRect(p.x-w/2+(i*29)%w,p.y-h/2+(i*17)%h,12,7);}
      this.label(`${object.name}${collapsed?' · collapsed':''}`,p.x,p.y-h/2-12);
      this.drawOrder.push(`facility:${object.id}`);
    }
    for(const item of state.objects||[]) {
      if(!loose.has(item.kind)||item.kind==='remains'||item.kind==='waste')continue;
      const p=this.project(item.position);
      c.fillStyle=item.kind==='food'?'#bd6040':'#b49161';c.fillRect(p.x-5*s,p.y-5*s,10*s,8*s);this.label(item.name,p.x,p.y+23);
      this.drawOrder.push(`object:${item.id}`);
    }
    const living=state.agents.filter(a=>a.alive).sort((a,b)=>a.position.y-b.position.y);
    for(const agent of living) {
      const p=this.project(agent.position);if(p.x<30||p.x>this.width-30||p.y<100||p.y>this.height-95)continue;
      const reaction=this.reactions.pose(agent,now,this.reduced), peer=this.interactions.pose(agent,now,this.reduced);
      const relief=this.sanitation.pose(agent,now,this.reduced);
      const detail=state.demo_details?.[agent.id], activity=detail?.activity?.action;
      const changed=this.previous?.agents.find(a=>a.id===agent.id)?.current_action!==agent.current_action;
      const instant=changed&&now-this.started<1600?/^(eat|take|drop|use item):/.exec(agent.current_action)?.[1]:null;
      const task={work:'work',cook:'cook',clean:'clean',repair:'work',build:'work',demolish:'work',salvage:'collect',rest:'rest',seek_shelter:'rest',use_toilet:'relieve',eat:'eat',take:'collect',drop:'collect','use item':'dress'}[activity||instant];
      const taskPose=task?`${task}-${this.reduced?2:Math.floor(now/230)%4}`:null;
      const pose=relief||(reaction.disgust?citizenPose(agent,reaction,now,false,this.reduced):peer?.pose||taskPose||citizenPose(agent,reaction,now,false,this.reduced));
      c.fillStyle=agent.id===selectedId?'#5d887348':'#50654c24';c.beginPath();c.ellipse(p.x,p.y+2,24*s,7*s,0,0,Math.PI*2);c.fill();
      drawCitizen(c,p.x,p.y,s,pose,peer?.facing||1);
      if(detail?.coat){c.fillStyle='#ad684b';c.fillRect(p.x-9*s,p.y-28*s,18*s,12*s);}
      if(reaction.splash&&!relief)drawWasteSplash(c,p.x,p.y,s);
      this.presentedActions.set(agent.id,{pose,kind:relief?'relieving':agent.current_action,targetId:peer?.targetId});
      this.drawOrder.push(`citizen:${agent.id}`);
    }
    for(const item of state.objects||[]) if(item.kind==='remains') {
      const p=this.project(item.position), frame=this.physicalEffects.fall(item,now,this.reduced);
      drawImpact(c,p.x,p.y,s,frame,confirmedTrauma(item,state));drawCitizen(c,p.x,p.y,s,`fall-${frame}`);
      this.drawOrder.push(`citizen:${item.metadata.citizen_id}`);
    }
    // Inspection priority: the small ground hazard stays visible even under a foot.
    for(const item of state.objects||[]) if(item.kind==='waste') {
      const p=this.project(item.position);
      drawWaste(c,p.x,p.y,s*this.sanitation.growth(item,now,this.reduced),this.physicalEffects.compression(item,now,this.reduced));
      this.drawOrder.push(`waste:${item.id}`);
    }
    this.interactions.draw(c,p=>this.project(p),now,this.reduced,s);
    for(const agent of state.agents) {
      const p=this.project(agent.position);if(p.x<30||p.x>this.width-30||p.y<100||p.y>this.height-95)continue;
      this.label(agent.name,p.x,p.y+70);
      const text=agent.alive?(this.sanitation.pose(agent,now,this.reduced)?'Relieving themselves':agent.current_action):`Died · ${agent.death_cause||'recorded death'}`;
      // Full action text stays in the inspector; these short captions never cover the body.
      this.label(text.length>27?`${text.slice(0,26)}…`:text,p.x,p.y+90,'#68716b',10);
      if(agent.speech) {
        const speech=agent.speech.length>64?`${agent.speech.slice(0,61)}…`:agent.speech;
        this.label(speech,p.x,p.y-70*s,'#38574b',12);
      }
    }
    const elapsed=now-this.started;
    const fresh=(state.events||[]).filter(e=>state.world.time-e.world_time<=1);
    if(fresh.some(e=>e.type==='lightning')&&elapsed<650&&!this.reduced){
      const p=this.project(fresh.find(e=>e.type==='lightning').position||this.focus);
      c.strokeStyle='#ffef96';c.lineWidth=5;c.beginPath();c.moveTo(p.x+20,0);c.lineTo(p.x-6,p.y*.45);c.lineTo(p.x+12,p.y*.5);c.lineTo(p.x,p.y);c.stroke();
    }
    if(state.world.weather==='fog'){c.fillStyle='#e4eceb55';c.fillRect(0,0,this.width,this.height);}
    this.canvas.dataset.ready='true';
  }
}
