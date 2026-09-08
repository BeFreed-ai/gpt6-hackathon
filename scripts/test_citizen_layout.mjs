import test from "node:test";
import assert from "node:assert/strict";
import { citizenLayout } from "../web/citizen-layout.js";

test("rendering never moves residents away from their physical positions", () => {
  const people = Array.from({length: 100}, (_, i) => ({id: `citizen-${i}`, position: {x: (i % 14) * 65, y: 200}}));
  const before = structuredClone(people);
  const positions = citizenLayout(people, p => p);
  assert.equal(new Set(positions.map(p => p.id)).size, 100);
  for (const item of positions) assert.deepEqual(item.point, people.find(p => p.id === item.id).position);
  assert.deepEqual(people, before);
});

test("street-level close-ups use exact physical coordinates, including overlapping feet", () => {
  const people = [{id:"a",position:{x:10,y:20}},{id:"b",position:{x:10,y:20}}];
  for (const zoom of [10, 13, 14.5, 16, 17, 19]) {
    const layout = citizenLayout(people, p => p, zoom);
    for (const item of layout) assert.deepEqual(item.point, {x:10,y:20});
  }
});
