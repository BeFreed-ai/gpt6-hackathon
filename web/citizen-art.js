// Presentation only: poses depict existing actions or confirmed physical events.
export const DETAIL_SCALE = ["interpolate", ["linear"], ["zoom"], 14, 0.42, 17, 0.65, 19, 1.4, 21, 3];
export const POSES = ["idle", "disgust", ...Array.from({length: 8}, (_, i) => `walk-${i}`),
  ...Array.from({length: 8}, (_, i) => `contact-${i}`),
  ...Array.from({length: 4}, (_, i) => `talk-${i}`),
  ...Array.from({length: 8}, (_, i) => `fall-${i}`)];

export function citizenPose(agent, reaction, now, paused, reduced) {
  if (reaction.phase !== undefined && !reduced) return `contact-${reaction.phase}`;
  if (reaction.disgust) return "disgust";
  if (paused || reduced) return "idle";
  if (/walking|commuting|going|seeking/.test(agent.current_action || "")) return `walk-${Math.floor(now / 110) % 8}`;
  if (agent.speech) return `talk-${Math.floor(now / 200) % 4}`;
  return "idle";
}

// Foot anchor (0,0); separate limbs and face remain legible at close zoom.
export function drawCitizen(c, x, y, scale = 1, pose = "idle", facing = 1) {
  c.save(); c.translate(x, y); c.scale(scale, scale);
  c.scale(facing < 0 ? -1 : 1, 1);
  const index = Number(pose.split("-")[1] || 0);
  const contact = pose.startsWith("contact-");
  const falling = pose.startsWith("fall-");
  const disgust = contact || pose === "disgust";
  const walk = pose.startsWith("walk-") ? Math.sin(index * Math.PI / 4) : 0;
  const recoil = contact ? [0, 0.25, 0.7, 1, 1, 0.8, 0.4, 0][index] : 0;
  const social = pose.split("-")[0];
  const squat = social === "relieve" ? [0,.5,1,1,1,.6,0][index] : 0;
  const reach = ["give","receive","help","offer","agree","strike","work","clean","cook","collect","dress"].includes(social) ? [0.2,0.7,1,.5][index] : 0;
  if (falling) { c.translate(index * 1.5, -2); c.rotate(index / 7 * Math.PI / 2); }
  c.translate(-recoil * 3, -Math.abs(walk));
  c.translate(0, squat * 12);
  if (social === "flinch") { c.translate(-4,-1); c.rotate(-.13); }
  const line = (color, width, points) => {
    c.strokeStyle = color; c.lineWidth = width; c.lineCap = "round"; c.lineJoin = "round";
    c.beginPath(); points.forEach(([px, py], i) => i ? c.lineTo(px, py) : c.moveTo(px, py)); c.stroke();
  };
  const limb = points => { line("#564830", 7, points); line("#eec044", 4, points); };
  const talk = pose.startsWith("talk-") ? Math.sin(index * Math.PI / 2) * 5 : 0;
  limb([[-8,-24],[-16,-18-recoil*12],[-19-walk*2,-13-recoil*23-talk]]);
  limb([[8,-24],[16+reach*3,-18-recoil*11],[19+walk*2+reach*7,-13-recoil*23+talk-reach*6]]);
  if (social === "decline") limb([[8,-24],[16,-24],[16,-34]]);
  if (social === "eat") limb([[8,-24],[19,-29],[10,-34-index*2]]);
  limb([[-5,-13],[-6-walk*3-squat*7,-7-squat*12],[-7-walk*5-squat*5,-2-squat*12]]);
  limb([[5,-13],[7+walk*2+squat*7,-7-recoil*7-squat*12],[8+walk*5+recoil*6+squat*5,-2-recoil*15-squat*12]]);
  line("#414443", 6, [[-10-walk*5-squat*5,-2-squat*12],[-5-walk*5-squat*5,-2-squat*12]]);
  line("#414443", 6, [[6+walk*5+recoil*6+squat*5,-2-recoil*15-squat*12],[12+walk*5+recoil*6+squat*5,-2-recoil*15-squat*12]]);
  if (contact) line("#805235", 3, [[7+recoil*6,-recoil*15],[13+recoil*6,-recoil*15]]);
  c.fillStyle = "#3c686e"; c.fillRect(-10,-29,20,17);
  c.fillStyle = "#76aaa5"; c.fillRect(-8,-28,16,10);
  c.fillStyle = "#c3d4ad"; c.fillRect(-5,-26,3,3); c.fillRect(3,-26,3,3);
  c.save(); c.translate(0,-40); c.rotate(recoil * -0.16);
  limb([[-9,-9],[-11,-21]]); limb([[9,-9],[11,-21]]);
  c.fillStyle = "#6b552e"; c.beginPath(); c.ellipse(0,0,17,17,0,0,Math.PI*2); c.fill();
  c.fillStyle = "#f5cf4e"; c.beginPath(); c.ellipse(0,-1,15,15,0,0,Math.PI*2); c.fill();
  c.fillStyle = "#ffe99b"; c.beginPath(); c.ellipse(-6,-8,5,3,-.5,0,Math.PI*2); c.fill();
  if (social === "rest") {
    line("#343c32",2,[[-10,0],[-4,0]]);line("#343c32",2,[[4,0],[10,0]]);
    line("#77532f",2,[[-3,8],[3,8]]);
  } else if (disgust || falling || social === "flinch" || squat) {
    line("#343c32",2,[[-10,-3],[-5,0],[-10,2]]); line("#343c32",2,[[10,-3],[5,0],[10,2]]);
    line("#6b4630",2,[[-5,8],[-1,6],[5,8]]);
    c.fillStyle="#a6a74e"; c.fillRect(8,5,4,3);
  } else {
    c.fillStyle="#fff4c9"; c.fillRect(-10,-4,6,8); c.fillRect(4,-4,6,8);
    c.fillStyle="#333e35"; c.fillRect(-7,-2,3,5); c.fillRect(4,-2,3,5);
    line("#77532f",2,[[-3,8],[3,8+Math.abs(talk)/3]]);
  }
  c.restore();
  // Simple tools follow the acting hand; they convey the confirmed action only.
  if (social === "eat") {c.fillStyle='#b55339';c.beginPath();c.arc(11,-35-index*2,4,0,Math.PI*2);c.fill();}
  if (social === "work") {line('#8d623d',3,[[20+reach*7,-18],[24+reach*7,-32]]);line('#64736d',6,[[19+reach*7,-32],[29+reach*7,-32]]);}
  if (social === "clean") {line('#947443',3,[[20+reach*7,-27],[12+reach*7,0]]);c.fillStyle='#bd9e58';c.fillRect(7+reach*7,-3,13,5);}
  if (social === "cook") {c.fillStyle='#697b72';c.fillRect(16+reach*7,-20,15,5);line('#71503a',2,[[24+reach*7,-21],[28+reach*7,-33]]);}
  if (social === "collect") {c.fillStyle='#b8955c';c.fillRect(20+reach*7,-20,8,8);}
  c.restore();
}

