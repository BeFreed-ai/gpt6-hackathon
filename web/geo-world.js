// Real geographic context; simulation coordinates and authority remain on the server.
import { buildingMeshes } from "./building-meshes.js";
import { WasteReactions, drawWaste, drawWasteSplash } from "./waste-reactions.js";
import { citizenLayout } from "./citizen-layout.js";
import { DETAIL_SCALE, POSES, PhysicalEffects, citizenPose, drawCitizen, drawImpact, confirmedTrauma } from "./citizen-art.js";
export const EAST_SF = [[-122.451, 37.708], [-122.354, 37.812]];
const collection = features => ({ type: "FeatureCollection", features });
const feature = (geometry, properties = {}) => ({ type: "Feature", geometry, properties });

export function toLngLat(position, bounds) {
  const [west, south, east, north] = bounds;
  return [west + (position.x - 40) / 1320 * (east - west), north - (position.y - 40) / 740 * (north - south)];
}

export function toWorld(coordinate, bounds) {
  const [west, south, east, north] = bounds;
  return { x: 40 + (coordinate.lng - west) / (east - west) * 1320, y: 40 + (north - coordinate.lat) / (north - south) * 740 };
}

let library;
export function loadMapLibrary() {
  if (globalThis.maplibregl) return Promise.resolve();
  if (!library) library = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://unpkg.com/maplibre-gl@5.6.2/dist/maplibre-gl.js";
    const timer = setTimeout(() => reject(new Error("Map library timed out")), 15000);
    script.onload = () => { clearTimeout(timer); resolve(); };
    script.onerror = () => { clearTimeout(timer); reject(new Error("Map library unavailable")); };
    document.head.append(script);
  });
  return library;
}

export class GeoWorld {
  constructor(container, bounds, onClick, onStatus) {
    this.geographic = true;
    this.bounds = bounds;
    this.positions = new Map();
    this.view = { scale: 0.4 };
    this.selected = null;
    this.ready = false;
    this.lastUpdate = 0;
    this.sourceData = new Map();
    this.seenEffects = new Set();
    this.effectsInitialized = false;
    this.hiddenContextBuildings = new Set();
    this.wasteReactions = new WasteReactions();
    this.physicalEffects = new PhysicalEffects();
    this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.followSelected = false;
    this.map = new maplibregl.Map({
      container,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: [-122.407, 37.768], zoom: 12.7,
      minZoom: 10, maxZoom: 22, maxPitch: 65,
      maxBounds: [[-122.53, 37.68], [-122.32, 37.84]],
      attributionControl: true, renderWorldCopies: false,
      canvasContextAttributes: { antialias: true },
    });
    this.map.addControl(new maplibregl.NavigationControl({ showZoom: false }), "top-right");
    this.map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    this.map.on("click", event => onClick(event.originalEvent));
    this.map.on("zoom", () => {
      document.querySelector("#zoom-level").textContent = `Z${this.zoom.toFixed(1)}`;
      container.dataset.zoom = this.zoom.toFixed(3);
    });
    this.map.on("pitch", () => {
      const tilted = this.map.getPitch() > 5;
      document.querySelector("#map-3d").setAttribute("aria-pressed", String(tilted));
      container.dataset.pitch = this.map.getPitch().toFixed(1);
    });
    this.map.on("error", () => onStatus("Map data could not load. Check connection, or use Offline map."));
    this.map.on("load", () => {
      this.addLayers();
      this.ready = true;
      container.dataset.ready = "true";
      onStatus("Eastern SF map · Outlined area is simulated · Sites are synthetic");
    });
    this.map.on("idle", () => this.maskContextBuildings());
    this.map.on("move", () => { this.cameraDirty = true; });
    this.fitEast(false);
  }

