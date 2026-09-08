# Citizen interaction lab

Open `/static/interaction-replay.html` on the existing app server. The default is the street sanitation case; `?case=housing_loss` shows the housing-loss, squat, waste-creation, and walking-away sequence. `?scene=sanitation` remains compatible, and `?scene=peer` opens the original sequential social fixture.

The catalog contains 45 isolated scenarios: all 34 current `ActionType` values and 11 physical scenarios. Search or choose a category, then use Play/Pause, the step arrows, Replay step, the timeline, and zoom controls. The details show actual engine events and before/after observer facts. Offers remain pending until a separately recorded recipient decision accepts or rejects them.

The demo uses a dedicated flat inspection stage. Facility footprints render below bodies, and small waste objects remain visible above feet. Names sit below the interaction area. Actor and object world coordinates come from recorded snapshots; the stage is not a geographic map. The production SF map renderer is unchanged by this page. Squatting, waste creation, compression, social gestures, and death impacts reuse the production presentation modules. Some actions share a gesture or appear as an object/state change rather than having a dedicated animation. Only confirmed traumatic deaths receive blood impacts.

## Rebuild and verify

From the project root, use the project environment (`.venv/bin/python` here):

```sh
.venv/bin/python scripts/build_sanitation_replay.py
.venv/bin/python scripts/build_interaction_catalog.py
.venv/bin/python -m pytest tests/test_interaction_catalog.py tests/test_street_sanitation.py -q
node --test scripts/test_citizen_art.mjs scripts/test_citizen_interactions.mjs scripts/test_street_sanitation.mjs scripts/test_waste_reactions.mjs
python scripts/smoke_interaction_catalog.py
python scripts/smoke_citizen_interactions.py
```

Generators report progress and use real engine actions in temporary SQLite stores; they never load or replace an existing saved city. Each fixture has a seeded world. Run identifiers are newly generated, so output IDs are not byte-identical between builds. The checked-in JSON plays offline from local static resources without importing the Python application or invoking a model. No provider credentials are read. Browser smoke checks expect the already-running local server on port 8007 and permit only local static GET requests. They do not start a server.

The generator asserts all actions are accepted and finish. Tests independently check transfer, wages, energy, toilet use, sanitation, cleanup, repairs, housing offers, and casualties. Browser coverage includes all 194 recorded steps, actor/facility drawing order, visible waste pixels, immutable snapshot data, playback pause, and search. Example screenshots are written to `/tmp/interaction-catalog-sanitation.png` and `/tmp/interaction-catalog-collapse.png`.

## Limits

This is an engine-mechanics catalog with test-supplied decisions, not a live LLM run. It enumerates supported actions, not every possible emergent conversation, biography, or future story. It does not schedule citizens or choose their next action in the live city. Independent model decision-making and existing request limits remain the runtime's responsibility.

Housing loss uses the existing 60-unpaid-budget-day scenario rule. Zero cash and no home do not cause street defecation; the bladder threshold is independent. The final housing frame includes an explicit test-supplied walking decision to demonstrate persistent waste. No real person's bodily or private history is asserted.

Static demo changes appear without a backend restart. The separate sanitation engine changes and scheduler's `relief_until` guard require the coordinator's normal backend integration/restart before affecting a live city. This task did not restart that server or enable paid calls.
