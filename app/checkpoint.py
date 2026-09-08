"""Versioned JSON world checkpoints, never executable pickle or a public snapshot."""

from __future__ import annotations

import json
import logging
import random
import re
from collections import deque
from typing import Any

from app.economy import Company, Economy, Offer
from app.lifecycle import Lifecycle
from app.models import AgentState, WorldEvent, WorldObject
from app.perception import PerceptionResolver
from app.terrain import Terrain
from app.urban import UrbanSystem

SCHEMA_VERSION = 1
WORLD_COMPONENTS = {
    "store",
    "random",
    "agents",
    "objects",
    "events",
    "interventions",
    "player_messages",
    "perception",
    "economy",
    "urban",
    "terrain",
    "lifecycle",
    "sf_economy",
    "sf_map",
}


def _attributes(instance: Any, excluded: set[str]) -> dict:
    result = {key: value for key, value in vars(instance).items() if key not in excluded}
    # Fail rather than silently omit a new stateful subsystem or non-finite balance.
    return json.loads(json.dumps(result, allow_nan=False))


def dump_world(world: Any) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "world": _attributes(world, WORLD_COMPONENTS),
        "random_state": world.random.getstate(),
        "agents": [agent.model_dump(mode="json") for agent in world.agents.values()],
        "objects": [item.model_dump(mode="json") for item in world.objects.values()],
        "events": [event.model_dump(mode="json") for event in world.events],
        "interventions": list(world.interventions),
        "player_messages": list(world.player_messages),
        "perception": _attributes(world.perception, set()),
        "terrain": {
            **_attributes(world.terrain, {"world", "protected_cells"}),
            "protected_cells": sorted(world.terrain.protected_cells),
        },
        "economy": {
            "state": _attributes(world.economy, {"world", "companies", "offers"}),
            "companies": [
                company.model_dump(mode="json") for company in world.economy.companies.values()
            ],
            "offers": [offer.model_dump(mode="json") for offer in world.economy.offers.values()],
        },
        "urban": {
            "state": _attributes(world.urban, {"world", "carried"}),
            "carried": [item.model_dump(mode="json") for item in world.urban.carried.values()],
        },
    }


def _tuples(value: Any) -> Any:
    return tuple(_tuples(item) for item in value) if isinstance(value, (list, tuple)) else value


def _restore_attributes(instance: Any, values: dict, excluded: set[str]) -> None:
    for key, value in values.items():
        if key in excluded or key.startswith("__"):
            raise ValueError("Invalid checkpoint state field")
        setattr(instance, key, value)


def restore_world(store: Any, checkpoint: dict) -> Any:
    from app.world import World

    if checkpoint.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported world checkpoint version; choose a new database explicitly")
    world = World.__new__(World)
    world.store = store
    _restore_attributes(world, checkpoint["world"], WORLD_COMPONENTS)
    world.random = random.Random()
    world.random.setstate(_tuples(checkpoint["random_state"]))
    world.agents = {a["id"]: AgentState.model_validate(a) for a in checkpoint["agents"]}
    world.objects = {o["id"]: WorldObject.model_validate(o) for o in checkpoint["objects"]}
    world.events = deque((WorldEvent.model_validate(e) for e in checkpoint["events"]), maxlen=160)
    world.interventions = deque(checkpoint["interventions"], maxlen=30)
    world.player_messages = deque(checkpoint["player_messages"], maxlen=40)
    world.perception = PerceptionResolver(world.run_id)
    _restore_attributes(world.perception, checkpoint["perception"], set())
    world.terrain = Terrain.__new__(Terrain)
    world.terrain.world = world
    _restore_attributes(world.terrain, checkpoint["terrain"], {"world"})
    world.terrain.protected_cells = set(world.terrain.protected_cells)
    world.economy = Economy(world)
    _restore_attributes(
        world.economy, checkpoint["economy"]["state"], {"world", "companies", "offers"}
    )
    world.economy.companies = {
        c["id"]: Company.model_validate(c) for c in checkpoint["economy"]["companies"]
    }
    world.economy.offers = {
        o["id"]: Offer.model_validate(o) for o in checkpoint["economy"]["offers"]
    }
    world.urban = UrbanSystem(world)
    _restore_attributes(world.urban, checkpoint["urban"]["state"], {"world", "carried"})
    world.urban.carried = {
        o["id"]: WorldObject.model_validate(o) for o in checkpoint["urban"]["carried"]
    }
    world.lifecycle = Lifecycle(world)
    if hasattr(world.economy, "sf_state"):
        from app.sf_economy import SFEconomy

        world.sf_economy = SFEconomy(world)
    renamed = 0
    for agent in world.agents.values():
        # Older checkpoints predate named casting. Repair only generated labels;
        # keep custom names and all original memories/events exactly as recorded.
        reference = agent.background.person_reference if agent.background else None
        name = reference.get("name") if reference else None
        if name and (
            re.fullmatch(r"Citizen \d+", agent.name)
            or agent.name == f"{name} (simulation)"
        ):
            agent.name = name
            renamed += 1
        # Network requests are not replayable. Their inbox remains unread for a new call.
        if agent.is_thinking:
            agent.next_think_at = min(agent.next_think_at, world.time)
        agent.is_thinking = False
    if renamed:
        logging.getLogger(__name__).info("Restored character names for %d citizens", renamed)
    # A crash may have journaled events after the latest checkpoint. Keep those audit
    # rows, never reuse their IDs, and resume only authoritative checkpoint state.
    event_high, memory_high = store.sequence_high_water(world.run_id)
    world.event_counter = max(world.event_counter, event_high)
    world.perception._memory_counter = max(world.perception._memory_counter, memory_high)
    return world
