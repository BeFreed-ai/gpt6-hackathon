// Visible reflexes from delivered earthquake events, never invented decisions.
export function disasterEvents(state) {
  const events = new Map((state.events || []).map(e => [e.id,e]));
  // A 100-person disaster can overflow the recent event window in one snapshot.
  // Its durable intervention receipt still proves who experienced it.
  for (const receipt of state.interventions || []) {
    if (receipt.type !== 'earthquake' || events.has(receipt.event_id)) continue;
    events.set(receipt.event_id, {...receipt,id:receipt.event_id,target_ids:receipt.delivered_to});
  }
  return [...events.values()].sort((a,b)=>a.world_time-b.world_time);
}

export class EarthquakeReactions {
  constructor() { this.run = null; this.event = null; this.start = -Infinity; }
  update(state, now) {
    const fresh = this.run !== state.world.experiment_id;
    if (fresh) { this.run = state.world.experiment_id; this.event = null; this.start = -Infinity; }
    const quake = disasterEvents(state).reverse().find(e => e.type === 'earthquake');
    if (quake && quake.id !== this.event?.id) {
      this.event = quake;
      this.start = fresh ? -Infinity : now;
      this.recipients = new Set(quake.payload?.delivered_to || quake.target_ids || []);
    }
    this.time = state.world.time;
  }
  reaction(agent) {
    return agent.alive && this.event && this.recipients.has(agent.id)
      && this.time - this.event.world_time < 8
      && agent.current_action === 'reconsidering';
  }
  pose(agent) { return this.reaction(agent) ? 'flinch-0' : null; }
  draw(c, agent, now, reduced) {
    if (!this.reaction(agent)) return;
    const {x,y} = agent.position;
    const blink = reduced || now - this.start > 4000 || Math.floor(now / 220) % 2 === 0;
    c.fillStyle = '#593f31'; c.fillRect(Math.round(x)-2,Math.round(y)-35,5,10);
    c.fillStyle = blink ? '#fff0a3' : '#e5ad62';
    c.fillRect(Math.round(x)-1,Math.round(y)-34,3,5);
    c.fillRect(Math.round(x)-1,Math.round(y)-27,3,2);
  }
}
