import test from "node:test";
import assert from "node:assert/strict";
import { WasteReactions, WASTE_REACTION_MS } from "../web/waste-reactions.js";

const citizen = (id, reaction = "") => ({id, alive: true, reaction, speech: "", current_action: "walking"});
const state = (time, agents, events = [], run = "preview") => ({
  world: {experiment_id: run, time, paused: true}, agents, events,
});
const event = (id = "step-1", time = 1) => ({id, type: "stepped_in_waste", world_time: time, target_ids: ["a"]});

test("only the target recoils; repeated snapshots do not restart or decide actions", () => {
  const reactions = new WasteReactions();
  reactions.update(state(0, [citizen("a"), citizen("b")]), 0);
  const hit = citizen("a", "Stepped in waste!");
  const witness = citizen("b", "Saw someone step in waste");
  const next = state(1, [hit, witness], [event()]);
  const original = structuredClone(next);
  reactions.update(next, 100);
  assert.equal(reactions.pose(hit, 400).liftedFoot, true);
  assert.equal(reactions.pose(witness, 400).disgust, false);
  assert.equal(reactions.pose(hit, 400, true).lift, 0);
  assert.equal(reactions.pose(hit, 400, true).tilt, 0);
  reactions.update(next, 700);
  assert.equal(reactions.active.get("a"), 100);
  reactions.update(next, 100 + WASTE_REACTION_MS);
  assert.equal(reactions.pose(hit, 100 + WASTE_REACTION_MS).splash, false);
  assert.equal(reactions.pose(hit, 100 + WASTE_REACTION_MS).label, "");
  assert.deepEqual(next, original); // Visual effects never mutate authoritative data.
});

test("loading an existing event or changing worlds never replays an impact", () => {
  const reactions = new WasteReactions();
  const hit = citizen("a", "Stepped in waste!");
  reactions.update(state(2, [hit], [event()]), 0);
  assert.equal(reactions.pose(hit, 1).splash, false);
  reactions.update(state(3, [hit], [event("step-2", 3)]), 100);
  assert.equal(reactions.pose(hit, 101).splash, true);
  reactions.update(state(3, [hit], [event("step-2", 3)], "other-world"), 200);
  assert.equal(reactions.pose(hit, 201).splash, false);
});

test("bounded event feeds still show newly affected citizens and new contacts can repeat", () => {
  const reactions = new WasteReactions();
  const hit = citizen("a", "Stepped in waste!");
  reactions.update(state(0, [citizen("a")]), 0);
  reactions.update(state(1, [hit]), 100);
  assert.equal(reactions.pose(hit, 101).splash, true);
  reactions.update(state(10, [citizen("a")]), 3000);
  assert.equal(reactions.pose(citizen("a"), 3001).disgust, false);
  reactions.update(state(30, [hit], [event("step-2", 30)]), 4000);
  assert.equal(reactions.pose(hit, 4001).splash, true);
  reactions.update(state(31, [{...hit, alive: false}]), 4100);
  assert.equal(reactions.active.size, 0);
});

test("stale event history does not animate a citizen whose reaction has ended", () => {
  const reactions = new WasteReactions();
  reactions.update(state(10, [citizen("a")]), 0);
  reactions.update(state(11, [citizen("a")], [event("old", 1)]), 100);
  assert.equal(reactions.active.size, 0);
});
