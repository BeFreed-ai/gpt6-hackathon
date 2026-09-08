// Observer presentation of completed interactions, never an action planner.
export const SOCIAL_TYPES = new Set(["speech", "give", "help", "attack", "offer", "agreement"]);
export const SOCIAL_DURATION = 1800;

export class CitizenInteractions {
  constructor() { this.run = null; this.seen = new Set(); this.active = new Map(); this.people = new Map(); }
  update(state, now) {
    this.people = new Map(state.agents.filter(a => a.alive).map(a => [a.id, a]));
    const events = state.events || [];
    if (this.run !== state.world.experiment_id) {
      this.run = state.world.experiment_id; this.seen = new Set(events.map(e => e.id)); this.active.clear(); return;
    }
    for (const event of events) {
      if (this.seen.has(event.id)) continue;
      this.seen.add(event.id);
      const age = state.world.time - event.world_time;
      if (!SOCIAL_TYPES.has(event.type) || age < 0 || age > 10 || !this.people.has(event.actor_id)) continue;
      const targetId = event.target_ids?.find(id => id !== event.actor_id && this.people.has(id));
      if (targetId) this.active.set(event.id, {event, targetId, start: now});
    }
    for (const [id, effect] of this.active) if (now-effect.start >= SOCIAL_DURATION ||
      !this.people.has(effect.event.actor_id) || !this.people.has(effect.targetId)) this.active.delete(id);
    if (this.seen.size > 1000) this.seen = new Set(events.map(e => e.id));
  }
  pose(agent, now, reduced = false) {
    const effect = [...this.active.values()].reverse().find(e => e.event.actor_id === agent.id || e.targetId === agent.id);
    if (!effect) return null;
    const actor = effect.event.actor_id === agent.id;
    const other = this.people.get(actor ? effect.targetId : effect.event.actor_id);
    const frame = reduced ? 2 : Math.min(3, Math.floor((now-effect.start)/220));
    let kind = null;
    if (actor) kind = {speech:"talk",give:"give",help:"help",attack:"strike",offer:"offer",
      agreement:effect.event.payload?.status === "accepted" ? "agree" : "decline"}[effect.event.type];
    else kind = {give:"receive",attack:"flinch"}[effect.event.type] || null;
    // Listening is not automatic agreement; recipients choose their next action themselves.
    return {pose: kind ? `${kind}-${frame}` : null, facing: other.position.x < agent.position.x ? -1 : 1, targetId: other.id};
  }
  draw(c, project, now, reduced = false, scale = 1) {
    for (const effect of this.active.values()) {
      const a=this.people.get(effect.event.actor_id), b=this.people.get(effect.targetId);
      if (!a || !b) continue;
      const from=project(a.position), to=project(b.position);
      const t=reduced ? 1 : Math.min(1, Math.max(0,(now-effect.start)/900));
      const direction=to.x<from.x?-1:1;
      const x=from.x+(to.x-from.x)*t, y=from.y+(to.y-from.y)*t-9*scale-Math.sin(t*Math.PI)*8*scale;
      c.save();
      if (effect.event.type === "give") {
        c.fillStyle="#795538";c.fillRect(x-3*scale,y-3*scale,6*scale,6*scale);
        c.fillStyle="#e0b968";c.fillRect(x-2*scale,y-2*scale,4*scale,4*scale);
        c.fillStyle="#faf0c8";c.fillRect(x-scale,y-3*scale,scale,6*scale);
      } else if (["offer","agreement"].includes(effect.event.type)) {
        const px=from.x+direction*12*scale, py=from.y-15*scale;
        c.fillStyle="#faf0d0";c.fillRect(px-3*scale,py-4*scale,6*scale,8*scale);
        c.fillStyle=effect.event.type==="offer"?"#8d784e":effect.event.payload?.status==="accepted"?"#48845a":"#a45643";
        c.fillRect(px-2*scale,py-scale,4*scale,scale);c.fillRect(px-2*scale,py+scale,3*scale,scale);
      } else if (effect.event.type === "help") {
        c.fillStyle="#eee5bd";c.fillRect(to.x-4*scale,to.y-21*scale,8*scale,8*scale);
        c.fillStyle="#53885c";c.fillRect(to.x-scale,to.y-20*scale,2*scale,6*scale);c.fillRect(to.x-3*scale,to.y-18*scale,6*scale,2*scale);
      } else if (effect.event.type === "attack" && t < 1 && !reduced) {
        c.strokeStyle="#ecc274";c.lineWidth=scale;
        for (let i=0;i<5;i++) {const angle=i*Math.PI*2/5;c.beginPath();c.moveTo(to.x,to.y-12*scale);
          c.lineTo(to.x+Math.cos(angle)*7*scale,to.y-12*scale+Math.sin(angle)*7*scale);c.stroke();}
      }
      c.restore();
    }
  }
}
