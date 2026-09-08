// Original, code-drawn pixel art. World coordinates stay server-authoritative.
import { WasteReactions, drawWaste, drawWasteSplash } from "./waste-reactions.js";
import { PhysicalEffects, citizenPose, drawCitizen, drawImpact, confirmedTrauma } from "./citizen-art.js";
const UNIT = 0.4;
const WIDTH = 560;
const HEIGHT = 328;
const palette = {
  outline: "#383c2a", grass: "#82994d", darkGrass: "#708443",
  path: "#c6b17b", lightPath: "#dac591", yellow: "#f5d54d",
};
const creature = [
  "...oo.....oo...",
  "..oyyo...oyyo..",
  "..oyyyyyyyyo..",
  ".oyyyyyyyyyyo.",
  ".oyhyyyyyyyyo.",
  "oyhhyyyyyyyyyo",
  "oyyyywyywyyyyo",
  "oyyyyeyyeyyyyo",
  "oyyyyyyyyyyyyo",
  ".oyyyyyyyyyyo.",
  "..oyyymyyyyo..",
  "...oyyyyyyo...",
  "...obbbbbbo...",
  "..oybbbbbbyo..",
  "...obbbbbbo...",
  "....oo.oo.....",
];

function hash(x, y) {
  let n = Math.imul(x + 319, 374761393) + Math.imul(y + 71, 668265263);
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 4294967295;
}

