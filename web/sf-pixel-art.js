// Original pixel architecture: SF warehouses, glass offices, waterfront and ballparks.
// Decorative architecture is restricted to non-walkable cells by the caller.
const rect=(c,color,x,y,w,h)=>{c.fillStyle=color;c.fillRect(Math.round(x),Math.round(y),Math.round(w),Math.round(h));};
const polygon=(c,color,points)=>{c.fillStyle=color;c.beginPath();points.forEach(([x,y],i)=>i?c.lineTo(Math.round(x),Math.round(y)):c.moveTo(Math.round(x),Math.round(y)));c.closePath();c.fill();};
const seedFor=item=>[...(item.id||item.name||'building')].reduce((n,ch)=>((n*31+ch.charCodeAt(0))>>>0),7);

export function pixelTree(c,x,y,size=1){
  const r=(color,a,b,w,h)=>rect(c,color,x+a*size,y+b*size,w*size,h*size);
  r('#8d967c',-7,1,15,3);r('#856e48',-1,-10,3,12);
  for(const [xx,yy,w,h] of [[-8,-15,15,7],[-6,-20,12,7],[-3,-23,7,6],[-10,-12,19,6]])r('#4f765d',xx,yy,w,h);
  r('#799858',-6,-19,10,8);r('#92ac70',-4,-21,6,5);r('#658c59',-9,-12,10,5);r('#a3b97b',-5,-17,3,3);
}

export function pixelPark(c,x,y,w=34,h=26){
  const p=(color,points)=>polygon(c,color,points.map(([a,b])=>[x+a,y+b]));
  p('#9baa76',[[-w/2+4,-h/2], [w/2-4,-h/2], [w/2,-h/2+5], [w/2-2,h/2-2], [-w/2+4,h/2],[-w/2,-h/2+5]]);
  p('#cfc09a',[[-w/2+2,4],[-2,-2],[w/2-2,-4],[w/2-2,-1],[-2,1],[-w/2+2,7]]);
  pixelTree(c,x-w/4,y-h/5,.6);pixelTree(c,x+w/4,y+h/5,.5);
  rect(c,'#806d4b',x+2,y-6,6,2);rect(c,'#697c62',x+2,y-4,1,2);rect(c,'#697c62',x+7,y-4,1,2);
}

export function cityBlock(c,x,y,w,h,seed,modern=false,mission=false) {
  const r=(col,a,b,ww,hh)=>rect(c,col,x+a,y+b,ww,hh);
  const p=(col,points)=>polygon(c,col,points.map(([a,b])=>[x+a,y+b]));
  const inset=seed%3,depth=3+seed%3;
  const wall=mission?['#d7987f','#83afa1','#dcb972','#a89bbc'][seed%4]:modern?'#a8babd':['#b88871','#ccb89b','#b7b8a8'][seed%3];
  p('#a4a18b',[[2,h-2],[w-2,h-2],[w,h],[5,h]]);
  p('#7b8176',[[w-depth,3],[w-1,0],[w-1,h-4],[w-depth,h-1]]);
  r(wall,inset,h-9,w-depth-inset,8);
  p(modern?'#b9cbd0':'#c6b899',[[inset,3],[depth+inset,0],[w-1,0],[w-depth,3]]);
  p(modern?'#819da5':seed%2?'#a89980':'#8f9585',[[inset,3],[w-depth,3],[w-depth,h-9],[inset,h-9]]);
  if(mission&&seed%2){
    p('#8c7663',[[inset,h-9],[w/2,1],[w-depth,h-9]]);
    p('#c19d76',[[inset,h-9],[w/2,1],[w/2-2,h-9]]);
  }
  for(let xx=3+inset;xx<w-depth-3;xx+=7){r('#547a81',xx,h-7,3,4);r('#c9dbc9',xx,h-7,3,1);}
  r('#e7d7b4',inset,h-10,w-depth-inset,1);
  if(w>25){r('#d6cab0',6,3,6,3);r('#829793',7,3,4,1);}
  if(seed%4===0){
    for(let xx=inset;xx<w-depth;xx+=4)r(xx%8?'#ead2a5':mission?'#b76753':'#5b8d88',xx,h-5,3,2);
  }
}

export function buildingHeight(item){
  const employer=item.metadata?.employer_id;
  return employer==='salesforce_sf'?82:employer==='openai_mission_bay'?27:employer==='anthropic_sf'?30:(['tech','workplace','company','launchpad'].includes(item.kind)?22:item.kind==='home'?24:13)+seedFor(item)%9-4;
}

