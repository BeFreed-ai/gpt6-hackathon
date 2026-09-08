import asyncio
import importlib
from types import SimpleNamespace

import pytest

from app.models import ActionIntent, ActionType, AgentDecision
from app.store import EventStore
from app.world import World


@pytest.mark.asyncio
async def test_new_signal_invalidates_inflight_decision_without_losing_wakeup(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("app.brain.openai_api_key", lambda: None)
    monkeypatch.setenv("SOCIETY_DB_PATH", str(tmp_path / "service.db"))
    module = importlib.import_module("app.main")
    service = module.SimulationService.__new__(module.SimulationService)
    store = EventStore(str(tmp_path / "world.db"))
    service.world = World(store, agent_count=1)
    service.semaphore = asyncio.Semaphore(1)
    agent = service.world.agents["yellow_01"]
    agent.is_thinking = True

    async def delayed_decision(snapshot, context):
        service.world.intervene("broadcast", None, "A new message arrived during your decision.")
        return AgentDecision(intent=ActionIntent(action=ActionType.WAIT), source="astra")

    service.brain = SimpleNamespace(decide=delayed_decision)
    await service._think(agent.id)
    assert agent.decision_count == 0
    assert agent.inbox
    assert not agent.is_thinking
    assert agent.next_think_at <= service.world.time

    async def fresh_decision(snapshot, context):
        assert "new message" in context["new_events"][-1]["message"]
        return AgentDecision(intent=ActionIntent(action=ActionType.WAIT), source="astra")

    service.brain = SimpleNamespace(decide=fresh_decision)
    await service._think(agent.id)
    assert agent.decision_count == 1
    assert not agent.inbox
    assert agent.last_decision_source == "astra"
    store.close()


@pytest.mark.asyncio
async def test_configured_astra_failure_never_becomes_a_scripted_decision(monkeypatch):
    from app.brain import ResilientBrain

    monkeypatch.setattr("app.brain.openai_api_key", lambda: None)
    brain = ResilientBrain()

    async def fail(*args):
        raise TimeoutError("provider timeout")

    brain.primary = SimpleNamespace(decide=fail)
    with pytest.raises(TimeoutError):
        await brain.decide(None, {})
    assert brain.last_error == "TimeoutError: Astra request failed."
