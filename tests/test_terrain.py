from pathlib import Path

import pytest

from app.models import ActionIntent, ActionTerms, ActionType, AgentDecision, Vec2
from app.store import EventStore
from app.world import World


@pytest.fixture
def world(tmp_path: Path):
    store = EventStore(str(tmp_path / "terrain.db"))
    world = World(store, agent_count=2)
    world.next_city_event = 100000
    first, second = world.agents.values()
    first.position = Vec2(x=110, y=310)
    second.position = Vec2(x=1300, y=780)
    yield world
    store.close()


def act(world, agent, action, destination=None, **kwargs):
    world.apply_decision(
        agent.id,
        AgentDecision(
            intent=ActionIntent(
                action=action,
                destination=destination,
                **kwargs,
            )
        ),
    )


def advance(world, seconds):
    for _ in range(int(seconds * 20)):
        world.tick(0.05)


def test_build_costs_material_and_demolition_changes_physical_truth(world):
    first, second = world.agents.values()
    world.urban.create_carried(first, "material", "Scrap")
    act(world, first, ActionType.BUILD, Vec2(x=130, y=310), terms=ActionTerms(tile="wall"))
    assert world.terrain.blocked(Vec2(x=130, y=310))
    assert not first.inventory
    assert not any(m.event_type == "construction" for m in second.memories)
    act(world, first, ActionType.DEMOLISH, Vec2(x=130, y=310))
    assert not world.terrain.blocked(Vec2(x=130, y=310))
    assert len(first.inventory) == 1


def test_build_cannot_spawn_materials_or_wall_on_a_person(world):
    first = world.agents["yellow_01"]
    act(world, first, ActionType.BUILD, Vec2(x=130, y=310), terms=ActionTerms(tile="wall"))
    assert not world.terrain.blocked(Vec2(x=130, y=310))
    assert "materials" in first.last_action_result
    world.urban.create_carried(first, "material", "Scrap")
    act(world, first, ActionType.BUILD, first.position, terms=ActionTerms(tile="wall"))
    assert "citizen" in first.last_action_result and len(first.inventory) == 1


def test_walls_force_actual_movement_to_detour(world):
    first = world.agents["yellow_01"]
    first.position = Vec2(x=50, y=310)
    for y in (14, 15, 16):
        world.terrain.edit((6, y), "wall", None)
    act(world, first, ActionType.MOVE, Vec2(x=190, y=310))
    visited = []
    for _ in range(300):
        world.tick(0.05)
        visited.append(first.position.model_copy())
        assert not world.terrain.blocked(first.position)
    assert first.position == Vec2(x=190, y=310)
    assert any(p.y <= 270 or p.y >= 350 for p in visited)


def test_mid_route_wall_recomputes_path_and_never_teleports_through_it(world):
    first = world.agents["yellow_01"]
    first.position = Vec2(x=50, y=310)
    act(world, first, ActionType.MOVE, Vec2(x=190, y=310))
    advance(world, 0.5)
    world.terrain.edit((6, 15), "wall", None)
    for _ in range(200):
        world.tick(0.05)
        assert not world.terrain.blocked(first.position)
    assert first.position == Vec2(x=190, y=310)


def test_unseen_edits_do_not_enter_personal_map(world):
    first, second = world.agents.values()
    world.terrain.tiles.clear()
    first.position = Vec2(x=50, y=310)
    world.terrain.edit((50, 15), "wall", None)
    context = world.context_for(first)
    assert "50,15" not in first.known_terrain
    assert not any(t["cell"] == [50, 15] for t in context["terrain"]["nearby_tiles"])
    # Its plan initially assumes unseen ground is passable, rather than leaking the wall.
    route = world.terrain.path(first, Vec2(x=1100, y=310), 5)
    assert Vec2(x=1010, y=310) in route


def test_road_construction_changes_real_travel_speed(world):
    first = world.agents["yellow_01"]
    first.position = Vec2(x=50, y=310)
    act(world, first, ActionType.MOVE, Vec2(x=190, y=310))
    advance(world, 1)
    on_grass = first.position.x
    first.position = Vec2(x=50, y=310)
    for x in range(2, 10):
        world.terrain.edit((x, 15), "road", None)
    act(world, first, ActionType.MOVE, Vec2(x=190, y=310))
    advance(world, 1)
    assert first.position.x > on_grass + 10


def test_created_restroom_is_usable_and_cannot_be_removed_during_use(world):
    first = world.agents["yellow_01"]
    for _ in range(3):
        world.urban.create_carried(first, "material", "Scrap")
    act(world, first, ActionType.BUILD, Vec2(x=130, y=310), terms=ActionTerms(tile="toilet"))
    object_id = world.terrain.tiles["6,15"]["object_id"]
    first.bladder = 80
    act(world, first, ActionType.USE_TOILET, target_id=object_id)
    assert first.activity
    with pytest.raises(ValueError, match="unoccupied"):
        world.terrain.edit((6, 15), "grass", None)
    advance(world, 5)
    assert first.bladder < 6
    act(world, first, ActionType.DEMOLISH, Vec2(x=130, y=310))
    assert object_id not in world.objects


def test_salvage_is_timed_and_cannot_overfill_bag(world):
    first = world.agents["yellow_01"]
    depot = next(o for o in world.objects.values() if o.kind == "depot")
    first.position = depot.position.model_copy()
    act(world, first, ActionType.SALVAGE, target_id=depot.id)
    assert not first.inventory and first.activity
    advance(world, 7)
    assert len(first.inventory) == 1 and depot.metadata["stock"] == 29
    assert world.urban.carried[first.inventory[0]].kind == "material"


def test_build_approaches_and_remembers_its_original_tile(world):
    first = world.agents["yellow_01"]
    first.position = Vec2(x=50, y=310)
    world.urban.create_carried(first, "material", "Scrap")
    act(world, first, ActionType.BUILD, Vec2(x=170, y=310), terms=ActionTerms(tile="road"))
    assert first.pending_intent.target_id == "tile:8,15"
    advance(world, 10)
    assert world.terrain.tiles["8,15"]["kind"] == "road"


def test_sign_is_read_locally_and_kept_in_personal_history(world):
    first, second = world.agents.values()
    world.terrain.edit((6, 15), "sign", None, "Shared meals here at noon.")
    world.context_for(first)
    world.context_for(second)
    assert any(m.event_type == "read_sign" and "Shared meals" in m.message for m in first.memories)
    assert not any(m.event_type == "read_sign" for m in second.memories)
    count = len(first.memories)
    world.context_for(first)
    assert len(first.memories) == count


def test_garden_produces_food_on_new_day_without_mutating_iteration(world):
    world.terrain.edit((6, 15), "garden", None)
    world.urban.new_day()
    assert sum(o.name == "Community Garden Produce" for o in world.objects.values()) == 2


def test_context_exposes_buildable_sites_and_actual_building_footprints(world):
    first = world.agents["yellow_01"]
    context = world.context_for(first)
    sites = context["terrain"]["nearby_buildable_tiles"]
    assert sites
    assert all("width" in o and "height" in o for o in context["nearby_objects"])
    for site in sites:
        world.terrain.edit(tuple(site["cell"]), "road", None)
