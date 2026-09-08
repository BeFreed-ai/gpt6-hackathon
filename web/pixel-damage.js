// Presentation of authoritative structural state. Never creates damage or casualties.
import { sfBuilding, buildingHeight } from './sf-pixel-art.js';

export function damageState(item){
  return item.structure?.state || item.metadata?.damage_state || (item.metadata?.quake_damage?'damaged':'intact');
}
const r=(c,color,x,y,w,h)=>{c.fillStyle=color;c.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h));};

export class PixelDamage {
  constructor(){this.run=null;this.previous=new Map();this.bursts=new Map();}
  update(state,now){
    const fresh=this.run!==state.world.experiment_id;
    if(fresh){this.run=state.world.experiment_id;this.previous.clear();this.bursts.clear();}
    const ids=new Set();
    for(const item of state.objects){
      ids.add(item.id);const phase=damageState(item),stamp=`${phase}:${item.metadata?.quake_damage||''}`;
      if(!fresh&&this.previous.has(item.id)&&this.previous.get(item.id)!==stamp&&['damaged','major','collapsed'].includes(phase)){
        this.bursts.set(item.id,{start:now,position:{...item.position},phase});
      }
      if(!['damaged','major','collapsed'].includes(phase))this.bursts.delete(item.id);
      this.previous.set(item.id,stamp);
    }
    for(const id of this.previous.keys())if(!ids.has(id))this.previous.delete(id);
    for(const [id,burst] of this.bursts)if(!ids.has(id)||now-burst.start>1800)this.bursts.delete(id);
  }
  progress(item,now,reduced){
    const burst=this.bursts.get(item.id);
    return reduced||!burst?1:Math.min(1,Math.max(0,(now-burst.start)/850));
  }
  drawDust(c,now,reduced){
    if(reduced)return;
    for(const burst of this.bursts.values()){
      const t=(now-burst.start)/1800;if(t<0||t>=1)continue;
      const {x,y}=burst.position;
      c.save();c.globalAlpha=(1-t)*.8;
      for(let i=0;i<14;i++){
        const angle=i*2.399,spread=7+t*(burst.phase==='collapsed'?40:24);
        r(c,i%3?'#d5c2a0':'#9c8c78',x+Math.cos(angle)*spread,y+Math.sin(angle)*spread*.3-t*20,4+i%4,3+i%3);
      }
      c.restore();
    }
  }
}

export function drawDamagedBuilding(c,item,progress=1){
  const phase=damageState(item),{x,y}=item.position,top=-10-buildingHeight(item);
  const box=(color,xx,yy,w,h)=>r(c,color,x+xx,y+yy,w,h);
  if(phase==='intact'){sfBuilding(c,item);return;}
  if(phase==='collapsed'){
    // Keep the same ground anchor while the upper structure drops, then retain rubble.
    if(progress<1){
      c.save();c.translate(x,y);c.scale(1,Math.max(.05,1-progress));
      sfBuilding(c,{...item,position:{x:0,y:0}});c.restore();
    }
    box('#887d69',-16,-3,32,15);box('#a28b70',-13,-1,28,11);
    for(let i=0;i<18;i++)box(['#c5ae87','#7b7060','#a19076','#e0cda4'][i%4],-16+(i*11)%31,-7+(i*7)%15,5+i%3,3+i%2);
    box('#6b6b5e',-11,-13,3,16);box('#c6b595',-8,-8,5,9);box('#736755',8,-10,4,13);
    return;
  }
  if(phase==='major'){
    c.save();c.beginPath();
    c.rect(x-18,y+top+8,36,-top+15);
    // Actual transparent missing wall/floor sections, not a black decal on an intact tower.
    c.rect(x-9,y+top+13,11,10);c.rect(x+1,y-14,9,13);c.clip('evenodd');sfBuilding(c,item);c.restore();
    box('#7a6652',-10,top+10,21,2);box('#bda482',-10,top+23,20,2);
    box('#786d5a',-10,-12,2,21);box('#786d5a',8,top+8,2,-top);
    box('#c1ad87',-15,9,11,6);box('#8f7b64',8,7,9,7);
  }else if(phase==='rebuilding'){
    const integrity=item.structure?.integrity??item.metadata?.structural_integrity??30;
    const height=(-top+10)*Math.max(.15,Math.min(1,integrity/100));
    c.save();c.beginPath();c.rect(x-14,y+10-height,28,height);c.clip();sfBuilding(c,item);c.restore();
    for(const dx of [-14,13])box('#7f765d',dx,top-2,2,-top+15);
    for(let yy=top;yy<11;yy+=10){box('#c6b382',-15,yy,31,2);box('#847960',-12,yy+2,2,8);}
  }else sfBuilding(c,item);
  if(phase!=='rebuilding'){
    const points=[[-3,top+5],[1,top+12],[-2,top+19],[3,top+25],[0,-6],[3,5]];
    c.save();c.strokeStyle='#514a41';c.lineWidth=2;c.beginPath();
    points.forEach(([xx,yy],i)=>i?c.lineTo(x+xx,y+yy):c.moveTo(x+xx,y+yy));c.stroke();c.restore();
    box('#5e5b51',-8,top+8,4,6);box('#c3b69a',-8,top+10,2,2);box('#bda785',-12,9,6,3);
  }
  // Physical closure is represented by a small striped barricade at the entrance.
  box('#705e45',-9,8,2,7);box('#705e45',8,8,2,7);box('#e6bf63',-11,8,23,3);
  for(let dx=-9;dx<11;dx+=6)box('#5d5548',dx,8,3,3);
}
