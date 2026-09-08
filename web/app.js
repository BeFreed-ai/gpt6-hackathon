import { PixelWorld } from "/static/pixel-world.js";

const canvas = document.querySelector("#world-canvas");
const renderer = new PixelWorld(canvas);
const canvasWrap = document.querySelector("#canvas-wrap");

let state = null;
let selectedAgentId = null;
let selectedTool = null;
let selectedTile = null;
let agentDetail = null;
let socket = null;
let reconnectTimer = null;
let hoveredAgentId = null;
let drag = null;
let wasDragged = false;
let statusTimer = null;
let pointer = { x: 0, y: 0 };


function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${location.host}/ws`);
  socket.addEventListener("open", () => {
    document.querySelector("#connection-dot").classList.add("online");
    socket.send("observer-ready");
  });
  socket.addEventListener("message", (event) => {
    state = JSON.parse(event.data);
    updateHud();
    updateFeed();
    updateEconomy();
    if (selectedAgentId) refreshAgentDetail();
  });
  socket.addEventListener("close", () => {
    document.querySelector("#connection-dot").classList.remove("online");
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 1200);
  });
}

function resizeCanvas() {
  renderer.resize();
}

function screenPoint(position) {
  return renderer.screenPoint(position);
}

function worldPoint(x, y) {
  return renderer.worldPoint(x, y);
}

function drawWorld() {
  requestAnimationFrame(drawWorld);
  renderer.draw(state, selectedAgentId, hoveredAgentId,
    selectedTool === "build" ? { position: worldPoint(pointer.x, pointer.y), tile: selectedTile } : null);
}

function updateHud() {
  document.querySelector("#world-time").textContent = state.world.time_of_day;
  document.querySelector("#weather").textContent = state.world.weather.toUpperCase();
  const mode = state.stats.brain_error
    ? "ASTRA / DEGRADED"
    : state.stats.brain_mode === "astra"
      ? state.stats.astra_decisions > 0 ? "ASTRA / LIVE" : "ASTRA / CONNECTING"
      : "RULE DEMO / NO LLM";
  document.querySelector("#brain-mode").textContent = mode;
  document.querySelector("#brain-mode").style.color = state.stats.brain_mode === "astra" ? "#526d43" : "#aa593d";
  document.querySelector("#stat-population").textContent = state.stats.population;
  document.querySelector("#stat-unhoused").textContent = state.stats.unhoused;
  document.querySelector("#stat-waste").textContent = state.stats.waste;
  document.querySelector("#stat-events").textContent = state.stats.companies || 0;
  document.querySelector("#play-pause").textContent = state.world.paused ? "▶" : "Ⅱ";
  document.querySelector("#play-pause").setAttribute("aria-label", state.world.paused ? "Play simulation" : "Pause simulation");
  document.querySelectorAll(".speed-button").forEach(button => button.classList.toggle("active", Number(button.dataset.speed) === state.world.speed));
  document.querySelector("#world-day").textContent = `DAY ${String(Math.floor(state.world.time / (state.world.day_length || 720)) + 1).padStart(2, "0")}`;
}

function updateFeed() {
  const feed = document.querySelector("#event-feed");
  const events = [...state.events].reverse();
  feed.innerHTML = events.map((event) => {
    const clock = (8 * 60 + event.world_time / (state.world.day_length || 720) * 1440) % 1440;
    const minutes = String(Math.floor(clock / 60)).padStart(2, "0");
    const seconds = String(Math.floor(clock % 60)).padStart(2, "0");
    return `<article class="feed-event ${escapeHtml(event.type)}"><time>${minutes}:${seconds}</time><p>${escapeHtml(event.public_text)}</p></article>`;
  }).join("");
}

async function refreshAgentDetail() {
  try {
    const response = await fetch(`/api/agents/${selectedAgentId}`);
    if (!response.ok) return;
    agentDetail = await response.json();
    renderAgentDetail();
  } catch (_) {
    // The live socket will retry and the next snapshot will refresh this view.
  }
}

function renderAgentDetail() {
  if (!agentDetail) return;
  document.querySelector("#empty-inspector").classList.add("hidden");
  document.querySelector("#agent-inspector").classList.remove("hidden");
  document.querySelector("#agent-id").textContent = agentDetail.id.toUpperCase();
  document.querySelector("#agent-name").textContent = agentDetail.name;
  document.querySelector("#agent-status").textContent = `${agentDetail.current_action}${agentDetail.is_thinking ? " / thinking" : ""}`;
  document.querySelector("#decision-source").textContent = `Decisions: ${agentDetail.last_decision_source === "astra" ? "ASTRA" : agentDetail.last_decision_source === "local" ? "RULE DEMO" : "WAITING"} / ${agentDetail.decision_count || 0} turns`;
  document.querySelector("#action-result").textContent = agentDetail.last_action_result || "";
  document.querySelector("#agent-thought").textContent = agentDetail.thought || "No thought has been expressed yet.";
  document.querySelector("#agent-goal").textContent = agentDetail.active_goal?.statement || "No committed goal yet";
  document.querySelector("#agent-goal-reason").textContent = agentDetail.active_goal?.reason || "This citizen is still deciding what matters.";
  document.querySelector("#health-meter").style.width = `${agentDetail.health}%`;
  document.querySelector("#energy-meter").style.width = `${agentDetail.energy}%`;
  document.querySelector("#hunger-meter").style.width = `${agentDetail.hunger}%`;
  document.querySelector("#stress-meter").style.width = `${agentDetail.stress}%`;
  document.querySelector("#agent-home").textContent = agentDetail.home || "No stable housing";
  document.querySelector("#agent-work").textContent = agentDetail.workplace || "No current workplace";
  document.querySelector("#agent-credits").textContent = agentDetail.credits.toFixed(1);
  document.querySelector("#agent-warmth").textContent = `${Math.round(agentDetail.warmth || 0)}%${agentDetail.wearing_coat ? " / coat equipped" : ""}`;
  document.querySelector("#agent-inventory").textContent = agentDetail.inventory_items?.map(item => item.name).join(", ") || "Empty";
  const businesses = agentDetail.economy?.my_businesses || [];
  const offers = agentDetail.economy?.my_offers || [];
  document.querySelector("#agent-business").innerHTML = businesses.map(companyCard).join("") + offers.slice(-5).reverse().map(offer => `<article class="business-card"><strong>${escapeHtml(offer.kind)} / ${escapeHtml(offer.status)}</strong><p>${escapeHtml(citizenName(offer.sender_id))} → ${escapeHtml(citizenName(offer.recipient_id))}</p><small>${offer.amount.toFixed(1)} credits${offer.kind === "investment" ? ` · ${(offer.equity * 100).toFixed(1)}% equity` : ""}</small></article>`).join("") || '<p class="muted">No business or agreements yet. Ambitions are theirs to choose.</p>';
  document.querySelector("#agent-values").innerHTML = agentDetail.values.length
    ? agentDetail.values.map((value) => `<span class="chip">${escapeHtml(value)}</span>`).join("")
    : '<span class="chip">Not expressed yet</span>';
  document.querySelector("#memory-count").textContent = `${agentDetail.memories.length} recalled`;
  document.querySelector("#agent-memories").innerHTML = [...agentDetail.memories].reverse().slice(0, 24).map((memory) => (
    `<article class="memory ${memory.importance >= 0.7 ? "high" : ""}">
      <p>${escapeHtml(memory.content)}</p>
      <small>${escapeHtml(memory.source_type)} · confidence ${Math.round(memory.confidence * 100)}%</small>
    </article>`
  )).join("") || '<p class="muted">No personal memories yet.</p>';
}

function citizenName(id) {
  return state?.agents.find(agent => agent.id === id)?.name || id;
}

function companyCard(company) {
  const ownership = Object.entries(company.shares).map(([id, share]) => `${citizenName(id)} ${(share * 100).toFixed(1)}%`).join(" · ");
  return `<article class="business-card"><span class="eyebrow">${escapeHtml(company.product)} / ${escapeHtml(citizenName(company.founder_id))}</span><h3>${escapeHtml(company.name)}</h3><p>${escapeHtml(company.purpose)}</p><div class="business-numbers"><span>Treasury <b>${company.treasury.toFixed(1)}</b></span><span>Raised <b>${company.raised.toFixed(1)}</b></span><span>Stock <b>${company.stock}</b></span><span>Sales <b>${company.revenue.toFixed(1)}</b></span></div><small>${escapeHtml(ownership)}</small><p class="muted">${Object.keys(company.employees).length} hired · ${company.produced} made · ${company.price.toFixed(1)} credits each</p></article>`;
}

function updateEconomy() {
  document.querySelector("#player-messages").innerHTML = [...(state.player_messages || [])].reverse().slice(0, 8).map(event => `<article class="business-card"><strong>${escapeHtml(citizenName(event.actor_id))}</strong><p>${escapeHtml(event.payload.message)}</p></article>`).join("") || '<p class="muted">No one has chosen to address you yet.</p>';
  document.querySelector("#intervention-log").innerHTML = [...(state.interventions || [])].reverse().slice(0, 6).map(item => `<article class="business-card"><strong>${escapeHtml(item.type.toUpperCase())}</strong><p>${item.killed.length} killed · ${item.injured.length} injured · ${item.delivered_to.length} noticed</p><small>${item.followups.length ? item.followups.map(f => `${escapeHtml(citizenName(f.agent_id))}: ${escapeHtml(f.action)}${f.reply_to_event_id ? " (linked response)" : " (next decision)"}`).join("<br>") : "Awaiting their next decisions"}</small></article>`).join("") || '<p class="muted">The city lives without your intervention. Change something to observe what follows.</p>';
  const companies = state.economy?.companies || [];
  document.querySelector("#economy-summary").textContent = `${companies.length} businesses · ${(state.stats.capital_raised || 0).toFixed(1)} credits invested`;
  document.querySelector("#company-list").innerHTML = companies.map(companyCard).join("") || '<div class="business-card"><h3>Room for an idea</h3><p>Citizens can found a company, negotiate funding, hire and make useful things. No founder role is assigned.</p></div>';
  document.querySelector("#facility-list").innerHTML = state.objects.filter(item => ["dining", "kitchen", "toilet", "shelter", "launchpad", "market", "cafe", "depot", "garden", "bench"].includes(item.kind)).map(item => {
    const meta = item.metadata;
    const details = [meta.stock !== undefined ? `${meta.stock} ${item.kind === "depot" ? "materials" : "meals"}` : null, meta.price !== undefined ? meta.price === 0 ? "Free" : `${meta.price} credits` : null, `${item.in_use || 0}/${meta.capacity || meta.beds || 2} in use`, meta.condition !== undefined ? `${Math.round(meta.condition)}% condition` : null].filter(Boolean).join(" · ");
    return `<article class="facility-card"><div><strong>${escapeHtml(item.name)}</strong><span class="facility-status ${item.open_now ? "" : "closed"}">${item.open_now ? "OPEN" : "CLOSED"}</span></div><p>${escapeHtml(details)}</p><small>${meta.hours ? `${meta.hours[0]}:00–${meta.hours[1]}:00` : "Open all day"}</small></article>`;
  }).join("");
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value);
  return element.innerHTML;
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    showStatus(error.detail || "That action failed. Please try again.");
    throw new Error(error.detail || "Action failed");
  }
  const result = await response.json();
  if (path === "/api/intervene") {
    const impact = result.killed?.length || result.injured?.length ? ` ${result.killed.length} killed / ${result.injured.length} injured.` : "";
    showStatus(`${payload.type === "broadcast" ? "Signal sent" : "World changed"}.${impact} ${result.delivered_to?.length || 0} citizens noticed.${result.paused ? " Simulation paused — press play to let them respond." : " Watch their responses in City Life."}`);
  }
  return result;
}

function showStatus(message) {
  clearTimeout(statusTimer);
  const status = document.querySelector("#interaction-status");
  status.textContent = message;
  status.classList.remove("hidden");
  statusTimer = setTimeout(() => status.classList.add("hidden"), 14000);
}

document.querySelector("#broadcast-cancel").addEventListener("click", () => document.querySelector("#broadcast-dialog").close());
document.querySelector("#broadcast-form").addEventListener("submit", async event => {
  event.preventDefault();
  const message = document.querySelector("#broadcast-message").value.trim();
  if (!message) return;
  try {
    await postJson("/api/intervene", { type: "broadcast", message });
    document.querySelector("#broadcast-dialog").close();
    showPanel("events");
  } catch (_) { /* postJson displays the failure. */ }
});

canvas.addEventListener("mousemove", (event) => {
  const rectangle = canvas.getBoundingClientRect();
  const nextPointer = { x: event.clientX - rectangle.left, y: event.clientY - rectangle.top };
  if (drag) {
    const dx = nextPointer.x - pointer.x, dy = nextPointer.y - pointer.y;
    if (Math.hypot(nextPointer.x - drag.x, nextPointer.y - drag.y) > 4) wasDragged = true;
    if (wasDragged) renderer.pan(dx, dy);
  }
  pointer = nextPointer;
  const hit = state?.agents.filter(agent => agent.alive).find(agent => {
    const point = screenPoint(renderer.positions.get(agent.id) || agent.position);
    return Math.hypot(point.x - pointer.x, point.y - pointer.y) < Math.max(14, 24 * renderer.view.scale);
  });
  hoveredAgentId = hit?.id || null;
  canvas.style.cursor = drag ? "grabbing" : selectedTool ? "crosshair" : hit ? "pointer" : "grab";
  const hoveredObject = !hit && state?.objects.find(item => {
    const point = worldPoint(pointer.x, pointer.y);
    return Math.abs(item.position.x - point.x) < item.width / 2 && Math.abs(item.position.y - point.y) < item.height / 2;
  });
  document.querySelector("#map-location").textContent = hit ? `${hit.name} / ${hit.current_action}` : hoveredObject ? hoveredObject.name : "SAN FRANCISCO / A SMALL WORLD";
  if (!hit && !hoveredObject && state?.terrain) {
    const point = worldPoint(pointer.x, pointer.y);
    const tile = state.terrain.tiles.find(tile => tile.cell[0] === Math.floor(point.x / 20) && tile.cell[1] === Math.floor(point.y / 20));
    if (tile) document.querySelector("#map-location").textContent = `${tile.kind.toUpperCase()} / ${tile.message || (tile.builder_id ? citizenName(tile.builder_id) : "City infrastructure")}`;
  }
});

canvas.addEventListener("click", async (event) => {
  if (!state || wasDragged) return;
  const rectangle = canvas.getBoundingClientRect();
  const click = { x: event.clientX - rectangle.left, y: event.clientY - rectangle.top };
  const position = worldPoint(click.x, click.y);
  if (position.x < 0 || position.x > state.world.width || position.y < 0 || position.y > state.world.height) return;
  if (selectedTool) {
    try {
      const victim = selectedTool === "kill" ? state.agents.filter(a => a.alive).find(a => {
        const point = screenPoint(renderer.positions.get(a.id) || a.position);
        return Math.hypot(point.x - click.x, point.y - click.y) <= Math.max(13, 24 * renderer.view.scale);
      }) : null;
      if (selectedTool === "kill" && !victim) {
        showStatus("Click a living citizen. This tool targets one citizen only.");
        return;
      }
      await postJson("/api/intervene", { type: selectedTool, position, tile: selectedTile, target_id: victim?.id });
      if (selectedTool !== "build") clearTool();
    } catch (_) { /* The status describes the failed placement. */ }
    return;
  }
  const hit = state.agents.find((agent) => {
    const point = screenPoint(renderer.positions.get(agent.id) || agent.position);
    return Math.hypot(point.x - click.x, point.y - click.y) <= Math.max(13, 24 * renderer.view.scale);
  });
  if (hit) {
    selectedAgentId = hit.id;
    await refreshAgentDetail();
    showPanel("citizen");
  } else {
    const place = state.objects.find(item => Math.abs(item.position.x - position.x) < item.width / 2 && Math.abs(item.position.y - position.y) < item.height / 2);
    if (place) {
      showPanel("economy");
      showStatus(`${place.name}${place.open_now === false ? " / CLOSED" : ""}`);
    }
  }
});

document.querySelector("#play-pause").addEventListener("click", async () => {
  if (!state) return;
  await postJson("/api/control", { action: state.world.paused ? "play" : "pause" });
});

document.querySelectorAll(".speed-button").forEach((button) => {
  button.addEventListener("click", async () => {
    const speed = Number(button.dataset.speed);
    await postJson("/api/control", { action: "speed", speed });
    document.querySelectorAll(".speed-button").forEach((item) => item.classList.toggle("active", item === button));
  });
});

document.querySelectorAll(".tool-button").forEach((button) => {
  button.addEventListener("click", async () => {
    const tool = button.dataset.tool;
    if (tool === "fog") {
      await postJson("/api/intervene", { type: "fog" });
      clearTool();
      return;
    }
    if (tool === "broadcast") {
      clearTool();
      document.querySelector("#broadcast-mode-note").textContent = state?.stats.brain_mode === "astra"
        ? "Astra is active. Citizens may question, discuss or act on the claim."
        : "Rule demo only: citizens can notice a signal but cannot interpret free-form language. Configure Astra for real responses.";
      document.querySelector("#broadcast-dialog").showModal();
      return;
    }
    selectedTool = selectedTool === tool ? null : tool;
    document.querySelector("#tool-hint").textContent = tool === "kill"
      ? "KILL / click a citizen · permanent for this run · ESC to cancel"
      : tool === "lightning" ? "LIGHTNING / direct hit kills · nearby citizens can be injured · ESC to cancel"
      : "Click the map to intervene · ESC to cancel";
    document.querySelectorAll(".tool-button").forEach((item) => item.classList.toggle("active", item.dataset.tool === selectedTool));
    document.querySelector("#tool-hint").classList.toggle("hidden", !selectedTool);
  });
});

function clearTool() {
  selectedTool = null;
  selectedTile = null;
  document.querySelector("#build-tool").value = "";
  document.querySelectorAll(".tool-button").forEach((item) => item.classList.remove("active"));
  document.querySelector("#tool-hint").classList.add("hidden");
}

document.querySelector("#build-tool").addEventListener("change", event => {
  const tile = event.target.value;
  clearTool();
  if (!tile) return;
  selectedTile = tile;
  selectedTool = "build";
  event.target.value = tile;
  document.querySelector("#tool-hint").textContent = `${tile.toUpperCase()} / click tiles to edit · ESC to stop`;
  document.querySelector("#tool-hint").classList.remove("hidden");
});

document.querySelectorAll(".panel-tab").forEach((button) => {
  button.addEventListener("click", () => showPanel(button.dataset.panel));
});

function showPanel(panel) {
  document.querySelectorAll(".panel-tab").forEach((button) => button.classList.toggle("active", button.dataset.panel === panel));
  document.querySelector("#citizen-panel").classList.toggle("hidden", panel !== "citizen");
  document.querySelector("#events-panel").classList.toggle("hidden", panel !== "events");
  document.querySelector("#economy-panel").classList.toggle("hidden", panel !== "economy");
}

canvas.addEventListener("mousedown", event => {
  if (event.button !== 0) return;
  wasDragged = false;
  if (selectedTool) return;
  const rectangle = canvas.getBoundingClientRect();
  pointer = { x: event.clientX - rectangle.left, y: event.clientY - rectangle.top };
  drag = { ...pointer };
});
window.addEventListener("mouseup", () => { drag = null; });
canvas.addEventListener("mouseleave", () => { hoveredAgentId = null; drag = null; });
function setZoom(value) {
  renderer.setZoom(value);
  document.querySelector("#zoom-level").textContent = `${Math.round(renderer.zoom * 100)}%`;
}
document.querySelector("#zoom-in").addEventListener("click", () => setZoom(renderer.zoom + 0.5));
document.querySelector("#zoom-out").addEventListener("click", () => setZoom(renderer.zoom - 0.5));
document.querySelector("#zoom-fit").addEventListener("click", () => setZoom(1));
canvas.addEventListener("wheel", event => {
  event.preventDefault();
  setZoom(renderer.zoom + (event.deltaY < 0 ? 0.25 : -0.25));
}, { passive: false });
window.addEventListener("keydown", event => {
  if (event.key === "Escape") clearTool();
});
new ResizeObserver(resizeCanvas).observe(canvasWrap);
connect();
resizeCanvas();
drawWorld();