export function wasteStamp(item) {
  const stamps = Object.entries(item.metadata || {}).filter(([key, value]) => key.startsWith("step_") && Number.isFinite(value));
  return stamps.length ? Math.max(...stamps.map(([, value]) => value)) : null;
}

export function confirmedTrauma(item, state) {
  const id = item.metadata?.citizen_id;
  const cause = item.metadata?.death_cause || state.agents?.find(a => a.id === id)?.death_cause;
  if (cause) return ["earthquake", "attack"].includes(cause);
  // Compatibility with an already-running server: use its explicit casualty receipt.
  return (state.interventions || []).some(event => event.type === "earthquake" && event.killed?.includes(id));
}

export class PhysicalEffects {
  constructor() { this.run = null; this.stamps = new Map(); this.impacts = new Map(); this.deaths = new Map(); }
  update(state, now) {
    const fresh = this.run !== state.world.experiment_id;
    if (fresh) { this.run = state.world.experiment_id; this.stamps.clear(); this.impacts.clear(); this.deaths.clear(); }
    const ids = new Set();
    for (const item of state.objects || []) {
      ids.add(item.id);
      if (item.kind === "waste") {
        const stamp = wasteStamp(item);
        if (!fresh && stamp !== null && stamp !== this.stamps.get(item.id) && state.world.time - stamp <= 8) this.impacts.set(item.id, now);
        this.stamps.set(item.id, stamp);
      }
      if (item.kind === "remains" && !this.deaths.has(item.id)) this.deaths.set(item.id, fresh ? -Infinity : now);
    }
    for (const table of [this.stamps, this.impacts, this.deaths]) for (const id of table.keys()) if (!ids.has(id)) table.delete(id);
  }
  compression(item, now, reduced = false) {
    if (wasteStamp(item) === null) return 0;
    const start = this.impacts.get(item.id);
    return reduced || start === undefined ? 1 : Math.min(1, Math.max(0, (now - start) / 300));
  }
  fall(item, now, reduced = false) {
    return reduced ? 7 : Math.min(7, Math.max(0, Math.floor((now - (this.deaths.get(item.id) ?? -Infinity)) / 120)));
  }
  animating(now) { return [...this.impacts.values(), ...this.deaths.values()].some(start => now - start < 1500); }
}

export function drawImpact(c, x, y, scale, frame, bloody) {
  c.save(); c.translate(x,y); c.scale(scale,scale);
  if (bloody) { c.fillStyle="#933f36"; c.beginPath(); c.ellipse(2,0,11,3,0,0,Math.PI*2); c.fill(); }
  if (frame < 7) for (let i=0;i<12;i++) {
    const angle=i*2.4, radius=3+frame*2.6+(i%3)*2;
    c.fillStyle=bloody && i%3===0 ? "#a83d32" : "#b9a78e";
    c.globalAlpha=1-frame/9;
    c.fillRect(Math.cos(angle)*radius,Math.sin(angle)*radius*.45-frame, i%3===0?3:4, 2);
  }
  c.restore();
}
