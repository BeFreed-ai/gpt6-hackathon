// A small, readable pixel city. All positions and actions come from the simulation.
import { WasteReactions, drawWaste, drawWasteSplash } from './waste-reactions.js';
import { PhysicalEffects, citizenPose, drawCitizen, drawImpact, confirmedTrauma } from './citizen-art.js';
import { CitizenInteractions } from './citizen-interactions.js';
import { StreetSanitation } from './street-sanitation.js';
import { EarthquakeReactions, disasterEvents } from './earthquake-reactions.js';
import { cityPlaces, geographicPoint } from './pixel-landmarks.js';
import { cityBlock, sfLandmark, pixelTree, pixelPark } from './sf-pixel-art.js';
import { SFCityContext, CONTEXT, SKYLINE } from './sf-city-context.js';
import { PixelDamage, drawDamagedBuilding, damageState } from './pixel-damage.js';

const W = 1400, H = 820, CELL = 20;
const colors = {grass:'#b7b8a7', grassLight:'#c4c4b2', edge:'#899791', road:'#76878c', curb:'#d7d2ba', ink:'#394b39', water:'#4b8fa5'};
const districts = {city:{x:-150,y:380,name:'San Francisco'},soma:{x:690,y:160,name:'SoMa'},mission:{x:320,y:530,name:'Mission'},mission_bay:{x:1100,y:370,name:'Mission Bay'}};
const noise = (x,y) => ((Math.imul(x+73,73856093)^Math.imul(y+19,19349663))>>>0)/4294967295;

export function visibleAction(agent) {
  const action = agent.current_action || 'idle';
  if (/^(going|walking|commuting|seeking)/.test(action)) return 'walking';
  if (agent.speech) return 'talking';
  if (/^work(?: |$)/.test(action)) return 'working';
  if (/^clean(?: |$)/.test(action)) return 'cleaning';
  if (/^eat(?: |$)/.test(action)) return 'eating';
  if (/^(rest|resting|sleep|seek shelter)(?: |$)/.test(action)) return 'resting';
  if (/^(repair|build)(?: |$)/.test(action)) return 'building';
  if (/^help(?: |$)/.test(action)) return 'helping';
  return 'idle';
}

