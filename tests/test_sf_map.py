"""Offline map provenance, projection, physical access and civic ownership checks."""

import json
import subprocess
import sys
from collections import deque

import pytest

from app.models import ActionIntent, ActionTerms, ActionType, Vec2
from app.sf_map import MAP_PATH, SFMap, _clip
from app.store import EventStore
from app.world import World


@pytest.fixture
def sf_world(tmp_path):
    store = EventStore(str(tmp_path / "map.db"))
    world = World(store, agent_count=24, scenario="sf")
    yield world
    store.close()


def test_checked_in_official_geometry_rebuilds_offline(tmp_path):
    output = tmp_path / "map.json"
    subprocess.run([sys.executable, "scripts/build_sf_map.py", "--output", str(output)], check=True)
    assert output.read_bytes() == MAP_PATH.read_bytes()
    data = json.loads(output.read_text())
    assert data["source"]["dataset_id"] == "3psu-pn9h"
    assert data["source"]["input_records"] == 2551
    assert len(data["segments"]) > 1000
    assert {"MARKET ST", "MISSION ST", "VALENCIA ST", "16TH ST", "24TH ST"} <= {
        row["name"] for row in data["segments"]
    }


def test_projection_roundtrip_orientation_and_clipped_graph():
    sf_map = SFMap()
    west, south, east, north = sf_map.bounds
    assert sf_map.project(west, north) == {"x": 40, "y": 40}
    assert sf_map.project(east, south) == {"x": 1360, "y": 780}
    point = sf_map.project(-122.4197, 37.765)
    assert sf_map.unproject(**point) == pytest.approx((-122.4197, 37.765), abs=1e-7)
    for node in sf_map.graph()["nodes"]:
        assert 40 <= node["position"]["x"] <= 1360
        assert 40 <= node["position"]["y"] <= 780
    assert _clip((-2, 0), (-1, 1), (0, 0, 2, 2)) is None
    assert _clip((-1, 1), (3, 1), (0, 0, 2, 2)) == [(0, 1), (2, 1)]


def test_all_facilities_and_agents_reach_one_connected_street_network(sf_world):
    terrain = sf_world.terrain
    roads = {cell for cell in sf_world.sf_map.road_cells}
    first = next(iter(roads))
    visited, queue = {first}, deque([first])
    while queue:
        for neighbor in sf_world.sf_map.neighbors(queue.popleft()):
            if neighbor in roads and neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    assert visited == roads
    for item in sf_world.objects.values():
        assert item.metadata["geography_status"] == "synthetic_street_adjacent"
        entrance = Vec2(**item.metadata["entrance"])
        assert terrain.cell(entrance) in visited
        assert not terrain.blocked(entrance)
        if terrain.tiles.get(terrain.key(terrain.cell(item.position)), {}).get("facility"):
            assert terrain.blocked(item.position)
            assert abs(item.position.x - entrance.x) + abs(item.position.y - entrance.y) == 20
    assert all(terrain.cell(a.position) in visited for a in sf_world.agents.values())
    agent = next(iter(sf_world.agents.values()))
    agent.known_terrain = {key: tile["kind"] for key, tile in terrain.tiles.items()}
    for item in sf_world.objects.values():
        entrance = Vec2(**item.metadata["entrance"])
        route = terrain.path(agent, entrance, 5)
        assert route is not None
        assert all(not terrain.blocked(point) for point in route)


def free_cell(world):
    for y in range(3, 38):
        for x in range(3, 67):
            cell = (x, y)
            if world.terrain.key(cell) not in world.terrain.tiles and all(
                world.terrain.cell(o.position) != cell for o in world.objects.values()
            ):
                return cell
    raise AssertionError("No editable ground")


def test_foreign_demolition_requires_owner_consent_and_consumes_it(sf_world):
    terrain = sf_world.terrain
    owner, visitor, *_ = sf_world.agents.values()
    cell = free_cell(sf_world)
    sf_world.urban.create_carried(owner, "material", "Scrap")
    terrain.edit(cell, "sign", owner, "Our noticeboard")
    before = list(visitor.inventory)
    with pytest.raises(ValueError, match="consent"):
        terrain.edit(cell, "grass", visitor)
    assert visitor.inventory == before
    assert terrain.tiles[terrain.key(cell)]["owner_id"] == owner.id
    assert terrain.disputes[-1]["actor_id"] == visitor.id
    with pytest.raises(ValueError, match="owner"):
        terrain.grant_consent(cell, visitor.id, visitor.id)
    terrain.grant_consent(cell, owner.id, visitor.id)
    terrain.edit(cell, "grass", visitor)
    assert terrain.key(cell) not in terrain.tiles
    assert terrain.key(cell) not in terrain.consents
    assert len(visitor.inventory) == len(before) + 1


