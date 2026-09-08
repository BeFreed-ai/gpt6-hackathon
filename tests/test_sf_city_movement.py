"""Physical movement checks independent of paid LLM decisions or the map renderer."""

from app.models import ActionIntent, ActionType, Vec2
from app.store import EventStore
from app.world import World


def test_one_hundred_residents_can_reach_home_or_work_without_collisions(tmp_path):
    store = EventStore(str(tmp_path / "movement.db"))
    try:
        world = World(store, agent_count=100, scenario="sf")
        for agent in world.agents.values():
            world.time = 0
            target_id = agent.workplace_id or agent.home_id
            if not target_id:
                continue
            target = world.objects[target_id]
            destination = Vec2(**target.metadata["entrance"])
            # This checks the physical network, not whether a citizen knows every street.
            agent.known_terrain = {key: tile["kind"] for key, tile in world.terrain.tiles.items()}
            intent = ActionIntent(action=ActionType.MOVE, destination=destination)
            assert world._execute(agent, intent)
            for _ in range(1600):
                world.time += 0.1
                previous = agent.position.model_copy()
                world._advance_movement(agent, 0.1)
                assert not world.terrain.blocked(agent.position)
                assert world.terrain.line_clear(previous, agent.position)
                if agent.action_target is None:
                    break
            assert agent.action_target is None, (agent.id, target.name, agent.last_action_result)
            assert agent.position == destination
    finally:
        store.close()
