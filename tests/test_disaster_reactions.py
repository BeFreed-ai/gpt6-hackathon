"""No paid requests. Verify stimulus delivery and real consequences, not sentience."""

import asyncio
from types import SimpleNamespace

import pytest

from app.models import ActionIntent, ActionType, Activity, AgentDecision, Vec2
from app.routines import schedule_context, update_reminders
from app.store import EventStore
from app.world import World


@pytest.fixture
def city(tmp_path):
    store = EventStore(str(tmp_path / "city.db"))
    world = World(store, agent_count=100, scenario="sf")
    yield world
    store.close()


def test_public_death_cause_drives_visuals_without_teaching_witnesses(city):
    victim = next(iter(city.agents.values()))
    assert city._public_agent(victim)["death_cause"] is None
    city.lifecycle.kill(victim, "earthquake", "Falling debris struck a citizen.")
    assert city._public_agent(victim)["death_cause"] == "earthquake"
    remains = next(o for o in city.objects.values() if o.kind == "remains")
    assert "death_cause" not in remains.metadata


def test_earthquake_interrupts_all_100_without_remote_damage_knowledge(city):
    for agent in city.agents.values():
        agent.inbox.clear()
        agent.action_target = Vec2(x=300, y=300)
        agent.next_think_at = 999
        agent.activity = Activity(action=ActionType.WAIT, ends_at=999, started_at=0)
    site = next(o for o in city.objects.values() if o.kind == "home")
    receipt = city.intervene("earthquake", site.position, None)
    assert len(receipt["delivered_to"]) == 100
    assert any(o.metadata.get("quake_damage") for o in city.objects.values())
    for agent in city.agents.values():
        assert agent.activity is None and agent.action_target is None
        assert agent.next_think_at <= city.time + 0.2
        memories = [m for m in agent.memories if m.id in agent.inbox]
        assert any(m.event_type == "earthquake" for m in memories)
        for memory in memories:
            if memory.event_type == "facility_damage":
                assert city._distance_to_position(agent, memory.position) <= 150


def test_stepping_in_waste_interrupts_self_and_cooldown_prevents_spam(city):
    agent = next(iter(city.agents.values()))
    city.intervene("waste", agent.position, None)
    agent.inbox.clear()
    agent.action_target = Vec2(x=300, y=300)
    city._handle_sanitation(agent)
    assert agent.action_target is None
    assert any(m.id in agent.inbox and m.event_type == "stepped_in_waste" for m in agent.memories)
    count = len(agent.memories)
    city._handle_sanitation(agent)
    assert len(agent.memories) == count


def test_damage_closes_facility_and_repair_reopens_it(city):
    agent = next(a for a in city.agents.values() if a.workplace_id)
    site = city.objects[agent.workplace_id]
    site.metadata.update(quake_damage="test", condition=35, open=False)
    workplace_id = agent.workplace_id
    city.sf_economy.tick()
    assert agent.workplace_id == workplace_id, "Temporary damage must not fire employees"
    agent.position = Vec2(**site.metadata["entrance"])
    assert not city.urban.is_open(site)
    intent = ActionIntent(action=ActionType.REPAIR, target_id=site.id)
    assert city.urban.execute(agent, intent)
    assert agent.activity.action == ActionType.REPAIR
    city.time = agent.activity.ends_at
    city.urban.tick()
    assert not site.metadata.get("quake_damage")
    assert site.metadata["condition"] == 100
    assert site.metadata["open"]


def test_schedule_reminders_are_private_deduplicated_and_do_not_force_work(city):
    agent = next(a for a in city.agents.values() if a.workplace_id)
    context = schedule_context(city, agent)
    assert context["work"]["start"] in {"08:00", "09:00"}
    city.time = 60
    update_reminders(city)
    events = [e for e in city.events if e.type == "schedule_reminder"]
    assert events
    for event in events:
        assert event.payload["delivered_to"] == event.target_ids
    count = city.event_counter
    update_reminders(city)
    assert city.event_counter == count
    assert agent.activity is None