def test_public_roads_and_entrances_cannot_be_stolen_or_walled(sf_world):
    terrain = sf_world.terrain
    actor = next(iter(sf_world.agents.values()))
    cell = next(iter(sf_world.sf_map.road_cells))
    with pytest.raises(ValueError, match="consent"):
        terrain.edit(cell, "grass", actor)
    with pytest.raises(ValueError, match="observer"):
        terrain.grant_consent(cell, actor.id, actor.id)
    terrain.grant_consent(cell, "observer", actor.id)
    terrain.edit(cell, "grass", actor)
    with pytest.raises(ValueError, match="access"):
        terrain.edit(cell, "wall", None)
    item = next(o for o in sf_world.objects.values() if o.kind == "home")
    with pytest.raises(ValueError, match="protected"):
        terrain.edit(tuple(item.metadata["footprint_cell"]), "grass", None)


def test_observer_override_is_recorded_and_snapshot_does_not_alias(sf_world):
    terrain = sf_world.terrain
    cell = next(iter(sf_world.sf_map.road_cells))
    terrain.edit(cell, "grass", None, "Reconfigure shared access")
    assert terrain.disputes[-1]["reason"] == "Reconfigure shared access"
    snapshot = terrain.snapshot()
    json.dumps(snapshot)
    snapshot["civic"]["disputes"].clear()
    snapshot["map"]["source"]["publisher"] = "Changed"
    assert terrain.disputes
    assert terrain.map_metadata["source"]["publisher"].startswith("City")


def test_wall_cannot_seal_citizen_away_from_roads(sf_world):
    terrain = sf_world.terrain
    actor = next(iter(sf_world.agents.values()))
    # Isolate a small test patch, keeping its one exit open until the final edit.
    cell = (1, 1)
    actor.position = terrain.center(cell)
    for wall in ((0, 1), (1, 0), (1, 2)):
        terrain.tiles[terrain.key(wall)] = {"kind": "wall"}
    with pytest.raises(ValueError, match="cut off"):
        terrain.edit((2, 1), "wall", None)
    assert not terrain.blocked(terrain.center((2, 1)))


def civic(world, agent, cell, action, message="", grantee_id=None):
    agent.position = world.terrain.center(cell)
    agent.known_terrain[world.terrain.key(cell)] = world.terrain.tiles.get(
        world.terrain.key(cell), {"kind": "grass"}
    )["kind"]
    return world.terrain.execute(
        agent,
        ActionIntent(
            action=ActionType.TALK,
            destination=world.terrain.center(cell),
            message=message,
            terms=ActionTerms(civic_action=action, grantee_id=grantee_id),
        ),
    )


def test_public_petition_needs_distinct_citizen_endorsement(sf_world):
    terrain = sf_world.terrain
    first, second, *_ = sf_world.agents.values()
    cell = next(iter(sf_world.sf_map.road_cells))
    key = terrain.key(cell)
    assert civic(sf_world, first, cell, "petition", "Remove worn road surfacing")
    assert terrain.petitions[key]["status"] == "pending"
    assert first.id not in terrain.consents.get(key, [])
    assert civic(sf_world, first, cell, "endorse")
    assert "one vote" in first.last_action_result
    assert terrain.petitions[key]["votes"] == [first.id]
    assert civic(sf_world, second, cell, "endorse")
    assert terrain.petitions[key]["status"] == "approved"
    assert first.id in terrain.consents[key]
    terrain.edit(cell, "grass", first)
    assert key not in terrain.petitions


def test_civic_talk_can_grant_private_consent_and_record_dispute(sf_world):
    terrain = sf_world.terrain
    first, second, *_ = sf_world.agents.values()
    cell = free_cell(sf_world)
    sf_world.urban.create_carried(first, "material", "Scrap")
    terrain.edit(cell, "sign", first, "Old noticeboard")
    second.position = terrain.center(cell)
    assert civic(sf_world, first, cell, "grant_consent", grantee_id=second.id)
    assert second.id in terrain.consents[terrain.key(cell)]
    assert civic(sf_world, second, cell, "dispute", "Please preserve the message")
    assert terrain.disputes[-1]["reason"] == "Please preserve the message"
    stranger = list(sf_world.agents.values())[2]
    stranger.known_terrain.clear()
    assert not terrain.civic_for(stranger)["disputes"]


def test_civic_wall_dispute_completes_after_walking_to_its_edge(sf_world):
    terrain = sf_world.terrain
    actor = next(iter(sf_world.agents.values()))
    cell = free_cell(sf_world)
    terrain.edit(cell, "wall", None)
    actor.position = terrain.center((3, 8))
    assert not terrain.blocked(actor.position)
    actor.known_terrain = {key: tile["kind"] for key, tile in terrain.tiles.items()}
    intent = ActionIntent(
        action=ActionType.TALK,
        destination=terrain.center(cell),
        terms=ActionTerms(civic_action="dispute"),
        message="This wall blocks my shortcut",
    )
    assert terrain.execute(actor, intent)
    assert actor.pending_intent
    for _ in range(500):
        sf_world._advance_movement(actor, 0.1)
        assert not terrain.blocked(actor.position)
        if actor.pending_intent is None:
            break
    assert actor.pending_intent is None
    assert terrain.disputes[-1]["cell"] == list(cell)
    assert terrain.disputes[-1]["actor_id"] == actor.id
