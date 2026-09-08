// Offline geographic context. No actors, services, collision or simulation state.
import { SF_COAST } from './sf-coast-data.js';
import { geographicPoint } from './pixel-landmarks.js';
import { cityBlock, pixelTree } from './sf-pixel-art.js';

export const CONTEXT = {x:-2500,y:-1100,width:4700,height:3000};
export const SKYLINE = [
  {name:'Golden Gate Bridge',coordinates:[-122.478,37.819],kind:'golden_gate'},
  {name:'Coit Tower',coordinates:[-122.40584,37.8024],kind:'coit'},
  {name:'Transamerica Pyramid',coordinates:[-122.4039,37.7952],kind:'pyramid'},
  {name:'Ferry Building',coordinates:[-122.39356,37.79543],kind:'ferry'},
  {name:'Salesforce Tower',coordinates:[-122.3966,37.7898],kind:'salesforce'},
  {name:'Sutro Tower',coordinates:[-122.4528,37.7553],kind:'sutro'},
];
const P = {water:'#488f9f',foam:'#91c7c3',land:'#d4c7a6',street:'#b0ac97',park:'#72966e'};
const hash=(x,y)=>((Math.imul(x+631,73856093)^Math.imul(y+329,19349663))>>>0)/4294967295;
// Continuous neighborhood emphasis, independent of simulation rectangle edges.
export function districtDetail(x,y){
  const distance=Math.min(((x-650)/820)**2+((y-210)/460)**2,((x-300)/600)**2+((y-530)/600)**2,((x-1130)/450)**2+((y-370)/650)**2);
  return .38+.62*Math.exp(-.7*distance);
}
const rect=(c,col,x,y,w,h)=>{c.fillStyle=col;c.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h));};
function path(c,points,closed=false){c.beginPath();points.forEach((p,i)=>i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y));if(closed)c.closePath();}

