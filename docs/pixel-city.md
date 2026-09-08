# Pixel city presentation

The default renderer is now `web/pixel-city.js`, not MapLibre. It draws an original
pixel city inspired by [Netflix's Thronglets screenshots](https://www.netflix.com/tudum/articles/black-mirror-thronglets-mobile-game-news).
This is a style reference, not a pixel-for-pixel reproduction or Netflix asset reuse.
No online basemap, map-library download, satellite imagery, or map API key is needed.

## What is retained

- Every existing simulation facility, employer, home, and citizen uses the original
  world ID and physical coordinate. Personal memories and saved lives are unchanged.
- SoMa and Mission Bay have dedicated camera buttons. Mission residents remain in
  the simulation with their own Mission camera button. SF overview reveals the
  whole peninsula, then district buttons return to detailed streets.
- All existing facilities are searchable in Go to a place. Selecting a citizen
  exposes Show home / Show workplace and highlights those places from their private
  inspector response, not from another citizen's knowledge.
- Named companies have visible signs and distinct office facades. Generic residual
  workplaces are retained but do not cover the map with long calibration labels.
- Road tiles and edited walls/floors come from authoritative terrain. Background
  texture and foliage are decorative. Building cracks and ruins use actual damage.
- Close-up ground is continuous and clipped to the geographic coastline, not a
  checkerboard of physics cells. Building sprites use side walls, pitched/parapet
  roof variants, bay windows and stable per-building height variation; tree crowns
  and small parks use stepped organic silhouettes. These are art changes only:
  entrances, citizen feet, collision cells and interaction targets do not move.
- The outer city and the live districts now share one cached decoration canvas,
  the same building scale, and the same ground palette. There is no rectangular
  cutout underneath the live canvas and no second interior building generator.
  Neighborhood detail emphasis changes continuously with geographic distance;
  it never fades actors, damage or interactions. The local ground is an exact crop
  of this shared canvas, with only authoritative terrain overlays. Cache invalidation
  includes terrain revision and place positions so newly built sites retain clearance.

## Landmarks

Existing map anchors include Yerba Buena Gardens, Victoria Manalo Draves Park,
Caltrain and Mission BART stations. Additional visual landmarks are Oracle Park,
Chase Center and UCSF Mission Bay (Housing South reference point). These pins use
longitude/latitude through the same north-up affine transform as `SFMap.project`.
Neither occupied cells nor screen layout may relocate a pin. Symbol dimensions are
illustrative, not surveyed footprints or implemented stadium/hospital services.
The location picker identifies reference pins separately from simulation facilities.

References: [Oracle Park](https://www.mlb.com/giants/ballpark),
[Chase Center](https://chasecenter.com/),
[UCSF locations](https://www.ucsf.edu/about/locations). Coordinate references:
[Oracle Park](https://mapcarta.com/23106278),
[Chase Center](https://mapcarta.com/W579646390),
[UCSF Housing South seismic evaluation](https://realestate.ucsf.edu/sites/g/files/tkssra17111/files/UCSF_3036_UCOP%20PRESUMPTIVE%20FORM_MB%20HOUSING%20SOUTH_20190904%20-%20Final.pdf).

## Coordinate contract and remaining geographic limitations

- Citizen feet, waste, usable facilities, road collision cells, camera transforms,
  picking and god-tool placement share authoritative world coordinates. Earthquake
  screen shake is included in the inverse click transform too.
- Pixel art does not spread citizens apart or move scenery into an empty block.
- Existing workplaces and homes still have **synthetic gameplay sites**, not verified
  street addresses. Navigation now displays their coordinate basis and world position.
  Rendering an office at a different real-address pin would break the contract;
  accurate workplace migration must update simulation placement and routing together.
- The coast now comes from the public-domain [DataSF shoreline dataset](https://data.sf.gov/Geographic-Locations-and-Boundaries/SF-Shoreline-and-Islands/txuc-3kzm),
  simplified by `scripts/build_sf_coast.py` and bundled offline. This is historical
  geographic data, not a current survey. Parks and background roofs are illustrative
  envelopes/architecture, not surveyed parcels. Road asphalt follows official
  centerlines inside the authoritative walkable street/sidewalk tiles.
- `sf-city-context.js` adds the full peninsula, both bridges, Coit Tower, the
  Transamerica Pyramid, Ferry Building, Salesforce Tower and Sutro Tower outside
  the live-area canvas, through the same projection. Tower heights and bridge
  elevations are exaggerated symbols. The northern bridge endpoint leads toward
  Marin; Marin itself is not included in the SF-only coastline dataset.
- The outer context has no actors or interactive services. All 100 existing lives,
  assigned places and paid-call limits remain unchanged. No reset or migration occurs.
- The map projection fits longitude and latitude independently; it is not to scale.
  Coordinates outside the world remain outside instead of being clamped inward.
  Some catalog addresses are outside this map; Anthropic's correspondence address
  is not evidence of a workplace. Private homes remain fictional.

Visual references: [SoMa / Yerba Buena](https://www.sftravel.com/neighborhoods/soma-yerba-buena),
[Mission murals](https://www.sftravel.com/article/guide-to-san-franciscos-mission-district-murals),
[Golden Gate Bridge location](https://www.goldengate.org/bridge/history-research/statistics-data/faqs/),
[Coit Tower coordinates](https://www.geonames.org/5338366/coit-tower.html),
[Sutro Tower coordinates](https://gml.noaa.gov/dv/site/index.php?stacode=STR).

## Visible actions and truthfulness

The articulated citizen and waste effects are shared with `citizen-art.js` and
`waste-reactions.js`. Walking, public speech gestures, waste contact/compression,
falling, and confirmed traumatic impacts use existing action/event state. Additional
work, cleaning, food, repair and aid props represent current execution strings;
walking to an office is not shown as working. Buying is not shown as eating.
Only public speech appears in dialogue bubbles. No renderer generates model choices,
dialogue, private beliefs, or societal reactions. Idle people remain idle.

Automated presentation tests use isolated fixtures without paid model calls.
Offscreen controlled action fixtures test rendering, not autonomous LLM behavior.

## Structural damage in pixel view

`pixel-damage.js` reads authoritative structure state, not distance to a visual
effect. Damaged buildings retain cracks, broken windows and closure barricades;
major damage removes roof/wall sections and exposes floors. Newly collapsed
structures descend at the same ground anchor for 850 ms, emit pixel dust, and
remain as rubble. Actual partial repairs show scaffolding and partial walls;
completed repairs restore the original facade. Reduced motion skips animation.
Old damage never replays on reload, and repair/deletion clears transient debris.
Decorative context architecture and reference-only landmarks remain non-physical;
they do not acquire invented damage from a nearby earthquake.

`earthquake-reactions.js` displays a flinch and an alert marker for living recipients
whose action was interrupted by an earthquake. The reflex expires after eight
simulation seconds or when a new action begins; it is not an LLM decision. Durable
intervention receipts preserve the earthquake when its damage/injury messages
overflow the 35-event public feed. Reload never replays the transient shaking.
Later walking, repair, shelter-seeking or speech comes only from actual decisions.

`uv run --with playwright python scripts/smoke_pixel_damage.py` runs actual quake
and repair mechanics in a temporary database, checks all 100 receive the stimulus,
validates a casualty and six rendered stages, and checks reload suppression. It
neither mutates the live preview nor invokes a model. Comparison screenshot:
`/tmp/sf-pixel-damage-stages.png`.

## Verification

`node --test scripts/test_pixel_city.mjs scripts/test_citizen_art.mjs scripts/test_waste_reactions.mjs scripts/test_pixel_damage.mjs scripts/test_earthquake_reactions.mjs`

`uv run --with playwright python scripts/smoke_pixel_city.py`

Browser checks cover both neighborhoods, OpenAI navigation, all 100 physical
positions, body selection, the selected resident's home, real waste navigation,
action fixtures, mobile layout, unchanged live state, and zero model calls.
They also compare undisturbed edge pixels with the shared context source and capture
the former inset at medium zoom in `/tmp/sf-pixel-continuous-city.png`.
