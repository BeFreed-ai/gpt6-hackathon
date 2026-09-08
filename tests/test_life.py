from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.life import (
    apply_life_update,
    life_context,
    restore_life_from_memories,
    select_memory_context,
)
from app.models import (
    ActionIntent,
    ActionType,
    AgentDecision,
    AgentState,
    Goal,
    LifeDirection,
    LifeState,
    LifeUpdate,
    Memory,
    MemoryRecall,
    MilestonePlan,
    ProjectChange,
    ProjectCreate,
    SourceType,
    Vec2,
)


def citizen():
    return AgentState(
        id="citizen", name="Citizen", position=Vec2(x=0, y=0),
        memories=[Memory(id="memory_1", world_time=1, content="I repaired a broken bench.",
                         source_type=SourceType.DIRECT_EXPERIENCE)],
    )


def project(key="garden"):
    return ProjectCreate(
        id=key, title="A place to rest", goal="Make a useful shared garden",
        next_step="Find a suitable place", commitment=0.7, evidence_memory_ids=["memory_1"],
        milestones=[MilestonePlan(id="bench", statement="Place a usable bench")],
    )


def change(operation, **kwargs):
    return ProjectChange(
        project_id="garden", operation=operation, note="My next step reflects what happened.",
        evidence_memory_ids=["memory_1"], **kwargs,
    )


def test_old_agent_and_decision_payloads_have_empty_life_defaults():
    agent = citizen()
    agent.active_goal = Goal(statement="Eat lunch", reason="Hungry")
    decision = AgentDecision(intent=ActionIntent(action=ActionType.EAT))
    assert agent.life == LifeState()
    assert decision.life_update is None
    assert AgentState.model_validate(agent.model_dump()).active_goal == agent.active_goal


def test_independent_direction_multiple_projects_and_hunger_detour():
    agent = citizen()
    update = LifeUpdate(direction=LifeDirection(statement="Make shared spaces welcoming"),
                        create_projects=[project()])
    memories = apply_life_update(agent, update, 2)
    apply_life_update(agent, LifeUpdate(create_projects=[project("repair")]), 3)
    agent.hunger = 95
    agent.active_goal = Goal(statement="Eat lunch", reason="Hungry")
    assert agent.life.direction.statement == "Make shared spaces welcoming"
    assert len(agent.life.projects) == 2
    assert all(p.status == "active" for p in agent.life.projects)
    assert memories[0] in agent.memories
    assert memories[0].event_type == "life_plan"
    assert agent.traits == {} and agent.values == []


def test_suspend_resume_progress_finish_and_replay_preserve_every_raw_memory():
    agent = citizen()
    for update in [
        LifeUpdate(create_projects=[project()]),
        LifeUpdate(project_changes=[change("suspend")]),
        LifeUpdate(project_changes=[change("resume")]),
        LifeUpdate(project_changes=[change("advance", milestone_id="bench", progress=1)]),
        LifeUpdate(project_changes=[change("finish")]),
    ]:
        apply_life_update(agent, update, len(agent.memories) + 1)
    expected = agent.life.model_copy(deep=True)
    history = agent.model_dump()["memories"]
    assert life_context(agent)["projects"][0]["progress"] == 1
    assert expected.projects[0].status == "finished"
    restored = AgentState.model_validate_json(agent.model_dump_json())
    assert restored.life == expected
    restored.life = LifeState()
    restore_life_from_memories(restored)
    assert restored.life == expected
    assert restored.model_dump()["memories"] == history


def test_abandon_retains_goal_and_commitment_evidence():
    agent = citizen()
    apply_life_update(agent, LifeUpdate(create_projects=[project()]), 2)
    apply_life_update(agent, LifeUpdate(project_changes=[change("abandon", commitment=0.1)]), 3)
    archived = agent.life.projects[0]
    assert archived.status == "abandoned"
    assert archived.goal == project().goal
    assert archived.commitment == 0.1
    assert archived.evidence_memory_ids == ["memory_1"]


@pytest.mark.parametrize("bad_change", [
    {"operation": "advance", "milestone_id": "invented", "progress": 1},
    {"operation": "advance", "milestone_id": "bench"},
    {"operation": "finish"},
    {"operation": "resume"},
    {"operation": "revise", "progress": 1},
])
def test_bad_transition_rejects_entire_update_atomically(bad_change):
    agent = citizen()
    apply_life_update(agent, LifeUpdate(create_projects=[project()]), 2)
    before = agent.model_dump()
    with pytest.raises(ValueError):
        apply_life_update(agent, LifeUpdate(
            direction=LifeDirection(statement="This must not be applied"),
            project_changes=[change(**bad_change)],
        ), 3)
    assert agent.model_dump() == before


@pytest.mark.parametrize("update", [
    LifeUpdate(direction=LifeDirection(statement="A new direction", evidence_memory_ids=["fake"])),
    LifeUpdate(recall=MemoryRecall(memory_ids=["fake"])),
    LifeUpdate(project_changes=[change("abandon")]),
])
def test_invented_references_are_rejected(update):
    agent = citizen()
    before = agent.model_dump()
    with pytest.raises(ValueError):
        apply_life_update(agent, update, 2)
    assert agent.model_dump() == before


def test_duplicate_ids_and_capacity_are_rejected():
    agent = citizen()
    for i in range(6):
        apply_life_update(agent, LifeUpdate(create_projects=[project(f"p{i}")]), i + 2)
    before = agent.model_dump()
    for key in ("p0", "one_too_many"):
        with pytest.raises(ValueError):
            apply_life_update(agent, LifeUpdate(create_projects=[project(key)]), 10)
        assert agent.model_dump() == before