export function sfBuilding(c,item) {
  const x=item.position.x,y=item.position.y,r=(col,a,b,w,h)=>rect(c,col,x+a,y+b,w,h);
  const employer=item.metadata?.employer_id||'',kind=item.kind;
  const modern=item.metadata?.neighborhood==='mission_bay'||['tech','clinic','workplace'].includes(kind);
  const office=['tech','workplace','company','launchpad'].includes(kind);
  const isHome=kind==='home',isSalesforce=employer==='salesforce_sf';
  const isAnthropic=employer==='anthropic_sf',isOpenAI=employer==='openai_mission_bay';
  const tall=buildingHeight(item);
  const top=-10-tall;
  const seed=seedFor(item),p=(col,points)=>polygon(c,col,points.map(([a,b])=>[x+a,y+b]));
  p('#8a968466',[[-9,7],[10,5],[17,10],[3,16],[-9,11]]);
  const wall=isAnthropic?'#b8856d':modern?['#c7d2c6','#adc3c1','#d2ccb6'][seed%3]:isHome?['#d5b89a','#b3bfa2','#d09b8b','#b5a4b6'][seed%4]:'#ba8870';
  p(modern?'#75979c':'#907c67',[[5,top+2],[11,top-3],[11,5],[5,10]]);
  r(wall,-9,top+2,14,tall+18);
  r('#e2d4b3',-9,top+3,1,tall+13);
  if(isSalesforce){
    // Rounded, tapering blue-glass crown, not a generic cottage roof.
    r('#8baab5',-9,top,18,tall+17);r('#b1c8cf',-7,top+1,4,tall+13);
    for(let yy=top+5;yy<5;yy+=5){r('#557e91',-8,yy,16,2);r('#a2bec9',-5,yy,3,1);}
    r('#799cae',-8,top-6,16,6);r('#96b6c3',-6,top-11,12,5);r('#bbd0d3',-3,top-14,6,3);
    r('#567381',-1,top-20,1,7);
  }else{
    p('#e0d3b5',[[-11,top+1],[-5,top-4],[12,top-4],[6,top+1]]);
    p(modern?'#7c979d':'#9e947e',[[-9,top],[-4,top-3],[10,top-3],[5,top]]);
    r('#b5b8a3',-11,top+1,17,2);
    if(isHome&&!modern&&seed%2){
      p('#92715c',[[-10,top],[-3,top-8],[5,top]]);p('#c4a17c',[[-10,top],[-3,top-8],[-3,top]]);
      r('#e9d8b2',-5,top-3,4,4);r('#607d7f',-4,top-2,2,3);
    }else{r('#8d9b95',-4,top-5,5,3);r('#d5d4bf',-3,top-5,4,1);}
    for(let yy=top+6;yy<-3;yy+=9)for(const xx of [-7,0]){
      r('#4c6979',xx,yy,5,6);r('#9fc6cb',xx,yy,5,2);
      if(isHome){r('#e7dfc0',xx-1,yy-1,7,1);r('#887763',xx-1,yy+6,7,1);}
    }
    if(isHome&&!modern){
      // Stacked bay windows and exterior fire escape suggest SF apartment blocks.
      for(let yy=top+7;yy<-4;yy+=8){p('#eee0be',[[-9,yy],[-6,yy-2],[-2,yy],[-2,yy+6],[-7,yy+7],[-9,yy+5]]);r('#6c9092',-7,yy,3,5);r('#a0c0b3',-7,yy,2,2);}
      r('#626f68',7,top+5,1,tall-5);for(let yy=top+8;yy<0;yy+=7)r('#626f68',3,yy,7,1);
    }
    if(isOpenAI){r('#edf1dd',-10,-5,20,5);r('#334c50',-6,-4,2,3);r('#334c50',-2,-4,2,3);r('#334c50',2,-4,2,3);r('#334c50',6,-4,1,3);}
    if(isAnthropic){r('#e3c5a5',-10,-5,20,5);r('#735b4c',-4,-4,8,2);}
    if(['cafe','market','dining','kitchen'].includes(kind)){
      r('#e7d1a4',-12,-5,24,6);for(let xx=-12;xx<12;xx+=6)r('#b65c4c',xx,-5,3,6);
      r('#6d7770',-8,2,5,5);r('#b5c7b3',-7,2,3,3);
    }
  }
  r('#3c545a',-2,0,5,10);r('#bbc6bb',-1,1,3,7);r('#596d69',1,4,1,1);
  r('#cabc9d',-3,10,7,1);r('#dfd0ac',-4,11,9,1);
  if(kind==='clinic'){r('#ece8d0',-4,top+2,8,8);r('#b7574c',-1,top+3,2,6);r('#b7574c',-3,top+5,6,2);}
  if(kind==='toilet'){r('#517d81',-8,-10,16,7);r('#e3e6d0',-4,-8,3,3);r('#e3e6d0',2,-8,3,3);}
  if(kind==='radio'){r('#66797e',7,top-20,1,20);r('#b7ccc9',2,top-13,11,1);r('#d9b673',7,top-22,2,2);}
  const entrance=item.metadata?.entrance;if(entrance){const dx=Math.sign(entrance.x-x),dy=Math.sign(entrance.y-y);r('#ddd6bd',dx*10-2,dy*9-1,4,3);}
  if(item.open_now===false)r('#b25c4b',-2,5,5,2);
  if(item.in_use>0){r('#405c60',-10,13,20,3);r('#ebc978',-9,14,Math.min(18,item.in_use*4),1);}
}

