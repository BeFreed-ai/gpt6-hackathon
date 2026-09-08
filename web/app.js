import { PixelCity } from "/static/pixel-city.js";
import { cityPlaces, placeLocationText } from "/static/pixel-landmarks.js";
import { SOCIAL_TYPES } from "/static/citizen-interactions.js";

const canvas = document.querySelector("#world-canvas");
let renderer = new PixelCity(canvas);
export { renderer };
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
let populationSignature = null;
let placeSignature = null;
let pointer = { x: 0, y: 0 };


function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${location.host}/ws`);
  socket.addEventListener("open", () => {
    // A backend restart may reset its transport sequence.
    if (state) delete state.sequence;
    document.querySelector("#connection-dot").classList.add("online");
    socket.send("observer-ready");
  });
  socket.addEventListener("message", (event) => {
    const incoming = JSON.parse(event.data);
    if (state?.sequence != null && incoming.sequence != null && incoming.sequence <= state.sequence) return;
    state = incoming;
    updateHud();
    updateFeed();
    updateEconomy();
    updatePopulation();
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
    selectedTool === "build" ? { position: worldPoint(pointer.x, pointer.y), tile: selectedTile } : null, selectedTool);
}

function updateHud() {
  const places = cityPlaces(state);
  const signature = places.map(p => `${p.id}:${p.name}`).join('|');
  if (signature !== placeSignature) {
    placeSignature = signature;
    const select = document.querySelector('#map-places');
    select.replaceChildren(new Option('Go to a place…', ''));
    for (const p of places.sort((a,b) => a.name.localeCompare(b.name))) select.add(new Option(`${p.name}${p.scenery ? ' (landmark)' : ''}`, p.id));
  }
  document.querySelector("#world-time").textContent = state.world.time_of_day;
  document.querySelector("#weather").textContent = state.world.weather.toUpperCase();
  const isLlm = ["astra", "novita"].includes(state.stats.brain_mode);
  const label = state.stats.brain_mode === "novita" ? "DEEPSEEK / NOVITA" : "ASTRA";
  const mode = !isLlm ? "RULE DEMO / NO LLM" : state.stats.brain_error
    ? `${label} / ERROR`
    : (state.stats.llm_decisions ?? state.stats.astra_decisions) > 0 ? `${label} / LIVE` : `${label} / WAITING`;
  document.querySelector("#brain-mode").textContent = "gpt astra";
  document.querySelector("#brain-mode").style.color = isLlm && !state.stats.brain_error ? "#526d43" : "#aa593d";
  document.querySelector("#brain-mode").title = state.stats.brain_error || `Actual runtime: ${mode}`;
  document.querySelector("#model-label").textContent = `MODEL: ${state.stats.brain_model || (isLlm ? label : "RULE DEMO")}`;
  document.querySelector("#stat-population").textContent = state.stats.population;
  document.querySelector("#stat-unhoused").textContent = state.stats.unhoused;
  document.querySelector("#stat-waste").textContent = state.stats.waste;
  document.querySelector("#stat-events").textContent = state.stats.companies || 0;
  document.querySelector("#play-pause").textContent = state.world.paused ? "▶" : "Ⅱ";
  document.querySelector("#play-pause").setAttribute("aria-label", state.world.paused ? "Play simulation" : "Pause simulation");
  document.querySelectorAll(".speed-button").forEach(button => button.classList.toggle("active", Number(button.dataset.speed) === state.world.speed));
  document.querySelector("#world-day").textContent = `DAY ${String(Math.floor(state.world.time / (state.world.day_length || 720)) + 1).padStart(2, "0")}`;
  const runtime = state.runtime;
  const disaster = [...(state.interventions || [])].reverse().find(i => i.type === "earthquake");
  const disasterStatus = document.querySelector("#disaster-status");
  disasterStatus.classList.toggle("hidden", !disaster);
  if (disaster) {
    const survivors = new Set(state.agents.filter(a => a.alive && disaster.delivered_to.includes(a.id)).map(a => a.id));
    const turns = new Set(disaster.followups.filter(f => survivors.has(f.agent_id)).map(f => f.agent_id));
    const llm = new Set(disaster.followups.filter(f => survivors.has(f.agent_id) && ["novita", "astra"].includes(f.source)).map(f => f.agent_id));
    disasterStatus.textContent = `EARTHQUAKE · ${disaster.delivered_to.length} felt it · ${disaster.killed.length} dead · ${disaster.injured.length} injured · ${turns.size}/${survivors.size} survivors decided (${llm.size} LLM)`;
    disasterStatus.title = "Shaking and injury labels are physical reactions. Decision counts advance only after an individual brain turn is applied; they do not prove causal reasoning.";
  }
  if (runtime) {
    const status = runtime.pause_reason || (state.world.paused ? "Paused" : runtime.clock_waiting ? "World clock waiting for citizen decisions" : "City living");
    document.querySelector("#runtime-status").textContent = `${status} · Calls ${runtime.requests}/${runtime.request_limit} · In flight ${runtime.inflight} · Queued ${runtime.queued} · ${runtime.restored ? "Restored world" : "New world"} · Saved ${runtime.checkpoint_age_seconds}s ago`;
  }
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
  const requestedAgentId = selectedAgentId;
  if (!requestedAgentId) return;
  try {
    const response = await fetch(`/api/agents/${encodeURIComponent(requestedAgentId)}`);
    if (!response.ok) return;
    const detail = await response.json();
    if (selectedAgentId !== requestedAgentId || detail.id !== requestedAgentId) return;
    agentDetail = detail;
    renderer.selectedPlaces = {home: detail.home_id, workplace: detail.workplace_id};
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
  renderPeerInteractions();
  renderAgentBackground(agentDetail.background);
  const decisionLabel = {astra: "ASTRA", novita: "DEEPSEEK / NOVITA", local: "RULE DEMO"}[agentDetail.last_decision_source] || "WAITING";
  document.querySelector("#decision-source").textContent = `Decisions: ${decisionLabel} / ${agentDetail.decision_count || 0} turns`;
  document.querySelector("#action-result").textContent = agentDetail.last_action_result || "";
  document.querySelector("#agent-thought").textContent = agentDetail.thought || "No thought has been expressed yet.";
  document.querySelector("#agent-goal").textContent = agentDetail.active_goal?.statement || "No committed goal yet";
  document.querySelector("#agent-goal-reason").textContent = agentDetail.active_goal?.reason || "This citizen is still deciding what matters.";
  document.querySelector("#life-direction").textContent = agentDetail.life?.direction?.statement || "No life direction expressed yet. Nobody assigns one.";
  document.querySelector("#project-list").innerHTML = (agentDetail.life?.projects || []).map(project => `<article class="business-card"><strong>${escapeHtml(project.title)}</strong><small>${escapeHtml(project.status)} · ${Math.round((project.progress || 0) * 100)}% self-reported</small><p>${escapeHtml(project.goal)}</p><p>Next: ${escapeHtml(project.next_step)}</p>${project.milestones.map(milestone => `<p class="muted">${Math.round(milestone.progress * 100)}% · ${escapeHtml(milestone.statement)}</p>`).join("")}</article>`).join("") || '<p class="muted">No projects yet. Immediate needs do not erase long-term plans.</p>';
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
  document.querySelector("#memory-count").textContent = `${agentDetail.memory_total ?? agentDetail.memories.length} stored · latest shown`;
  document.querySelector("#agent-memories").innerHTML = [...agentDetail.memories].reverse()
    .map(memory => ({...memory, content: memory.event_type === "personal_background" ? biographyText(memory.content) : memory.content}))
    .filter(memory => memory.content).slice(0, 24).map((memory) => (
    `<article class="memory ${memory.importance >= 0.7 ? "high" : ""}">
      <p>${escapeHtml(memory.content)}</p>
      <small>${escapeHtml(memory.source_type)} · confidence ${Math.round(memory.confidence * 100)}%</small>
    </article>`
  )).join("") || '<p class="muted">No personal memories yet.</p>';
}

function citizenName(id) {
  return state?.agents.find(agent => agent.id === id)?.name || id;
}

function renderPeerInteractions() {
  const id = agentDetail.id;
  const events = (state?.events || []).filter(e => SOCIAL_TYPES.has(e.type) &&
    (e.actor_id === id || e.target_ids?.includes(id)));
  document.querySelector("#agent-interactions").innerHTML = events.slice(-6).reverse().map(event => {
    const names = (event.target_ids || []).map(citizenName).join(", ");
    const title = `${citizenName(event.actor_id)}${names ? ` → ${names}` : ""}`;
    return `<article class="memory"><small>${escapeHtml(title)} · ${escapeHtml(event.type)}</small><p>${escapeHtml(event.public_text)}</p></article>`;
  }).join("") || '<p class="muted">No recent interaction with another citizen.</p>';
  document.querySelector("#agent-relationships").innerHTML = (agentDetail.relationships || []).map(person =>
    `<div><dt>${escapeHtml(person.name)}</dt><dd>${Number(person.value) > 0 ? "Positive" : Number(person.value) < 0 ? "Negative" : "Neutral"} · ${Number(person.value).toFixed(2)}</dd></div>`
  ).join("") || '<p class="muted">No opinion of another citizen expressed yet.</p>';
}

function readableLabel(value) {
  if (typeof value !== "string" || !value.trim()) return "Not provided";
  const label = value.trim().replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function formatCount(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") return "Not provided";
  const number = typeof value === "number" || typeof value === "string" && value.trim() ? Number(value) : NaN;
  return Number.isFinite(number) && number >= 0 ? number.toLocaleString("en-US") : "Not provided";
}

// Keep provenance in stored history; present the life story without repeated source boilerplate.
function biographyText(value) {
  if (typeof value !== "string") return "";
  const text = value.trim();
  if (/^(This is a fictional character with a public professional counterpart;|This is a clearly labeled fictional public-figure simulation,|My assigned neighborhood, rental room, finances and physical circumstances are synthetic game conditions,|Public counterpart reference:|Public career fact about |Public counterpart source:|Public history source:)/.test(text)) return "";
  return text.replace(/^Fictional simulation memory:\s*/, "")
    .replace(/^My synthetic starting cash reserve is /, "My starting savings are ")
    .replace("my modeled annual gross wage", "my annual gross wage")
    .replace("my assumed annual nonlabor support", "my annual nonlabor support");
}

function renderAgentBackground(background) {
  const facts = document.querySelector("#agent-background-facts");
  const biography = document.querySelector("#agent-biography");
  facts.innerHTML = "";
  biography.innerHTML = "";
  const available = background && typeof background === "object" && !Array.isArray(background) && Object.keys(background).length > 0;
  document.querySelector("#agent-background").classList.toggle("hidden", !available);
  if (!available) return;
  const rows = [
    ["Age", formatCount(background.age)],
    ["Neighborhood", readableLabel(background.neighborhood)],
    ["Housing", readableLabel(background.housing_status)],
    ["Employment", readableLabel(background.employment_status)],
    ["Occupation group", readableLabel(background.occupation_group)],
    ["Work sector", readableLabel(background.occupation_sector)],
  ];
  if (typeof background.employer_name === "string" && background.employer_name.trim()) rows.push(["Employer", background.employer_name]);
  facts.innerHTML = rows.map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`).join("");
  biography.innerHTML = (Array.isArray(background.biography) ? background.biography : [])
    .map(biographyText).filter(Boolean)
    .map(line => `<p>${escapeHtml(line)}</p>`).join("");
  const reference = background.public_figure || background.person_reference;
  if (reference) {
    const facts = (reference.public_career_facts || []).map(fact => `<p>${escapeHtml(fact)}</p>`).join("");
    biography.insertAdjacentHTML("beforeend", `<details class="biography-sources"><summary>Sources</summary>${facts}<p>${sourceLinks(reference.sources)}</p></details>`);
  }
}

