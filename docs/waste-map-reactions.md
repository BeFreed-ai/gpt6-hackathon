# Citizen close-ups and physical-event presentation

The camera's **Close-up** button focuses the selected citizen (or a reacting/live
citizen if none is selected). The geographic camera supports zoom 22 and enlarges
the actual sprite with zoom; the offline camera focuses at 600%. Selection and
hazard placement include the visible body while retaining the exact server foot
position. No citizen is displaced to make a crowd easier to see.

`web/citizen-art.js` draws separate arms, legs, shoes, torso, head and facial
features. Eight walking frames depict an existing walking/commuting action;
four gesturing frames accompany existing public speech. Pausing freezes voluntary
motion. Eight contact poses depict foot contact, arm recoil, a raised dirty shoe
and a pinched expression. These are original code-drawn sprites, not assets copied
from the television reference, and are a limited animation set rather than a
complete cinematic character system.

Both map renderers draw a layered pixel-art waste pile from live world objects.
The pile spreads and loses height over 300 ms after a confirmed contact. Its
flattened state derives from numeric `step_<agent_id>` timestamps already saved
on the waste object; loading a save shows that shape without replaying a step.
Removing the object after cleanup removes its marker. A new `stepped_in_waste`
event briefly gives the targeted citizen a pinched-eye expression, lifted foot,
small recoil and shoe-level splatter. The animation lasts at most 2.4 seconds of
browser time, including when the simulation is paused. An active server reaction
can retain the expression after the moving effect ends. Reduced-motion preference
disables the lift and rotation.

A newly appearing remains object gets an eight-frame fall. Confirmed earthquake
or attack deaths show a brief stylized red splatter, impact dust, and a small
persistent blood mark beneath the body. The renderer checks the existing
`death_cause` on the public agent or remains metadata. For an already-running
server without that field, an explicit earthquake casualty in `interventions`
also provides confirmation. Unknown or health-failure deaths do not acquire an
invented traumatic cause. On legacy servers, the casualty receipt is bounded;
once it leaves the feed, retaining blood requires the death-cause snapshot hook.
Removing remains removes the presentation. Initial loads show bodies already
down, reduced motion shows the final pose, and no animation changes anyone's
health or decides death.

`web/waste-reactions.js` and `web/citizen-art.js` consume public snapshots only. Neither sends requests
nor modifies positions, plans, speech, memories, or action targets. Its short text
is an unquoted event label; only actual agent speech receives quotation marks in
the geographic renderer. Existing independent brain decisions still choose all
subsequent actions, including doing nothing. No cleaning, reporting, route change,
dialogue, or future goal is selected by the renderer.

The event target IDs distinguish the person who stepped from witnesses. A rising
public contact flag covers bounded event feeds that omit an earlier impact.
Repeated snapshots do not restart an animation; initial loads and world changes
prime the event history without replaying impacts. Existing backend contact
cooldowns and physical cleanliness/stress consequences are unchanged.

Validation:

```sh
node --test scripts/test_citizen_art.mjs scripts/test_waste_reactions.mjs scripts/test_building_meshes.mjs scripts/test_citizen_layout.mjs
python -m pytest tests/test_disaster_reactions.py -q
```

Twelve JavaScript checks and eight backend checks passed. An isolated Playwright
fixture also exercised the actual MapLibre 5.6.2 layer definitions and the offline
canvas, checking target-only sprites, cleanup, death frames and blood sprites,
close-up body picking, animation expiry on a paused
snapshot, no authoritative-state mutations, and no browser/style errors. The
fixture made no requests to a running simulation or model provider; it used a
pinned map-library download with local synthetic data and empty map tiles.
