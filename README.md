# Throng City

Product direction: an [SF urban survival society](docs/ai-survival-direction.md), with San Francisco-inspired housing, food access and shared facilities, consequential survival in the spirit of Don't Starve, and Thronglets-inspired pixel presentation. The current playable build is the city prototype; the linked research and module plan distinguish proposed mechanics from implemented features.

Throng City is a live 2D society simulation in which every yellow citizen has an independent memory, private perspective, self-chosen goal, and LLM decision loop. Citizens can only know what they personally experience, observe, overhear, or receive through a broadcast.

The world is authoritative: an LLM may choose any goal or say anything, but it can only affect physical reality through validated actions.

## What is playable

- 12 independently scheduled citizens
- Local vision and hearing with private memory delivery
- Autonomous goals, values, relationships, work, housing, hunger, energy, and stress
- Face-to-face conversation, overhearing, shouting, and citywide radio
- Rent, eviction, job loss, shelter, public restrooms, street waste, and service reports
- Player interventions: food, lightning, restrooms, fog, and unknown broadcasts
- Click-only citizen inspector with private memories and self-expressed values
- Objective city event feed and persistent SQLite event history
- Real-time browser rendering with no game engine installation
- Novita DeepSeek and OpenAI Astra modes, with an explicitly labeled rule demo
- Shops and scheduled free meal service, finite food stocks, portable goods and cooking
- Timed work, cooking, cleaning, toilet use and indoor/outdoor rest with facility capacity
- Vacant-bed rentals, bilateral roommate invitations, shared rent and a missed-rent warning
- Fog exposure, wearable coats and usable route apps that improve travel speed
- Citizen-founded companies with separate treasuries, product stock and real sales
- Bilateral funding offers, counteroffers, consent, equity dilution and stale-term rejection
- Accepted job offers, reserved production costs/payroll, wages paid only on completion
- Founder-controlled prices and share-proportional cash distributions
- City Life observer panel for facilities, company accounts and ownership
- Editable 20-unit tiles: salvage materials, lay roads/floors, build walls or signs,
  place gardens/benches/kitchens/toilets/shelters, and dismantle editable structures
- Roads change travel speed; walls block movement; paths use each citizen's observed map
- Built facilities are usable, gardens grow food, and locally read signs enter memory

## Run locally

Install dependencies and start the server:

