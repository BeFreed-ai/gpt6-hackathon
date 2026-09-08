# Pixel city visual direction

## Reference

The visual reference is Black Mirror: Thronglets, developed by Night School Studio.

- [Netflix's official screenshot gallery](https://www.netflix.com/tudum/galleries/black-mirror-thronglets-game-easter-eggs)
- [Night School Studio's game page and gameplay trailer](https://nightschoolstudio.com/project/black-mirror-thronglets/)

The reference uses tiny yellow creatures, visible pixel clusters, grassy terrain,
chunky trees and facilities, and a cheerful surface over an unsettling simulation.
Our artwork is original, drawn in code; Netflix screenshots are reference material,
not bundled game assets. The design borrows the visual language while retaining
the independent-agent society experiment and its San Francisco setting.

## Repository map

- `app/world.py`: authoritative state, physical needs, actions, resources, housing,
  jobs, weather and world events.
- `app/perception.py`: decides which individual receives which observation.
- `app/brain.py`: OpenAI Astra decisions, plus the explicitly labeled local fallback.
- `app/main.py`: independent asynchronous agent scheduling, HTTP and WebSocket delivery.
- `app/store.py`: SQLite event and memory recording.
- `web/app.js`: connection, controls, selected citizen, private inspector and event feed.
- `web/pixel-world.js`: pixel rendering, animation, camera and coordinate conversion.
- `web/styles.css`: paper-colored observer UI and retro controls.

The implementation is an MVP, not the full design document. In particular, the
initial jobs and housing are seeded, local fallback goals are rule-based, and
replication, a full replay interface and emergent institutions are not implemented.
Pixel art does not change any of these simulation semantics.

## Rendering rules

- Render a 1400 by 820 world into a 560 by 328 logical pixel buffer.
- Disable image smoothing and upscale the buffer with nearest-neighbor sampling.
- Keep the server coordinates intact for selection and interventions at every zoom.
- Cache deterministic grass, paths and small decorative details.
- Draw entities in depth order, with public speech above the scene.
- Give creatures a yellow head, tiny ears, blue clothing and discrete walking frames.
- Show names on hover, selection or closer zoom; show private beliefs only on selection.
- Give building types different roof palettes and identifiable features: clinic cross,
  cafe awning, radio aerial, restroom sign and park benches.
- Keep fog translucent so the observer can still see the population. The simulation
  independently controls each resident's reduced sight range.
- Decoration does not introduce collision geometry or new simulation resources.

## Interaction

Click a citizen to inspect it. Drag to pan. Scroll or use the plus/minus controls to
zoom. Click the percentage to fit the city. Existing interventions retain their
server-side effects. Escape cancels an armed intervention.

## Validation

Browser smoke checks cover startup without JavaScript errors, selection using world
coordinates, zoom in/out, food placement and a narrow mobile viewport. A live run
checks that citizen positions and event counts continue to change independently of
rendering. These checks validate the presentation and simulation connection, not
whether a real LLM society emerges; that requires a configured OpenAI API key.
