import asyncio
import importlib
from types import SimpleNamespace

import pytest

from app.models import ActionIntent, ActionType, AgentDecision, Vec2


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIETY_LLM_PROVIDER", "local")
    monkeypatch.setenv("SOCIETY_DB_PATH", str(tmp_path / "runtime.db"))
    monkeypatch.setenv("SOCIETY_AGENT_COUNT", "2")
    monkeypatch.delenv("SOCIETY_START_PAUSED", raising=False)
    monkeypatch.delenv("SOCIETY_ALLOW_PAID_CALLS", raising=False)
    module = importlib.import_module("app.main")
    result = module.SimulationService()
    yield result
    result.store.close()


def test_startup_is_paused_and_paid_calls_require_explicit_opt_in(service):
    assert service.world.paused
    assert not service.allow_paid_calls
    service.world.paused = False
    service.brain = SimpleNamespace(mode="novita")
    service._schedule_ready_agents()
    assert service.world.paused
    assert "disabled" in service.world.runtime_metrics["pause_reason"]
    assert not service.agent_tasks
    assert service.store.call_count(service.world.run_id) == 0


def test_shared_clock_waits_for_slow_agents_without_erasing_actions(service):
    agent = next(iter(service.world.agents.values()))
    agent.is_thinking = True
    assert service.clock_waiting()
    agent.is_thinking = False
    assert not service.clock_waiting()


@pytest.mark.asyncio
async def test_relief_pause_blocks_rescheduling_even_after_a_stale_response(service):
    for agent in service.world.agents.values():
        agent.next_think_at = service.world.time
        agent.relief_until = service.world.time + 2.4
    service._schedule_ready_agents()
    assert not service.agent_tasks
    assert service.world.runtime_metrics['requests'] == 0


def test_resolved_walk_continues_while_neighbor_is_thinking(service):
    thinker, walker = list(service.world.agents.values())
    thinker.is_thinking = True
    walker.action_target = Vec2(x=300, y=400)
    assert not service.clock_waiting()
    walker.action_target = None
    assert service.clock_waiting()


def test_budget_drains_existing_motion_without_scheduling_more_calls(service):
    agent = next(iter(service.world.agents.values()))
    service.world.paused = False
    service.world.runtime_metrics["requests"] = service.request_limit
    agent.action_target = Vec2(x=300, y=400)
    service._schedule_ready_agents()
    assert not service.world.paused
    assert not service.agent_tasks
    assert "without new calls" in service.world.runtime_metrics["pause_reason"]
    agent.action_target = None
    service._schedule_ready_agents()
    assert service.world.paused
    assert service.world.runtime_metrics["requests"] == service.request_limit


@pytest.mark.asyncio
async def test_request_budget_is_durable_and_no_hidden_retries(service):
    async def decide(agent, context):
        return AgentDecision(
            intent=ActionIntent(action=ActionType.WAIT),
            source="novita",
            provider_usage={"prompt_tokens": 50, "completion_tokens": 10},
            provider_response_id="response_test",
        )

    service.brain = SimpleNamespace(mode="novita", model="test", decide=decide)
    service.allow_paid_calls = True
    service.request_limit = 1
    service.world.paused = False
    service.world.time = 1
    service._schedule_ready_agents()
    assert len(service.agent_tasks) == 1
    await asyncio.gather(*service.agent_tasks.values())
    await asyncio.sleep(0)
    service._schedule_ready_agents()
    assert service.world.paused
    assert service.world.runtime_metrics["requests"] == 1
    assert service.store.call_count(service.world.run_id) == 1
    row = service.store._connection.execute(
        "SELECT status, response_id, usage FROM model_calls"
    ).fetchone()
    assert row[0] == "returned" and row[1] == "response_test"
    assert '"prompt_tokens": 50' in row[2]


@pytest.mark.asyncio
async def test_provider_failures_record_sanitized_error_and_pause(service):
    async def decide(agent, context):
        raise TimeoutError("Secret provider text must not enter audit logs")

    service.brain = SimpleNamespace(mode="novita", model="test", decide=decide)
    service.allow_paid_calls = True
    service.world.paused = False
    agent = next(iter(service.world.agents.values()))
    for _ in range(3):
        await service._think(agent.id)
    assert service.world.paused
    assert service.world.runtime_metrics["failed"] == 3
    rows = service.store._connection.execute("SELECT error_type FROM model_calls").fetchall()
    assert rows == [("TimeoutError",)] * 3


def test_sf_checkpoint_restores_economy_and_civic_permissions(service):
    from app.checkpoint import dump_world, restore_world

    world = service.world
    world.terrain.consents["5,5"] = [next(iter(world.agents))]
    checkpoint = dump_world(world)
    restored = restore_world(service.store, checkpoint)
    assert restored.sf_economy.report() == world.sf_economy.report()
    assert restored.terrain.protected_cells == world.terrain.protected_cells
    assert restored.terrain.consents == world.terrain.consents
    assert restored.snapshot("local")["terrain"]["map"] == world.snapshot("local")["terrain"]["map"]