```sh
uv sync --dev
uv run uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## SF population baseline

The server now defaults to `SOCIETY_SCENARIO=sf`. It generates a reproducible adult
resident sample instead of repeating twelve preset life situations. `SOCIETY_AGENT_COUNT`
still defaults to 12 (eight Mission residents and four South of Market residents),
and `SOCIETY_SEED` defaults to 17. Increasing the live count increases model usage;
the population generator itself is offline and makes no model calls.

- Population and age: DataSF ACS **2019–2023**, totaling 79,129 residents, with
  70,568 adults used as the sampling denominator. These are not 2026 counts.
- Employment and broad occupations: SF Planning ACS **2016–2020** resident
  marginals, explicitly treated as older age-16+ proxies for the adult sample.
  Assignment is independent of age within neighborhood, not an observed joint distribution.
- Workplaces: 19 sourced examples across technology and non-tech sectors, with
  historical SF-city counts kept separate from unknown office counts. Four contextual
  locations are outside the resident analysis neighborhoods. Occupation-to-industry
  mapping and the at-most-25% named-example allocation are labeled scenario assumptions;
  this is **not** allocation proportional to measured company staffing.
- Personal backgrounds are private, included in every Astra decision and saved as
  individual memories. No values, career ambitions or life goals are assigned by census group.
- The observer's **Population calibration** panel shows dates, counts, sources and
  limitations. Click a citizen for their private background. Real reference employers
  are separate from companies that citizens create during play.
- Scripted prototype layoffs, phantom street fairs and rent-rumor broadcasts are disabled
  in this scenario. Physical survival, conversations and player interventions still work.

The playable map remains **schematic**, and credits, wages, rooms and opening hours
remain game assumptions. Household structure, real rents, inbound commuters, a full
employer census and measured company-level staffing are not yet calibrated. The
[actual street reference](docs/maps/soma-mission-reference.svg) is not yet the playable map.
Multi-project life planning and full world save/resume also remain separate work.

See [population methodology](docs/sf-population-sources.md) and
[employer evidence](docs/sf-employer-sources.md). Set `SOCIETY_SCENARIO=prototype`
to use the old fixture city; direct `World(...)` construction retains that default
for existing mechanics tests.

Validate a disposable preview without model calls, or add a bounded real-Astra run:

```sh
uv run --with playwright python scripts/smoke_sf_population.py --url http://127.0.0.1:8003
uv run --with playwright python scripts/smoke_sf_population.py --url http://127.0.0.1:8003 --seconds 60
```

The live check resumes and then pauses only its target server, without staging goals
or interventions. It verifies integration, not long-run emergence or consciousness.

## Enable Novita DeepSeek citizens

The active local configuration uses **Novita DeepSeek V4 Pro 0813**. Keep credentials on
the server; never put them in browser code. Set these in `.env`:

```dotenv
SOCIETY_LLM_PROVIDER=novita
NOVITA_MODEL=deepseek/deepseek-v4-pro-0813
NOVITA_API_KEY=your_novita_key
```

Or leave `NOVITA_API_KEY` unset and configure `NOVITA_SECRET_ID`, `AWS_REGION`, and
`NOVITA_SECRET_FIELD` (the JSON field holding the credential; defaults to
`NOVITA_API_KEY`). The configured local AWS secret uses `api_key`. A plain-text
secret value is also supported. Novita never reads or forwards the OpenAI key.

The integration follows [Novita's model endpoint](https://novita.ai/models-console/model-detail/deepseek-deepseek-v4-pro-0813)
and [structured-output interface](https://docs.novita.ai/guides/llm-structured-outputs):
`https://api.novita.ai/openai` and Chat Completions. The V4 Pro endpoint currently
rejects `json_schema` despite its catalog listing, so V4 uses `json_object` with
the schema in its prompt and mandatory local validation. V4 uses its default
reasoning mode with an 8,192-token completion budget and a 120-second timeout.
Other Novita models retain the `json_schema` request format. Both model
providers receive the same private history and action rules. Responses are validated
locally before execution; truncated, empty or invalid decisions fail and retry,
without silently switching providers or generating scripted behavior.

The UI and `/api/health` report the selected model; decision records retain the
`novita` source. `stats.llm_decisions` counts LLM decisions while the existing
`astra_decisions` field remains Astra-specific. Set `SOCIETY_LLM_PROVIDER=local`
for an explicit offline rule demo. A selected Novita provider without credentials
fails startup instead of silently falling back.

## Enable OpenAI Astra citizens

