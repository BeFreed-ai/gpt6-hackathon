from __future__ import annotations

from pathlib import Path

import pytest

from app.models import ActionIntent, ActionType, AgentDecision, Goal, Vec2
from app.store import EventStore
from app.world import World


@pytest.fixture
def world(tmp_path: Path) -> World:
    store = EventStore(str(tmp_path / "events.db"))
    result = World(store, agent_count=3, seed=1)
    yield result
    store.close()


def test_local_event_does_not_leak_to_distant_agent(world: World) -> None:
    first, second, third = list(world.agents.values())
    first.position = Vec2(x=100, y=100)
    second.position = Vec2(x=125, y=100)
    third.position = Vec2(x=900, y=700)

    world.emit(
        "speech",
        f'{first.name} said: "The apples are hidden by the park."',
        actor_id=first.id,
        target_ids=[second.id],
        position=first.position,
        radius=115,
    )

    assert any("apples are hidden" in memory.content for memory in first.memories)
    assert any("apples are hidden" in memory.content for memory in second.memories)
    assert not any("apples are hidden" in memory.content for memory in third.memories)


def test_broadcast_reaches_every_living_agent_as_a_claim(world: World) -> None:
    world.emit(
        "broadcast",
        "Circuit Hill has run out of food.",
        actor_id="yellow_01",
        position=Vec2(x=1000, y=500),
        payload={"station": "KTHR Public Radio"},
        radius=1600,
        broadcast=True,
    )

    for agent in world.agents.values():
        memory = agent.memories[-1]
        assert memory.source_type.value in {"broadcast", "direct_experience"}
        assert "run out of food" in memory.content
        if agent.id != "yellow_01":
            assert "heard KTHR Public Radio report" in memory.content


def test_broadcast_respects_signal_coverage(world: World) -> None:
    first, second, third = list(world.agents.values())
    first.position = Vec2(x=100, y=100)
    second.position = Vec2(x=180, y=100)
    third.position = Vec2(x=900, y=700)

    world.emit(
        "broadcast",
        "A neighborhood meeting begins at sunset.",
        actor_id=first.id,
        position=first.position,
        payload={"station": "Low Power Community Radio"},
        radius=120,
        broadcast=True,
    )

    assert any("meeting begins" in memory.content for memory in first.memories)
    assert any("meeting begins" in memory.content for memory in second.memories)
    assert not any("meeting begins" in memory.content for memory in third.memories)


def test_invalid_action_cannot_change_world(world: World) -> None:
    agent = world.agents["yellow_01"]
    original_hunger = agent.hunger
    decision = AgentDecision(
        intent=ActionIntent(
            action=ActionType.EAT,
            target_id="missing_apple",
            public_reason="I want to eat an apple that is not here.",
            goal=Goal(statement="Eat", reason="Hunger", created_at=world.time),
        )
    )

    world.apply_decision(agent.id, decision)

    assert agent.hunger == original_hunger
    assert world.events[-1].type == "action_failed"


def test_player_food_is_perceived_only_near_drop_point(world: World) -> None:
    first, second, third = list(world.agents.values())
    first.position = Vec2(x=100, y=100)
    second.position = Vec2(x=160, y=100)
    third.position = Vec2(x=1000, y=700)

    world.intervene("food", Vec2(x=120, y=100), None)

    assert any("appeared from beyond the sky" in memory.content for memory in first.memories)
    assert any("appeared from beyond the sky" in memory.content for memory in second.memories)
    assert not any("appeared from beyond the sky" in memory.content for memory in third.memories)
    assert len([item for item in world.objects.values() if item.name == "Sky Apple"]) == 5


def test_reported_waste_is_cleaned_after_service_delay(world: World) -> None:
    agent = world.agents["yellow_01"]
    waste = world._add_object("waste", "Street Waste", agent.position.x, agent.position.y)
    decision = AgentDecision(
        intent=ActionIntent(
            action=ActionType.REPORT,
            target_id=waste.id,
            public_reason="This is a public health hazard.",
            goal=Goal(statement="Clean the street", reason="Public care", created_at=world.time),
        )
    )

    world.apply_decision(agent.id, decision)
    world.tick(15)

    assert waste.id not in world.objects
    assert any(event.type == "cleanup" for event in world.events)
