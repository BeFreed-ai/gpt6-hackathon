# Throng City

**Your city. Their decisions.**

A browser-based, pixel-art San Francisco society simulation. Watch yellow citizens
go to work, find food, talk, pursue projects, start businesses, and respond to a
city you can change—or shake with an earthquake.

Each citizen has a separate decision loop, personal history, memories, and
perspective. In LLM mode, the model chooses intentions; the simulation validates
and executes actions. Citizens do not share an omniscient conversation thread.

This is a prototype for exploring emergent behavior, not evidence of consciousness
or a validated prediction of real San Francisco.

## Current build

- **100-person SF scenario:** named adults living in Mission, SoMa, and Mission Bay,
  with individual backgrounds, homes, workplaces, schedules, and financial state.
- **Continuous pixel map:** SF coastline and landmark context, detailed playable
  neighborhoods, pan/zoom, citizen following, and searchable personal places.
  No game engine, online basemap, or map API key is required.
- **Private lives:** local perception, conversations and broadcasts, durable memory,
  self-authored life direction, multiple projects, milestones, and relationships.
  Private backgrounds and values appear in the click-to-inspect panel.
- **Survival and city life:** hunger, energy, stress, work shifts, rent, shared
  housing, eviction, food access, restrooms, street waste, and cleanup.
- **Economic actions:** company formation, bilateral investment and job offers,
  production, sales, prices, shares, and dividends.
- **Editable terrain:** roads, walls, floors, signs, gardens, and usable facilities.
  Paths and collisions use authoritative terrain and each citizen's knowledge.
- **Consequential disasters:** earthquakes and lightning can interrupt actions,
  injure or kill citizens, close facilities, and leave visible cracks and rubble.
  Actual repair progress changes the building art.
- **Save/resume:** SQLite checkpoints restore the same city and personal histories.
- **Interaction lab:** 45 replayable engine scenarios covering all 34 supported
  actions and 11 physical cases, without making model calls.

## Quick start: no API key required

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and a browser.
Node.js is needed only for the JavaScript tests.

From the repository root:

```sh
uv sync --dev

SOCIETY_LLM_PROVIDER=local \
SOCIETY_AGENT_COUNT=100 \
SOCIETY_SCENARIO=sf \
SOCIETY_DB_PATH=.data/sf-local-demo.db \
SOCIETY_START_PAUSED=1 \
SOCIETY_ALLOW_PAID_CALLS=0 \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8007
```