Create an API key at [platform.openai.com](https://platform.openai.com/), then configure the server:

```sh
cp .env.example .env
```

Set the key in `.env`:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-6-astra
SOCIETY_LLM_PROVIDER=openai
```

Restart the server. The header will display `ASTRA / LIVE` when real LLM decisions are active. API keys remain server-side and `.env` is excluded from git.

Alternatively, configure `OPENAI_SECRET_ID` with the name of an AWS Secrets Manager secret containing an `OPENAI_API_KEY` field, and optionally `AWS_REGION`. The AWS CLI must already be authenticated. The credential is loaded into server memory and never sent to the browser.

If an Astra request fails, the citizen waits and retries; it does not silently switch to scripted decisions. The header shows provider errors. Without a configured key, the app runs a clearly labeled rule demo that cannot interpret arbitrary broadcast language.

Important broadcasts, direct speech and nearby interventions interrupt current travel and wake the affected citizens. Targeted actions retain their intent while approaching and execute on arrival. Full personal memory is passed to Astra, together with unread events and action instructions. Long-running experiments will eventually need an explicit context-budget policy.

Overheard conversation is remembered without aborting every journey. Short physical tasks finish before replying to non-dangerous messages; attacks and lightning interrupt them and refund reserved resources. Basic body depletion is suspended while a citizen waits for its model decision. A simulation day lasts 720 seconds at 1x and begins at 08:00.

Economic mechanics are fictional. Companies currently make meals, coats or route apps; names, purposes and ambitions are agent-authored. There is no real money, external incorporation or investment execution. City-backed jobs and shop restocking are explicit background sources; the city ledger tracks credits entering or leaving the citizen/company economy. This is not a closed or calibrated model of SF's economy.

The current model of company governance gives founders control over pricing, new financing and cash distributions. Investors receive shares and proportional distributions, not a guaranteed return or governance votes. Production uses a simplified materials charge; broader manufacturing, loans, bankruptcy, secondary share trading and arbitrary new product mechanics are not implemented.

## Controls

- Click a citizen to inspect its private perspective.
- Drag the pixel map to pan; scroll or use the camera buttons to zoom. Click the percentage to fit the city.
- Select **Drop food**, **Lightning**, or **Add restroom**, then click the map.
- Lightning kills on a direct hit and injures citizens nearby, even while paused.
- **Kill citizen** targets one living citizen. Death is permanent within this run;
  click the remains to inspect their last recorded perspective.
- **City Life** shows messages citizens choose to send you and an intervention
  ledger separating memory delivery from subsequent decisions.
- **Toggle fog** changes every citizen's effective sight range.
- **Broadcast** injects a sourced claim into every living citizen's memory.
- Pause or change world speed from the top toolbar.
- Use **Build / edit** to paint terrain tiles as the observer. Keep clicking to build;
  select **Demolish** to remove a tile, or press Escape to leave the brush.

Citizens use the same terrain engine through `salvage`, `build` and `demolish`, with
material costs and local knowledge checks. Building a road or wall changes actual
movement, not just the artwork. Starting roads and citizen-built facilities can be
dismantled; preset landmark buildings are not yet destructible. This is a first 2D
editable-world foundation, not unrestricted voxel physics or arbitrary code execution.

## Architecture

```text
Browser canvas
    ↕ WebSocket / HTTP
FastAPI world server
    ├── Authoritative world simulation
    ├── Perception and communication resolver
    ├── Independent Agent actors and private memories
    ├── Concurrent OpenAI Responses API calls
    ├── Validated action executor
    └── SQLite event store
```

The implementation follows the full [agent society design](docs/agent-society-design.md).

The original pixel artwork and rendering approach are documented in [pixel visual direction](docs/pixel-visual-direction.md), including the Thronglets references and the MVP's current limits.

## Test

```sh
uv run pytest
uv run ruff check app tests
```

Optional live tests (these make real model calls when credentials are configured):

```sh
uv run python -m scripts.smoke_astra_economy
uv run python -m scripts.smoke_astra_interventions
uv run --with playwright python scripts/smoke_browser.py --seconds 60 --pause-after
```

The first is an explicitly seeded seven-decision company/funding/production/build/demolish integration test in a separate world, not evidence of spontaneous entrepreneurship. The browser test observes the local server at port 8001 and pauses it afterward. Event histories are persisted; restarting the server currently creates a new world rather than restoring full simulation state.

The intervention test stages a fatal strike in a separate world and observes six
unprescribed Astra decisions. To test destructive canvas tools on a disposable
server world, run `uv run --with playwright python scripts/smoke_god_browser.py --url http://127.0.0.1:8002`.
It kills two citizens and leaves the remaining simulation running.
See [Thronglets intervention design](docs/thronglets-intervention-design.md) for
episode research, perception boundaries, implemented mechanics and remaining limits.
