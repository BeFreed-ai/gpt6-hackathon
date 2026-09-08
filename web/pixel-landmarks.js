// Geographic reference points, not surveyed footprints or simulated services.
// Functional places always retain the backend position used by their occupants.
export const PIXEL_LANDMARKS = [
  {id:'landmark-oracle',name:'Oracle Park',kind:'ballpark',coordinates:[-122.38941,37.77841],source:'https://mapcarta.com/23106278'},
  {id:'landmark-chase',name:'Chase Center',kind:'arena',coordinates:[-122.38742,37.76789],source:'https://mapcarta.com/W579646390'},
  {id:'landmark-ucsf',name:'UCSF Mission Bay · Housing South',kind:'campus',coordinates:[-122.3904,37.7691],source:'https://realestate.ucsf.edu/sites/g/files/tkssra17111/files/UCSF_3036_UCOP%20PRESUMPTIVE%20FORM_MB%20HOUSING%20SOUTH_20190904%20-%20Final.pdf'},
];

// Same north-up affine projection as app/sf_map.py. Never clamp or relocate pins.
export function geographicPoint(coordinates, map) {
  if (!map?.bounds) return null;
  const [west,south,east,north]=map.bounds;
  const [lon,lat]=coordinates;
  return {x:Number((40+(lon-west)/(east-west)*1320).toFixed(3)),y:Number((40+(north-lat)/(north-south)*740).toFixed(3))};
}

export function placeLocationText(place) {
  const physical=`World (${place.position.x.toFixed(1)}, ${place.position.y.toFixed(1)})`;
  if(place.scenery) return `${physical} · Geographic reference pin; symbol size is illustrative, no simulated service.`;
  return `${physical} · ${place.metadata?.coordinate_basis || 'Simulation location; not a verified real-world address.'}`;
}

const cache = new WeakMap();
export function cityPlaces(state) {
  if (cache.has(state)) return cache.get(state);
  const objects=state.objects.filter(o=>o.metadata?.footprint_cell);
  const context=(state.terrain?.map?.landmarks||[]).filter(l=>l.kind!=='district').map((l,i)=>({...l,id:`map-landmark-${i}`,scenery:true}));
  const projected=PIXEL_LANDMARKS.map(l=>({...l,scenery:true,position:geographicPoint(l.coordinates,state.terrain?.map)})).filter(l=>l.position);
  const scenery=[...context,...projected];
  const result=[...objects,...scenery];cache.set(state,result);return result;
}
