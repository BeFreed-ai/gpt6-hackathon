import json

import pytest

from app.checkpoint import dump_world, restore_world
from app.economy import Company, Offer
from app.models import ActionType, Activity, Vec2, WorldObject
from app.store import EventStore
from app.world import World


def test_old_citizen_labels_restore_existing_names_without_resetting_lives(tmp_path):
    store = EventStore(str(tmp_path / "names.db"))
    try:
        world = World(store, agent_count=100, scenario="sf")
        people = list(world.agents.values())
        for index, agent in enumerate(people):
            agent.name = f"Citizen {index + 1:03d}"
        people[-1].name = "My custom character"
        before = dump_world(world)
        restored = restore_world(store, before)
        for agent in people:
            after = restored.agents[agent.id]
            expected = (
                "My custom character"
                if agent is people[-1]
                else agent.background.person_reference["name"]
            )
            assert after.name == expected
            assert after.model_dump(exclude={"name"}) == agent.model_dump(exclude={"name"})
        assert dump_world(world) == before, "Do not mutate the source save while reading it"
        assert len(restored.agents) == 100
    finally:
        store.close()


def test_checkpoint_restores_private_history_goods_routes_companies_and_random(tmp_path):
    store = EventStore(str(tmp_path / "world.db"))
    world = World(store, agent_count=3)
    agent = next(iter(world.agents.values()))
    agent.credits = 123.45
    agent.is_thinking = True
    agent.next_think_at = 100
    world.time = 42
    agent.route = [Vec2(x=300, y=400)]
    coat = WorldObject(id="saved_coat", kind="coat", name="My coat", position=agent.position)
    world.urban.carried[coat.id] = coat
    agent.inventory.append(coat.id)
    agent.activity = Activity(
        action=ActionType.REST,
        target_id=agent.home_id,
        started_at=40,
        ends_at=60,
        reserved_credits=2,
    )
    world.economy.companies["company_saved"] = Company(
        id="company_saved",
        name="Shared meals",
        purpose="Feed neighbors",
        founder_id=agent.id,
        product="meals",
        treasury=8.5,
        price=2,
        shares={agent.id: 1},
        stock=3,
    )
    world.economy.offers["offer_saved"] = Offer(
        id="offer_saved",
        kind="job",
        sender_id=agent.id,
        recipient_id=list(world.agents)[1],
        subject_id="company_saved",
        amount=4,
        expires_at=90,
    )
    world.terrain.tiles["8,8"] = {"kind": "garden", "builder_id": agent.id}
    world.terrain.revision += 1
    world.runtime_metrics = {"requests": 12}
    store.save_checkpoint(dump_world(world))
    event_count = len(store.recent_events(1000))
    restored = restore_world(store, store.load_checkpoint())
    assert len(store.recent_events(1000)) == event_count  # No new greetings or reseeding.
    restored_agent = restored.agents[agent.id]
    assert restored_agent.credits == 123.45
    assert restored_agent.memories == agent.memories
    assert restored_agent.inbox == agent.inbox
    assert restored_agent.activity == agent.activity
    assert restored_agent.route == agent.route
    assert not restored_agent.is_thinking
    assert restored_agent.next_think_at == 42
    assert restored.urban.carried == world.urban.carried
    assert restored.economy.companies == world.economy.companies
    assert restored.economy.offers == world.economy.offers
    assert restored.terrain.tiles == world.terrain.tiles
    assert restored.random.random() == world.random.random()
    assert restored.economy.world is restored and restored.terrain.world is restored
    assert restored.runtime_metrics == {"requests": 12}
    store.close()


def test_restart_keeps_death_permanent_and_never_reuses_journal_ids(tmp_path):
    store = EventStore(str(tmp_path / "world.db"))
    world = World(store, agent_count=2)
    agent = next(iter(world.agents.values()))
    world.lifecycle.kill(agent, "test", "A permanent death.")
    store.save_checkpoint(dump_world(world))
    late = world.emit("broadcast", "Journaled after checkpoint", broadcast=True)
    restored = restore_world(store, store.load_checkpoint())
    assert not restored.agents[agent.id].alive
    assert restored.agents[agent.id].health == 0
    next_event = restored.emit("broadcast", "After restart", broadcast=True)
    assert next_event.id != late.id
    assert any(event["id"] == late.id for event in store.recent_events())
    store.close()


def test_bad_checkpoints_fail_closed_without_reseeding(tmp_path):
    store = EventStore(str(tmp_path / "world.db"))
    world = World(store, agent_count=1)
    payload = dump_world(world)
    payload["schema_version"] = 999
    store.save_checkpoint(payload)
    with pytest.raises(ValueError, match="version"):
        restore_world(store, store.load_checkpoint())
    store._connection.execute("UPDATE world_checkpoints SET data = '{}' WHERE slot = 1")
    store._connection.commit()
    with pytest.raises(ValueError, match="checksum"):
        store.load_checkpoint()
    assert store.recent_events()
    store.close()


def test_checkpoint_rejects_nonfinite_and_nonserializable_state(tmp_path):
    store = EventStore(str(tmp_path / "world.db"))
    world = World(store, agent_count=1)
    world.unsupported = object()
    with pytest.raises(TypeError):
        dump_world(world)
    with pytest.raises(ValueError):
        store.save_checkpoint({"credits": float("nan")})
    del world.unsupported
    assert json.dumps(dump_world(world))
    store.close()
