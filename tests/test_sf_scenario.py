"""Integration checks for the source-grounded resident scenario and private histories."""

from collections import Counter

import pytest

from app.models import ActionIntent, ActionType, Vec2
from app.store import EventStore
from app.world import World


@pytest.fixture
def sf_world(tmp_path):
    store = EventStore(str(tmp_path / "sf.db"))
    world = World(store, agent_count=24, seed=17, scenario="sf")
    yield world
    store.close()


def test_calibration_is_attached_without_seeding_life_goals(sf_world):
    report = sf_world.snapshot("local")["population"]
    assert report["agent_count"] == 24
    assert sum(report["neighborhood_counts"].values()) == 24
    assert set(report["neighborhood_counts"]) == {"mission", "soma", "mission_bay"}
    assert report["limitations"]
    assert all(a.background and a.background.synthetic for a in sf_world.agents.values())
    assert all(a.active_goal is None and not a.values for a in sf_world.agents.values())
    assert any(a.workplace_id for a in sf_world.agents.values())
    assert report["employment_calibration"]["vintage"] == "2016-2020 ACS 5-year estimates"
    assert report["employer_calibration"]["allocation"]["status"] == "scenario_assumption"


def test_personal_background_enters_only_own_context_and_inspector(sf_world):
    first, second, *_ = sf_world.agents.values()
    marker = "A private childhood recollection unique to this citizen."
    first.background.biography.append(marker)
    assert marker in sf_world.context_for(first)["personal_background"]["biography"]
    assert marker not in str(sf_world.context_for(second))
    assert marker not in str(sf_world.snapshot("local"))
    assert marker in sf_world.agent_detail(first.id)["background"]["biography"]
    assert all("background" not in a for a in sf_world.snapshot("local")["agents"])


def test_background_memories_are_persisted_and_not_broadcast(sf_world):
    for agent in sf_world.agents.values():
        memories = [m for m in agent.memories if m.event_type == "personal_background"]
        assert memories
        assert all(m.source_id == agent.id and m.original_event_id is None for m in memories)
        assert {m.content for m in memories} == set(agent.background.biography)
        for other in sf_world.agents.values():
            if other.id != agent.id:
                assert not ({m.id for m in memories} & {m.id for m in other.memories})


def test_housing_capacity_and_neighborhood_are_consistent(sf_world):
    occupants = Counter(a.home_id for a in sf_world.agents.values() if a.home_id)
    for agent in sf_world.agents.values():
        if agent.home_id:
            home = sf_world.objects[agent.home_id]
            assert home.metadata["neighborhood"] == agent.background.neighborhood
            assert occupants[home.id] <= home.metadata["beds"]
            assert agent.home_id in agent.known_places
        if agent.workplace_id:
            assert agent.background.employment_status == "employed"
            assert agent.workplace_id in agent.known_places


def test_preexisting_employers_are_not_agent_founded_companies(sf_world):
    snapshot = sf_world.snapshot("local")
    assert snapshot["employers"]
    assert not snapshot["economy"]["companies"]
    assert all("headcount_scope" in e for e in snapshot["employers"])
    assert all(e["simulated_workers"] >= 0 for e in snapshot["employers"])
    agent = next(iter(sf_world.agents.values()))
    employer = next(e for e in snapshot["employers"] if e["object_id"] != agent.workplace_id)
    target = sf_world.objects[employer["object_id"]]
    agent.position = Vec2(**target.metadata["entrance"])
    credits = agent.credits
    sf_world.urban.execute(agent, ActionIntent(action=ActionType.WORK, target_id=target.id))
    assert agent.activity is None
    assert agent.credits == credits
    assert "do not have a job" in agent.last_action_result


def test_sf_does_not_invent_recurring_layoffs_or_street_fairs(sf_world):
    before = list(sf_world.events)
    sf_world.time = 1000
    sf_world._maybe_city_event()
    assert list(sf_world.events) == before


def test_sf_scenario_reproducible_and_not_fixed_twelve_characters(tmp_path):
    stores = [EventStore(str(tmp_path / f"replica-{i}.db")) for i in range(2)]
    try:
        worlds = [World(store, agent_count=36, scenario="sf", seed=4) for store in stores]
        first, second = [list(world.agents.values()) for world in worlds]
        assert [a.background for a in first] == [a.background for a in second]
        assert [a.traits for a in first] == [a.traits for a in second]
        assert [a.position for a in first] == [a.position for a in second]
        assert len({a.name for a in first}) == 36
        assert len({tuple(a.traits.values()) for a in first}) == 36
    finally:
        for store in stores:
            store.close()


@pytest.mark.parametrize("count", [100, 500])
def test_residents_spawn_on_distinct_local_walkable_street_points(tmp_path, count):
    store = EventStore(str(tmp_path / f"spawns-{count}.db"))
    try:
        world = World(store, agent_count=count, scenario="sf", seed=17)
        positions = [(a.position.x, a.position.y) for a in world.agents.values()]
        assert len(set(positions)) == count
        for agent in world.agents.values():
            cell = (int(agent.position.x // 20), int(agent.position.y // 20))
            assert cell in world.sf_map.road_cells
            assert world.sf_map.in_catchment(cell, agent.background.neighborhood)
            assert not world.terrain.blocked(agent.position)
        if count == 100:
            assert len({(int(x // 20), int(y // 20)) for x, y in positions}) == 100
            assert Counter(a.background.neighborhood for a in world.agents.values()) == {
                "mission": 56, "soma": 27, "mission_bay": 17,
            }
    finally:
        store.close()


def test_spawn_seed_changes_positions_but_restore_preserves_them(tmp_path):
    from app.checkpoint import dump_world, restore_world

    stores = [EventStore(str(tmp_path / f"spawn-seed-{i}.db")) for i in range(2)]
    try:
        worlds = [World(store, agent_count=100, scenario="sf", seed=i + 17)
                  for i, store in enumerate(stores)]
        positions = [[a.position for a in w.agents.values()] for w in worlds]
        assert positions[0] != positions[1]
        restored = restore_world(stores[0], dump_world(worlds[0]))
        assert [a.position for a in restored.agents.values()] == positions[0]
    finally:
        for store in stores:
            store.close()


@pytest.mark.parametrize("count", [0, -1, 501])
def test_world_rejects_unbounded_agent_counts(tmp_path, count):
    store = EventStore(str(tmp_path / "invalid.db"))
    try:
        with pytest.raises(ValueError, match="Agent count"):
            World(store, agent_count=count, scenario="sf")
    finally:
        store.close()
