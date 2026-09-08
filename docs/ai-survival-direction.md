# SF urban survival society

Research and design recommendation, 2026-09-08. Proposed mechanics below are not a
claim that the current prototype implements them or that social emergence is proven.

## Product target

An AI urban-survival sandbox set in a fictionalized San Francisco, with Thronglets-
inspired original pixel presentation and consequential survival in the spirit of
Don't Starve. SF determines the resource system: housing, food access, public
facilities, neighborhood weather, travel, livelihoods and mutual aid.

Each creature has an independent LLM context, private history and self-chosen
projects. The player observes or changes local conditions. Clicking a creature
reveals its own stated values and perspective; it does not share them with others.

The recommended core is **access to resources + improvable shared places + repeated
relationships**. Basic needs create decisions; successful decisions should eventually
buy time for art, friendship, exploration, comfort and ambitions beyond survival.

## Research basis and limits

- SF's housing plan describes affordability and displacement pressures. Housing is
  a useful long-term planning constraint; game prices and simplified rental rules
  will be fictional, not a reproduction of current law or market prices.
  [SF Planning Housing Element](https://generalplan.sfplanning.org/I1_Housing.htm)
- St. Anthony's serves meals at scheduled times and describes its dining room as a
  community gathering place. This suggests food access can depend on timing and
  knowledge as well as money.
  [St. Anthony's Dining Room](https://www.stanthonysf.org/services/dining-room/)
- Pit Stop toilets have location-specific hours and paid attendants. Availability
  and maintenance can connect sanitation, routes and public work.
  [SF Public Works](https://sfpublicworks.org/pitstop)
- SF community gardens include individual and shared plots, volunteer operation
  and shared expenses. This provides a concrete setting for contributions and
  collective resource use.
  [SF Recreation and Parks](https://sfrecpark.org/717/Farms-and-Gardens)
- Neighborhood microclimates and fog make clothing, location and shelter relevant.
  [National Park Service](https://www.nps.gov/safr/planyourvisit/weather.htm)
- Multi-agent reinforcement-learning experiments found trade and regional prices
  in environments with complementary resources and geographic differences. This
  motivates testing interdependence, but is not evidence that our LLM population
  will develop the same behavior.
  [DeepMind bartering research](https://deepmind.google/blog/emergent-bartering-behaviour-in-multi-agent-reinforcement-learning/)
- Generative Agents demonstrated memory-based behavior and social coordination,
  including a party originating from a seeded intention. It supports memory and
  planning as useful architecture, not a claim of unprompted desires or consciousness.
  [Generative Agents](https://arxiv.org/abs/2304.03442)

The mechanics, priorities and balancing targets below are design hypotheses derived
from these references. They require playtesting with the actual model.

## Recommended mechanics

| Priority | System | Concrete choices and consequences | Social behavior to look for |
| --- | --- | --- | --- |
| P1 | Beds, rooms and storage | Rent a room, share costs, accept a guest, use a limited-capacity night center, or rest outdoors with lower recovery. Rooms provide storage and weather protection. Missed payments have visible warnings and a recovery window. | Roommates, lending, hospitality, exclusion, shared savings. |
| P1 | Food access and cooking | Buy a quick meal, attend scheduled free service, collect available surplus, trade ingredients, or cook several portions at a kitchen. Travel, queues, freshness and equipment make each route different. | Meal sharing, deliveries, kitchen groups, hoarding, negotiated exchange. |
| P1 | Public facilities and maintenance | Toilets have capacity, hours and condition. Queues consume time. Cleaning and repairs restore service; neglect has visible consequences. | Paid cleanup, voluntary care, requests for help, disputes about contributions. |
| P2 | Useful urban production | Repair discarded equipment, assemble furniture from reusable materials, grow food, maintain a shared pantry, or improve a resting place. Require tools, time and inputs. | Specialization, tool lending, workshops, public goods and free riding. |
| P2 | Weather and travel | Local fog and wind affect exposure and outdoor recovery. A jacket, a dry room or a shorter route helps. Later, transit offers a time-versus-money choice. | Shared shelter, equipment borrowing, deliveries and local knowledge. |
| P2 | Exchange and commitments | Offer goods, credits, a service or temporary access. The other party can accept, reject or counteroffer. Track actual delivery separately from speech. | Trust based on experience, repeated partnerships, default and reconciliation. |
| P2 | Enjoyment and expression | Use a gathering space, make a sign or mural, perform, host a meal, collect objects or improve a home. These take real time and materials. | Traditions, friendships, tastes and projects beyond daily maintenance. |

Information is a cross-cutting prerequisite, not a late-game feature: hours, offers
and incidents are learned through direct observation, conversation, posted notices
or broadcasts. No creature receives an omniscient list of everyone else's resources.

### Why these systems belong together

A possible, unscripted chain: a creature misses meal service while earning rent,
asks a neighbor for food, discovers that the neighbor has ingredients but no kitchen,
and proposes using a third creature's room. A shared dinner consumes ingredients and
creates observed contributions. Tomorrow they may repeat it, refuse, ask for payment
or propose a shared pantry. The engine makes these choices possible; it does not
select the story or award a bonus for forming a cooperative.

A second chain: a toilet closes, a creature learns about another one farther away,
and broadcasts that information. Recipients can reroute, ask for confirmation, ignore
irrelevant advice or help repair the nearby facility. Hearing a broadcast must be
observable even when the recipient deliberately continues its current task.

## Rules that protect autonomy and playability

1. Give each urgent need multiple feasible solutions with different costs. Avoid
   balancing all creatures into the same work-eat-sleep sequence.
2. Cooperation should sometimes improve efficiency, while acting alone remains
   viable. Leave surplus time for self-selected projects; constant emergencies
   suppress long-term behavior.
3. Keep an authoritative physical state: inventory, capacity, access, time and
   transactions cannot be changed by narration. A promise is not a transfer.
4. Separate possession, physical access and social claims. Saying "this is mine"
   does not automatically lock a public resource; changing a lock requires a real,
   supported action. Norms require participants to observe and act on them.
5. Make reputation personal and sourced. Witnesses remember an act; others only
   learn of it through communication. Claims can be mistaken or disputed.
6. Do not assign "leader," "criminal," "founder" or "caregiver" goals to manufacture
   emergence. Vary initial resources, experiences and optional preferences, then
   record those conditions so experiments can distinguish seeded behavior.
7. Housing status is a changeable condition, not a personality. Do not make mental
   illness or homelessness an automatic violence trigger. Conflict can have flight,
   negotiation, assistance, injury and recovery consequences for any creature.
8. Keep waste causal and repairable: unmet toilet access can create street waste;
   encountering it affects movement or cleanliness; cleaning removes it. Avoid
   spawning it as a label attached to a population group.
9. Make time fair. Measure decision latency and schedule slack so an ordinary API
   round trip cannot cause starvation or erase a meaningful opportunity. On provider
   outages, explicitly pause affected progression or the experiment; log the policy.
10. Let projects persist through urgent interruptions. Record outcome, next step,
    collaborators and observable progress. "Open a kitchen" must eventually involve
    supplies, a place and cooking, or be marked blocked, abandoned or incomplete.

## Modules to build next

These are proposed responsibilities; file splits should follow implementation size.

| Module | Responsibilities | Acceptance check |
| --- | --- | --- |
| Items and containers | Typed items, quantity, freshness, durability, carrying limits, possession and storage. | Two agents cannot consume or transfer the same final item. |
| Facilities and clock | Opening hours, queues, occupancy, reservations, condition and timed use. | A closed or full toilet returns a specific failure; a released slot becomes usable. |
| Body and exposure | Hunger, fatigue, bladder, cleanliness, warmth and recovery from actual conditions. | Clothing and indoor rest change outcomes; API waiting is handled by the declared time policy. |
| Production and maintenance | Recipes and work orders with inputs, duration, output, interruption and repair. | A completed kitchen job consumes ingredients once and creates the correct portions. |
| Exchange and access | Offers, explicit acceptance, atomic immediate trades, deferred obligations and invitations. | Concurrent offers cannot overspend credits; speech alone cannot grant a bed. |
| Perception and communication | Local events, directed speech, overhearing, coverage, notices and sourced beliefs. | Only actual recipients learn a message; hearing and choosing to comply are distinct. |
| Individual projects | Persistent self-chosen outcomes, steps, evidence and completion or abandonment. | A creature resumes a project after eating without a newly assigned external goal. |
| Observer and experiments | Click-only private inspection, physical progress, event traces and scenario controls. | A social claim can be checked against delivered items, occupied rooms and completed work. |

The existing world, perception, brain and store layers are the base. First extend the
item and facility models; then implement validated actions; then expose those
affordances to the LLM. Adding goal prompts without corresponding world operations
does not create additional agency. Unsupported ideas should produce a clear limit
and allow replanning, not silently invent an action or execute generated code.

Preserve each creature's complete experienced history as the source of truth. An
active project is operational state, not a replacement for history or an externally
assigned worldview. Any future retrieval or context budgeting needs an explicit
policy; it must not leak other creatures' private experiences.

## First playable experiment

Build one compact fictional SF neighborhood with 12 creatures, a grocery, a scheduled
meal service, rentable/shared rooms, a backup night center, two toilets with different
hours, a kitchen, a repairable communal storage area and a public noticeboard.
Population and resource counts are test settings, not claims about real SF.

Start with beds + food + toilets. Add one concrete shared improvement, such as
repairing storage and preparing a shared meal. Introduce a forecastable fog period
or temporary facility closure only after basic actions work. Keep several routes to
survival and recovery available. Defer a full city, complex transit, detailed policing,
large crafting trees and reproduction until this loop is interesting and reliable.

Do not script a desired ending. Observe whether creatures notice opportunities,
form their own plans, deliver promised help, change their environment and maintain
relationships across multiple simulated days.

## How to decide whether it works

- Mechanical correctness: action completion, conservation of items and credits,
  capacity enforcement, private information isolation and intelligible failures.
- Responsiveness: time from message receipt to the next decision; distinguish a
  missed event from a deliberate refusal or a message requiring no action.
- Agency: completed projects, persistent commitments and distinct strategies,
  measured through world changes rather than goal wording or speech volume.
- Social structure: repeated voluntary exchanges, shared resource maintenance,
  enduring agreements and changes after observed promise keeping or breaking.
- Playability: survival and recovery rates, time available beyond urgent needs,
  variety of feasible choices and frequency of visible consequential events.
- Controlled comparisons: vary one factor at a time, such as communication enabled
  versus disabled or maintainable shared storage versus individual storage. Repeat
  across seeds with the same model and decision budgets, logging scenario parameters,
  initial prompts, interventions and provider failures. Store responses for replay;
  repeated live LLM calls are not assumed deterministic.

A convincing outcome is persistent, consequential coordination under these controls.
It is not proof of consciousness, genuine preferences or society in the full human
sense. Do not prewrite cooperation into the prompt and then count its appearance as
an independent discovery.

## Companies and financing

Citizens can found a company with a self-authored name and purpose, contribute seed
credits, propose investments, negotiate counteroffers, hire and sell actual products.
Investment transfers cash only after explicit recipient consent and records post-money
equity. New issuance dilutes prior shares; intervening ownership changes invalidate
pending terms. Company cash is separate from its founder's wallet.

Production reserves materials cost and wages, creates stock on completion, and pays
the worker then. Buyers receive usable goods. Founders can change prices and distribute
available cash proportionally to shareholders. These are game mechanics, not real
financial instruments, legal structures or investment advice. Founder control and
background city supply are deliberate initial simplifications.

## An editable city, not a fixed backdrop

Citizens can change the layout through composable physical operations: salvage,
build and demolish. The first implementation uses a 20-unit tile grid with roads,
walls, floors, gardens, benches, signs and usable kitchens, toilets and shelters.
Roads provide a travel-speed advantage; walls are impassable. Removing a structure
removes its function, and an occupied facility cannot be dismantled mid-use.

Agents plan paths using their personally observed terrain. Unseen cells are assumed
to be ordinary ground until observed. Physical collision always uses the actual world,
and newly discovered obstructions invalidate a route. Signs are read locally and
their text enters the reader's own history. Multi-tile projects remain agent-chosen.

The observer's build brush uses the same world mutation rules without citizen material
costs. Terrain edits emit local events and update the pixel renderer. Preset landmark
buildings remain protected in this first slice; unrestricted demolition, height/voxel
construction and agent-defined new physical rules are not implemented.

## Current implementation boundary

The build is a working pixel-city prototype with basic hunger, work, rent, shelter,
toilets, waste, food transfer and independently scheduled Astra decisions. Interaction
repairs provide event wakeups, retained approach-and-act intents, directed replies
and visible delivery/results. The first SF implementation adds typed portable goods,
scheduled meal service and shops, capacity-limited timed facilities, cooking, cleaning,
vacant-bed rental, accepted roommate invitations, shared rent, fog exposure, usable
coats and route apps, and the company/funding/production loop described above.

Homes and baseline workplaces remain seeded. Services use wait-or-choose-another-place
capacity checks, not an automatic queue. Company products are meals, coats and route
apps; the three underlying effects are implemented, not an arbitrary product executor.
The interface exposes company ledgers only to the observer; agent contexts contain
their own agreements/accounts and observed storefront data.

Beyond the first editable-tile construction system, equipment repair, item freshness,
richer project progress, automatic
queues, full state restoration and long-horizon context budgeting remain future work.
The game pauses body depletion during model calls, but a comprehensive provider-outage
and experiment-time policy still needs further work. Tests of prompted company actions
are integration checks, not independent evidence of social emergence.