Open [the city](http://127.0.0.1:8007/) and press Play.
This configuration uses deterministic local rules, **not LLM reasoning**.

For a no-call inspection of the supported mechanics, open the
[interaction lab](http://127.0.0.1:8007/static/interaction-replay.html).
Search scenarios, play or pause, scrub through recorded steps, and zoom in.
The lab uses test-supplied decisions and real engine snapshots; it is not a replay
of an autonomous LLM society. It does not change the live city.

The server's population default remains **12**; the command above explicitly
requests 100. Count, seed, and scenario initialize a new database only. If the
chosen path already contains a checkpoint, its saved population is restored.
Use a different, unused database path to start a separate experiment.

## Enable independent LLM citizens

Copy [.env.example](.env.example) to `.env` if you do not already have one.
Keep keys server-side; `.env` and the runtime `.data/` directory are ignored by Git.

For the implemented Novita integration, configure:

```dotenv
SOCIETY_LLM_PROVIDER=novita
NOVITA_MODEL=deepseek/deepseek-v4-pro-0813
NOVITA_SECRET_ID=your-novita-secret-name
NOVITA_SECRET_FIELD=api_key
AWS_REGION=us-east-1

SOCIETY_SCENARIO=sf
SOCIETY_AGENT_COUNT=100
SOCIETY_DB_PATH=.data/sf-llm-demo.db
SOCIETY_START_PAUSED=1
SOCIETY_ALLOW_PAID_CALLS=1
SOCIETY_REQUEST_LIMIT=100
SOCIETY_MAX_CONCURRENT_LLM_CALLS=4
SOCIETY_LATENCY_AWARE=1
```

The AWS CLI must be authenticated. The secret can be a JSON object with the selected
field or a plain-text key. Alternatively, set `NOVITA_API_KEY` in your local
environment instead of using Secrets Manager. Novita never uses the OpenAI key.

Start the server, then press Play when ready to spend the configured budget:

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8007
```

For the OpenAI backend, set `SOCIETY_LLM_PROVIDER=openai`,
`OPENAI_MODEL` to a model available to your API account, and either
`OPENAI_API_KEY` or `OPENAI_SECRET_ID`. The JSON secret field defaults to
`OPENAI_API_KEY`. The repository's model default is `gpt-6-astra`; this is a
configuration value, not a guarantee of account access.

The Novita implementation uses Chat Completions; the OpenAI implementation uses
Responses. Both receive private citizen context and return locally validated
actions. A configured provider failure is not replaced by a scripted decision.
Novita without credentials fails startup; OpenAI without credentials falls back
to the local rule demo.

**The header's Brain text is currently hardcoded to `gpt astra`. It does not select
or identify the actual backend.** Check `GET /api/health` for the actual provider
and model, and `GET /api/state` for runtime counters. The footer and decision
records also retain provider information.

### Cost and scheduling safeguards

- Startup is paused by default; paid calls require explicit opt-in.
- `SOCIETY_REQUEST_LIMIT` is a cumulative request cap for the saved run, not a
  dollar cap and not a fresh allowance on every restart.
- `SOCIETY_MAX_CONCURRENT_LLM_CALLS` controls simultaneous requests, separately
  from the total cap. Each citizen has at most one pending turn.
- Request counts are persisted. Provider clients disable automatic SDK retries;
  later decision attempts still consume the run budget.
- Three consecutive provider failures pause the simulation.
- Pause prevents new provider requests from starting, but already-sent requests
  may finish and remain billable.
- New stimuli can invalidate an in-flight decision. A spent request is therefore
  not necessarily an applied action; 100 requests do not guarantee 100 reactions.
- With latency-aware scheduling, the shared clock waits when citizens are
  thinking and nobody has a resolved physical action. Existing movement can
  continue while other citizens think.
- At the cap, already-resolved physical actions can finish without new calls;
  the simulation then pauses when no such work remains.

Check the runtime status before resuming a saved experiment. Do not raise the cap
or change database paths merely to bypass a spent budget.

## Controls and disasters

- **Click a citizen:** inspect their background, memories, plans, values, and
  relationships. Use Show home / Show workplace to locate personal places.
- **Drag / scroll:** pan and zoom. District buttons, Find citizens, Find waste,
  Follow, and the place picker help frame a scene.
- **Earthquake / Lightning / Drop food / Street waste / Add restroom:** select a
  tool, then click its target location.
- **Kill citizen:** target a living citizen. Death persists in that saved run.
- **Broadcast:** deliver an external claim to living citizens; delivery does not
  force agreement, speech, or a specific response.
- **Build / edit:** paint terrain; use Demolish to remove editable tiles and Escape
  to leave the brush.
- **City Feed / City Life:** inspect public events, facilities, businesses, and
  intervention follow-ups separately from private citizen information.

Interventions apply even while paused. Back up an experiment before destructive
demonstrations; there is no general undo button.

An earthquake delivers shaking to every living citizen before resolving casualties.
Facility damage and falling debris depend on physical locations. Cracks, missing
walls, collapse, dust, remains, and rebuilding come from authoritative world state.
A flinch or injury label is a **physical reaction**, not proof of an LLM decision.
Survivors subsequently decide whether to move, help, repair, communicate, or
continue their own business. The intervention ledger distinguishes event delivery
from subsequent applied decisions.

Decorative skyline buildings and reference-only landmarks are not physical
facilities and do not take simulated damage. Terrain editing is a bounded 2D
mechanic, not unrestricted Minecraft-style voxel physics.

## Geography and population: what is real?

The checked-in 100-adult, seed-17 scenario allocates **56 Mission, 27 SoMa, and
17 Mission Bay residents**. It includes 73 employed adults, three illustrative
OpenAI assignments, and one Anthropic assignment. These company allocations are
scenario choices, not measured local staffing.

Road and landmark references use geographic data. Citizen feet, waste, usable
facilities, picking, and god tools share the same physical coordinates; the
renderer does not move people to make a prettier composition. However, homes and
workplaces still use synthetic gameplay sites, and the broader SF context is
decorative—not a surveyed, fully simulated city or a complete 3D model.

The population combines historical neighborhood demographics, an industry-level
jobs proxy, and fictional personal lives. It excludes children and inbound
commuters. Real names and public career references—including Sam Altman and
Dario Amodei—are used as character context; private biographies, finances,
relationships, actions, and in-world statements are fictional.

See [population calibration](docs/sf-100-population.md),
[economic assumptions](docs/sf-economy-calibration.md),
[public-figure provenance](docs/public-figure-characters.md), and
[map coordinate limits](docs/pixel-city.md).

## How citizen lives work

Every turn includes the citizen's background, clock and schedule, bodily needs,
known places, nearby observations, unread events, and personal plans. A citizen
can revise their life direction and manage multiple projects—up to six active
projects and 24 total—with evidence-linked milestones.

Full memory history is persisted, but **the entire history is not sent in every
request**. A bounded selection of personal memories, recall results, and unread
events supplies the model context. Plans are self-reports; writing a milestone
does not itself move money, repair a building, or make another citizen agree.

The action vocabulary is finite. Companies currently produce meals, coats, and
route apps. Financing and ownership are game mechanics, not real incorporation,
investment, banking, or external transactions. Observed behavior may emerge from
the interaction of these rules and model choices, but long-run social emergence
and consciousness have not been established.

## Architecture

```text
Pixel canvas + citizen inspector / separate static interaction lab
                         ↕ HTTP + WebSocket
                 FastAPI SimulationService
                         ├── Per-citizen scheduling + request budget
                         ├── Private perception, memory, schedules, life projects
                         ├── Novita / OpenAI decisions or explicit local rules
                         ├── Validated movement, economy, terrain, disaster physics
                         └── SQLite events, memories, call audit, world checkpoints
```

Key implementation modules:

- `app/main.py`: server, scheduler, controls, budget, and snapshot delivery.
- `app/world.py`, `app/perception.py`: physical state and private event delivery.
- `app/brain.py`, `app/life.py`, `app/routines.py`: decisions, projects, recall,
  and schedule context.
- `app/terrain.py`, `app/urban.py`, `app/disasters.py`: movement, timed actions,
  facilities, and casualties.
- `app/economy.py`, `app/sf_economy.py`: businesses, households, and credit flows.
- `app/store.py`, `app/checkpoint.py`: persistence and restoration.
- `web/pixel-city.js`, `web/sf-city-context.js`, `web/pixel-damage.js`:
  geographic pixel presentation and visible damage.
- `web/interaction-replay.html`: isolated mechanics catalog.

Checkpoints are saved periodically, on successful controls/interventions, and on
graceful shutdown. Reusing the database restores the world rather than creating
new lives; startup pause behavior is controlled separately by
`SOCIETY_START_PAUSED`. Existing in-flight network requests are not resumable.

## Tests and offline data checks

```sh
uv run pytest -q
node --test scripts/test_*.mjs
uv run python scripts/build_sf_population_100.py --check
```

Browser checks require Playwright's Chromium installation:

```sh
uv run --with playwright playwright install chromium
uv run --with playwright python scripts/smoke_interaction_catalog.py
uv run --with playwright python scripts/smoke_pixel_damage.py
```

These two checks expect an existing server at `http://127.0.0.1:8007`.
The catalog check permits only local static GET requests. The damage check runs
quake/repair fixtures in a temporary database and verifies that the live world
is unchanged; keep the live simulation paused during that check. Neither test
invokes an LLM.

To regenerate the offline population audit after changing its inputs:

```sh
uv run python scripts/build_sf_population_100.py
```

This rewrites the checked-in JSON audit, not a saved live city.
For additional replay generators and checks, see the
[interaction lab documentation](docs/interaction-lab.md).

Other legacy `smoke_*` scripts may resume a server, stage destructive events, or
make paid model calls. Read their documented behavior before running them against
a city you want to preserve.

## Design notes

- [Agent society design](docs/agent-society-design.md)
- [SF life and project planning](docs/sf-life-design.md)
- [Pixel map and damage presentation](docs/pixel-city.md)
- [Citizen interactions](docs/citizen-interactions.md)
- [Street sanitation](docs/street-sanitation.md)
- [Disaster demo mechanics](docs/demo-reactions.md)
- [Thronglets intervention research](docs/thronglets-intervention-design.md)

Thronglets and Don't Starve are design references. The pixel presentation is
original; this project is not affiliated with Netflix.
