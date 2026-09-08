# Geographic city renderer

Historical renderer: the default view has been replaced by [Pixel city](pixel-city.md).
MapLibre modules remain in the repository for reference, but the main UI no longer loads them.

The default SF view uses MapLibre GL JS 5.6.2 and the OpenFreeMap Liberty style.
It is not Google Maps and does not use a Google account or a paid map API key.
Attribution remains visible. Internet access is required for the library, style,
fonts and tiles; the local simulation renderer remains available as Offline map.

- Scroll or pinch to zoom around the pointer, drag to pan, use the compass to rotate.
- The zoom readout button fits eastern San Francisco; Find citizens fits living residents.
- 3D tilts the camera and renders map building heights. Pixel 2D renders the same
  geography at a deliberately low pixel ratio, without perspective. It is a
  pixel-rendered map, not a hand-painted sprite city.
- Yellow creatures are live simulation agents, not decorative pedestrians. Their
  positions are projected using the exact inverse of `SFMap.project`. Selection,
  observer interventions and terrain editing use the inverse camera projection.
- Native map clicks suppress intervention placement after dragging. Intervention
  coordinates outside the authoritative simulation bounds are rejected in the UI.
- Zoom, map navigation, inspection and map styles never resume the simulation or
  invoke an LLM. The API budget is independent of map navigation.

## Important boundary

Eastern SF is geographic context. Only the outlined simulation extent contains the
authoritative resident scenario, facilities and editable terrain. The v2 offline
street geometry extends SoMa and Mission through Mission Bay. Old saved worlds
retain their own v1 geometry: never relabel or reproject old positions with v2 bounds.
Use a fresh database to seed the expanded scenario rather than resetting an old run.

OpenStreetMap building footprints and height extrusions are **visual context**, not
authoritative simulation walls, office interiors or verified resident addresses.
Simulation facilities remain explicitly synthetic street-adjacent sites. Collision
and pathfinding use the server terrain, whose street widths and raster connections
are gameplay approximations. Whole-city routing, surveyed parcels and building
interiors are not implemented by adding this renderer.

## Validation

`uv run --with playwright python scripts/smoke_geo_map.py` checks the paused local
preview on port 8006: actual online map loading, wheel zoom, 2D and 3D selection,
camera projection round trips, safe armed-tool dragging, pixel mode, mobile layout
and offline fallback. Intervention requests are intercepted; no saved world changes
or model calls are permitted. Browser screenshots are written under `/tmp`.

`uv run pytest tests/test_sf_city_movement.py tests/test_sf_map.py` checks official
geometry provenance, connected paths, all 100 residents reaching their home/work
entrances without collisions, and civic editing rules. The route test supplies
street knowledge and fixed move intents to isolate physics; it is not a test of
autonomous LLM behavior or emergent society.

References: [OpenFreeMap setup](https://openfreemap.org/quick_start/),
[MapLibre 3D buildings](https://maplibre.org/maplibre-gl-js/docs/examples/display-buildings-in-3d/).
# Citizen visibility

The initial camera fits the living population instead of the entire eastern SF context.
New SF worlds randomly distribute residents across connected, walkable street cells
within their neighborhood's approximate gameplay catchment. The 100-person sample
uses 100 distinct cells (Mission 56, SoMa 27, Mission Bay 17). Larger samples can use
distinct points within a cell. A fixed seed reproduces the initial layout; saved worlds
keep their existing positions. Homes and workplaces remain separate assignments.
Sprites use physical coordinates at every zoom: no crowd expansion or fake offsets.
Dropping waste, food, or lightning on a sprite targets its physical position.
The map legend reports visible/total living citizens. `Find citizens` restores this framing.
Use `node --test scripts/test_citizen_layout.mjs scripts/test_waste_reactions.mjs` and
`uv run --with playwright python scripts/smoke_citizens_map.py` to verify physical positions,
individual selection, unchanged simulation state, and placement targeting.