function sourceLinks(sources) {
  return (Array.isArray(sources) ? sources : []).filter(source => source && typeof source === "object").map(source => {
    const name = typeof source.name === "string" && source.name.trim() ? source.name : typeof source.title === "string" ? source.title : "Source";
    try {
      const url = new URL(source.url);
      if (!["http:", "https:"].includes(url.protocol)) return escapeHtml(name);
      const href = escapeHtml(url.href).replace(/"/g, "&quot;");
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${escapeHtml(name)}</a>`;
    } catch (_) {
      return escapeHtml(name);
    }
  }).join(" · ");
}

function employerCard(employer) {
  const generic = employer.is_generic === true;
  const count = formatCount(employer.local_headcount);
  const status = employer.headcount_status;
  const countLabel = count === "Not provided" ? "Unknown"
    : status === "verified" ? `${count} · Verified published count`
    : status === "estimate" ? `${count} · Estimated count`
    : "Unknown · Count not verified";
  const identity = generic ? "Scenario workplace" : employer.is_generic === false ? "Named real employer" : "Employer type not provided";
  const confidence = employer.confidence && typeof employer.confidence === "object"
    ? Object.entries(employer.confidence).map(([key, value]) => `${readableLabel(key)}: ${readableLabel(value)}`).join(" · ")
    : readableLabel(employer.confidence);
  return `<article class="calibration-employer">
    <span class="eyebrow">${identity}</span>
    <h4>${escapeHtml(typeof employer.name === "string" && employer.name.trim() ? employer.name : "Unnamed workplace")}</h4>
    <p>${escapeHtml(readableLabel(employer.neighborhood))} · ${escapeHtml(readableLabel(employer.sector))}</p>
    <dl class="facts">
      <div><dt>Reference headcount</dt><dd>${generic ? "No real employer count" : countLabel}</dd></div>
      ${generic ? "" : `<div><dt>Count scope</dt><dd>${escapeHtml(readableLabel(employer.headcount_scope))}</dd></div>
      <div><dt>Count year</dt><dd>${escapeHtml(employer.headcount_year ?? "Not provided")}</dd></div>`}
      <div><dt>Simulated workers</dt><dd>${formatCount(employer.simulated_workers)}</dd></div>
    </dl>
    ${employer.within_resident_reference_area === false ? '<p>Contextual location outside the resident reference area.</p>' : ""}
    ${!generic && employer.confidence ? `<p>Confidence: ${escapeHtml(confidence)}</p>` : ""}
    <p class="calibration-sources">${sourceLinks(employer.sources) || (generic ? "Generic sector setting; not a real employer." : "Sources not provided.")}</p>
  </article>`;
}

function updatePopulation() {
  const population = state?.population;
  const available = population && typeof population === "object" && !Array.isArray(population) && Object.keys(population).length > 0;
  document.querySelector("#population-panel").classList.toggle("hidden", !available);
  if (!available) {
    populationSignature = null;
    document.querySelector("#population-content").innerHTML = "";
    document.querySelector("#population-sample").textContent = "";
    return;
  }
  const employers = Array.isArray(population.employers) ? population.employers : Array.isArray(state.employers) ? state.employers : [];
  const signature = JSON.stringify([population, employers]);
  if (signature === populationSignature) return;
  populationSignature = signature;
  const sample = formatCount(population.agent_count);
  document.querySelector("#population-sample").textContent = sample === "Not provided" ? "" : `${sample} agents`;
  const neighborhoods = population.neighborhood_counts && typeof population.neighborhood_counts === "object" && !Array.isArray(population.neighborhood_counts)
    ? Object.entries(population.neighborhood_counts) : [];
  const limitations = (Array.isArray(population.limitations) ? population.limitations : []).filter(item => typeof item === "string" && item.trim());
  document.querySelector("#population-content").innerHTML = `
    <p class="calibration-scenario">${escapeHtml(readableLabel(population.scenario_label || population.scenario || population.label))}</p>
    <dl class="facts">
      <div><dt>Simulated sample</dt><dd>${sample} agents</dd></div>
      <div><dt>Reference residents</dt><dd>${formatCount(population.resident_population)}</dd></div>
      <div><dt>Adult reference (18+)</dt><dd>${formatCount(population.adult_population)}</dd></div>
      <div><dt>Reference geography</dt><dd>${escapeHtml(readableLabel(population.geography))}</dd></div>
      <div><dt>Source year</dt><dd>${escapeHtml(population.source_year ?? "Not provided")}</dd></div>
      <div><dt>Employment proxy year</dt><dd>${escapeHtml(population.employment_calibration?.vintage ?? "Not provided")}</dd></div>
    </dl>
    <p>${escapeHtml(typeof population.sampling_note === "string" && population.sampling_note.trim() ? population.sampling_note : "A synthetic sample; population representativeness is not specified.")}</p>
    <h3>Neighborhoods in the sample</h3>
    ${neighborhoods.length ? `<dl class="facts">${neighborhoods.map(([name, count]) => `<div><dt>${escapeHtml(readableLabel(name))}</dt><dd>${formatCount(count)}</dd></div>`).join("")}</dl>` : "<p>Neighborhood counts not provided.</p>"}
    <h3>Workplace references</h3>
    <p>Reference employers and generic sector workplaces are separate from citizen-founded businesses. Simulated workers are model assignments, not measured staffing. Published and estimated counts retain their stated scope: citywide is not one office, and global is not San Francisco.</p>
    <div class="calibration-employers">${employers.filter(item => item && typeof item === "object").map(employerCard).join("") || "<p>No employer references provided.</p>"}</div>
    ${limitations.length ? `<h3>Limitations</h3><ul>${limitations.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    <h3>Public sources</h3><p class="calibration-sources">${sourceLinks(population.sources) || "Sources not provided."}</p>`;
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

canvasWrap.addEventListener("mousemove", (event) => {
  const rectangle = canvasWrap.getBoundingClientRect();
  const nextPointer = { x: event.clientX - rectangle.left, y: event.clientY - rectangle.top };
  if (drag) {
    const dx = nextPointer.x - pointer.x, dy = nextPointer.y - pointer.y;
    if (Math.hypot(nextPointer.x - drag.x, nextPointer.y - drag.y) > 4) wasDragged = true;
    if (wasDragged && !renderer.geographic) renderer.pan(dx, dy);
  }
  pointer = nextPointer;
  const hit = state?.agents.filter(agent => agent.alive).find(agent => {
    const point = screenPoint(renderer.positions.get(agent.id) || agent.position);
    return renderer.hitTest(agent, pointer);
  });
  hoveredAgentId = hit?.id || null;
  canvas.style.cursor = drag ? "grabbing" : selectedTool ? "crosshair" : hit ? "pointer" : "grab";
  const hoveredObject = !hit && state?.objects.find(item => {
    const point = worldPoint(pointer.x, pointer.y);
    return Math.abs(item.position.x - point.x) < item.width / 2 && Math.abs(item.position.y - point.y) < item.height / 2;
  });
  document.querySelector("#map-location").textContent = hit ? `${hit.name} / ${hit.current_action}` : hoveredObject ? hoveredObject.name : state?.world.scenario === "sf" ? "SAN FRANCISCO / SOMA + MISSION RESIDENTS" : "SAN FRANCISCO / A SMALL WORLD";
  if (!hit && !hoveredObject && state?.terrain) {
    const point = worldPoint(pointer.x, pointer.y);
    const tile = state.terrain.tiles.find(tile => tile.cell[0] === Math.floor(point.x / 20) && tile.cell[1] === Math.floor(point.y / 20));
    if (tile) document.querySelector("#map-location").textContent = `${tile.kind.toUpperCase()} / ${tile.message || (tile.builder_id ? citizenName(tile.builder_id) : "City infrastructure")}`;
  }
});

async function handleMapClick(event, nativeMapClick = false) {
  if (!state || (!nativeMapClick && wasDragged)) return;
  const rectangle = canvasWrap.getBoundingClientRect();
  const click = { x: event.clientX - rectangle.left, y: event.clientY - rectangle.top };
  let position = worldPoint(click.x, click.y);
  // Clicking any part of a sprite places the hazard at its physical feet.
  if (["waste", "lightning", "food"].includes(selectedTool)) {
    const target = state.agents.filter(a => a.alive).find(a => {
      const point = screenPoint(renderer.positions.get(a.id) || a.position);
      return renderer.hitTest(a, click);
    });
    if (target) position = target.position;
  }
  if (position.x < 0 || position.x > state.world.width || position.y < 0 || position.y > state.world.height) {
    if (selectedTool) showStatus("Outside the active simulation. This area is geographic context only.");
    return;
  }
  if (selectedTool) {
    try {
      const victim = selectedTool === "kill" ? state.agents.filter(a => a.alive).find(a => {
        const point = screenPoint(renderer.positions.get(a.id) || a.position);
        return renderer.hitTest(a, click);
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
    return renderer.hitTest(agent, click);
  });
  if (hit) {
    if (selectedAgentId !== hit.id) {
      agentDetail = null;
      renderAgentBackground(null);
      document.querySelector("#agent-inspector").classList.add("hidden");
      document.querySelector("#empty-inspector").classList.remove("hidden");
    }
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
}
canvas.addEventListener("click", event => handleMapClick(event));

document.querySelector("#play-pause").addEventListener("click", async () => {
  if (!state) return;
  await postJson("/api/control", { action: state.world.paused ? "play" : "pause" });
});

document.querySelector("#save-world").addEventListener("click", async () => {
  await postJson("/api/control", { action: "save" });
  showStatus("World saved. Private histories, projects and city state preserved.");
});

document.querySelectorAll(".speed-button[data-speed]").forEach((button) => {
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
      document.querySelector("#broadcast-mode-note").textContent = ["astra", "novita"].includes(state?.stats.brain_mode)
        ? "LLM citizens may question, discuss or act on the claim. Check provider status for errors."
        : "Rule demo only: citizens can notice a signal but cannot interpret free-form language. Configure an LLM provider for real responses.";
      document.querySelector("#broadcast-dialog").showModal();
      return;
    }
    selectedTool = selectedTool === tool ? null : tool;
    document.querySelector("#tool-hint").textContent = tool === "kill"
      ? "KILL / click a citizen · permanent for this run · ESC to cancel"
      : tool === "lightning" ? "LIGHTNING / direct hit kills · nearby citizens can be injured · ESC to cancel"
      : tool === "earthquake" ? "EARTHQUAKE / buildings can collapse · falling debris can kill · survivors decide what comes next · ESC to cancel"
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
function setZoom(value, anchor) {
  renderer.setZoom(value, anchor);
  if (!renderer.geographic) document.querySelector("#zoom-level").textContent = `${Math.round(renderer.zoom * 100)}%`;
}
document.querySelector("#zoom-in").addEventListener("click", () => setZoom(renderer.zoom + 0.5));
document.querySelector("#map-closeup").addEventListener("click", async () => {
  const agent = state?.agents.find(a => a.id === selectedAgentId) || state?.agents.find(a => a.alive && a.reaction) || state?.agents.find(a => a.alive);
  if (!agent) { showStatus("No citizen to observe yet."); return; }
  clearTool();
  selectedAgentId = agent.id;
  renderer.focusCitizen(agent);
  if (!renderer.geographic) document.querySelector("#zoom-level").textContent = `${Math.round(renderer.zoom * 100)}%`;
  await refreshAgentDetail();
  showPanel("citizen");
});
document.querySelector("#zoom-out").addEventListener("click", () => setZoom(renderer.zoom - 0.5));
document.querySelector("#zoom-fit").addEventListener("click", () => {
  if (state) renderer.fitResidents(state);
});
document.querySelector("#map-residents").addEventListener("click", () => { if (state) renderer.fitResidents(state); });
for (const district of ["city", "soma", "mission", "mission_bay"]) document.querySelector(`#map-${district}`).addEventListener("click", () => {
  renderer.focusDistrict(district);
});
document.querySelector("#map-waste").addEventListener("click", async () => {
  const waste = state?.objects.find(o => o.kind === "waste");
  if (!waste) { showStatus("No street waste exists. Use Street waste to place a real hazard."); return; }
  renderer.focusWaste(waste);
});
document.querySelector('#map-places').addEventListener('change', event => {
  const place = state && cityPlaces(state).find(p => p.id === event.target.value);
  if (place) { renderer.focusPlace(place); showStatus(`${place.name} · ${placeLocationText(place)}`); }
});
for (const kind of ['home','workplace']) document.querySelector(`#visit-${kind}`).addEventListener('click', () => {
  const place = state?.objects.find(o => o.id === agentDetail?.[`${kind}_id`]);
  if (place) { renderer.focusPlace(place); showStatus(`${place.name} · ${placeLocationText(place)}`); }
  else showStatus(`This citizen has no assigned ${kind}.`);
});
document.querySelector("#map-follow").addEventListener("click", event => {
  if (!selectedAgentId) { showStatus("Select a citizen to follow."); return; }
  renderer.followSelected = !renderer.followSelected;
  event.currentTarget.setAttribute("aria-pressed", String(renderer.followSelected));
});
canvas.addEventListener("wheel", event => {
  event.preventDefault();
  const box = canvas.getBoundingClientRect();
  const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? box.height : 1);
  setZoom(renderer.zoom * Math.exp(-Math.max(-300, Math.min(300, delta)) * 0.002), { x: event.clientX - box.left, y: event.clientY - box.top });
}, { passive: false });
window.addEventListener("keydown", event => {
  if (event.key === "Escape") clearTool();
});
new ResizeObserver(resizeCanvas).observe(canvasWrap);
connect();
resizeCanvas();
drawWorld();
