# Reproducible 100-adult SF neighborhood scenario

The checked-in [roster and allocation audit](../data/sf_population_100.json) contains
exactly 100 unique simulated adults: 98 fictional residents with distinct public
professional counterparts and two explicitly
labeled public-figure simulations. It represents **Mission, South of Market and
Mission Bay residents**, with a **citywide workplace-industry proxy**. It is not a measured
representative sample of all San Francisco or eastern SF. The runnable geography
includes SoMa/Mission/Mission Bay; a broader eastern-SF renderer does not change the resident
denominator. This document supersedes the older documents' 25% allocation description
for newly created SF worlds. The legacy two-neighborhood demographic sampler and
25% employer allocator remain available for existing callers.

## Rebuild and inspect

From the repository root, with the project's installed dependencies:

```sh
python scripts/build_sf_population_100.py
python scripts/build_sf_population_100.py --check
python -m pytest tests/test_population.py tests/test_employers.py tests/test_sf_scenario.py tests/test_sf_population_100.py tests/test_sf_economy.py -q
```

The generator reports three stages. It reads checked-in JSON, constructs one
disposable in-memory world to validate placement and finalize household finances,
then writes only the requested JSON artifact. It creates no service or brain,
uses no network, credentials, LLM calls or saved-world database, and starts no
server. `--check` compares complete deterministic output without writing. `--seed`
changes fictional assignments reproducibly; default 17 is the audited realization.
The artifact is an audit, **not an importable checkpoint**. Runtime regenerates the
same baseline from count/seed and checked-in inputs.

Each of the 100 roster entries contains an ID, name, age, neighborhood, occupation
group and title, industry, workplace ID/name, private life history, initial position,
home, rental arrangement, household rent, rent share, wages/support and starting
cash. Source hashes identify population, employer, economy, map and public-figure inputs. No roster
or private finance fields are added to the public world snapshot.

## Denominators and evidence

Sources checked September 8, 2026:

