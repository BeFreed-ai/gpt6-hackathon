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
- OpenAI Astra mode, with a clearly labeled rule demo when no key is configured
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

## Enable OpenAI Astra citizens

Create an API key at [platform.openai.com](https://platform.openai.com/), then configure the server:

```sh
cp .env.example .env
```

Set the key in `.env`:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-6-astra
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
