# Citizen-to-citizen interactions

Citizens act through the existing independent brain and `ActionIntent` runtime.
The renderer never chooses an action, reply, relationship, acceptance or refusal.
No player-to-citizen messaging UI was added.

| Interaction | Engine behavior | Presentation |
| --- | --- | --- |
| Talk / shout / radio | Approach a recipient or station; deliver speech through local perception; a separate decision may reply using a received memory ID | Existing speech bubbles; the speaker faces a confirmed recipient and gestures |
| Give | Approach another living citizen; transfer a carried item into their bag, subject to capacity | Reach, recipient handoff pose and a generic parcel transfer |
| Help | Approach and apply first aid to a living citizen | Reach and brief aid marker; no automatic gratitude |
| Attack | Approach and apply injury; death goes through the existing lifecycle | Strike, recipient flinch and impact; existing death effects handle fatalities |
| Housing / job / investment offer | Create a private pending offer; acceptance and refusal require the recipient's decision | Document marker and offering pose; no implied agreement |
| Accept / reject | Validate recipient, offer status, availability and resources before changing housing, work, shares or credits | Distinct agreement/refusal poses |
| Relationships | Each brain may explicitly update its own opinion of known people | Observer inspector shows that person's recorded view |

Other existing actions include movement, eating, rest, work, buying, cooking,
cleaning, repair, shelter, toilets, construction, founding companies, pricing and
dividends. They are capabilities with prerequisites, not behaviors every citizen
is forced to perform. Some of these have props in the main renderer; this change
does not claim a complete bespoke animation for every action.

`web/citizen-interactions.js` consumes confirmed event IDs and live participants.
It rejects stale events, deduplicates repeated snapshots, clears effects on world
changes or death, and never replays old events on initial load. Effects expire
after 1.8 seconds of browser time. Reduced-motion uses a static pose. Witnesses
do not get recipient poses, and receiving speech or an offer does not generate
a speaking or accepting animation. Map positions stay authoritative.

The `With others` inspector section shows the selected person's recent peer events
from the bounded public event feed. It is not a complete archived conversation.
Private source data and agent memories remain unchanged.

## Validation and viewing

```sh
python scripts/build_interaction_replay.py
python -m pytest tests/test_interactions.py tests/test_economy.py tests/test_lifecycle.py -q
node --test scripts/test_citizen_interactions.mjs scripts/test_citizen_art.mjs scripts/test_pixel_city.mjs
python scripts/smoke_citizen_interactions.py
```

Use the project Python environment for the builder and pytest; the browser script
requires Playwright. The builder creates a temporary isolated database, executes
real World actions supplied by the test, asserts their consequences, and writes
`web/interaction-replay-data.json`. It calls no brain or model API.

With the existing preview server available, open
`http://127.0.0.1:8007/static/interaction-replay.html` and use **Next interaction**
or **Replay this interaction**. This is explicitly a mechanics test replay, not
a live LLM demonstration. The browser check allows only GET requests to static
files and exercises the integrated renderer for all eight interaction steps.

Validation completed: 35 existing backend tests, 13 targeted JavaScript tests,
and the browser sequence passed, with zero model calls or simulation commands.
The live city's save, paused state, request cap and provider configuration were
not changed. Live autonomous interaction remains dependent on the coordinator's
LLM runtime configuration; the current preview keeps paid calls disabled.