def test_total_capacity_preserves_closed_projects_instead_of_overwriting_them():
    agent = citizen()
    for index in range(24):
        create = project(f"p{index}")
        close = change("abandon")
        close.project_id = create.id
        apply_life_update(agent, LifeUpdate(create_projects=[create], project_changes=[close]),
                          index + 2)
    before = agent.model_dump()
    with pytest.raises(ValueError, match="capacity"):
        apply_life_update(agent, LifeUpdate(create_projects=[project("overflow")]), 30)
    assert agent.model_dump() == before
    assert len(agent.life.projects) == 24


def test_nonfinite_values_and_long_ids_fail_validation():
    for field, value in (("commitment", float("nan")), ("id", "p" * 49)):
        data = project().model_dump()
        data[field] = value
        with pytest.raises(ValidationError):
            ProjectCreate.model_validate(data)
    with pytest.raises(ValidationError):
        change("advance", milestone_id="bench", progress=float("inf"))


def test_milestone_regression_is_atomic_and_closed_project_cannot_resume():
    agent = citizen()
    apply_life_update(agent, LifeUpdate(create_projects=[project()]), 2)
    apply_life_update(agent, LifeUpdate(project_changes=[
        change("advance", milestone_id="bench", progress=0.5),
    ]), 3)
    before = agent.model_dump()
    with pytest.raises(ValueError, match="regress"):
        apply_life_update(agent, LifeUpdate(project_changes=[
            change("advance", milestone_id="bench", progress=0.2),
        ]), 4)
    assert agent.model_dump() == before
    apply_life_update(agent, LifeUpdate(project_changes=[change("abandon")]), 5)
    with pytest.raises(ValueError, match="closed"):
        apply_life_update(agent, LifeUpdate(project_changes=[change("resume")]), 6)


@pytest.mark.parametrize("data", [
    {"create_projects": [project().model_dump()] * 2},
    {"project_changes": [change("suspend").model_dump()] * 3},
    {"recall": {"memory_ids": ["m"] * 9}},
    {"direction": {"statement": "x" * 241}},
    {"hidden_reasoning": "Not an allowed field"},
])
def test_updates_are_small_and_do_not_accept_reasoning_fields(data):
    with pytest.raises(ValidationError):
        LifeUpdate.model_validate(data)


def test_plan_alone_cannot_establish_physical_progress():
    agent = citizen()
    audit = apply_life_update(agent, LifeUpdate(create_projects=[project()]), 2)[0]
    update = change("advance", milestone_id="bench", progress=1)
    update.evidence_memory_ids = [audit.id]
    with pytest.raises(ValueError, match="inference alone"):
        apply_life_update(agent, LifeUpdate(project_changes=[update]), 3)


def test_selection_keeps_recent_anchors_project_evidence_and_explicit_omission_count():
    agent = citizen()
    agent.memories[0].importance = 0.01
    apply_life_update(agent, LifeUpdate(create_projects=[project()]), 2)
    agent.memories.append(Memory(
        id="autobiography", world_time=0, content="My starting history", importance=0.01,
        source_type=SourceType.DIRECT_EXPERIENCE, event_type="personal_background",
    ))
    agent.memories.append(Memory(
        id="important", world_time=0, content="A formative experience", importance=1,
        source_type=SourceType.DIRECT_EXPERIENCE,
    ))
    for index in range(100):
        agent.memories.append(Memory(
            id=f"recent_{index}", world_time=index + 10, content="An ordinary event",
            source_type=SourceType.DIRECT_OBSERVATION, importance=0.1,
        ))
    before = agent.model_dump()
    context = select_memory_context(agent, limit=20)
    ids = {m["id"] for m in context["recent_memories"]}
    assert {"memory_1", "autobiography", "important", "recent_99"} <= ids
    assert len(ids) == 20
    assert context["memory_context"]["omitted_count"] == len(agent.memories) - 20
    assert agent.model_dump() == before


def test_recall_finds_old_personal_evidence_without_external_io_or_deleting_history():
    agent = citizen()
    for index in range(100):
        agent.memories.append(Memory(
            id=f"m{index}", world_time=index + 2, content="Ordinary event",
            source_type=SourceType.DIRECT_OBSERVATION,
        ))
    apply_life_update(agent, LifeUpdate(recall=MemoryRecall(query="broken bench")), 103)
    selected = select_memory_context(agent, 20)
    assert "memory_1" in selected["memory_context"]["recall_selected_ids"]
    assert len(agent.memories) == 102
    assert selected["memory_context"]["recall_match_count"] >= 1


def test_long_prompt_text_is_marked_and_raw_record_remains_complete():
    agent = citizen()
    agent.memories[0].content = "a" * 3000
    selected = select_memory_context(agent)
    assert len(selected["recent_memories"][0]["content"]) == 1200
    assert selected["recent_memories"][0]["content_truncated"]
    assert selected["memory_context"]["truncated_memory_ids"] == ["memory_1"]
    assert agent.memories[0].content == "a" * 3000


def test_noop_updates_do_not_create_audit_noise():
    agent = citizen()
    assert apply_life_update(agent, None, 1) == []
    assert apply_life_update(agent, LifeUpdate(), 1) == []
    assert len(agent.memories) == 1
