// Procedural, persistent 3D geometry. No stock photograph or API text stands in for damage.
// All footprints and structural states come from the authoritative simulation snapshot.
const palettes = {
  home: ["#d99b72", "#efc28d"], tech: ["#769aa8", "#c0d5d6"],
  workplace: ["#879caa", "#d2d8ca"], clinic: ["#80ad9c", "#d6e6d2"],
  market: ["#c98972", "#f0bf86"], cafe: ["#ca9785", "#f1d4a2"],
};

export function buildingMeshes(objects, polygon, falling = new Set(), progress = 1) {
  const meshes = [];
  for (const site of objects) {
    const shape = site.structure;
    if (!shape) continue;
    const { width: w, depth: d, height: h, seed } = shape;
    const broken = shape.state !== "intact";
    const collapsed = shape.state === "collapsed";
    const major = collapsed || shape.state === "major" || shape.state === "rebuilding";
    const colors = palettes[site.kind] || ["#b5a18b", "#ded3b1"];
    const x = site.position.x - w / 2, y = site.position.y - d / 2;
    const add = (px, py, pw, pd, base, height, color, part) => meshes.push({
      type: "Feature", geometry: polygon(px, py, pw, pd),
      properties: { site_id: site.id, part, state: shape.state, base, height, color },
    });
    add(x, y, w, d, 0, 0.8, broken ? "#69635b" : "#c5b79e", "foundation");
    // Nine independently shortened volumes produce exposed floors and roof holes.
    const heights = [];
    for (let row = 0; row < 3; row++) for (let col = 0; col < 3; col++) {
      const i = row * 3 + col;
      const noise = ((seed + i * 17) % 11) / 10;
      let height = h;
      if (collapsed) height = 1.2 + noise * h * 0.19;
      else if (major) height = Math.max(2, h * (shape.integrity / 100) * (0.4 + noise));
      else if (broken && (i + seed) % 4 === 0) height = h * 0.74;
      if (falling.has(site.id) && progress < 1) height = h + (height - h) * progress;
      heights.push(height);
      const px = x + col * w / 3, py = y + row * d / 3;
      const gap = broken ? 0.3 : 0.03;
      add(px, py, w / 3 - gap, d / 3 - gap, 0.8, height, broken ? "#a9907c" : colors[0], "wall");
      add(px, py, w / 3 - gap, d / 3 - gap, height, height + 0.5,
        broken ? "#706960" : colors[1], "roof");
      // Pale floor edges, and recessed blue window bands on exterior faces.
      for (let floor = 1; floor * 5 < height; floor++) {
        const z = floor * 5;
        if (row === 2) add(px + 0.5, py + d / 3 - 0.22, w / 3 - 1, 0.3, z - 2.8, z - 1, "#456573", "window");
        if (col === 2) add(px + w / 3 - 0.22, py + 0.5, 0.3, d / 3 - 1, z - 2.8, z - 1, "#55757c", "window");
      }
    }
    if (!broken) {
      add(x + w * 0.18, y + d * 0.2, w * 0.22, d * 0.2, h + 0.5, h + 2, "#7c827f", "roof-equipment");
      add(x + w * 0.3, y + d - 0.1, w * 0.4, 1, 2.5, 3, "#567b71", "awning");
    } else {
      // Deterministic rubble does not reshuffle each network frame or page reload.
      const count = collapsed ? 22 : major ? 15 : 7;
      for (let i = 0; i < count; i++) {
        const angle = (seed + i * 137.508) * Math.PI / 180;
        const radius = 0.4 + (i % 5) * 0.17;
        const size = 0.9 + (i % 4) * 0.65;
        add(site.position.x + Math.cos(angle) * w * radius,
          site.position.y + Math.sin(angle) * d * radius,
          size, size * 0.7, 0, 0.8 + (i % 5) * 0.6,
          i % 2 ? "#8c7564" : "#c3b19b", "rubble");
      }
      // Narrow gaps and jagged dark strips remain legible even in top-down mode.
      for (let i = 0; i < 4; i++) {
        const z = heights[4] + 0.55;
        add(x + w * (0.35 + i * 0.035), y + d * (0.34 + i * 0.07),
          0.35, d * 0.085, z, z + 0.1, "#382e28", "crack");
      }
    }
  }
  return meshes;
}
