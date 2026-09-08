import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { visibleAction, PixelCity } from '../web/pixel-city.js';
import { cityPlaces, geographicPoint, placeLocationText, PIXEL_LANDMARKS } from '../web/pixel-landmarks.js';
import { districtDetail } from '../web/sf-city-context.js';
const map=JSON.parse(readFileSync(new URL('../data/sf_map.json',import.meta.url),'utf8'));

test('neighborhood detail emphasis has no jump at former inset edges',()=>{
  for(const x of [0,1400])for(const y of [0,200,400,820])assert.ok(Math.abs(districtDetail(x-.01,y)-districtDetail(x+.01,y))<.001);
  for(const y of [0,820])for(const x of [0,400,900,1400])assert.ok(Math.abs(districtDetail(x,y-.01)-districtDetail(x,y+.01))<.001);
  assert.ok(districtDetail(650,210)>districtDetail(-1800,900));
});

test('actions depict execution, never a destination or a private ambition',()=>{
  assert.equal(visibleAction({current_action:'going to OpenAI to work'}),'walking');
  assert.equal(visibleAction({current_action:'work at OpenAI'}),'working');
  assert.equal(visibleAction({current_action:'clean at Street Waste'}),'cleaning');
  assert.equal(visibleAction({current_action:'buy at Market'}),'idle');
  assert.equal(visibleAction({current_action:'resting outdoors'}),'resting');
  assert.equal(visibleAction({current_action:'idle',speech:'Hello there!'}),'talking');
  assert.equal(visibleAction({current_action:'idle',thought:'I want to start a company'}),'idle');
});
test('all personal facilities survive the visual simplification',()=>{
  const objects=[{id:'home',kind:'home',name:'Home',metadata:{footprint_cell:[1,1]}},{id:'work',kind:'tech',name:'OpenAI',metadata:{footprint_cell:[2,2]}}];
  const places=cityPlaces({objects,terrain:{map}});
  assert.ok(objects.every(o=>places.includes(o)));
  assert.ok(places.some(p=>p.name==='Oracle Park'&&p.scenery));
  assert.ok(places.some(p=>p.name==='Chase Center'&&p.scenery));
});
test('camera roundtrip and body selection preserve physical feet',()=>{
  const r=Object.create(PixelCity.prototype);
  r.canvas={clientWidth:1000,clientHeight:700};r.focus={x:950,y:350};r.zoom=5;
  r.calculateView();const pos={x:970,y:330};const p=r.screenPoint(pos);
  assert.deepEqual(r.worldPoint(p.x,p.y),pos);
  assert.equal(r.hitTest({position:pos},{x:p.x,y:p.y-80}),true);
  assert.equal(r.hitTest({position:pos},{x:p.x+100,y:p.y}),false);
});
test('geographic anchors never move to make room for scenery or streets',()=>{
  const tiles=Array.from({length:30},(_,i)=>({cell:[50,i+2],kind:'road'}));
  const original={name:'Existing anchor',kind:'park',coordinates:[-122.4023,37.7849],position:{x:797.68,y:82.575}};
  const state={objects:[],terrain:{tiles,map:{...map,landmarks:[original]}}};
  const places=cityPlaces(state);
  assert.deepEqual(places.find(p=>p.name===original.name).position,original.position);
  for(const place of PIXEL_LANDMARKS){
    assert.deepEqual(places.find(p=>p.id===place.id).position,geographicPoint(place.coordinates,map));
  }
  assert.deepEqual(geographicPoint([-122.38941,37.77841],map),{x:1137.976,y:214.153});
  assert.ok(geographicPoint([-122.3966,37.7898],map).y<0,'outside-map locations must not be clamped into the city');
  assert.equal(geographicPoint([-122.38941,37.77841],null),null);
});
test('synthetic workplaces are never presented as verified real addresses',()=>{
  const place={name:'OpenAI',position:{x:1070,y:450},metadata:{coordinate_basis:'Synthetic gameplay site; catalog address is not a geocode'}};
  assert.match(placeLocationText(place),/Synthetic gameplay site/);
  assert.match(placeLocationText(place),/1070.0, 450.0/);
});
test('camera shaking shares the same transform with clicking and zooming',()=>{
  const r=Object.create(PixelCity.prototype);
  r.canvas={clientWidth:1000,clientHeight:700};r.focus={x:950,y:350};
  for(const zoom of [.45,1.35,4,8])for(const shake of [-3,0,3]){
    r.zoom=zoom;r.shake=shake;r.calculateView();
    const position={x:1137.976,y:214.153},screen=r.screenPoint(position),actual=r.worldPoint(screen.x,screen.y);
    assert.ok(Math.abs(actual.x-position.x)<1e-9&&Math.abs(actual.y-position.y)<1e-9);
    assert.ok(r.hitTest({position},{x:screen.x,y:screen.y-10*zoom}));
  }
});
