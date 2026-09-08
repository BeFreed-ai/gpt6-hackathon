// Depict recorded bodily events; housing and income never trigger an animation themselves.
export class StreetSanitation {
  constructor() { this.run = null; this.seen = new Set(); this.active = new Map(); }
  update(state, now) {
    const events = state.events || [];
    if (this.run !== state.world.experiment_id) {
      this.run = state.world.experiment_id; this.seen = new Set(events.map(e => e.id)); this.active.clear(); return;
    }
    for (const event of events) {
      if (this.seen.has(event.id)) continue;
      this.seen.add(event.id);
      if (event.type !== "waste" || !event.actor_id || state.world.time-event.world_time < 0 || state.world.time-event.world_time > 8) continue;
      const person = state.agents.find(a => a.id === event.actor_id && a.alive);
      if (!person) continue;
      const waste = state.objects.find(o => o.kind === "waste" && (o.id === event.payload?.object_id ||
        (!event.payload?.object_id && o.metadata?.created_at === event.world_time &&
          Math.hypot(o.position.x-event.position?.x,o.position.y-event.position?.y) < 1)));
      if (waste) this.active.set(person.id,{start:now,wasteId:waste.id});
    }
    for (const [id, effect] of this.active) if (now-effect.start >= 2400 ||
      !state.agents.some(a => a.id===id && a.alive) || !state.objects.some(o => o.id===effect.wasteId)) this.active.delete(id);
    if (this.seen.size > 1000) this.seen = new Set(events.map(e => e.id));
  }
  pose(agent, now, reduced = false) {
    const effect=this.active.get(agent.id);
    if (!effect) return null;
    return `relieve-${reduced?2:Math.min(6,Math.floor((now-effect.start)/340))}`;
  }
  growth(item, now, reduced = false) {
    const effect=[...this.active.values()].find(e=>e.wasteId===item.id);
    return !effect || reduced ? 1 : Math.max(.15,Math.min(1,(now-effect.start-250)/800));
  }
}