  get zoom() { return this.map.getZoom(); }
  resize() { this.map.resize(); }
  screenPoint(position) { return this.map.project(toLngLat(position, this.bounds)); }
  worldPoint(x, y) { return toWorld(this.map.unproject([x, y]), this.bounds); }
  hitTest(agent, click) {
    const point = this.screenPoint(agent.position);
    const stops = [[14,.42],[17,.65],[19,1.4],[21,3]];
    let scale = stops.at(-1)[1];
    for (let i = 1; i < stops.length; i++) if (this.zoom <= stops[i][0]) {
      const [z0,s0] = stops[i-1], [z1,s1] = stops[i];
      scale = s0 + Math.max(0,(this.zoom-z0)/(z1-z0))*(s1-s0); break;
    }
    return Math.abs(point.x-click.x) <= Math.max(13,12*scale) && click.y >= point.y-32*scale && click.y <= point.y+10;
  }
  setZoom(value) { this.map.zoomTo(value, { duration: 180 }); }
  focusCitizen(agent) {
    this.map.easeTo({ center: toLngLat(agent.position, this.bounds), zoom: 20.5,
      pitch: 0, bearing: 0, duration: this.reducedMotion ? 0 : 600 });
  }
  fitEast(animate = true) { this.map.fitBounds(EAST_SF, { padding: 45, pitch: 0, bearing: 0, duration: animate ? 500 : 0 }); }
  fitResidents(state) {
    const people = state.agents.filter(a => a.alive);
    if (!people.length) return;
    const bounds = new maplibregl.LngLatBounds();
    people.forEach(a => bounds.extend(toLngLat(a.position, this.bounds)));
    this.map.fitBounds(bounds, { padding: {top: 140, bottom: 160, left: 105, right: 105},
      maxZoom: 16, pitch: this.map.getPitch(), duration: 500 });
  }
  toggle3D() {
    this.setPixelMode(false);
    const tilted = this.map.getPitch() > 5;
    const selected = this.lastState?.agents.find(a => a.id === this.selected);
    this.map.easeTo({
      ...(selected ? { center: toLngLat(selected.position, this.bounds) } : {}),
      pitch: tilted ? 0 : 55, bearing: tilted ? 0 : -18,
      zoom: tilted ? this.zoom : Math.max(15.5, this.zoom), duration: 650,
    });
  }
  destroy() { this.map.remove(); }

  setPixelMode(enabled) {
    this.pixelMode = enabled;
    this.map.setPixelRatio(enabled ? 0.65 : Math.min(devicePixelRatio || 1, 2));
    this.map.getCanvas().classList.toggle("pixel-map", enabled);
    document.querySelector("#map-pixel").setAttribute("aria-pressed", String(enabled));
    if (enabled) this.map.easeTo({ pitch: 0, bearing: 0, duration: 400 });
    if (this.ready) this.map.setLayoutProperty("city-buildings-3d", "visibility", enabled ? "none" : "visible");
  }

  updateSource(name, features) {
    const data = collection(features);
    const signature = JSON.stringify(data);
    if (this.sourceData.get(name) === signature) return;
    this.sourceData.set(name, signature);
    this.map.getSource(name).setData(data);
  }

  polygon(x, y, width, height) {
    return { type: "Polygon", coordinates: [[
      [x, y], [x + width, y], [x + width, y + height], [x, y + height], [x, y],
    ].map(([x, y]) => toLngLat({ x, y }, this.bounds))] };
  }

  maskContextBuildings() {
    if (!this.ready || !this.buildingBounds || this.zoom < 14) return;
    let changed = false;
    for (const building of this.map.querySourceFeatures("openmaptiles", {sourceLayer: "building"})) {
      if (building.id == null || this.hiddenContextBuildings.has(building.id)) continue;
      const points = building.geometry.coordinates.flat(building.geometry.type === "MultiPolygon" ? 2 : 1);
      if (!points.length) continue;
      const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
      const west = Math.min(...xs), east = Math.max(...xs), south = Math.min(...ys), north = Math.max(...ys);
      if (this.buildingBounds.some(b => west < b.east && east > b.west && south < b.north && north > b.south)) {
        this.hiddenContextBuildings.add(building.id);
        changed = true;
      }
    }
    if (changed) this.map.setFilter("city-buildings-3d", ["all", ["!=", ["get", "hide_3d"], true],
      ["!", ["in", ["id"], ["literal", [...this.hiddenContextBuildings]]]]]);
  }

