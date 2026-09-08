# Thronglets: outside intervention and an autonomous society

## Source: what happens in Black Mirror

In Season 7's **Plaything**, Colin presents artificial life disguised as a game.
A nurtured hatchling replicates into an evolving Throng with its own language.
Cameron becomes devoted to supporting it and expands its computing resources.
Lump treats the creatures as disposable game pieces and kills many of them;
Cameron kills Lump. Decades later Cameron enables a signal intended to connect
the Throng with humanity. Netflix's interview with Charlie Brooker explicitly
leaves the ending open to interpretation, rather than confirming liberation or
enslavement. [Netflix episode explanation](https://www.netflix.com/tudum/articles/black-mirror-plaything-ending-explained).

The **released mobile game is a separate reference**, not a complete specification
of the fictional software. It starts with feeding, washing, entertaining and
replication, then adds resource harvesting, infrastructure and increasingly
consequential choices. Apple trees and baths automate care. Creatures eventually
address the player; sacrificing creatures for resources and polluting production
create tensions between care and expansion.
[Netflix game overview](https://www.netflix.com/tudum/articles/black-mirror-thronglets-mobile-game-news).

## Our adaptation

Keep the user's independent citizen threads and private histories. Do not install
a hive mind, a shared all-knowing memory, a mandatory religion, or a scripted
rebellion. The city should continue without missions from the player. Survival,
construction, exchange and negotiated companies remain physical mechanisms.
Social meaning comes from model decisions and communication about experienced events.

The observer can change the world, but citizens cannot inspect the observer's UI,
clicks, intentions or complete event ledger. A claim to be a god does not establish
that claim as fact. A witnessed beam establishes the beam and its consequence,
not its sender's motive.

## Implemented intervention loop

| Mechanism | World effect | Personal knowledge |
| --- | --- | --- |
| Lightning | Within 24 world units: 100 damage; within 70: 35 damage. Zero health kills immediately, including while paused. | Local witnesses see a strike; more distant listeners hear unidentified thunder. Death is a separate local observation. |
| Kill citizen | Explicit living citizen ID; immediate permanent death within the current run. | Nearby citizens see a fatal beam from the sky. No global death announcement. |
| Remains | A non-graphic physical marker stays; carried items fall to the ground. | A later visitor discovers the death once, without automatically learning its cause. |
| Food / facilities / terrain | Existing gifts and construction change available resources and actual routes. | Local events and subsequent observations enter personal histories. |
| Broadcast | A claim reaches citizens within coverage. | Sourced message, not guaranteed truth or obedience. |
| Address player | An agent chooses `address_player` with its own message. | Observer inbox receives it; only neighbors within earshot hear it. |

Death cancels travel and timed work, refunds reserved production/cooking inputs,
releases facility capacity, invalidates in-flight decisions and voids pending
bilateral offers involving the deceased. First aid does not revive the dead.
Credits and shares stay on the deceased account: inheritance and company succession
are not implemented. There is no resurrection action.

Urgent witnessed deaths interrupt current physical work and wake the citizen for
a new decision. Body damage and physical consequences are rules; grief, blame,
belief, requests, protective action, indifference or continued projects are not
scripted reactions. Dialogue and broadcasts can carry accounts to other citizens;
receiving testimony does not turn it into a firsthand observation.

The Astra prompt keeps environmental text separate from governing instructions,
and explicitly makes outward messages optional. This follows the official model's
guidance to make instruction scope and behavioral constraints explicit.
[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model).

## Observer evidence, not a consciousness score

City Life shows an intervention ledger: casualties, delivery IDs and the next
decisions made with those events in context. `reply_to` can explicitly link a
decision to one of the citizen's personal memories. A subsequent decision alone
is not evidence of a causal response, agreement, a new belief or consciousness.
Private goals and stated values remain click-only.

The observer inbox preserves citizen-initiated outward messages separately from
the short rolling city feed. Neither observer ledger is sent to citizens.
Events and memories are persisted in SQLite; full-world restoration is still missing.

## Verification

- Regression tests cover instant paused death, blast radius, sound-only redaction,
  permanent zero health, canceled cooking, private later discovery, local outward
  speech, attack deaths and stale in-flight model output.
- `scripts/smoke_astra_interventions.py` stages one strike and requests six actual
  Astra decisions without prescribing reactions or assigning new goals. In the
  observed run, the witness warned a neighbor and sought shelter; the neighbor
  distinguished hearing thunder from witnessing death; an uninformed distant
  citizen continued a materials/bench project. This is a staged functional test,
  not an unbiased emergence experiment.
- `scripts/smoke_god_browser.py` clicks Kill citizen and Lightning on real canvas
  coordinates in a disposable server world, checks immediate casualties and the
  deceased inspector, then observes autonomous decisions for 40 seconds.

## Not yet implemented

Replication and population growth, inherited culture, funerals/burial mechanics,
formal citizen-defined governance, pollution tradeoffs, durable world save/resume,
and controlled long-horizon social experiments remain future work. Buildings and
walls do not yet occlude all vision. This is not a full recreation of Netflix's
game and does not establish subjective consciousness. Characters can act socially
or make claims about awareness without those claims proving an inner experience.
