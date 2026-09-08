from pathlib import Path

import pytest

from app.brain import LocalBrain
from app.models import ActionIntent, ActionType, AgentDecision, Vec2
from app.store import EventStore
from app.world import World


@pytest.fixture
def world(tmp_path: Path):
    store = EventStore(str(tmp_path / "interactions.db"))
    world = World(store, agent_count=3)
    world.next_city_event = 10000
    for agent in world.agents.values():
        agent.memories.clear()
        agent.inbox.clear()
    yield world
    store.close()


def act(world, agent, action, **kwargs):
    world.apply_decision(agent.id, AgentDecision(intent=ActionIntent(action=action, **kwargs)))


def advance(world, seconds=15):
    for _ in range(seconds * 10):
        world.tick(0.1)


def test_talk_approaches_then_delivers_and_wakes_recipient(world):
    first, second, far = world.agents.values()
    first.position = Vec2(x=100, y=100)
    second.position = Vec2(x=300, y=100)
    far.position = Vec2(x=1300, y=700)
    second.action_target = Vec2(x=305, y=100)
    second.next_think_at = 100
    act(world, first, ActionType.TALK, target_id=second.id, message="Will you share an apple?")
    assert first.pending_intent is not None
    advance(world)
    assert any(m.message == "Will you share an apple?" for m in second.memories)
    assert second.action_target is None
    assert second.inbox
    assert not any("share an apple" in m.content for m in far.memories)
    assert not any(e.type == "action_failed" for e in world.events)


def test_broadcast_interrupts_movement_and_returns_delivery_receipt(world):
    for agent in world.agents.values():
        act(world, agent, ActionType.MOVE, destination=Vec2(x=1300, y=700))
        agent.next_think_at = 100
    receipt = world.intervene("broadcast", None, "Meet at the park to share food.")
    assert len(receipt["delivered_to"]) == 3
    for agent in world.agents.values():
        assert agent.action_target is None
        assert agent.next_think_at <= 0.2
        assert (
            world.context_for(agent)["new_events"][-1]["message"]
            == "Meet at the park to share food."
        )


def test_food_action_is_completed_on_arrival(world):
    agent = world.agents["yellow_01"]
    agent.position = Vec2(x=100, y=100)
    agent.hunger = 80
    food = world._add_object("food", "Test Apple", 240, 100)
    act(world, agent, ActionType.EAT, target_id=food.id)
    advance(world)
    assert food.id not in world.objects
    assert agent.hunger < 40
    assert any(e.type == "eat" and e.actor_id == agent.id for e in world.events)


def test_toilet_action_is_completed_on_arrival(world):
    agent = world.agents["yellow_01"]
    agent.position = Vec2(x=100, y=100)
    agent.bladder = 80
    toilet = world._add_object("toilet", "Test Restroom", 230, 100)
    act(world, agent, ActionType.USE_TOILET, target_id=toilet.id)
    advance(world)
    assert agent.bladder < 20
    assert any(e.type == "use_toilet" for e in world.events)


def test_food_can_be_given_then_eaten_from_inventory(world):
    first, second, _ = world.agents.values()
    first.position = second.position = Vec2(x=100, y=100)
    food = world._add_object("food", "Test Apple", 100, 100)
    act(world, first, ActionType.TAKE, target_id=food.id)
    act(world, first, ActionType.GIVE, target_id=second.id)
    second.hunger = 80
    act(world, second, ActionType.EAT, target_id=food.id)
    assert not first.inventory and not second.inventory
    assert second.hunger == 32


def test_disappearing_target_aborts_route_without_hanging(world):
    first, second, _ = world.agents.values()
    first.position = Vec2(x=100, y=100)
    food = world._add_object("food", "Contested Apple", 300, 100)
    second.position = food.position.model_copy()
    act(world, first, ActionType.EAT, target_id=food.id)
    act(world, second, ActionType.EAT, target_id=food.id)
    advance(world, 1)
    assert first.pending_intent is None
    assert first.action_target is None
    assert "no longer available" in first.last_action_result


@pytest.mark.asyncio
async def test_rule_demo_acknowledges_direct_speech_once_without_echo_loop(world):
    first, second, _ = world.agents.values()
    first.position = second.position = Vec2(x=100, y=100)
    act(world, first, ActionType.TALK, target_id=second.id, message="What about a shared meal?")
    brain = LocalBrain()
    answer = await brain.decide(second, world.context_for(second))
    assert answer.intent.reply_to == second.memories[-1].id
    world.apply_decision(second.id, answer)
    reply = await brain.decide(first, world.context_for(first))
    assert reply.intent.action != ActionType.TALK
    assert "I did this" not in (answer.intent.message or "")


def test_fog_reduces_context_sight_and_trees_replenish_food(world):
    first, second, _ = world.agents.values()
    first.position = Vec2(x=100, y=100)
    second.position = Vec2(x=300, y=100)
    assert second.id in [a["id"] for a in world.context_for(first)["nearby_agents"]]
    world.weather = "fog"
    assert second.id not in [a["id"] for a in world.context_for(first)["nearby_agents"]]
    before = sum(o.kind == "food" for o in world.objects.values())
    advance(world, 26)
    assert sum(o.kind == "food" for o in world.objects.values()) > before