export class SFCityContext {
  constructor(map,{tiles=[],reserved=[]}={}){
    this.map=map;this.canvas=document.createElement('canvas');
    this.occupied=new Set(tiles.map(t=>t.cell.join(',')));
    this.reserved=reserved;
    this.canvas.width=CONTEXT.width/2;this.canvas.height=CONTEXT.height/2;
    this.c=this.canvas.getContext('2d');this.land=new Path2D();
    for(const polygon of SF_COAST.polygons)for(const ring of polygon){
      ring.forEach((ll,i)=>{const p=geographicPoint(ll,map);if(i)this.land.lineTo(p.x,p.y);else this.land.moveTo(p.x,p.y);});this.land.closePath();
    }
    this.paint();
  }
  onLand(x,y){return this.c.isPointInPath(this.land,x,y,'evenodd');}
  point(ll){return geographicPoint(ll,this.map);}
  paint(){
    const c=this.c,{x,y,width,height}=CONTEXT;
    c.save();c.scale(.5,.5);c.translate(-x,-y);
    rect(c,P.water,x,y,width,height);
    for(let yy=y;yy<y+height;yy+=46)for(let xx=x;xx<x+width;xx+=75){
      if(hash(xx,yy)>.3)rect(c,'#74b0b8',xx+hash(yy,xx)*20,yy,12+hash(xx,yy)*17,2);
    }
    c.strokeStyle='#387887';c.lineWidth=24;c.stroke(this.land);
    c.fillStyle=P.land;c.fill(this.land,'evenodd');c.strokeStyle='#a4c6b3';c.lineWidth=9;c.stroke(this.land);
    c.save();c.clip(this.land,'evenodd');
    // One architectural scale and one continuous ground for the entire peninsula.
    // There is no rectangular hole for the simulation canvas. Only real streets
    // and individually reserved facilities remove decorative buildings.
    const reservedCells=new Set(this.occupied),used=new Set();
    for(const p of this.reserved){
      for(let yy=Math.floor((p.y-30)/20);yy<=Math.floor((p.y+30)/20);yy++)
        for(let xx=Math.floor((p.x-27)/20);xx<=Math.floor((p.x+27)/20);xx++)reservedCells.add(`${xx},${yy}`);
    }
    for(let yy=-820;yy<1780;yy+=20)for(let xx=-2380;xx<1820;xx+=20){
      const cell=`${xx/20},${yy/20}`;
      if(reservedCells.has(cell)||used.has(cell))continue;
      c.globalAlpha=districtDetail(xx,yy);
      const n=hash(xx,yy);
      if(n<.22){if(n<.1)pixelTree(c,xx+10,yy+17,.65);continue;}
      const neighbor=`${xx/20+1},${yy/20}`;
      const wide=!reservedCells.has(neighbor)&&!used.has(neighbor)&&n>.45;
      cityBlock(c,xx+2,yy+2,wide?35:15,16,Math.floor(n*50),xx>900,yy>380&&xx<750);
      if(wide)used.add(neighbor);
      if(n>.86)pixelTree(c,xx+15,yy+17,.35);
    }
    c.globalAlpha=1;
    // Parks are simplified geographic envelopes, not usable facilities.
    const parks=[[-122.510,37.771,-122.454,37.765],[-122.487,37.807,-122.448,37.789],[-122.460,37.760,-122.447,37.746]];
    for(const [west,north,east,south] of parks){
      const a=this.point([west,north]),b=this.point([east,south]);rect(c,P.park,a.x,a.y,b.x-a.x,b.y-a.y);
      for(let yy=a.y+10;yy<b.y;yy+=22)for(let xx=a.x+10;xx<b.x;xx+=28){
        const n=hash(Math.round(xx),Math.round(yy));rect(c,n>.5?'#577d5e':'#87a372',xx,yy,12,9);rect(c,'#acc092',xx+2,yy,6,3);
      }
    }
    // Market Street outside the playable road network is contextual only.
    const market=[[-122.443,37.762],[-122.419,37.776],[-122.394,37.794]].map(ll=>this.point(ll));
    c.save();c.beginPath();c.rect(CONTEXT.x,CONTEXT.y,CONTEXT.width,CONTEXT.height);
    c.rect(0,0,1400,820);c.clip('evenodd');
    path(c,market);c.strokeStyle='#eee0be';c.lineWidth=10;c.stroke();c.strokeStyle='#92978d';c.lineWidth=6;c.stroke();c.restore();
    c.restore();
    // Bridges use geographic endpoints; their vertical structure is exaggerated pixel art.
    this.bridge([[-122.475,37.8075],[-122.480,37.829]],true);
    this.bridge([[-122.3893,37.7878],[-122.366,37.803]],false);
    for(const item of SKYLINE.filter(i=>i.kind!=='golden_gate'))this.tower(item);
    c.restore();
  }
  bridge(endpoints,golden){
    const c=this.c,[a,b]=endpoints.map(ll=>this.point(ll));
    const deck=golden?'#a64c35':'#697f85',light=golden?'#ee9561':'#c3d0c4';
    path(c,[{x:a.x+9,y:a.y+18},{x:b.x+9,y:b.y+18}]);c.strokeStyle='#346e7b';c.lineWidth=27;c.stroke();
    path(c,[a,b]);c.strokeStyle=deck;c.lineWidth=23;c.stroke();c.strokeStyle=light;c.lineWidth=12;c.stroke();
    const towers=[.23,.73].map(t=>({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t}));
    const h=golden?165:112;
    for(const p of towers){
      for(const dx of [-13,13]){rect(c,deck,p.x+dx-4,p.y-h,8,h+20);rect(c,light,p.x+dx-3,p.y-h,3,h+17);}
      for(let yy=10;yy<h;yy+=30){rect(c,deck,p.x-14,p.y-h+yy,28,9);rect(c,light,p.x-13,p.y-h+yy,25,2);}
    }
    for(const dx of [-12,12]){
      c.beginPath();c.moveTo(a.x+dx,a.y);
      c.quadraticCurveTo(a.x+(b.x-a.x)*.1+dx,a.y,towers[0].x+dx,towers[0].y-h);
      c.quadraticCurveTo((towers[0].x+towers[1].x)/2+dx,(towers[0].y+towers[1].y)/2+45,towers[1].x+dx,towers[1].y-h);
      c.quadraticCurveTo(b.x+dx,b.y,b.x+dx,b.y);c.strokeStyle=light;c.lineWidth=4;c.stroke();
    }
  }
  tower(item){
    const c=this.c,{x,y}=this.point(item.coordinates),r=(col,a,b,w,h)=>rect(c,col,x+a,y+b,w,h);
    if(item.kind==='pyramid'){
      for(let yy=0;yy<310;yy+=4){const w=5+yy*.28;r('#8b9388',-w/2,-310+yy,w+6,4);r('#e9e0c8',-w/2,-310+yy,w*.66,4);}
      r('#f4e6c8',-2,-345,4,40);r('#9ba396',-44,-95,88,8);return;
    }
    if(item.kind==='sutro'){
      for(const dx of [-25,0,25])for(let yy=0;yy<190;yy+=20)r(yy%40?'#e5d7b6':'#b75d49',dx-3,-yy,6,20);
      for(let yy=-30;yy>-145;yy-=35)r('#c36b4e',-28,yy,56,5);return;
    }
    const ferry=item.kind==='ferry',coit=item.kind==='coit',h=ferry?115:coit?150:360,w=ferry?30:coit?35:65;
    if(ferry){r('#bcb299',-65,-25,130,31);r('#799688',-68,-35,136,12);for(let xx=-60;xx<60;xx+=12)r('#5d7e82',xx,-18,6,16);}
    r('#637b7d',-w/2+7,-h+7,w,h);r(coit||ferry?'#ded4b9':'#7fa4b0',-w/2,-h,w-5,h);
    r(coit||ferry?'#f5e5c4':'#bed5d0',-w/2+3,-h,7,h);
    for(let yy=-h+10;yy<-4;yy+=10)r(coit||ferry?'#929d91':'#4e7c8e',-w/2+13,yy,w-21,3);
    r('#b9c6ba',-w/2+4,-h-9,w-13,10);r('#dbe0c9',-w/2+9,-h-15,w-23,7);
    if(ferry){r('#63867b',-13,-h-10,26,12);r('#f8efd4',-7,-h+9,14,14);r('#566c63',-1,-h+11,2,8);r('#566c63',-1,-h+17,5,2);}
  }
  draw(c,view,zoom){
    const {x,y,width,height}=CONTEXT;
    c.drawImage(this.canvas,view.offsetX+x*zoom,view.offsetY+y*zoom,width*zoom,height*zoom);
  }
  drawLocal(c){
    c.imageSmoothingEnabled=false;
    c.drawImage(this.canvas,-CONTEXT.x/2,-CONTEXT.y/2,700,410,0,0,1400,820);
  }
}