export class PixelWorld {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.scene = document.createElement("canvas");
    this.scene.width = WIDTH;
    this.scene.height = HEIGHT;
    this.art = this.scene.getContext("2d");
    this.ground = document.createElement("canvas");
    this.ground.width = WIDTH;
    this.ground.height = HEIGHT;
    this.view = { scale: 1, offsetX: 0, offsetY: 0 };
    this.zoom = 1;
    this.focus = { x: WIDTH / 2, y: HEIGHT / 2 };
    this.positions = new Map();
    this.lastFrame = 0;
    this.wasteReactions = new WasteReactions();
    this.physicalEffects = new PhysicalEffects();
    this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.createGround();
  }

  rect(ctx, color, x, y, w, h) {
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
  }

  label(text, x, y, color = "#f6edce", background = "#444933") {
    const c = this.art;
    c.font = "7px monospace";
    const width = Math.ceil(c.measureText(text).width);
    this.rect(c, background, x - width / 2 - 3, y - 7, width + 6, 10);
    c.fillStyle = color;
    c.textAlign = "center";
    c.fillText(text, Math.round(x), Math.round(y));
  }

  createGround() {
    const c = this.ground.getContext("2d");
    const r = (color, x, y, w, h) => this.rect(c, color, x, y, w, h);
    r("#657944", 0, 0, WIDTH, HEIGHT);
    r("#9bb064", 6, 6, WIDTH - 12, HEIGHT - 12);
    r(palette.grass, 9, 9, WIDTH - 18, HEIGHT - 18);
    for (let y = 10; y < HEIGHT - 10; y += 3) {
      for (let x = 10; x < WIDTH - 10; x += 3) {
        const n = hash(x, y);
        if (n > 0.77) r(n > 0.92 ? "#96a75a" : "#788c46", x, y, 2, 1);
        if (n < 0.015) { r("#556f3d", x, y, 1, 2); r("#a5b968", x + 1, y - 1, 1, 2); }
      }
    }
    // Pocket gardens, flower beds and roadside fences add scale without collisions.
    for (const [x, y] of [[20, 110], [133, 105], [220, 112], [383, 100], [459, 295], [35, 278]]) {
      r("#6b8041", x - 3, y - 3, 19, 12);
      for (let i = 0; i < 5; i++) {
        const xx = x + i * 3;
        const yy = y + Math.floor(hash(x, i) * 5);
        r("#546b39", xx, yy, 1, 4);
        r(i % 2 ? "#f1d79a" : "#e5a181", xx - 1, yy, 3, 2);
      }
    }
    for (const [x, y, count] of [[17, 86, 12], [329, 128, 14], [394, 306, 11], [38, 299, 18]]) {
      r("#9a8155", x, y + 2, count * 5, 2);
      for (let i = 0; i < count; i++) {
        r("#5d5938", x + i * 5, y, 2, 7);
        r("#d5bf8c", x + i * 5, y, 1, 6);
      }
    }
  }

  resize() {
    const box = this.canvas.getBoundingClientRect();
    const ratio = Math.min(devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(box.width * ratio);
    this.canvas.height = Math.round(box.height * ratio);
    this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.ctx.imageSmoothingEnabled = false;
    this.calculateView();
  }

  calculateView() {
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    const scale = Math.min((width - 32) / WIDTH, (height - 56) / HEIGHT) * this.zoom;
    this.view = {
      scale: scale * UNIT,
      offsetX: Math.round(width / 2 - this.focus.x * scale),
      offsetY: Math.round(height / 2 - this.focus.y * scale + 8),
    };
    return scale;
  }

  setZoom(value, anchor) {
    const before = anchor ? this.worldPoint(anchor.x, anchor.y) : null;
    this.zoom = Math.max(0.6, Math.min(8, value));
    this.calculateView();
    if (before) {
      const after = this.worldPoint(anchor.x, anchor.y);
      this.focus.x += (before.x - after.x) * UNIT;
      this.focus.y += (before.y - after.y) * UNIT;
      this.calculateView();
    }
  }

  focusCitizen(agent) {
    this.focus = {x: agent.position.x * UNIT, y: agent.position.y * UNIT - 10};
    this.setZoom(6);
  }
  hitTest(agent, click) {
    const point = this.screenPoint(this.positions.get(agent.id) || agent.position);
    return Math.abs(point.x-click.x) <= Math.max(13,22*this.view.scale) &&
      click.y >= point.y-64*this.view.scale && click.y <= point.y+10;
  }

  pan(dx, dy) {
    const scale = this.view.scale / UNIT;
    this.focus.x = Math.max(0, Math.min(WIDTH, this.focus.x - dx / scale));
    this.focus.y = Math.max(0, Math.min(HEIGHT, this.focus.y - dy / scale));
    this.calculateView();
  }

  screenPoint(position) {
    return { x: this.view.offsetX + position.x * this.view.scale, y: this.view.offsetY + position.y * this.view.scale };
  }

  worldPoint(x, y) {
    return { x: (x - this.view.offsetX) / this.view.scale, y: (y - this.view.offsetY) / this.view.scale };
  }

  tree(x, y, seed = 0) {
    const r = (color, a, b, w, h) => this.rect(this.art, color, x + a, y + b, w, h);
    r("#63743b", -8, 4, 21, 4);
    r("#50462e", -2, -3, 5, 11); r("#9b7446", -1, -3, 2, 10);
    r("#344e32", -8, -16, 17, 15); r("#344e32", -12, -12, 24, 8);
    r("#446638", -9, -18, 17, 15); r("#446638", -12, -13, 23, 8);
    r("#5b803e", -7, -21, 13, 15); r("#6e9646", -5, -21, 7, 3);
    r("#83a650", -7, -16, 3, 4); r("#527539", 4, -14, 5, 7);
    for (const [a, b] of [[-7, -10], [4, -7], [1, -17]]) {
      if (hash(a + seed, b) > 0.25) {
        r("#6d3930", a, b, 4, 4); r("#c15a3b", a, b, 3, 3); r("#ef9970", a, b, 1, 1);
      }
    }
  }

  building(item) {
    const c = this.art;
    if (item.metadata?.footprint_cell) {
      // Source street geometry has synthetic one-cell sites, not giant parcel sprites.
      const x = item.position.x * UNIT, y = item.position.y * UNIT;
      const tones = { home: "#b8795e", tech: "#628c99", clinic: "#78a083", park: "#779553", shelter: "#b0a07c" };
      if (item.metadata.quake_damage) {
        if (item.metadata.damage_state === "collapsed") {
          this.rect(c, "#74695c", x - 6, y - 4, 12, 9);
          for (let i = 0; i < 8; i++) this.rect(c, i % 2 ? "#b9a185" : "#8e7766", x - 7 + i * 2, y - 3 + (i % 3) * 3, 3, 2);
          if (this.zoom > 1.1) this.label("COLLAPSED / CLOSED", x, y - 9, "#8a3025", "#fff0ce");
          return;
        }
        this.rect(c, "#8a3025", x - 5, y - 5, 10, 10);
        this.rect(c, "#f3bb63", x - 2, y - 4, 2, 5);
        this.rect(c, "#f3bb63", x, y + 1, 2, 3);
        this.rect(c, "#786756", x - 7, y + 4, 3, 2);
        this.rect(c, "#786756", x + 5, y + 3, 3, 3);
        if (this.zoom > 1.1) this.label("DAMAGED / CLOSED", x, y - 9, "#8a3025", "#fff0ce");
        return;
      }
      this.rect(c, "#444b42", x - 4, y - 5, 8, 9);
      this.rect(c, tones[item.kind] || "#bd9c76", x - 3, y - 4, 6, 7);
      this.rect(c, "#ebdcb5", x - 2, y - 2, 2, 2);
      this.rect(c, "#ebdcb5", x + 1, y - 2, 2, 2);
      const entrance = item.metadata.entrance;
      if (entrance) {
        const dx = Math.sign(entrance.x - item.position.x), dy = Math.sign(entrance.y - item.position.y);
        this.rect(c, "#f6d580", x + dx * 4 - 1, y + dy * 4 - 1, 2, 2);
      }
      if (this.zoom > 2.2) this.label(item.name.slice(0, 23), x, y - 8);
      return;
    }
    const w = Math.max(14, Math.round(item.width * UNIT));
    const h = Math.max(12, Math.round(item.height * UNIT));
    const x = Math.round(item.position.x * UNIT - w / 2);
    const y = Math.round(item.position.y * UNIT - h / 2);
    const r = (color, a, b, ww, hh) => this.rect(c, color, x + a, y + b, ww, hh);
    if (item.kind === "bench") {
      r("#534e36", 1, 5, w - 2, 3); r("#c2a368", 1, 2, w - 2, 3);
      r("#534e36", 2, 8, 2, 4); r("#534e36", w - 4, 8, 2, 4);
      return;
    }
    if (item.kind === "garden") {
      r("#695d37", 0, 0, w, h);
      for (let xx = 2; xx < w - 2; xx += 4) {
        r("#96ab58", xx, 2, 2, h - 4); r("#d6bd6b", xx, 3, 1, 2);
      }
      return;
    }
    if (item.kind === "park") {
      r("#5f7f40", 0, 0, w, h); r("#a2b762", 2, 2, w - 4, h - 4);
      r("#c7b885", w / 2 - 3, 0, 6, h);
      for (const xx of [10, w - 20]) {
        r("#515737", xx, h / 2 + 3, 11, 2); r("#bf9960", xx, h / 2, 11, 3);
        r("#515737", xx + 1, h / 2 + 5, 1, 3); r("#515737", xx + 9, h / 2 + 5, 1, 3);
      }
      this.tree(x + 12, y + 13, 11); this.tree(x + w - 12, y + 13, 9);
      return;
    }
    const tones = {
      home: ["#e0cda0", "#a56046", "#d98b63"], cafe: ["#e6c58a", "#6e4937", "#a46b49"],
      tech: ["#9eafb0", "#485f67", "#6c8385"], clinic: ["#d1d8b7", "#467569", "#6d9d81"],
      market: ["#dbc096", "#984a3c", "#c46c4f"], radio: ["#c2b9c7", "#615d78", "#898099"],
      public_works: ["#c0c09a", "#65705c", "#94947a"], shelter: ["#cbb38d", "#6a5944", "#988064"],
      toilet: ["#a9c7b3", "#3d6961", "#658c77"],
      dining: ["#ead6a5", "#aa6245", "#dc9f6f"], kitchen: ["#d9deaf", "#647e4d", "#8ba45e"],
      launchpad: ["#ccc3de", "#68557e", "#9e83aa"], company: ["#efce8d", "#477f7d", "#76aaa1"],
      depot: ["#c9bf9b", "#776645", "#a49064"],
      workplace: ["#d5cab1", "#696964", "#939587"],
    };
    const [wall, roof, tile] = tones[item.kind] || tones.home;
    r("#63713e", 4, h - 2, w + 3, 6);
    r(palette.outline, 0, 4, w, h - 3);
    r(wall, 2, 5, w - 4, h - 7);
    r("#af9975", w - 7, 6, 5, h - 8);
    for (let row = 0; row < Math.floor(h * 0.43); row += 3) {
      const inset = Math.max(0, Math.floor((h * 0.4 - row) / 3));
      r(palette.outline, inset - 2, row, w - inset * 2 + 4, 4);
      r(roof, inset - 1, row, w - inset * 2 + 2, 2);
      for (let xx = inset + 2; xx < w - inset; xx += 8) r(tile, xx + (row % 2), row, 5, 1);
    }
    const windowY = Math.round(h * 0.58);
    for (let xx = 5; xx < w - 8; xx += 12) {
      r("#655844", xx, windowY, 7, 9); r("#749c9a", xx + 1, windowY + 1, 5, 6);
      r("#c3d7bb", xx + 1, windowY + 1, 2, 3); r(wall, xx + 3, windowY, 1, 8);
      r("#f1d9a6", xx - 1, windowY + 8, 9, 1);
    }
    r("#574b38", w / 2 - 3, h - 11, 7, 10); r("#a3885c", w / 2 - 2, h - 10, 4, 9);
    r("#dfc279", w / 2 + 1, h - 6, 1, 1); r("#d6c397", w / 2 - 5, h - 1, 11, 3);
    if (["cafe", "market"].includes(item.kind)) {
      for (let xx = 2; xx < w - 3; xx += 5) r(xx % 2 ? "#efe1ac" : roof, xx, windowY - 4, 5, 6);
    }
    if (item.kind === "home") {
      r("#69533e", w - 14, -3, 5, 7); r("#d19c6e", w - 14, -3, 3, 7);
      r("#775c3c", 3, h - 2, 8, 3); r("#587b41", 3, h - 5, 8, 3);
    }
    if (item.kind === "clinic") { r("#e1e7cc", w / 2 - 6, 4, 12, 10); r("#aa4940", w / 2 - 1, 5, 3, 8); r("#aa4940", w / 2 - 4, 8, 9, 3); }
    if (item.kind === "radio") {
      r("#454854", w - 9, -21, 2, 26);
      for (let k = 0; k < 4; k++) r("#bbc1ac", w - 13 - k, -18 + k * 5, 10 + k * 2, 1);
      r("#ed9a65", w - 9, -23, 2, 2);
    }
    if (item.kind === "tech") { r("#587175", 10, 3, w - 20, 8); r("#a2ccc0", 12, 4, w - 25, 1); }
    if (item.kind === "toilet") this.label("WC", x + w / 2, y + 11);
    if (["company", "dining", "kitchen", "launchpad", "depot"].includes(item.kind)) {
      const sign = {company: "SHOP", dining: "MEALS", kitchen: "COOK", launchpad: "IDEAS", depot: "REUSE"}[item.kind];
      r("#f4e8c3", 1, h - 11, w - 2, 7);
      this.label(sign, x + w / 2, y + h - 5);
    }
    if (item.open_now === false) r("#b26149", w / 2 - 3, h - 7, 7, 2);
    if (item.metadata?.quake_damage) {
      r("#9a3e2e", w / 2, 1, 3, h - 3);
      r("#e8b15d", w / 2 - 3, h / 2, 8, 2);
      this.label("DAMAGED / CLOSED", x + w / 2, y - 8, "#8a3025", "#fff0ce");
    }
    if (item.in_use > 0) {
      r("#3b6455", 1, h + 5, w - 2, 3);
      r("#dfb949", 1, h + 5, Math.max(3, (w - 2) * Math.min(1, item.in_use / (item.metadata.capacity || item.metadata.beds || 2))), 3);
    }
  }

  citizen(agent, time, selected) {
    const pose = this.wasteReactions.pose(agent, this.lastFrame, this.reducedMotion);
    const position = this.positions.get(agent.id) || agent.position;
    const x = Math.round(position.x * UNIT);
    const groundY = Math.round(position.y * UNIT);
    const y = groundY;
    const c = this.art;
    this.rect(c, "#586637", x - 6, y, 14, 3);
    if (pose.splash) drawWasteSplash(c, x, groundY, 0.8);
    drawCitizen(c, x, y, 0.4, citizenPose(agent, pose, time, !time, this.reducedMotion));
    if (selected) {
      const r = (a, b, w, h) => this.rect(c, "#fff6cf", x + a, y + b, w, h);
      for (const sign of [-1, 1]) { r(sign * 12, -13, 1, 5); r(sign * 12, 5, 1, 5); }
      r(-12, -13, 5, 1); r(8, -13, 5, 1); r(-12, 9, 5, 1); r(8, 9, 5, 1);
    }
    if (pose.disgust && !agent.speech) this.label("Stepped in waste", x, y - 30);
    else if (agent.is_thinking) this.label("...", x + 8, y - 30);
    else if (agent.reaction && !agent.speech) this.label("!", x + 8, y - 30);
    if (selected || this.zoom > 1.3) this.label(agent.name, x, y + 20);
  }

  geography(map, labelsOnly = false) {
    const c = this.art;
    if (!labelsOnly) {
      this.rect(c, "#e1dbbd", 0, 0, WIDTH, HEIGHT);
      for (const street of map.streets) {
        c.beginPath();
        street.points.forEach((point, index) => {
          if (index === 0) c.moveTo(point.x * UNIT, point.y * UNIT);
          else c.lineTo(point.x * UNIT, point.y * UNIT);
        });
        c.strokeStyle = street.name === "MARKET ST" ? "#b89457" : "#b9b39c";
        c.lineWidth = street.name === "MARKET ST" ? 4 : 2;
        c.stroke();
      }
      return;
    }
    const occupied = [];
    for (const label of map.labels) {
      const major = /MARKET|MISSION|VALENCIA|FOLSOM|HOWARD|HARRISON|DIVISION|16TH|24TH|DOLORES/.test(label.text);
      if (!major && this.zoom < 1.5) continue;
      const x = label.x * UNIT, y = label.y * UNIT;
      if (occupied.some(p => Math.abs(p.x - x) < 43 && Math.abs(p.y - y) < 12)) continue;
      occupied.push({ x, y });
      c.save();
      c.translate(x, y); c.rotate(label.angle * Math.PI / 180);
      c.font = "bold 5px monospace"; c.textAlign = "center";
      c.lineWidth = 2; c.strokeStyle = "#eee8cf";
      c.strokeText(label.text.replace(/^0/, ""), 0, 0);
      c.fillStyle = "#655b4b"; c.fillText(label.text.replace(/^0/, ""), 0, 0);
      c.restore();
    }
    for (const district of map.district_labels) {
      this.label(district.name, district.x * UNIT, district.y * UNIT, "#f8eecf", "#6b7364");
    }
    for (const landmark of map.landmarks) {
      const x = landmark.position.x * UNIT, y = landmark.position.y * UNIT;
      this.rect(c, landmark.kind === "park" ? "#58815b" : "#39738c", x - 2, y - 2, 4, 4);
      if (this.zoom > 1.8) this.label(landmark.name, x, y - 6);
    }
    this.label("N ↑ · SF STREETS / SYNTHETIC SITES", WIDTH / 2, 10, "#f5edcf", "#626959");
  }

  draw(state, selectedId, hoveredId, brush = null) {
    const now = performance.now();
    const dt = Math.min(0.1, (now - this.lastFrame) / 1000);
    this.lastFrame = now;
    const c = this.art;
    c.clearRect(0, 0, WIDTH, HEIGHT);
    c.drawImage(this.ground, 0, 0);
    if (state) {
      this.wasteReactions.update(state, now);
      this.physicalEffects.update(state, now);
      const map = state.terrain?.map;
      if (map) this.geography(map);
      const tileSize = (state.terrain?.cell_size || 20) * UNIT;
      if (map) {
        const currentTiles = new Map((state.terrain?.tiles || []).map(tile => [tile.cell.join(","), tile]));
        for (const cell of map.road_cells || []) {
          if (currentTiles.get(cell.join(","))?.kind !== "road") {
            this.rect(c, "#e1dbbd", cell[0] * tileSize, cell[1] * tileSize, tileSize, tileSize);
          }
        }
      }
      for (const tile of state.terrain?.tiles || []) {
        if (tile.facility) continue;
        const x = tile.cell[0] * tileSize, y = tile.cell[1] * tileSize;
        if (tile.kind === "road") {
          if (map && tile.source === "sf_map") continue;
          this.rect(c, palette.path, x, y, tileSize, tileSize);
          this.rect(c, "#bca873", x + 2, y + 2, 2, 1);
        } else if (tile.kind === "floor") {
          this.rect(c, "#bea073", x, y, tileSize, tileSize);
          this.rect(c, "#9b8059", x, y + tileSize - 1, tileSize, 1);
        } else if (tile.kind === "wall") {
          this.rect(c, "#536044", x + 2, y + 3, tileSize, tileSize);
          this.rect(c, "#737468", x, y - 4, tileSize, tileSize + 4);
          this.rect(c, "#c1bda0", x, y - 4, tileSize, 3);
          this.rect(c, "#92907b", x + 1, y, tileSize - 2, 2);
        } else if (tile.kind === "sign") {
          this.rect(c, "#6f5438", x + 3, y, 2, tileSize);
          this.rect(c, "#ead29a", x, y - 3, tileSize, 5);
          this.rect(c, "#87714c", x + 1, y - 1, tileSize - 2, 1);
        }
      }
      if (map) this.geography(map, true);
      const entities = [...state.objects, ...state.agents.filter(a => a.alive).map(a => ({ ...a, kind: "citizen" }))];
      entities.sort((a, b) => a.position.y - b.position.y || Number(a.kind === "citizen") - Number(b.kind === "citizen"));
      for (const item of entities) {
        const x = Math.round(item.position.x * UNIT), y = Math.round(item.position.y * UNIT);
        if (item.kind === "citizen") {
          const previous = this.positions.get(item.id) || { ...item.position };
          const ease = 1 - Math.exp(-dt * 15);
          previous.x += (item.position.x - previous.x) * ease;
          previous.y += (item.position.y - previous.y) * ease;
          this.positions.set(item.id, previous);
          this.citizen(item, state.world.paused ? 0 : now, item.id === selectedId || item.id === hoveredId);
        } else if (item.kind === "tree") this.tree(x, y, x);
        else if (item.kind === "food") {
          this.rect(c, "#62703e", x - 2, y + 2, 6, 2); this.rect(c, "#803c2e", x - 2, y - 2, 5, 5);
          this.rect(c, "#d36043", x - 2, y - 2, 4, 4); this.rect(c, "#f4a275", x - 1, y - 2, 1, 1);
          this.rect(c, "#415d32", x, y - 4, 3, 2);
        } else if (item.kind === "remains") {
          const frame = this.physicalEffects.fall(item, now, this.reducedMotion);
          drawImpact(c, x, y, 0.5, frame, confirmedTrauma(item, state));
          drawCitizen(c, x, y, 0.4, `fall-${frame}`);
          if (item.metadata.citizen_id === selectedId) this.label(item.metadata.citizen_name + " / deceased", x, y - 12, "#514439", "#f1dfbc");
        } else if (item.kind === "material") {
          this.rect(c, "#65563b", x - 3, y, 7, 3);
          this.rect(c, "#b69b68", x - 4, y - 2, 7, 2);
          this.rect(c, "#d3b681", x - 2, y - 4, 6, 2);
        } else if (item.kind === "coat") {
          this.rect(c, "#455a65", x - 4, y - 3, 8, 8);
          this.rect(c, "#81a2a6", x - 5, y - 3, 3, 5);
          this.rect(c, "#81a2a6", x + 2, y - 3, 3, 5);
          this.rect(c, "#efdeb7", x, y - 3, 1, 7);
        } else if (item.kind === "route_guide") {
          this.rect(c, "#485353", x - 3, y - 4, 6, 9);
          this.rect(c, "#9fc4ab", x - 2, y - 3, 4, 6);
        } else if (item.kind === "waste") {
          drawWaste(c, x, y, 0.8, this.physicalEffects.compression(item, now, this.reducedMotion));
        } else this.building(item);
      }
      if (brush) {
        const x = Math.floor(brush.position.x / 20) * tileSize;
        const y = Math.floor(brush.position.y / 20) * tileSize;
        c.strokeStyle = brush.tile === "grass" ? "#e79b77" : "#fff0b7";
        c.lineWidth = 1;
        c.strokeRect(x + 0.5, y + 0.5, tileSize - 1, tileSize - 1);
      }
      // Public speech is painted above scenery; private thoughts never enter the map.
      for (const agent of state.agents.filter(a => a.alive && a.speech)) {
        const x = Math.max(70, Math.min(WIDTH - 70, agent.position.x * UNIT));
        const y = Math.max(17, agent.position.y * UNIT - 31);
        const text = agent.speech.length > 30 ? `${agent.speech.slice(0, 27)}...` : agent.speech;
        this.label(text, x, y, "#3c402e", "#fff0c3");
        this.rect(c, "#fff0c3", x, y + 3, 3, 3);
      }
      if (state.world.weather === "fog") {
        this.rect(c, "#d5e0c326", 0, 0, WIDTH, HEIGHT);
        for (let i = 0; i < 5; i++) {
          const x = (i * 157 + state.world.time * 0.8) % (WIDTH + 130) - 130;
          this.rect(c, "#e7e9cc24", x, 35 + i * 59, 130, 9);
          this.rect(c, "#e7e9cc1a", x + 20, 44 + i * 59, 130, 7);
        }
      }
      for (const event of state.events) {
        const age = state.world.time - event.world_time;
        if (age < 0 || age > 3 || !event.position) continue;
        const x = event.position.x * UNIT, y = event.position.y * UNIT;
        if (event.type === "lightning") {
          for (let i = 0; i < 8; i++) this.rect(c, i % 2 ? "#fff4c9" : "#f5d54d", x + (i % 2) * 4, y - 70 + i * 9, 4, 12);
        } else if (event.type === "death") {
          this.rect(c, "#efe7cc", x - 1, y - 16 - age * 4, 2, 6);
          this.rect(c, "#efe7cc", x - 3, y - 14 - age * 4, 6, 2);
        } else if (["player_gift", "player_build"].includes(event.type)) {
          for (const sign of [-1, 1]) this.rect(c, "#fff0bf", x + sign * (8 + age * 8), y - 5 - age * 5, 3, 3);
        }
      }
    }
    const scale = this.calculateView();
    const output = this.ctx;
    output.clearRect(0, 0, this.canvas.clientWidth, this.canvas.clientHeight);
    output.imageSmoothingEnabled = false;
    output.drawImage(this.scene, this.view.offsetX, this.view.offsetY, Math.round(WIDTH * scale), Math.round(HEIGHT * scale));
  }
}
