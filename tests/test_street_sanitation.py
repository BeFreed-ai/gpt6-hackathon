from pathlib import Path

import pytest

from app.checkpoint import dump_world, restore_world
from app.models import ActionIntent, ActionType, Vec2
from app.store import EventStore
from app.world import World


@pytest.fixture
def world(tmp_path: Path):
    store = EventStore(str(tmp_path / "sanitation.db"))
    result = World(store, agent_count=3, seed=17)
    for index, agent in enumerate(result.agents.values()):
        agent.position = Vec2(x=700 + index * 30, y=390)
    yield result
    store.close()


def accident(world):
    person = next(iter(world.agents.values()))
    person.bladder = 99
    world._handle_sanitation(person)
    waste = next(o for o in world.objects.values() if o.metadata.get("created_by") == person.id)
    return person, waste


def test_creator_grace_expires_but_other_people_can_step_immediately(world):
    person, waste = accident(world)
    assert f"step_{person.id}" not in waste.metadata
    assert person.relief_until == 2.4
    assert world.events[-1].payload["object_id"] == waste.id
    other = list(world.agents.values())[1]
    other.position = waste.position.model_copy()
    world._handle_sanitation(other)
    assert waste.metadata[f"step_{other.id}"] == 0
    world.time = 2.9
    world._handle_sanitation(person)
    assert f"step_{person.id}" not in waste.metadata
    world.time = 3
    world._handle_sanitation(person)
    assert waste.metadata[f"step_{person.id}"] == 3


def test_relief_interrupts_motion_and_stale_intent_without_choosing_followup(world):
    person = next(iter(world.agents.values()))
    person.action_target = Vec2(x=900, y=390)
    version = person.stimulus_version
    person, waste = accident(world)
    assert person.action_target is None and person.pending_intent is None
    assert person.stimulus_version == version + 1
    before = person.position.model_copy()
    world._advance_movement(person, 1)
    assert person.position == before
    world.time = 2.4
    world._handle_sanitation(person)
    assert person.current_action == "observing" and person.relief_until == 0
    assert person.action_target is None and waste.id in world.objects


def test_active_toilet_use_prevents_accident(world):
    person = next(iter(world.agents.values()))
    toilet = world._add_object("toilet", "Test restroom", 700, 390)
    person.bladder = 99
    world.urban.execute(person, ActionIntent(action=ActionType.USE_TOILET, target_id=toilet.id))
    assert person.activity.action == ActionType.USE_TOILET
    world._handle_sanitation(person)
    assert not any(o.metadata.get("created_by") == person.id for o in world.objects.values())
    world.time = person.activity.ends_at
    world.urban.tick()
    assert person.bladder == 4


def test_waste_and_relief_persist_in_checkpoint_until_actual_cleanup(world):
    person, waste = accident(world)
    restored = restore_world(world.store, dump_world(world))
    assert restored.agents[person.id].relief_until == 2.4
    assert restored.objects[waste.id].metadata["created_by"] == person.id
    restored.time = 100
    restored._update_city_services()
    assert waste.id in restored.objects  # Unreported waste does not vanish by itself.
    cleaner = list(restored.agents.values())[1]
    cleaner.position = waste.position.model_copy()
    restored.urban.execute(cleaner, ActionIntent(action=ActionType.CLEAN, target_id=waste.id))
    assert cleaner.activity is not None
    restored.time = cleaner.activity.ends_at
    restored.urban.tick()
    assert waste.id not in restored.objects


def test_no_cash_or_home_is_not_a_sanitation_trigger(world):
    person = next(iter(world.agents.values()))
    person.credits = 0
    person.home_id = None
    person.bladder = 20
    before = len(world.objects)
    world._handle_sanitation(person)
    assert len(world.objects) == before and person.relief_until == 0


def test_sf_housing_loss_uses_existing_unpaid_day_threshold(tmp_path):
    store = EventStore(str(tmp_path / "housing.db"))
    try:
        world = World(store, agent_count=12, scenario="sf")
        person = next(a for a in world.agents.values() if a.home_id)
        person.credits = 0
        ledger = world.sf_economy.state["agents"][person.id]
        ledger["daily_support_credits"] = 0
        world.time = world.day_length
        world.sf_economy.new_day()
        assert person.home_id is not None
        threshold = world.sf_economy.state["calibration"]["scenario"]["housing_loss_after_unpaid_days"]
        ledger["unpaid_days"] = threshold - 1
        world.time += world.day_length
        world.sf_economy.new_day()
        assert person.home_id is None
        assert person.background.housing_status == "housing_insecure"
        assert not any(o.metadata.get("created_by") == person.id for o in world.objects.values())
    finally:
        store.close()
