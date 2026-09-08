// Observer-only animation state. Never sends an action, edits a citizen, or invents speech.
export const WASTE_REACTION_MS = 2400;

export function hasWasteContact(agent) {
  // Existing snapshots distinguish the person stepping from nearby witnesses.
  return agent.reaction_kind === "waste_contact" || agent.reaction === "Stepped in waste!";
}

export class WasteReactions {
  constructor() {
    this.run = null;
    this.seen = new Set();
    this.contacts = new Map();
    this.active = new Map();
  }

  update(state, now) {
    const run = state.world.experiment_id;
    const people = new Map(state.agents.filter(a => a.alive).map(a => [a.id, a]));
    const events = state.events || [];
    if (this.run !== run) {
      this.run = run;
      this.seen = new Set(events.map(e => e.id));
      this.contacts = new Map([...people].map(([id, a]) => [id, hasWasteContact(a)]));
      this.active.clear();
      return; // Loading/reloading a saved world never replays historical impacts.
    }
    const newlyHit = new Set();
    for (const event of events) {
      if (this.seen.has(event.id)) continue;
      this.seen.add(event.id);
      const age = state.world.time - event.world_time;
      if (event.type !== "stepped_in_waste" || age < 0 || age > 8) continue;
      for (const id of event.target_ids || []) if (people.has(id)) newlyHit.add(id);
    }
    for (const [id, agent] of people) {
      const contact = hasWasteContact(agent);
      // Public event feeds are bounded; a new contact flag covers a dropped event.
      if (newlyHit.has(id) || (contact && !this.contacts.get(id))) this.active.set(id, now);
      this.contacts.set(id, contact);
    }
    for (const [id, start] of this.active) {
      if (!people.has(id) || now - start >= WASTE_REACTION_MS) this.active.delete(id);
    }
    for (const id of this.contacts.keys()) if (!people.has(id)) this.contacts.delete(id);
    if (this.seen.size > 1000) this.seen = new Set(events.map(e => e.id));
  }

  pose(agent, now, reducedMotion = false) {
    const start = this.active.get(agent.id);
    const elapsed = start === undefined ? WASTE_REACTION_MS : Math.max(0, now - start);
    const active = agent.alive && elapsed < WASTE_REACTION_MS;
    const disgust = agent.alive && (active || hasWasteContact(agent));
    const recoil = active && !reducedMotion && elapsed < 900;
    return {
      disgust,
      phase: active && !reducedMotion ? Math.min(7, Math.floor(elapsed / 220)) : undefined,
      liftedFoot: recoil,
      lift: recoil ? Math.round(Math.sin(Math.PI * elapsed / 900) * 5) : 0,
      tilt: recoil ? Math.round(Math.sin(Math.PI * elapsed / 450) * 9) : 0,
      splash: active && elapsed < 1100,
      label: active ? "Stepped in waste" : "",
    };
  }
}

export function drawWaste(ctx, x, y, scale = 1, compression = 0) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);
  // Contact spreads the base and collapses height, with the bottom fixed on the street.
  ctx.translate(0, 5);
  ctx.scale(1 + compression * 0.65, 1 - compression * 0.72);
  ctx.translate(0, -5);
  for (const [color, left, top, width, height] of [
    ["#493624", -7, 2, 14, 3], ["#795033", -6, -1, 12, 4],
    ["#956340", -4, -4, 8, 4], ["#ac7e51", -2, -7, 4, 4],
    ["#cfaa74", -2, -4, 4, 1], ["#c29660", -4, 0, 6, 1],
  ]) { ctx.fillStyle = color; ctx.fillRect(left, top, width, height); }
  ctx.restore();
}

export function drawWasteSplash(ctx, x, y, scale = 1) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);
  ctx.fillStyle = "#956340";
  for (const [left, top, width, height] of [[-8, 0, 4, 2], [3, 1, 5, 2],
    [-11, -4, 2, 2], [9, -5, 2, 2], [5, -8, 2, 2]]) ctx.fillRect(left, top, width, height);
  ctx.restore();
}