export class PixelCity {
  constructor(canvas) {
    this.canvas=canvas; this.ctx=canvas.getContext('2d');
    this.scene=document.createElement('canvas'); this.scene.width=W; this.scene.height=H;
    this.art=this.scene.getContext('2d');
    this.ground=document.createElement('canvas'); this.ground.width=W; this.ground.height=H;
    this.zoom=.24; this.focus={x:-150,y:380}; this.district='city';this.initialCamera=true;
    this.view={scale:1,offsetX:0,offsetY:0}; this.positions=new Map();
    this.wasteReactions=new WasteReactions(); this.physicalEffects=new PhysicalEffects();
    this.damage=new PixelDamage();
    this.interactions=new CitizenInteractions();
    this.sanitation=new StreetSanitation();
    this.quakeReactions=new EarthquakeReactions();
    this.reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.followSelected=false; this.lastFrame=0; this.lastState=null; this.groundKey=null;
    this.presentedActions=new Map(); this.effects=new Map(); this.seenEvents=new Set();
  }
  resize() {
    const ratio=Math.min(devicePixelRatio||1,2);
    this.canvas.width=Math.round(this.canvas.clientWidth*ratio);
    this.canvas.height=Math.round(this.canvas.clientHeight*ratio);
    this.ctx.setTransform(ratio,0,0,ratio,0,0); this.ctx.imageSmoothingEnabled=false;
    if(this.initialCamera){this.initialCamera=false;this.focusDistrict('city');}
    this.calculateView();
  }
  calculateView() {
    this.view={scale:this.zoom,offsetX:Math.round(this.canvas.clientWidth/2-this.focus.x*this.zoom)+(this.shake||0),offsetY:Math.round(this.canvas.clientHeight/2-this.focus.y*this.zoom)};
  }
  screenPoint(p) { return {x:this.view.offsetX+p.x*this.zoom,y:this.view.offsetY+p.y*this.zoom}; }
  worldPoint(x,y) { return {x:(x-this.view.offsetX)/this.zoom,y:(y-this.view.offsetY)/this.zoom}; }
  setZoom(value,anchor) {
    const before=anchor&&this.worldPoint(anchor.x,anchor.y);
    this.zoom=Math.max(.12,Math.min(8,value)); this.calculateView();
    if(before) {const after=this.worldPoint(anchor.x,anchor.y);this.focus.x+=before.x-after.x;this.focus.y+=before.y-after.y;this.calculateView();}
    const label=document.querySelector('#zoom-level'); if(label) label.textContent=`${Math.round(this.zoom*100)}%`;
  }
  pan(dx,dy) {this.followSelected=false;this.focus.x=Math.max(CONTEXT.x,Math.min(CONTEXT.x+CONTEXT.width,this.focus.x-dx/this.zoom));this.focus.y=Math.max(CONTEXT.y,Math.min(CONTEXT.y+CONTEXT.height,this.focus.y-dy/this.zoom));this.calculateView();}
  focusDistrict(id) {
    this.district=id;this.followSelected=false;this.focus={x:districts[id].x,y:districts[id].y};
    this.setZoom(id==='city'?Math.min((this.canvas.clientWidth-40)/4300,(this.canvas.clientHeight-130)/2800):Math.max(1,Math.min(2.2,this.canvas.clientWidth/520)));
    if(id==='city'){this.focus.y-=45/this.zoom;this.calculateView();}
  }
  focusCitizen(agent) {this.focus={...agent.position};this.setZoom(5);}
  focusWaste(waste) {this.focus={...waste.position};this.setZoom(5);}
  focusPlace(place) {this.focus={...place.position};this.focusedPlace=place.id;this.followSelected=false;this.setZoom(4);}
  fitResidents(state) {
    const people=state.agents.filter(a=>a.alive); if(!people.length)return;
    const xs=people.map(a=>a.position.x),ys=people.map(a=>a.position.y);
    const left=Math.min(...xs)-35,right=Math.max(...xs)+35,top=Math.min(...ys)-65,bottom=Math.max(...ys)+35;
    this.focus={x:(left+right)/2,y:(top+bottom)/2};this.followSelected=false;
    this.setZoom(Math.min((this.canvas.clientWidth-50)/(right-left),(this.canvas.clientHeight-150)/(bottom-top)));
  }
  hitTest(agent,click) {
    const p=this.worldPoint(click.x,click.y);
    return Math.abs(p.x-agent.position.x)<11 && p.y>=agent.position.y-28 && p.y<=agent.position.y+4;
  }
  rect(c,color,x,y,w,h) {c.fillStyle=color;c.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h));}
  makeGround(state) {
    const places=cityPlaces(state);
    const key=`${state.world.experiment_id}:${state.terrain?.revision}:${places.map(p=>`${p.id}:${p.position.x}:${p.position.y}`).join('|')}`;
    if(this.groundKey===key)return;this.groundKey=key;
    if(state.terrain?.map)this.context=new SFCityContext(state.terrain.map,{tiles:state.terrain.tiles||[],reserved:places.map(p=>p.position)});
    const c=this.ground.getContext('2d'),r=(color,x,y,w,h)=>this.rect(c,color,x,y,w,h);
    const tiles=new Map((state.terrain?.tiles||[]).map(t=>[t.cell.join(','),t]));
    r(colors.grass,0,0,W,H);
    this.context?.drawLocal(c);
    for(let y=0;y<H;y+=CELL)for(let x=0;x<W;x+=CELL){
      const cell=[x/CELL,y/CELL],t=tiles.get(cell.join(',')),n=noise(...cell);
      if(!t&&this.context&&!this.context.onLand(x+10,y+10))continue;
      if(t?.kind==='road'){
        // The entire traversable cell is sidewalk/public space; asphalt follows
        // the real centerline below. Never add a decorative building on this cell.
        r('#d4c7a6',x,y,20,20);
      }
      if(t&&!t.facility&&t.kind!=='road'){
        if(t.kind==='wall'){r('#4d5849',x,y,20,20);r('#9b9d83',x,y,20,4);r('#697762',x+2,y+6,16,12);}
        if(t.kind==='floor')r('#dac7a0',x,y,20,20);
        if(t.kind==='sign'){r('#6c5739',x+9,y+4,2,15);r('#eee0af',x+2,y+1,16,8);}
      }
    }
    // Draw official centerlines through their authoritative walkable tile mask.
    c.save();c.beginPath();
    for(const t of tiles.values())if(t.kind==='road')c.rect(t.cell[0]*20,t.cell[1]*20,20,20);
    c.clip();c.lineCap='round';
    for(const width of [10,6]){
      c.lineWidth=width;c.strokeStyle=width===10?'#eee0be':'#92978d';c.beginPath();
      for(const s of state.terrain?.map?.streets||[]){c.moveTo(s.points[0].x,s.points[0].y);c.lineTo(s.points[1].x,s.points[1].y);}c.stroke();
    }
    c.restore();
    // Decoration is already baked into the same context canvas on both sides
    // of every simulation edge. Only authoritative gameplay terrain overlays it.
  }
  building(item) {
    const c=this.art,x=item.position.x,y=item.position.y,r=(color,a,b,w,h)=>this.rect(c,color,x+a,y+b,w,h);
    const park=['park','garden'].includes(item.kind);
    if(park){pixelPark(c,x,y,22,20);return;}
    drawDamagedBuilding(c,item,this.damage.progress(item,this.lastFrame,this.reducedMotion));
  }
  landmark(item) {
    if(sfLandmark(this.art,item))return;
    const c=this.art,x=item.position.x,y=item.position.y,r=(col,a,b,w,h)=>this.rect(c,col,x+a,y+b,w,h);
    if(item.kind==='park'){
      pixelPark(c,x,y,34,26);
    }
  }
  label(text,x,y,bg='#faf0d0',fg='#3c503e') {
    this.callouts.push({text,x,y,bg,fg});
  }
  paintLabels() {
    const c=this.ctx,placed=[];c.font='11px monospace';c.textAlign='center';
    for(const item of [...this.callouts].reverse()){
      const p=this.screenPoint(item),lines=[];let line='';
      for(const word of String(item.text).split(' ')){if((line+' '+word).length>34&&line){lines.push(line);line=word;}else line+=(line?' ':'')+word;}lines.push(line);
      const shown=lines.slice(0,3),w=Math.min(250,Math.max(...shown.map(t=>c.measureText(t).width))+14),h=shown.length*14+8;
      const x=Math.max(w/2+5,Math.min(this.canvas.clientWidth-w/2-5,p.x)),y=p.y-h;
      if(p.x<0||p.x>this.canvas.clientWidth||y<105||y+h>this.canvas.clientHeight-35)continue;
      if(placed.some(b=>Math.abs(b.x-x)<(b.w+w)/2+5&&y<b.y+b.h+3&&y+h>b.y-3))continue;
      this.rect(c,'#526346',x-w/2-1,y-1,w+2,h+2);this.rect(c,item.bg,x-w/2,y,w,h);
      c.fillStyle=item.fg;shown.forEach((t,i)=>c.fillText(t,Math.round(x),Math.round(y+14+i*14),w-10));
      placed.push({x,y,w,h});
    }
  }
  paintStreetNames(state){
    if(this.zoom<1.6)return;
    const c=this.ctx,occupied=[];
    const main=/^(MARKET|MISSION|VALENCIA|DOLORES|16TH|24TH|03RD|04TH|KING|CHANNEL|BRANNAN|FOLSOM|TERRY A FRANCOIS)/;
    for(const label of state.terrain?.map?.labels||[]){
      if(!main.test(label.text))continue;
      const p=this.screenPoint(label);
      if(p.x<55||p.x>this.canvas.clientWidth-65||p.y<150||p.y>this.canvas.clientHeight-45||occupied.some(q=>Math.hypot(q.x-p.x,q.y-p.y)<85))continue;
      c.save();c.translate(p.x,p.y);c.rotate(label.angle*Math.PI/180);c.font='9px monospace';c.textAlign='center';
      c.lineWidth=3;c.strokeStyle='#ede0bd';c.strokeText(label.text,0,0);c.fillStyle='#59675f';c.fillText(label.text,0,0);c.restore();occupied.push(p);
    }
  }
  activity(agent,kind,now) {
    const x=agent.position.x,y=agent.position.y,c=this.art,r=(col,a,b,w,h)=>this.rect(c,col,x+a,y+b,w,h);
    const frame=this.lastState.world.paused||this.reducedMotion?0:Math.floor(now/180)%2;
    if(kind==='working'){r('#67583d',9,-12,13,3);r('#576c64',11,-20,9,8);r('#a7d0b9',12,-19,7,5);r('#e6d6a3',11+frame*2,-11,3,2);}
    if(kind==='cleaning'){r('#866344',10+frame*2,-18,2,18);r('#d1b061',7+frame*2,-2,9,3);}
    if(kind==='eating'){r('#a7553e',8,-15-frame*2,4,4);r('#6b8b49',10,-17-frame*2,2,2);}
    if(kind==='building'){r('#846749',10,-13-frame*4,2,12);r('#bfc6b1',7,-16-frame*4,8,4);}
    if(kind==='helping'){r('#f5e8c7',10,-15,8,7);r('#af5f49',13,-14,2,5);r('#af5f49',11,-12,6,1);}
    if(kind==='resting')this.label('z',x+12,y-24,'#eff0c9');
  }
  draw(state,selectedId,hoveredId,brush=null) {
    if(!state)return;
    const now=performance.now();if(now-this.lastFrame<32)return;this.lastFrame=now;
    this.lastState=state;
    this.callouts=[];
    const visualEvents=disasterEvents(state);
    if(this.run!==state.world.experiment_id){this.run=state.world.experiment_id;this.seenEvents=new Set(visualEvents.map(e=>e.id));this.effects.clear();}
    for(const e of visualEvents){if(!this.seenEvents.has(e.id)){this.seenEvents.add(e.id);if(['earthquake','lightning'].includes(e.type))this.effects.set(e.id,{event:e,start:now});}}
    for(const [id,e] of this.effects)if(now-e.start>2200)this.effects.delete(id);
    this.wasteReactions.update(state,now);this.physicalEffects.update(state,now);
    this.damage.update(state,now);
    this.interactions.update(state,now);
    this.sanitation.update(state,now);
    this.quakeReactions.update(state,now);
    this.makeGround(state);const c=this.art;c.clearRect(0,0,W,H);c.drawImage(this.ground,0,0);
    this.positions.clear();this.presentedActions.clear();
    for(const a of state.agents)if(a.alive)this.positions.set(a.id,{...a.position});
    const selected=state.agents.find(a=>a.id===selectedId);
    if(this.followSelected&&selected){this.focus={...selected.position};this.calculateView();}
    const scenery=cityPlaces(state).filter(p=>p.scenery);
    for(const place of scenery)this.landmark(place);
    const objects=[...state.objects,...state.agents.filter(a=>a.alive).map(a=>({...a,kind:'citizen'}))];
    objects.sort((a,b)=>a.position.y-b.position.y||Number(a.kind==='citizen')-Number(b.kind==='citizen'));
    for(const item of objects){
      const x=item.position.x,y=item.position.y;
      if(item.kind==='citizen'){
        const reaction=this.wasteReactions.pose(item,now,this.reducedMotion);
        const peer=this.interactions.pose(item,now,this.reducedMotion);
        const relief=this.sanitation.pose(item,now,this.reducedMotion);
        const quakePose=this.quakeReactions.pose(item);
        const pose=quakePose||relief||(!reaction.disgust&&peer?.pose)||citizenPose(item,reaction,now,state.world.paused,this.reducedMotion),kind=quakePose?'startled':relief?'relieving':visibleAction(item);
        this.presentedActions.set(item.id,{pose,kind,targetId:peer?.targetId});
        this.rect(c,'#6c7e47',x-7,y,14,3);
        if(item.id===selectedId||item.id===hoveredId){c.strokeStyle='#fff0a6';c.lineWidth=1;c.strokeRect(Math.round(x)-11,Math.round(y)-28,22,32);}
        if(reaction.splash&&!relief)drawWasteSplash(c,x,y,.7);
        drawCitizen(c,Math.round(x),Math.round(y),.4,pose,peer?.facing||1);this.activity(item,kind,now);
        this.quakeReactions.draw(c,item,now,this.reducedMotion);
      }else if(item.kind==='waste')drawWaste(c,x,y,.7*this.sanitation.growth(item,now,this.reducedMotion),this.physicalEffects.compression(item,now,this.reducedMotion));
      else if(item.kind==='remains'){const frame=this.physicalEffects.fall(item,now,this.reducedMotion);drawImpact(c,x,y,.4,frame,confirmedTrauma(item,state));drawCitizen(c,x,y,.4,`fall-${frame}`);}
      else if(item.kind==='food'){this.rect(c,'#844f36',x-3,y-5,6,5);this.rect(c,'#db8254',x-2,y-5,4,3);this.rect(c,'#466b43',x,y-7,3,2);}
      else if(item.kind==='tree')pixelTree(c,x,y);
      else if(['material','coat','route_guide'].includes(item.kind)){this.rect(c,item.kind==='coat'?'#637f89':'#af915e',x-4,y-5,8,5);}
      else this.building(item);
    }
    this.interactions.draw(c,p=>p,now,this.reducedMotion);
    this.damage.drawDust(c,now,this.reducedMotion);
    const labels=[];
    this.displayedPlaces=[];
    for(const place of cityPlaces(state)){
      const personal=place.id===this.selectedPlaces?.home?'HOME':place.id===this.selectedPlaces?.workplace?'WORK':null;
      const employer=place.metadata?.employer_id;
      const damage=damageState(place);
      const important=damage!=='intact'||personal||place.id===this.focusedPlace||place.scenery||(employer&&!employer.startsWith('sector_'));
      if(!important||this.zoom<1.15)continue;
      const x=place.position.x,y=place.position.y-27,p=this.screenPoint({x,y});
      if(p.x<20||p.x>this.canvas.clientWidth-20||p.y<90||p.y>this.canvas.clientHeight-40)continue;
      if(!personal&&place.id!==this.focusedPlace&&labels.some(p=>Math.abs(p.x-x)<85&&Math.abs(p.y-y)<23))continue;
      let title=personal?`${personal} · ${place.name}`:place.name.replace('San Francisco Museum of Modern Art','SFMOMA').split(' — ')[0];
      if(damage!=='intact')title+=` · ${damage.toUpperCase()}`;
      this.label(title,x,y,damage!=='intact'?'#efbd8d':personal?'#f3da88':'#e5e5bf');labels.push({x,y});this.displayedPlaces.push(place.id);
    }
    // Readable public action captions, never private thoughts or invented dialogue.
    for(const a of state.agents.filter(a=>a.alive)){
      const p=this.screenPoint(a.position);if(p.x<0||p.x>this.canvas.clientWidth||p.y<60||p.y>this.canvas.clientHeight-30)continue;
      const selected=a.id===selectedId||a.id===hoveredId;
      if(this.quakeReactions.reaction(a)&&this.zoom>=2.5)this.label(a.reaction||'Ground shaking!',a.position.x,a.position.y-45,'#f7df9b');
      else if(this.sanitation.pose(a,now,this.reducedMotion)&&this.zoom>=2.5)this.label('Relieving themselves',a.position.x,a.position.y-40);
      else if(a.speech&&this.zoom>=1.7)this.label(`"${a.speech}"`,a.position.x,a.position.y-56);
      else if(selected)this.label(`${a.name}${a.has_home?'':' · No home'} · ${a.current_action}`,a.position.x,a.position.y-43);
      else if(/stepped in waste/i.test(a.reaction||'')&&this.zoom>=2.5)this.label(a.reaction,a.position.x,a.position.y-32,'#f7df9b');
      else if(a.is_thinking&&this.zoom>=2.5)this.label('...',a.position.x,a.position.y-30);
    }
    if(brush){c.strokeStyle='#fff3b5';c.lineWidth=2;c.strokeRect(Math.floor(brush.position.x/20)*20,Math.floor(brush.position.y/20)*20,20,20);}
    for(const {event:e,start} of this.effects.values()){
      if(e.type==='lightning'&&e.position&&now-start<900)for(let i=0;i<8;i++)this.rect(c,'#fff2bb',e.position.x+(i%2)*4,e.position.y-80+i*10,3,13);
    }
    const quake=!this.reducedMotion&&[...this.effects.values()].some(e=>e.event.type==='earthquake'&&now-e.start<1500);
    this.shake=quake?Math.round(Math.sin(now/26)*3):0;
    this.calculateView();const out=this.ctx;
    out.fillStyle='#488f9f';out.fillRect(0,0,this.canvas.clientWidth,this.canvas.clientHeight);out.imageSmoothingEnabled=false;
    this.context?.draw(out,this.view,this.zoom);
    out.drawImage(this.scene,this.view.offsetX,this.view.offsetY,W*this.zoom,H*this.zoom);
    if(this.zoom<1.15){
      for(const item of SKYLINE){const p=geographicPoint(item.coordinates,state.terrain?.map);if(p)this.label(item.name,p.x,p.y-35,'#e8dcc0');}
      for(const id of ['soma','mission','mission_bay']){const p=districts[id];this.label(p.name.toUpperCase(),p.x,p.y-50,'#f4cb70');}
    }
    this.paintStreetNames(state);this.paintLabels();
    const visible=[...this.positions.values()].filter(p=>{const s=this.screenPoint(p);return s.x>=0&&s.y>=0&&s.x<=this.canvas.clientWidth&&s.y<=this.canvas.clientHeight;}).length;
    document.querySelector('#citizens-visible').textContent=`${visible} in view / ${this.positions.size} citizens`;
    document.querySelector('#map-status').textContent=`${districts[this.district].name} · Pixel city · ${state.world.paused?'PAUSED':'LIVE'}`;
    document.querySelector('#map-follow')?.setAttribute('aria-pressed',String(this.followSelected));
    document.querySelector('#zoom-level').textContent=`${Math.round(this.zoom*100)}%`;
    this.canvas.dataset.ready='true';this.canvas.dataset.zoom=String(this.zoom);
    this.canvas.dataset.district=this.district;
  }
}
