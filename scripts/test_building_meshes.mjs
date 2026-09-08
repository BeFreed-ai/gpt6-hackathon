import test from "node:test";
import assert from "node:assert/strict";
import { buildingMeshes } from "../web/building-meshes.js";

const polygon = (x, y, w, d) => ({type: "Polygon", coordinates: [[[x,y], [x+w,y], [x+w,y+d], [x,y+d], [x,y]]]});
const site = {id: "home-1", kind: "home", position: {x: 40, y: 80},
  structure: {width: 16, depth: 16, height: 20, floors: 4, seed: 123, state: "intact", integrity: 100}};

test("persistent meshes change topology and heights, not just a marker color", () => {
  const intact = buildingMeshes([site], polygon);
  const broken = {...site, structure: {...site.structure, state: "collapsed", integrity: 0}};
  const rubble = buildingMeshes([broken], polygon);
  assert.equal(intact.filter(f => f.properties.part === "rubble").length, 0);
  assert.equal(rubble.filter(f => f.properties.part === "rubble").length, 22);
  assert.ok(Math.max(...rubble.map(f => f.properties.height)) < 6);
  assert.ok(Math.max(...intact.map(f => f.properties.height)) > 20);
  assert.deepEqual(rubble, buildingMeshes([broken], polygon));
  assert.deepEqual(intact, buildingMeshes([{...broken, structure: site.structure}], polygon));
  for (const mesh of [...intact, ...rubble]) {
    assert.ok(mesh.properties.height >= mesh.properties.base);
    assert.equal(mesh.geometry.type, "Polygon");
  }
});

test("collapse interpolation ends at the same saved ruin", () => {
  const broken = {...site, structure: {...site.structure, state: "collapsed", integrity: 0}};
  const initial = buildingMeshes([broken], polygon, new Set([site.id]), 0);
  const final = buildingMeshes([broken], polygon, new Set([site.id]), 1);
  assert.equal(initial.find(f => f.properties.part === "wall").properties.height, 20);
  assert.deepEqual(final, buildingMeshes([broken], polygon));
});