export function sfLandmark(c,item) {
  const x=item.position.x,y=item.position.y,r=(col,a,b,w,h)=>rect(c,col,x+a,y+b,w,h);
  if(item.kind==='ballpark'){
    // Red-brick horseshoe stands around a visible baseball diamond.
    r('#817f6b',-27,-24,54,45);r('#9e6859',-27,-24,54,7);r('#be8e75',-27,-17,9,33);r('#be8e75',19,-17,8,33);
    r('#a47862',-23,13,46,8);r('#587d51',-18,-15,37,29);r('#799a5b',-14,-13,28,25);
    for(let i=0;i<10;i++)r('#b49368',-i,7-i,2*i+1,1);
    for(const [a,b] of [[0,8],[-9,-1],[9,-1],[0,-10]])r('#f2e7c8',a,b,2,2);
    for(let i=-23;i<24;i+=5){r('#664e45',i,-21,3,3);r('#dfcbb0',i,15,3,1);}
    r('#536d71',14,-32,13,8);r('#dbb975',15,-30,11,3);
    for(const a of [-26,24]){r('#879da0',a,-36,1,16);r('#d4dfd3',a-3,-36,7,2);}
    return true;
  }
  if(item.kind==='arena'){
    // Chase Center's broad white oval roof, stepped into pixels.
    const spans=[[0,54],[4,62],[9,68],[15,72],[22,72],[29,66],[35,58],[40,44]];
    for(const [yy,w] of spans)r(yy>29?'#aebdc0':'#d8ded1',-w/2,-26+yy,w,7);
    for(let yy=0;yy<27;yy+=3){const w=48+Math.min(yy,18);r(yy%6?'#e9e9d8':'#c8d3cf',-w/2,-24+yy,w,2);}
    r('#577785',-13,-10,26,5);r('#b8ccd0',-10,-9,20,2);r('#7a9d9f',-27,10,54,7);
    for(let xx=-25;xx<27;xx+=5)r('#dae2d4',xx,10,1,6);
    r('#c3b99d',-35,19,70,7);r('#52767d',-8,18,16,6);
    return true;
  }
  if(item.kind==='campus'){
    r('#759698',-26,-25,17,38);r('#b9cdca',-24,-24,13,35);r('#cccbb9',-7,-12,34,25);
    for(let yy=-20;yy<8;yy+=6)r('#517887',-22,yy,9,3);
    for(let xx=-4;xx<24;xx+=7)for(let yy=-8;yy<10;yy+=6)r('#7999a0',xx,yy,4,3);
    r('#ece8d4',4,-18,15,10);r('#af6255',10,-17,3,8);r('#af6255',7,-14,9,3);return true;
  }
  if(item.kind==='transit'){
    r('#bec1af',-26,-14,52,28);
    for(const yy of [-8,3,14]){r('#717e7c',-28,yy,56,1);r('#717e7c',-28,yy+3,56,1);for(let xx=-25;xx<28;xx+=5)r('#9e9b89',xx,yy-1,1,6);}
    r('#9c564b',-23,-6,45,7);r('#ebe6d1',-22,-11,42,8);for(let xx=-19;xx<19;xx+=7)r('#658b99',xx,-10,4,4);
    r('#d3c3a4',-25,-23,50,9);r('#787869',-25,-24,50,2);return true;
  }
  return false;
}

export function bayBridge(c) {
  const r=(col,x,y,w,h)=>rect(c,col,x,y,w,h);
  // Gray Bay Bridge rather than the Golden Gate, which is outside these districts.
  for(let i=0;i<230;i+=2){const y=130-i*.30;r('#879b9b',1170+i,y,3,11);r('#c5d0c7',1170+i,y,3,2);}
  for(const x of [1230,1340]){
    const y=130-(x-1170)*.30;
    r('#526e79',x-3,y-66,5,84);r('#afc2c2',x-2,y-66,2,80);r('#657e85',x+10,y-66,5,84);
    for(let yy=-60;yy<0;yy+=15)r('#96adb0',x,y+yy,12,3);
  }
  c.strokeStyle='#c3d0c9';c.lineWidth=1;
  for(const offset of [0,12]){c.beginPath();c.moveTo(1170+offset,130);c.quadraticCurveTo(1200+offset,110,1230+offset,46);c.quadraticCurveTo(1285+offset,100,1340+offset,13);c.quadraticCurveTo(1380+offset,48,1400+offset,61);c.stroke();}
}
