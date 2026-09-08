# SF playable map and civic-space implementation

The SF scenario now uses official San Francisco street centerlines in the existing
1400 × 820 play area. All simulated buildings and entrances remain synthetic;
catalog employer addresses are context, never claimed geocodes or real parcels.
The original prototype keeps its existing terrain and renderer branch.

## Source and offline reproduction

The input is the pre-existing `.data/maps/soma-mission-streets.json` cache created
by `scripts/draw_sf_reference.py`. Its source is the City and County of San
Francisco's [DataSF Streets — Active and Retired dataset](https://data.sfgov.org/Geographic-Locations-and-Boundaries/Streets-Active-and-Retired/3psu-pn9h).
The cache contains 2,551 records, retrieved September 8, 2026, with
`data_as_of=2026-09-08T03:55:00.000`. The checked-in file preserves the input
SHA-256, source CNN identifiers, dataset ID, query description and selected
longitude/latitude polylines rounded to seven decimal places.

`data/sf_map.json` contains 1,033 selected named street segments. This selection
excludes freeways, private roads, paper streets and most alleys. No network or API
calls were made for this implementation. To reproduce the checked-in file:

```sh
python scripts/build_sf_map.py
```

To reimport the existing official reference cache:

```sh
python scripts/build_sf_map.py --source .data/maps/soma-mission-streets.json
```

The generator reports input and completion status and supports `--output` for
comparison without overwriting the checked-in map.

## Geometry, gameplay and uncertainty

`SFMap.project(lon, lat)` maps the reference bounds
`[-122.431, 37.7505, -122.393, 37.787]` to a 40-pixel inset. North is up.
Longitude and latitude independently fill the play area, exaggerating east-west
distance. The result preserves recognizable street topology and orientation,
but is explicitly not a scale map. Segments crossing the bounds are geometrically
clipped rather than clamped onto map edges.

`SFMap.graph()` exposes clipped source centerline vertices and edges with CNN
IDs. The physical play network is a connected 20-pixel raster with 1,301 road
cells; 17 disconnected raster cells are omitted from entrance allocation. Road
widths, corner connections and walking access are gameplay assumptions. This is
not a pedestrian accessibility dataset and does not model signal crossings,
elevated structures, transit service or actual rights-of-way.

`SFMap.place(item, neighborhood)` assigns a deterministic, street-adjacent
synthetic one-cell footprint. Each facility's metadata contains
`geography_status=synthetic_street_adjacent`, `footprint_cell`, `entrance`,
`street_names` and `coordinate_basis`. Seeded facilities block movement, while
their adjacent road entrances belong to the connected walk network. Citizen
spawns are at entrances. Neighborhood assignment uses approximate geographic
regions; the renderer labels SoMa and Mission without invented official borders.
Approximate park and transit pins come from the existing reference generator and
are labelled as reference pins, not footprints or functional transit routes.

The pixel renderer displays source street lines and street names, small synthetic
building sprites with entrance marks, district names, approximate landmark pins
and a north indicator. More labels appear with zoom. Demolished road cells erase
the corresponding visual street section; citizen-built tiles remain visible.

## Civic actions and ownership

Citizen-built structures belong to their builder. Roads are shared public space.
Foreign demolition without consent records a dispute, leaves the structure
intact and consumes no materials. Consent is cleared when demolition succeeds.
Seeded facilities remain scenario anchors. Original street and entrance cells
cannot be replaced by walls or facilities, and wall construction cannot seal a
living citizen away from public street access. Open ground remains editable.

Citizens use `talk` with `destination`, `message` and `terms.civic_action`:

| Civic action | Behavior |
| --- | --- |
| `grant_consent` | Owner grants a nearby citizen identified by `terms.grantee_id` demolition consent. |
| `petition` | Proposes removal of an existing public tile; message explains why; proposer casts first vote. |
| `endorse` | Adds one distinct citizen vote to the tile's current petition. |
| `dispute` | Records the citizen's stated objection without granting demolition authority. |

Public petitions require two distinct living nearby participants, or one in a
singleton world. Approval grants the proposer consent for that tile. This small
quorum is an explicit simulation convention, not a claim about San Francisco law
or a measured community preference. Observer edits can override ownership, but
their reason is recorded as a civic dispute/override; no police or enforcement
agents are invented. A dispute does not veto an approved petition automatically.

## Root integration contract

1. `seed_sf_scenario` installs `world.sf_map`, `terrain.map_metadata` and facility
   metadata before population spawning. `world.sf_map` is a seed-time facade.
2. `Terrain.snapshot()` includes `map` and `civic`. Preserve those in observer
   snapshots; `PixelWorld` reads `state.terrain.map`.
3. In `_approach` and pending-action arrival, use `metadata.entrance` when present;
   otherwise preserve the old object position. Civic TALK approaches an adjacent
   open edge when its destination tile is a wall. If pending movement refreshes
   tile targets each tick, include civic TALK in its end-cell clearance exception
   alongside BUILD/DEMOLISH. Update tests
   that manually stand agents inside a seeded SF building to use its entrance.
4. Add `terrain.civic_for(agent)` to the citizen context. It filters civic sites
   by the citizen's surveyed terrain. Full `civic_snapshot()` is for observers.
5. Model/brain integration requires optional `ActionTerms.civic_action` with
   `grant_consent|petition|endorse|dispute` and optional `grantee_id`. The terrain
   handler intercepts TALK only when civic_action is set; ordinary speech is
   unchanged. Validate model action fields and teach these civic choices.
6. Persist terrain `tiles`, `revision`, `map_metadata`, `consents`, `petitions`,
   `disputes`, `civic_revision`, and `protected_cells`. All are JSON-compatible
   except `protected_cells`, which must encode as a sorted list and restore as
   `set[str]`. Store physical and civic state with the same World transaction.
7. Exclude `world.sf_map` from JSON checkpoints. Restore with `SFMap()` only if a
   consumer needs the static graph. Runtime construction uses Terrain, not its
   seed-time placement allocator. If using `place` after restore, repopulate
   `_used` from object `footprint_cell` metadata first.

Root owns shared API/UI integration, action context, durable checkpointing and
browser verification. This worker changed only the assigned map/scenario/terrain,
pixel renderer, generator, map data, module tests and this document.

## Validation

`tests/test_sf_map.py` covers byte-identical offline regeneration, provenance,
projection orientation and roundtrip, clipping, all building entrances on one
connected road network, physical routes to every entrance, ownership and
single-use consent, public-road protection, recorded observer overrides,
snapshot isolation, anti-entrapment, petition quorum and civic TALK actions.
Existing `tests/test_terrain.py` exercises prototype movement and construction.
JavaScript syntax is checked with `node --check web/pixel-world.js`.
No live server, credentials, LLM provider or paid API is used by these checks.

Worker completion checks: 32 tests passed across `test_sf_map.py`,
`test_terrain.py` and `test_sf_scenario.py`; Ruff and JavaScript syntax checks
passed. The 500-citizen offline smoke check created 71 objects and zero blocked
spawns. Root subsequently took ownership of the pixel renderer for a requested
visual redesign; the map JSON/interface contracts remain available to that work.