  addLayers() {
    const map = this.map;
    // The basemap already contains its own extrusion layer. Leaving it enabled
    // would draw an undamaged duplicate on top of our masked contextual buildings.
    for (const layer of map.getStyle().layers) {
      if (layer.type === "fill-extrusion") map.setLayoutProperty(layer.id, "visibility", "none");
    }
    const before = map.getStyle().layers.find(layer => layer.type === "symbol")?.id;
    map.addLayer({
      id: "city-buildings-3d", source: "openmaptiles", "source-layer": "building",
      type: "fill-extrusion", minzoom: 14,
      filter: ["!=", ["get", "hide_3d"], true],
      paint: {
        "fill-extrusion-color": "#c4cdd3",
        "fill-extrusion-height": ["coalesce", ["get", "render_height"], 6],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.85,
      },
    }, before);
    map.addSource("simulation-area", { type: "geojson", data: collection([feature(this.polygon(0, 0, 1400, 820))]) });
    map.addLayer({ id: "simulation-area", type: "line", source: "simulation-area", paint: { "line-color": "#b88a20", "line-width": 2, "line-dasharray": [3, 3] } });
    for (const name of ["citizens", "sites", "edits", "brush", "building-meshes"]) map.addSource(name, { type: "geojson", data: collection([]) });
    map.addLayer({ id: "simulation-buildings-3d", type: "fill-extrusion", source: "building-meshes", minzoom: 13,
      paint: { "fill-extrusion-color": ["get", "color"], "fill-extrusion-height": ["get", "height"],
        "fill-extrusion-base": ["get", "base"], "fill-extrusion-opacity": 1,
        "fill-extrusion-vertical-gradient": true },
    });
    map.addLayer({ id: "city-edits", type: "fill", source: "edits", paint: {
      "fill-color": ["match", ["get", "kind"], "road", "#ac9274", "garden", "#71aa76", "wall", "#625f66", "grass", "#a7c38a", "#d4b887"], "fill-opacity": 0.65,
    } });
    map.addLayer({ id: "city-edits-outline", type: "line", source: "edits", paint: { "line-color": "#756451", "line-width": 1 } });
    map.addLayer({ id: "build-preview", type: "line", source: "brush", paint: { "line-color": "#d29413", "line-width": 3 } });
    map.addLayer({ id: "simulation-sites", type: "circle", source: "sites", minzoom: 13,
      filter: ["!=", ["get", "kind"], "waste"], paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 13, 3, 17, 6],
      "circle-color": ["match", ["get", "kind"], "home", "#967b60", "food", "#e07842", "clinic", "#56a390", "tech", "#5e87ad", "waste", "#79553b", "remains", "#666666", "#8e8e72"],
      "circle-stroke-width": 1.5, "circle-stroke-color": "#ffffff",
    } });
    map.addLayer({ id: "site-labels", type: "symbol", source: "sites", minzoom: 16, layout: {
      "text-field": ["get", "name"], "text-font": ["Noto Sans Regular"], "text-size": 10, "text-offset": [0, 1.3], "text-anchor": "top", "text-max-width": 14,
    }, paint: { "text-color": "#456070", "text-halo-color": "#ffffff", "text-halo-width": 2 } });
    map.addLayer({ id: "damaged-sites", type: "circle", source: "sites", filter: ["==", ["get", "damaged"], true], paint: {
      "circle-radius": 14, "circle-color": "#c84827", "circle-opacity": 0.08,
      "circle-stroke-width": 1, "circle-stroke-color": "#c84827",
    } });
    map.addLayer({ id: "damage-labels", type: "symbol", source: "sites", filter: ["==", ["get", "damaged"], true], layout: {
      "text-field": ["concat", ["get", "damage_label"], " / CLOSED\n", ["get", "name"]], "text-font": ["Noto Sans Regular"],
      "text-size": 12, "text-offset": [0, -1.8], "text-anchor": "bottom", "text-max-width": 18,
    }, paint: { "text-color": "#9b2e16", "text-halo-color": "#fff1d4", "text-halo-width": 2 } });
    const icon = document.createElement("canvas");
    icon.width = icon.height = 32;
    const c = icon.getContext("2d");
    c.fillStyle = "#82681d"; c.fillRect(7, 7, 18, 18); c.fillRect(9, 3, 5, 7); c.fillRect(19, 3, 5, 7);
    c.fillStyle = "#ffdc55"; c.fillRect(9, 8, 14, 15); c.fillRect(10, 4, 3, 6); c.fillRect(20, 4, 3, 6);
    c.fillStyle = "#fff3b0"; c.fillRect(10, 9, 4, 3);
    c.fillStyle = "#353a35"; c.fillRect(12, 14, 2, 3); c.fillRect(19, 14, 2, 3);
    c.fillStyle = "#729795"; c.fillRect(10, 23, 12, 4);
    c.fillStyle = "#5e522e"; c.fillRect(10, 27, 4, 3); c.fillRect(18, 27, 4, 3);
    map.addImage("yellow-citizen", c.getImageData(0, 0, 32, 32), { pixelRatio: 1.5 });
    for (const pose of POSES) {
      const falling = pose.startsWith("fall-");
      const sprite = document.createElement("canvas"); sprite.width = falling ? 160 : 128; sprite.height = falling ? 128 : 80;
      const context = sprite.getContext("2d");
      drawCitizen(context, sprite.width / 2, falling ? 96 : 76, 1, pose);
      map.addImage(`body-${pose}`, context.getImageData(0, 0, sprite.width, sprite.height), {pixelRatio: 2});
    }
    for (let frame = 0; frame < 8; frame++) {
      const sprite = document.createElement("canvas"); sprite.width = sprite.height = 80;
      const context = sprite.getContext("2d");
      drawWaste(context, 40, 65, 1.5, frame / 7);
      map.addImage(`waste-flat-${frame}`, context.getImageData(0,0,80,80), {pixelRatio: 2});
      for (const bloody of [false, true]) {
        context.clearRect(0,0,80,80); drawImpact(context,40,40,1,frame,bloody);
        map.addImage(`impact-${bloody}-${frame}`, context.getImageData(0,0,80,80), {pixelRatio: 2});
      }
    }
    for (const lifted of [false, true]) {
      const face = document.createElement("canvas");
      face.width = face.height = 32;
      const f = face.getContext("2d");
      f.drawImage(icon, 0, 0);
      f.fillStyle = "#ffdc55"; f.fillRect(11, 13, 12, 9);
      f.fillStyle = "#353a35";
      // Pinched eyes and a crooked mouth: a brief physical reaction, not generated speech.
      for (const [x, y, w, h] of [[12, 13, 2, 2], [14, 15, 2, 2], [12, 17, 2, 1],
        [21, 13, 2, 2], [19, 15, 2, 2], [21, 17, 2, 1], [15, 20, 5, 2]]) f.fillRect(x, y, w, h);
      f.fillStyle = "#9ca347"; f.fillRect(20, 19, 3, 3);
      if (lifted) {
        f.clearRect(18, 27, 4, 3);
        f.fillStyle = "#5e522e"; f.fillRect(20, 24, 5, 3);
        f.fillStyle = "#956340"; f.fillRect(22, 26, 4, 2);
      }
      map.addImage(lifted ? "citizen-waste-recoil" : "citizen-waste-face",
        f.getImageData(0, 0, 32, 32), { pixelRatio: 1.5 });
    }
    for (const [name, draw] of [["street-waste", drawWaste], ["waste-splash", drawWasteSplash]]) {
      const sprite = document.createElement("canvas");
      sprite.width = sprite.height = 40;
      const context = sprite.getContext("2d");
      draw(context, 20, 24, 1.5);
      map.addImage(name, context.getImageData(0, 0, 40, 40), { pixelRatio: 1.5 });
    }
    map.addLayer({ id: "street-waste", type: "symbol", source: "sites", minzoom: 10,
      filter: ["==", ["get", "kind"], "waste"], layout: {
        "icon-image": ["get", "waste_sprite"], "icon-allow-overlap": true, "icon-ignore-placement": true,
        "icon-size": DETAIL_SCALE, "icon-anchor": "bottom", "icon-offset": [0, 3.75],
      } });
    const fallen = document.createElement("canvas");
    fallen.width = fallen.height = 32;
    const fc = fallen.getContext("2d");
    fc.translate(16, 16); fc.rotate(Math.PI / 2); fc.globalAlpha = 0.65;
    fc.drawImage(icon, -16, -16);
    map.addImage("fallen-citizen", fc.getImageData(0, 0, 32, 32), { pixelRatio: 1.5 });
    map.addLayer({id: "death-impact", type: "symbol", source: "sites", filter: ["==", ["get", "kind"], "remains"],
      layout: {"icon-image": ["get", "impact_sprite"], "icon-size": DETAIL_SCALE, "icon-allow-overlap": true}});
    map.addLayer({id: "fallen-citizens", type: "symbol", source: "sites", filter: ["==", ["get", "kind"], "remains"],
      layout: {"icon-image": ["get", "fallen_sprite"], "icon-size": DETAIL_SCALE, "icon-anchor": "bottom",
        "icon-offset": [0, 16], "icon-allow-overlap": true}});
    map.addLayer({ id: "citizen-halo", type: "circle", source: "citizens", paint: { "circle-color": "#ffffff", "circle-opacity": 0.35, "circle-radius": 11, "circle-stroke-color": "#d0a735", "circle-stroke-width": 1, "circle-translate": [0, -9] } });
    map.addLayer({ id: "citizen-selected", type: "circle", source: "citizens", filter: ["==", ["get", "id"], ""], paint: { "circle-radius": 15, "circle-color": "#ffffff", "circle-opacity": 0.3, "circle-stroke-color": "#2586bb", "circle-stroke-width": 3 } });
    map.addLayer({ id: "waste-contact-splash", type: "symbol", source: "citizens",
      filter: ["==", ["get", "waste_splash"], true], layout: {
        "icon-image": "waste-splash", "icon-offset": [0, 0],
        "icon-size": DETAIL_SCALE,
        "icon-allow-overlap": true, "icon-ignore-placement": true,
      } });
    map.addLayer({ id: "citizens", type: "symbol", source: "citizens", layout: {
      "icon-image": ["get", "sprite"], "icon-offset": ["get", "visual_offset"], "icon-anchor": "bottom",
      "icon-size": DETAIL_SCALE,
      "icon-rotate": ["get", "visual_tilt"], "icon-rotation-alignment": "viewport",
      "icon-allow-overlap": true, "icon-ignore-placement": true,
    } });
    map.addLayer({ id: "citizen-names", type: "symbol", source: "citizens", minzoom: 14.5, layout: { "text-field": ["get", "name"], "text-font": ["Noto Sans Regular"], "text-size": 11, "text-offset": [0, 1.5], "text-anchor": "top" }, paint: { "text-color": "#363a35", "text-halo-color": "#ffffff", "text-halo-width": 2 } });
    map.addLayer({ id: "citizen-reactions", type: "symbol", source: "citizens", minzoom: 14,
      filter: ["!=", ["get", "public_label"], ""], layout: {
        "text-field": ["get", "public_label"], "text-font": ["Noto Sans Regular"], "text-size": 12,
        "text-offset": ["interpolate", ["linear"], ["zoom"], 17, ["literal", [0,-2]], 21, ["literal", [0,-9]]], "text-anchor": "bottom", "text-max-width": 18,
        "text-allow-overlap": true,
      }, paint: { "text-color": "#513d1b", "text-halo-color": "#fff8df", "text-halo-width": 3 },
    });
  }

  showEffects(state) {
    // A citywide event may create >35 local events and leave the visible feed immediately.
    const events = [...(state.events || []), ...(state.interventions || []).map(i => ({id: i.event_id, type: i.type}))];
    for (const event of events) {
      if (this.seenEffects.has(event.id)) continue;
      this.seenEffects.add(event.id);
      // Loading an old save must not replay old disasters.
      if (!this.effectsInitialized) continue;
      if (event.type === "earthquake") {
        const container = this.map.getContainer();
        container.animate([
          { transform: "translate(0,0)" }, { transform: "translate(-7px,4px)" },
          { transform: "translate(6px,-4px)" }, { transform: "translate(-3px,3px)" },
          { transform: "translate(0,0)" },
        ], { duration: 350, iterations: 9 });
        const dust = document.createElement("div");
        dust.className = "quake-dust";
        container.append(dust);
        setTimeout(() => dust.remove(), 4000);
      }
      if (event.type === "lightning") {
        this.map.getCanvas().animate([{ filter: "brightness(3)" }, { filter: "brightness(1)" }], { duration: 550 });
      }
    }
    this.effectsInitialized = true;
    if (this.seenEffects.size > 500) this.seenEffects = new Set(events.map(e => e.id));
  }

  draw(state, selectedId, hoveredId, brush, tool) {
    if (!this.ready || !state) return;
    if (!this.initialResidentsFramed) {
      this.initialResidentsFramed = true;
      this.fitResidents(state);
    }
    if (this.tool !== tool) {
      this.tool = tool;
      // A drag remains navigation even when an intervention is armed. MapLibre
      // suppresses click after drags, preventing accidental destructive actions.
      this.map.getCanvas().style.cursor = tool ? "crosshair" : "grab";
    }
    const selection = selectedId || hoveredId || "";
    if (selection !== this.selected) {
      this.selected = selection;
      this.map.setFilter("citizen-selected", ["==", ["get", "id"], selection]);
    }
    const brushKey = brush ? `${Math.floor(brush.position.x / 20)},${Math.floor(brush.position.y / 20)}` : "";
    if (brushKey !== this.brushKey) {
      this.brushKey = brushKey;
      const [x, y] = brushKey.split(",").map(Number);
      const valid = brush && x >= 0 && x < 70 && y >= 0 && y < 41;
      this.map.getSource("brush").setData(collection(valid ? [feature(this.polygon(x * 20, y * 20, 20, 20))] : []));
    }
    const now = performance.now();
    const hadWasteAnimation = this.wasteReactions.active.size > 0;
    this.wasteReactions.update(state, now);
    this.physicalEffects.update(state, now);
    if (hadWasteAnimation && !this.wasteReactions.active.size) this.wasteNeedsClear = true;
    const wasteAnimating = this.wasteNeedsClear || this.wasteReactions.active.size > 0;
    const collapseAnimating = this.collapseStarted && now - this.collapseStarted < 2300;
    const bodyAnimating = !this.reducedMotion && (!state.world.paused || this.physicalEffects.animating(now));
    const animating = wasteAnimating || collapseAnimating || bodyAnimating;
    if ((state === this.lastState && !animating && !this.cameraDirty) || now - this.lastUpdate < (animating ? 40 : 150)) return;
    this.cameraDirty = false;
    this.lastState = state;
    this.lastUpdate = performance.now();
    this.showEffects(state);
    this.positions.clear();
    const people = state.agents.filter(a => a.alive);
    const layout = citizenLayout(people, position => this.screenPoint(position), this.zoom);
    for (const person of people) this.positions.set(person.id, person.position);
    const visible = layout.filter(p => p.point.x >= 0 && p.point.y >= 0 &&
      p.point.x <= this.map.getContainer().clientWidth && p.point.y <= this.map.getContainer().clientHeight).length;
    const count = document.querySelector("#citizens-visible");
    if (count) count.textContent = `${visible} / ${people.length} citizens in view · True street positions`;
    this.updateSource("citizens", people.map(a => {
      const pose = this.wasteReactions.pose(a, now, this.reducedMotion);
      return feature({ type: "Point", coordinates: toLngLat(this.positions.get(a.id) || a.position, this.bounds) }, {
      id: a.id, name: a.name,
      sprite: `body-${citizenPose(a, pose, now, state.world.paused, this.reducedMotion)}`,
      visual_offset: [0, 2], visual_tilt: 0, waste_splash: pose.splash,
      public_label: a.speech ? `“${a.speech.slice(0, 140)}”` : pose.label || a.reaction || (a.id === selectedId ? a.current_action : ""),
    }); }));
    this.wasteNeedsClear = false;
    this.updateSource("sites", state.objects.map(o => feature({ type: "Point", coordinates: toLngLat(o.position, this.bounds) }, {
      id: o.id, name: o.name, kind: o.kind, damaged: Boolean(o.metadata?.quake_damage),
      damage_label: (o.structure?.state || "damaged").toUpperCase(),
      waste_sprite: `waste-flat-${Math.round(this.physicalEffects.compression(o, now, this.reducedMotion) * 7)}`,
      fallen_sprite: `body-fall-${this.physicalEffects.fall(o, now, this.reducedMotion)}`,
      impact_sprite: `impact-${confirmedTrauma(o, state)}-${this.physicalEffects.fall(o, now, this.reducedMotion)}`,
    })));
    const buildings = state.objects.filter(o => o.structure);
    const signature = JSON.stringify(buildings.map(o => [o.id, o.position, o.structure]));
    if (signature !== this.buildingSignature) {
      this.buildingSignature = signature;
      const falling = buildings.filter(o => this.previousBuildings?.get(o.id) === "intact" && o.structure.state !== "intact");
      if (falling.length) {
        this.fallingBuildings = new Set(falling.map(o => o.id));
        this.collapseStarted = performance.now();
      }
      this.previousBuildings = new Map(buildings.map(o => [o.id, o.structure.state]));
      this.updateSource("building-meshes", buildingMeshes(buildings, this.polygon.bind(this), this.fallingBuildings,
        this.collapseStarted ? Math.min(1, (performance.now() - this.collapseStarted) / 2100) : 1));
      // Hide intersecting contextual footprints by feature ID, not `within`: a real
      // building may extend far beyond a synthetic site and otherwise cover its ruins.
      this.buildingBounds = buildings.map(o => {
        const a = toLngLat({x: o.position.x - o.structure.width / 2, y: o.position.y - o.structure.depth / 2}, this.bounds);
        const b = toLngLat({x: o.position.x + o.structure.width / 2, y: o.position.y + o.structure.depth / 2}, this.bounds);
        return {west: a[0], east: b[0], south: b[1], north: a[1]};
      });
      this.maskContextBuildings();
    }
    if (collapseAnimating) {
      const progress = Math.min(1, (performance.now() - this.collapseStarted) / 2100);
      this.updateSource("building-meshes", buildingMeshes(buildings, this.polygon.bind(this), this.fallingBuildings, progress));
    }
    const followed = this.followSelected && people.find(a => a.id === selectedId);
    if (followed && !this.map.isMoving()) this.map.setCenter(toLngLat(followed.position, this.bounds));
    const edits = (state.terrain?.tiles || []).filter(tile => !tile.facility && tile.source !== "sf_map");
    this.updateSource("edits", edits.map(tile => feature(this.polygon(tile.cell[0] * 20, tile.cell[1] * 20, 20, 20), { kind: tile.kind })));
  }
}
