# Implementation checkpoint

## Latest: god interventions and permanent death

- Current app: `http://127.0.0.1:8002`, server session 88704, process 28713,
  database `.data/sf-god-live.db`. Running at 1x after browser validation.
  The old port 8001 world was paused and preserved, not restarted or deleted.
- Added `app/lifecycle.py`: instant death, canceled work/reservations, dropped
  inventory, voided pending offers, local remains and private later discovery.
- Lightning: 100 damage within 24 units, 35 within 70; immediately fatal at zero
  health even while paused. Explicit Kill citizen tool targets a living ID.
  Natural and attack deaths use the same lifecycle. No resurrection.
- Sound-only listeners no longer receive victim/attacker identities as sight;
  later remains do not reveal cause. Nearby deaths wake and interrupt citizens.
- New `address_player` action delivers optional citizen-initiated messages to an
  observer inbox and to local ears, never globally to other agent contexts.
- City Life now contains an observer-only intervention/followup ledger. Records
  distinguish delivery from subsequent decisions; no consciousness score.
- Latest verification: 56 passing tests, Ruff and JS syntax clean. Six real Astra
  decisions in a staged strike test: witness warned another and sought shelter,
  listener distinguished testimony from sight, distant citizen built a bench.
  No reaction or new goal was specified in that test.
- Canvas browser test killed Mimo with Kill citizen and Piko with Lightning while
  paused. Deceased inspector worked; remaining 10 citizens made 21 real decisions
  over 40 seconds, with four logged followups and no browser/provider errors.
  No spontaneous address_player message occurred during that short observation.
- Screenshots inspected: `/tmp/sf-god-desktop.png`, `/tmp/sf-god-mobile.png`.
- Source research and limits: `docs/thronglets-intervention-design.md`.
  Replication, inherited culture, funerals, governance, inheritance/succession and
  full-state restoration are still absent. No claim of consciousness or complete
  Netflix game recreation. No commits or pushes in this iteration.

## Product decisions

- Build a playable original pixel-art SF urban survival society, inspired by
  Thronglets and Don't Starve. All implementation and UI text must be English.
- Every citizen uses an independent OpenAI `gpt-6-astra` decision context. Only
  personally experienced or locally received events become its knowledge.
- Goals and stated values are self-selected. Private inspection appears on click.
- SF defines survival: housing, food access, public toilets, maintenance, weather,
  mutual aid and opportunities beyond survival. See `ai-survival-direction.md`.
- Latest addition: citizens must be able to found companies, seek investment,
  negotiate, hire and deliver products/services with actual economic consequences.
  These are fictional simulation mechanics, not real-world financial/legal advice.

## Existing implementation

- FastAPI authoritative world, per-agent concurrent decisions, SQLite event history,
  WebSocket pixel canvas, independent memories and click-only inspector.
- Broadcast delivery and action approach/arrival repaired; stale in-flight decisions
  rejected on new stimuli; configured provider errors do not silently use rules.
- Real Astra tested with all 12 citizens. Credential loads server-side from AWS
  Secrets Manager using the gitignored `.env` reference. Never print secret values.
- Baseline: 17 passing tests and clean Ruff. App and web implementation are currently
  uncommitted; preserve all existing work. Do not push without a new request.
- Last tested server: `http://127.0.0.1:8001`, simulation paused, database
  `.data/astra-live.db`. Inspect process state before restarting.

## Current implementation plan

1. Inspect existing world, action schema, brain and UI before extending them.
2. Implement a coherent first urban survival/economic slice: actual food access,
   facility capacity/time, production or maintenance and visible world results.
3. Add companies, treasuries, ownership, explicit investment offers/acceptance and
   paid work with real outputs. Company funds stay separate from personal credits.
4. Expose only observed opportunities and supported actions to each citizen; retain
   self-chosen projects without assigning everyone a founder role.
5. Add visible facilities/businesses, relevant inspection and progress feedback.
6. Test resource conservation, negotiation consent, action completion, privacy and
   browser behavior. Run bounded live Astra tests using the existing AWS credential.

## Progress and latest steering

- SF facilities, portable goods, timed actions, housing invitations, companies,
  funding consent/dilution, hiring, production, sales and dividends are implemented.
- 34 tests passed before the latest overhearing regression test was added.
- Real Astra five-decision seeded integration test passed: found, offer funding,
  accept, produce, buy. This is NOT evidence of unprompted entrepreneurship.
- Browser live test passed: 12 citizens, 61 applied Astra decisions, no JS/provider
  errors. Citizens rented rooms, cooked and shared meals; no spontaneous company yet.
- Server session 94592 is paused on port 8001, using `.data/sf-economy-live.db`.
  It predates the newest overhearing change; restart after the next implementation.
- Latest user requirement: an open, Minecraft-like editable city. Citizens must
  physically change routes and appearance, not merely request changes in speech.
- Next: editable terrain/building primitives with real collision and pathfinding,
  material costs, reversible construction/demolition, perception and visible pixels.

## Latest verified implementation

- Editable terrain is implemented in `app/terrain.py`: roads, walls, floors, signs,
  and placed gardens, benches, kitchens, toilets and shelters. Costs use reclaimed
  material items obtained through timed salvage. Preset landmarks remain protected.
- Pathfinding uses personal terrain observations; physical collision checks real
  walls. Roads affect movement speed. New obstacles cause route recalculation.
- Browser Build / edit brush places and removes tiles; actual clicks verified road,
  wall and demolition. Desktop/mobile renders passed without JS errors.
- 47 tests pass; Ruff and JavaScript syntax checks are clean.
  Seven real Astra decisions passed the explicitly seeded
  economy + build/demolish integration check. Test history remains in SQLite.
- Current server session: 54357, port 8001, `.data/sf-editable-live.db`.
  The visible simulation was resumed after the browser editing check.
- Construction updates are real physical mutations. Arbitrary physics, full voxel
  building and full world restoration on server restart are still outside this slice.
- In the prior unscripted editable-city run, three citizens actually built benches:
  Piko at (44,17), Luma at (33,29), and Kiko at (60,22). These were model-selected,
  material-consuming actions, not the seeded integration test. No spontaneous
  company was observed in that short run. Histories remain in the database.
- Latest improvement exposes facility footprints and surveyed free tile coordinates
  in personal context after observing placement failures. Restarted for this change;
  the latest run starts a new city (full-state resume is not implemented).
- Latest browser run passed at 40 simulated seconds with 23 Astra decisions, no
  provider or JavaScript errors, and Piko autonomously built a bench at (44,10).
  The visible Chrome window shows ASTRA / LIVE and the simulation is running at 1x.

## Working constraints

- Use `apply_patch` for edits, `python` rather than `python3`, and preserve dirty work.
- No delegated agents unless specifically authorized. No real external company,
  investment, message or payment actions: every economic operation is in-game only.
- There is no exposed manual context-compaction tool. This file is a durable concise
  checkpoint for continuation; it is not a claim that conversation context was reset.
