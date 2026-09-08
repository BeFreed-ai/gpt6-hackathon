import asyncio
import importlib
from types import SimpleNamespace

import pytest

from app.models import ActionIntent, ActionType, AgentDecision, Vec2
from app.store import EventStore
from app.world import World


@pytest.fixture
def world(tmp_path):
    store = EventStore(str(tmp_path / "lifecycle.db"))
    world = World(store, agent_count=4)
    world.next_city_event = 100000
    for agent, x in zip(world.agents.values(), (100, 150, 400, 1300), strict=True):
        agent.position = Vec2(x=x, y=310)
        agent.memories.clear()
        agent.inbox.clear()
    yield world
    store.close()


def test_paused_strike_kills_immediately_and_injures_only_living_neighbors(world):
    victim, neighbor, listener, far = world.agents.values()
    world.paused = True
    victim.action_target = Vec2(x=900, y=310)
    victim.is_thinking = True
    receipt = world.intervene("lightning", victim.position, None)
    assert receipt["killed"] == [victim.id]
    assert receipt["injured"] == [neighbor.id]
    assert not victim.alive and victim.health == 0 and victim.current_action == "dead"
    assert victim.action_target is None and not victim.is_thinking
    assert neighbor.health == 65 and listener.health == far.health == 100
    assert any(m.event_type == "death" for m in neighbor.memories)
    assert not any(m.event_type == "death" for m in listener.memories)
    assert listener.memories[-1].source_type == "overheard"
    assert victim.name not in listener.memories[-1].message
    assert not far.memories
    assert set(receipt["delivered_to"]) == {victim.id, neighbor.id, listener.id}
    world.tick(1)
    assert not victim.alive and victim.health == 0


def test_targeted_kill_idempotency_and_no_reviving_by_first_aid(world):
    victim, helper, *_ = world.agents.values()
    world.intervene("kill", None, None, target_id=victim.id)
    count = len([o for o in world.objects.values() if o.kind == "remains"])
    with pytest.raises(ValueError, match="living"):
        world.intervene("kill", None, None, target_id=victim.id)
    world.apply_decision(helper.id, AgentDecision(intent=ActionIntent(
        action=ActionType.HELP, target_id=victim.id
    )))
    assert not victim.alive and victim.health == 0
    assert len([o for o in world.objects.values() if o.kind == "remains"]) == count == 1


def test_death_releases_reserved_cooking_items_and_facility(world):
    victim = next(iter(world.agents.values()))
    home = world.objects[victim.home_id]
    victim.position = home.position.model_copy()
    for _ in range(2):
        world.urban.create_carried(victim, "food", "Apple")
    world.apply_decision(victim.id, AgentDecision(intent=ActionIntent(
        action=ActionType.COOK, target_id=home.id
    )))
    assert victim.activity and len(victim.activity.inputs) == 2
    inputs = list(victim.activity.inputs)
    world.intervene("kill", None, None, target_id=victim.id)
    assert victim.activity is None and not victim.inventory
    assert all(key in world.objects and key not in world.urban.carried for key in inputs)
    world.tick(20)
    assert not any(e.type == "cook" for e in world.events)


def test_later_discovery_is_private_once_and_does_not_reveal_cause(world):
    victim, _, _, far = world.agents.values()
    world.intervene("kill", None, None, target_id=victim.id)
    assert not far.memories
    far.position = victim.position.model_copy()
    world.context_for(far)
    discoveries = [m for m in far.memories if m.event_type == "discovery"]
    assert len(discoveries) == 1
    assert "cannot be established" in discoveries[0].content
    assert "beam" not in discoveries[0].content
    world.context_for(far)
    assert len([m for m in far.memories if m.event_type == "discovery"]) == 1


def test_sky_messages_reach_observer_not_every_citizen(world):
    speaker, neighbor, _, far = world.agents.values()
    world.apply_decision(speaker.id, AgentDecision(intent=ActionIntent(
        action=ActionType.ADDRESS_PLAYER, message="Who is changing our streets?"
    )))
    assert world.snapshot("test")["player_messages"][-1]["actor_id"] == speaker.id
    assert any(m.event_type == "address_player" for m in neighbor.memories)
    assert not far.memories
    assert "player_messages" not in world.context_for(far)
    assert "interventions" not in world.context_for(far)


def test_attack_kills_before_next_tick_and_overhearing_hides_attacker(world):
    attacker, victim, listener, _ = world.agents.values()
    victim.position.x = 120
    listener.position.x = 350
    victim.health = 1
    world.apply_decision(attacker.id, AgentDecision(intent=ActionIntent(
        action=ActionType.ATTACK, target_id=victim.id
    )))
    assert not victim.alive and victim.death_cause == "attack"
    heard = next(m for m in listener.memories if m.event_type == "attack")
    assert heard.source_id is None
    assert attacker.name not in heard.message and victim.name not in heard.content


def test_zero_health_never_passively_heals_back_to_life(world):
    agent = next(iter(world.agents.values()))
    agent.health = 0
    agent.hunger = 10
    world.tick(0.1)
    assert not agent.alive and agent.health == 0


@pytest.mark.asyncio
async def test_dead_agent_cannot_finish_inflight_decision(world, tmp_path, monkeypatch):
    monkeypatch.setattr("app.brain.openai_api_key", lambda: None)
    monkeypatch.setenv("SOCIETY_DB_PATH", str(tmp_path / "service.db"))
    module = importlib.import_module("app.main")
    service = module.SimulationService.__new__(module.SimulationService)
    service.world = world
    service.semaphore = asyncio.Semaphore(1)
    agent = next(iter(world.agents.values()))

    async def delayed(snapshot, context):
        world.intervene("kill", None, None, target_id=agent.id)
        return AgentDecision(intent=ActionIntent(action=ActionType.SHOUT, message="Still alive"))

    service.brain = SimpleNamespace(decide=delayed)
    await service._think(agent.id)
    assert agent.decision_count == 0 and agent.speech is None and not agent.alive


def test_followup_log_is_observer_only_and_records_noticed_events(world):
    agent = next(iter(world.agents.values()))
    receipt = world.intervene("food", agent.position, None)
    consumed = set(agent.inbox)
    decision = AgentDecision(intent=ActionIntent(action=ActionType.WAIT))
    world.apply_decision(agent.id, decision)
    world.record_followup(agent, decision, consumed)
    entry = world.snapshot("test")["interventions"][-1]
    assert entry["event_id"] == receipt["event_id"]
    assert entry["followups"][0]["action"] == "wait"
    assert entry["followups"][0]["reply_to_event_id"] is None
