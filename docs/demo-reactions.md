# SF demo reaction mechanisms

Implemented:

- 100 independent private event inboxes and histories. Earthquake sensation reaches all
  living residents; facility damage is learned locally, not from a global damage list.
- Earthquakes invalidate pending model decisions, interrupt movement and refund canceled
  physical activities. Within 90 world units buildings collapse; within 170 they take major
  damage; within 240 they take minor damage. Repeat quakes compound damage. Falling masonry
  beside the shared building footprint can kill; health is no longer clamped above zero.
  This is a deliberately stylized gameplay model, not seismic engineering or SF risk data.
- Synthetic gameplay sites have procedural 3D geometry: nine wall/roof sections, exterior
  windows, rooftop equipment, cracks, broken floors and deterministic scattered rubble.
  The snapshot carries the same footprint used for casualty exposure. Collapse animates
  over 2.1 seconds, then persists as low rubble geometry. Surviving damaged walls remain
  visibly uneven. MapLibre adds camera shake and dust; reload restores ruins without
  replaying the earthquake. Corpses use fallen citizen sprites. Offline mode shows ruins.
  Unmanaged OSM buildings remain contextual, not destructible surveyed building models.
- Repair takes 12 simulation seconds and adds 30 structural integrity, so a collapsed
  building needs four work blocks. Geometry changes during rebuilding; services reopen at
  100. This simplified reconstruction currently costs labor but no materials. Temporary
  damage does not fire employees. Company sync cannot reopen a quake-damaged workplace.
  Ruins do not yet block neighboring roads; there is no rigid-body debris collision solver.
- Every living citizen first receives the earthquake in their own history. Death is
  permanent in the run, cancels scheduled model work and leaves discoverable remains.
  Survivors learn individual injuries, deaths and damage only within perception range.
  Queued turns are ordered by due time and decision count to avoid insertion-order bias.
- Street-waste placement creates a real proximity hazard. Stepping in it changes stress
  and cleanliness, creates private experience plus nearby observation, and interrupts the
  citizen for a fresh decision. The same hazard has a 25-second per-person cooldown.
- Public speech and visible reactions appear over citizens. Selecting a citizen shows
  their current action; Follow keeps the camera centered. Private beliefs stay in the
  inspector, not map labels.
- Personal clock context and deduplicated private work reminders. Service schedules are
  08:00–16:00 daily and office schedules 09:00–17:00 weekdays, explicitly synthetic.
  Reminders do not force work. Paid work is still compressed into short blocks, not a
  realistic eight-hour employment simulation. Start date is a synthetic Monday.

Validation separates physical correctness from model behavior: offline tests exercise
100 scheduled decisions with a stub provider. This does not prove 100 live LLM responses,
diverse personalities, consciousness or emergence. Dialogue, arguments and rescue are
not scripted or guaranteed. Real footage needs a bounded live run and editing of events
that actually occur, not invented AI reactions. The Novita preview retains its 24-request
cap; 100 residents cannot all receive a paid turn under that cap.

Live playback does not hold already-resolved physical actions behind pending model
responses. The shared clock waits only when no resident has an active physical action;
thinking residents retain per-person body-clock protection, but city time and schedules
can advance while other residents act. This trades strict lockstep timing for visible
continuous playback. At the request cap, no more model calls are scheduled; existing
walks and activities finish (or are interrupted naturally), then the world pauses.
`Find waste` zooms to an existing hazard; it never creates one or fabricates a reaction.

Geometry implementation uses native MapLibre polygon extrusions rather than a new game
engine or external model downloads. Reference:
https://maplibre.org/maplibre-gl-js/docs/examples/3d-extrusion-floorplan/
Run `node --test scripts/test_building_meshes.mjs` for geometry invariants, and
`uv run --with playwright python scripts/smoke_disaster_map.py` against a disposable,
paused, LOCAL-provider 100-person server on port 8008 for before/after 3D browser checks.