| Measure | Observation and use |
| --- | --- |
| Latest verified state city/county total | California DOF E-2 preliminary July 1, 2025 population **842,457**, published February 2026; citywide context only, not a 2026 count or the neighborhood denominator. [Official release](https://dof.ca.gov/media/docs/forecasting/Demographics/estimates/PressRelease_July2025.pdf), [E-2 landing page](https://dof.ca.gov/forecasting/demographics/estimates/e-2/) |
| Neighborhood residents | DataSF ACS 2019–2023: Mission **54,431** all ages / **47,644** adults; South of Market **24,698** / **22,924**; Mission Bay **16,710** / **14,213**. Combined **95,839** residents, including **11,058** children excluded from this adult scenario. Same-vintage city context is **836,321**, a different series from DOF. [DataSF](https://data.sfgov.org/d/4qbq-hvtt) |
| Resident work status/occupation | SF Planning ACS 2016–2020 age-16+ neighborhood marginals, explicitly used as an older adult proxy. The source's unemployment column uses all age-16+ residents as denominator; employed share is participation minus that column. No 2026 joint distribution is asserted. [Official Planning repository CSV](https://raw.githubusercontent.com/sfcpc/san-francisco-neighborhood-profiles/main/output/Neighborhood_profiles_by_geo_2020.csv) |
| Industry jobs and establishments | **2025 annual-average QCEW**, SF County FIPS 06075; checked-in rows preserve ownership and NAICS. Private total: **586,454 jobs**, **65,884 establishments**. Federal/state/local totals: **11,030 / 50,166 / 49,242 jobs**. Selected disjoint sector rows sum to **696,891**, one job below the all-ownership sum due to annual-average rounding. [BLS source CSV](https://data.bls.gov/cew/data/api/2025/a/area/06075.csv), [API documentation](https://www.bls.gov/cew/additional-resources/open-data/home.htm) |
| Actual locations | Existing catalog retains official employer/agency address links, approximate coordinates, and geographic scope. DataSF's registry describes registered business **locations**, not staffing, attendance, company totals or worker counts. No registration count is used as a workforce weight. [Registry](https://data.sfgov.org/Economy-and-Community/Registered-Business-Locations-San-Francisco/g8m3-pdis), [catalog](../data/sf_employers.json) |
| Available local staff estimates | Salesforce **8,500** and Google **4,000** are historical SF-city estimates from January 2025, republished in a city bond disclosure; they are neither current site headcounts nor sample-resident shares. The disclosure excludes subsequent announced reductions. Other catalog local counts remain **null**; all unknown site counts remain unknown. [Disclosure, Appendix A-5 / PDF page 109](https://media.api.sf.gov/documents/City__County_of_San_Francisco_IRFDNo.1_TIRB_Ser2025B_POS.pdf) |
| OpenAI Mission Bay office | Official OpenAI public letterhead gives **1455 3rd Street, San Francisco, CA 94158**, dated October 27, 2025. Coordinates are approximate, and local/site staffing stays **null**. Three synthetic workers are a requested scenario quota, not measured staffing. [OpenAI primary source, page 1](https://cdn.openai.com/pdf/21b88bb5-10a3-4566-919d-f9a6b9c3e632/openai-ostp-rfi-oct-27-2025.pdf) |
| Anthropic office context | Anthropic confirms an SF office in its [April 2026 Project Deal report](https://www.anthropic.com/features/project-deal). Its [March 2025 public letter](https://assets.anthropic.com/m/4e20a4ab6512e217/original/Anthropic-Response-to-OSTP-RFI-March-2025-Final-Submission-v3.pdf) gives a separate PMB correspondence address, **not a verified office location**. The playable Anthropic site is explicitly a SoMa proxy; local/site staffing remains null, and the correspondence coordinates are not an office geocode. |

QCEW counts covered employer jobs by place of work, including jobs held by inbound
commuters. Multiple jobholders and self-employment differ from a resident-person
denominator. Establishments are employer units, not unique companies. We use job
counts only as an explicitly imperfect **industry proxy**; no measured commuting
flows, remote-work shares or individual employment links are inferred.
[BLS concepts](https://www.bls.gov/opub/hom/cew/concepts.htm)

The directly retrieved BLS source replaces reliance on a secondary industry table
in the city bond document whose displayed total has a different labor-force label.
The bond source remains useful for its explicitly scoped historical company counts.
The available BLS annual table is newer than the retained neighborhood ACS inputs;
the mixed vintages are intentional and exposed, not silently treated as contemporary.

## Exact allocation and default audit

Hamilton/largest remainder allocates neighborhood adults, then ages within each
neighborhood. Employment and broad occupation margins retain the existing sampler.
Exact Fraction arithmetic and local seeded tie breaking preserve totals. Industry
allocation separately apportions all employed adults to the checked-in QCEW proxy
weights. Every realized industry quota differs from its target by less than one
person; industry pairing is independent of occupation and demographic identity.

| Resident dimension | Count |
| --- | ---: |
| Mission / SoMa / Mission Bay | 56 / 27 / 17 |
| Ages 18–34 / 35–54 / 55–64 / 65+ | 38 / 37 / 10 / 15 |
| Employed / unemployed / outside labor force | 73 / 3 / 24 |
| Children / inbound commuters | 0 / 0 |
| Shared rental / solo rental adults | 64 / 36 |

| Simulation industry | Employed adults |
| --- | ---: |
| Professional services | 24 |
| Public service | 12 |
| Healthcare | 9 |
| Other | 9 |
| Food service | 7 |
| Technology | 6 |
| Retail | 3 |
| Education | 2 |
| Arts | 1 |
| **Total** | **73** |

The industry crosswalk is deliberately coarse: information maps to technology;
finance, real estate and NAICS 54–56 map to professional services; accommodation
joins food service; all government ownership maps to public service, including
public health/education. Other retains construction, manufacturing, transport,
utilities, wholesale and personal services. Thus the technology category is not a
count of all technology workers, and healthcare is not all public/private care jobs.

Within each industry, the allocator first reserves the user-requested **three
OpenAI example seats and one Anthropic seat** within the technology quota, then provides **at most one
illustrative seat per other curated named site**, and uses generic sector
workplaces for the residual. This coverage rule produces 19 named assignments and
54 generic assignments at seed 17. OpenAI's quota is an explicit exception to the
one-seat rule; requested seats are capped by eligible technology workers for smaller populations,
with requested and realized quotas both reported. No extra residents are created.
It removes the arbitrary 25% ceiling from new SF worlds without pretending that a
short reference catalog covers the employment market. A site may get no assignment
when its sector has fewer agents than example sites; ties use a seeded shuffle.
Named seats and generic residuals are **scenario assumptions**, never company
market shares, published staff counts or hiring capacities. Unknown, global and
citywide headcounts never weight this allocation. Nonworkers have no workplace or
company membership. Existing firms remain separate from agent-founded companies.

The JSON `workplace_counts` maps all 33 assigned workplace IDs to exact counts;
`roster` lists all 100 people, including the 27 with null workplace assignments.
The runtime report includes source weights, fractional targets, realized counts,
policy, geographic scope and limitations. Descriptive resident weights sum to
84,781; they never multiply money, actions, citizens or API requests.

## Individual lives and remaining assumptions

The 98 fictional adults have distinct starting histories: previous everyday
experiences, an age-bounded learning/work timeline, neighborhood residence duration,
current occupation or nonemployment circumstances, and a private financial starting
situation. Young adults receive junior roles when experience is short. Role titles
describe broad occupational work and are not claims that a named company actually
employs that person or has that exact vacancy. Each has a distinct, named real
professional counterpart in [the reference catalog](../data/sf_person_references.json).
The other two counterparts are the explicitly requested public figures below.
Public professional records establish only the attributed career facts; they do
not establish private housing, income, motives or family lives.

Each fictional `life_story` contains ten chronological episodes, including three
connected recent experiences. These cover childhood, adolescent
learning, early practical work, current work/nonemployment, a household or community
episode and the neighborhood move. Events are bounded by the character's age;
young adults do not acquire decades of experience, and childhood moves do not
describe infants independently maintaining transit notebooks. Public-figure stories
retain their sourced professional biographies and add two expressly fictional
early-life scenes and three fictional recent experiences. Across all 100 characters,
stories contain 366–592 English words. Every added timeline event has
`provenance=fictional_simulation_history` and a visible fiction prefix. Recent events
occur 19–28, nine and two days before simulation start; they are relative game
history, not claims about real people's activities on specific calendar dates.

The source catalog was researched on September 8, 2026, using official professional
pages and primary interviews comparable to public LinkedIn career profiles. It
contains 98 distinct people and at least two brief career facts per person; the
public-figure packet supplies the other two. All 100 roster entries expose
`person_reference` with the actual source name, facts, links, matching basis and
fiction notice. All 100 display names use the corresponding person's name directly;
synthetic identifiers remain internal, and fiction labels remain in the biography
and reference metadata. There are 51 distinct source URLs across the complete cast.

Source examples include [UCSF professional profiles](https://profiles.ucsf.edu/andrea.jackson),
[La Cocina staff biographies](https://www.lacocinasf.org/people),
[SF-Marin Food Bank leadership](https://www.sfmfoodbank.org/management-team/),
[municipal career recognition](https://sfpublicworks.org/sites/default/files/2025%20Public%20Works%20Employee%20Recognition%20Program.pdf),
[SFMTA professional interviews](https://www.sfmta.com/blog/celebrating-heart-our-system-today-transit-employee-appreciation-day),
[Green Apple Books' history](https://greenapplebooks.com/about-us), and
[civic technology biographies](https://localdata.com/about.html).
Historical recognitions and archived biographies are dated context, not verified
current jobs. Unknown real ages, residences, households and finances remain null
in the 98-person reference catalog. No private contacts or account access are used.

Counterpart selection is a convenience sample of publicly documented careers,
with substantial institutional, leadership and public-visibility bias. It is not
a second population calibration. References are assigned after demographic and
workplace allocation: 68 use a broad industry analogy, two use documented OpenAI
affiliations, two are the requested public figures, and 28 provide career context
while simulated employment differs (including all 27 nonemployed characters).
Role, seniority and age can differ even within an industry match. The other two
OpenAI workers reference Jakub Pachocki and Mark Chen, alongside Sam Altman;
their simulated roles are not assertions of actual local staffing or residences.

Broad occupational duties were checked against primary BLS role descriptions for
[management analysis](https://www.bls.gov/ooh/business-and-financial/management-analysts.htm),
[customer service](https://www.bls.gov/ooh/office-and-administrative-support/customer-service-representatives.htm)
and [maintenance work](https://www.bls.gov/ooh/installation-maintenance-and-repair/general-maintenance-and-repair-workers.htm).
Those pages inform plausible activities, not measured personal histories or required
credentials for every fictional person. The fictional episodes are authored
scenario material, combined deterministically offline. Eleven recent-story arcs
cover repairs, reading, transit, cooking, classes, community work, photographs,
sketching, shopping, borrowing and practical exercises. These are authored variants,
not 100 verified diaries or a claim to reconstruct every event in a human life.

The existing economy supplies independently varied cash reserves, modeled wages,
nonlabor support and one-to-three-adult rental households. Starting cash spans
0–2,199.07 simulation credits in this realization. These are scenario amounts
anchored by the existing [economy inputs](../data/sf_economy.json), not measured
personal wealth or a fitted household distribution. Public-figure simulation
budgets are also fictional game conditions, never their real wealth or salary.
Rental tenure is a simplifying
scenario assumption; homeowners, children and a measured homelessness quota are
not reconstructed. Shared households do not imply family relationships.

Each history enters only that agent's background and durable personal memories.
Existing independent decision loops and private life planning continue unchanged;
initial life direction, projects, values and active goals remain empty. No new
personality rules or demographic behavior mapping are introduced. The existing
runtime's random numeric traits remain independent of these histories.

All work sites are playable proxies, including businesses whose documented points
lie outside the three resident analysis neighborhoods. Mission Bay has four
synthetic residential buildings, a market, dining and restroom facilities, generic
workplaces where assigned, and the OpenAI workplace, all with actual walkable
entrances on the expanded map. No actual parcels, commuting
patterns, company payrolls, owner assets or detailed occupation-industry joint
distribution are reconstructed. These limitations prevent interpreting the run
as a representative citywide survey or a forecast.

## Launch integration for the coordinator

The 100-person preview intentionally casts **Sam Altman** at OpenAI
and **Dario Amodei** at Anthropic into two existing employed management
slots aged 35–54. These are not two additional agents. Workplace/industry swaps
retain the industry totals; their exact biographies and cited public statements come
from the coordinator-owned `data/public_figure_backgrounds.json`. The casting audit
exposes the two overrides and makes no claim that the actual people reside in their
assigned neighborhoods. Public
historical material enters document-source memories with citations; new actions,
speech, invented early-life/recent episodes, housing and budgets are explicitly
fictional. Both have uninitialized
private life plans, like the other agents. The two-neighborhood legacy demographic
sampler does not apply these character overrides.

The coordinator added optional `AgentBackground.person_reference` metadata;
`seed_sf_scenario` populates it and records source notes as document memories.
Fictional memories remain private direct-experience memories. The seeder uses
`generate_scenario_population`, and the existing `apply_sf_economy` finalizes rent
and households. Existing checkpoints restore their saved populations. To inspect
100 new people, select a **new database path**, since count/seed environment values
do not replace a restored checkpoint. Example command for the coordinator to run
only when ready (this worker did not run it):

```sh
preview_dir=$(mktemp -d .data/sf100-preview.XXXXXX)
SOCIETY_DB_PATH="$preview_dir/world.db" SOCIETY_SCENARIO=sf \
SOCIETY_AGENT_COUNT=100 SOCIETY_SEED=17 SOCIETY_START_PAUSED=1 \
SOCIETY_ALLOW_PAID_CALLS=0 SOCIETY_REQUEST_LIMIT=24 \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Use an available port. The unique directory protects old databases. The default
24-request cap and paused startup are retained; 100 people does not authorize
100 model calls or an increased cap. Do not change `.env` or reset an existing
world to apply this preview. The generator and focused tests never launch this
command or contact a model provider.

Validation: 99 focused population, employer, scenario, roster, economy and life tests
pass, including network-denied artifact generation, exact quotas, 100 unique adults,
nonblocked placements, Mission Bay residents, three OpenAI assignments, the two
public-figure roles, 100 distinct sourced counterparts, 100 distinct recent-event
sequences, document-source histories and private-context isolation.
Ruff and `git diff --check` pass; `--check` reproduces the checked-in JSON.