@pytest.mark.asyncio
@pytest.mark.parametrize("fatality", [False, True])
async def test_runtime_processes_100_independent_emergency_turns(tmp_path, monkeypatch, fatality):
    from app.main import SimulationService

    monkeypatch.setenv("SOCIETY_LLM_PROVIDER", "local")
    monkeypatch.setenv("SOCIETY_DB_PATH", str(tmp_path / "runtime.db"))
    monkeypatch.setenv("SOCIETY_AGENT_COUNT", "100")
    monkeypatch.setenv("SOCIETY_SCENARIO", "sf")
    service = SimulationService()
    seen = {}

    async def decide(agent, context):
        seen[agent.id] = context
        assert any(e["event_type"] == "earthquake" for e in context["new_events"])
        await asyncio.sleep(0)
        # Stubbed output exercises the real scheduling/application path, not LLM quality.
        return AgentDecision(intent=ActionIntent(action=ActionType.WAIT), source="test")

    try:
        service.brain = SimpleNamespace(mode="local", model="test-stub", decide=decide)
        service.request_limit = 100
        service.world.paused = False
        # Test all 100 surviving turns separately from lethal proximity physics.
        for agent in service.world.agents.values():
            agent.position = Vec2(x=1300, y=780)
        epicenter = Vec2(x=700, y=400)
        if fatality:
            site = next(o for o in service.world.objects.values() if o.kind == "home")
            epicenter = site.position
            next(iter(service.world.agents.values())).position = site.position.model_copy()
        receipt = service.world.intervene("earthquake", epicenter, None)
        expected = 99 if fatality else 100
        assert len(receipt["delivered_to"]) == 100
        assert len(receipt["killed"]) == int(fatality)
        service.world.time += 0.2
        service._schedule_ready_agents()
        await asyncio.gather(*list(service.agent_tasks.values()))
        assert len(seen) == expected
        assert service.world.runtime_metrics["completed"] == expected
        assert len(service.world.interventions[-1]["followups"]) == expected
        assert not set(receipt["killed"]).intersection(seen)
        for agent_id, context in seen.items():
            own_ids = {m.id for m in service.world.agents[agent_id].memories}
            assert all(e["id"] in own_ids for e in context["new_events"])
    finally:
        service.store.close()


def test_collapse_kills_by_position_not_character_identity_and_persists(city):
    from app.checkpoint import dump_world, restore_world

    victim, witness, remote = list(city.agents.values())[:3]
    site = next(o for o in city.objects.values() if o.kind == "home")
    for agent in city.agents.values():
        agent.position = Vec2(x=1390, y=810)
    victim.position = site.position.model_copy()
    witness.position = Vec2(x=site.position.x + 40, y=site.position.y)
    victim.health = 100
    receipt = city.intervene("earthquake", site.position, None)
    assert len(receipt["delivered_to"]) == 100
    assert victim.id in receipt["killed"] and victim.id not in receipt["injured"]
    assert not victim.alive and victim.death_cause == "earthquake"
    assert victim.activity is None and victim.action_target is None
    assert any(
        o.kind == "remains" and o.metadata["citizen_id"] == victim.id for o in city.objects.values()
    )
    assert any(m.event_type == "death" for m in witness.memories)
    assert not any(m.event_type == "death" for m in remote.memories)
    assert site.metadata["damage_state"] == "collapsed"
    shape = city.urban.describe(site)["structure"]
    assert shape["integrity"] == 0 and shape["width"] == site.width * 0.8
    restored = restore_world(city.store, dump_world(city))
    assert not restored.agents[victim.id].alive
    assert restored.urban.describe(restored.objects[site.id])["structure"] == shape


def test_collapsed_building_needs_multiple_repairs_and_restores_geometry(city):
    agent = next(iter(city.agents.values()))
    site = next(o for o in city.objects.values() if o.kind == "home")
    site.metadata.update(
        quake_damage="test", structural_integrity=0, damage_state="collapsed", open=False
    )
    agent.position = Vec2(**site.metadata["entrance"])
    for integrity in [30, 60, 90, 100]:
        assert city.urban.execute(agent, ActionIntent(action=ActionType.REPAIR, target_id=site.id))
        city.time = agent.activity.ends_at
        city.urban.tick()
        assert site.metadata["structural_integrity"] == integrity
        assert bool(site.metadata.get("quake_damage")) == (integrity < 100)
        assert site.metadata["open"] == (integrity == 100)
    assert city.urban.describe(site)["structure"]["state"] == "intact"
