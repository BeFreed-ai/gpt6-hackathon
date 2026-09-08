"""Private, evidence-linked life plans and bounded access to durable personal history."""

from __future__ import annotations

import json
import math
import re
from uuid import uuid4

from app.models import (
    AgentState,
    LifeMilestone,
    LifeProject,
    LifeState,
    LifeUpdate,
    Memory,
    SourceType,
)

MAX_PROJECTS = 24
MAX_ACTIVE_PROJECTS = 6
MEMORY_CONTEXT_LIMIT = 40
LIFE_MEMORY_PREFIX = "My recorded life-plan update: "


def apply_life_update(agent: AgentState, update: LifeUpdate | None, now: float) -> list[Memory]:
    """Atomically apply a private update; append and return audit memories for store persistence.

    Raises ValueError for invented references, invalid transitions or exhausted capacity.
    No action goal, body state, demographic, other agent or external data is modified.
    """
    if update is None:
        return []
    # Revalidate even callers that used model_construct or mutated an existing object.
    update = LifeUpdate.model_validate(update.model_dump())
    if not math.isfinite(now):
        raise ValueError("Life update time must be finite")
    state = agent.life.model_copy(deep=True)
    memories = {memory.id: memory for memory in agent.memories}

    def check_evidence(ids: list[str]) -> None:
        if len(ids) != len(set(ids)) or any(key not in memories for key in ids):
            raise ValueError("Life evidence must reference distinct personal memory IDs")

    if update.direction is not None:
        check_evidence(update.direction.evidence_memory_ids)
        state.direction = update.direction.model_copy(deep=True)
    for create in update.create_projects:
        check_evidence(create.evidence_memory_ids)
        if any(project.id == create.id for project in state.projects):
            raise ValueError("Project ID already exists; resume or revise it instead")
        if len(state.projects) >= MAX_PROJECTS:
            raise ValueError("Personal project capacity reached")
        if len({milestone.id for milestone in create.milestones}) != len(create.milestones):
            raise ValueError("Milestone IDs must be distinct within a project")
        state.projects.append(
            LifeProject(
                **create.model_dump(exclude={"milestones"}),
                milestones=[LifeMilestone(**item.model_dump()) for item in create.milestones],
                created_at=now,
                updated_at=now,
            )
        )
    for change in update.project_changes:
        check_evidence(change.evidence_memory_ids)
        project = next((p for p in state.projects if p.id == change.project_id), None)
        if project is None:
            raise ValueError("Cannot change an unknown project")
        if project.status in {"finished", "abandoned"}:
            raise ValueError("A closed project cannot be changed")
        operation = change.operation
        if operation == "resume" and project.status != "suspended":
            raise ValueError("Only a suspended project can resume")
        if operation in {"advance", "suspend", "finish"} and project.status != "active":
            raise ValueError("This transition requires an active project")
        if operation == "advance":
            milestone = next((m for m in project.milestones if m.id == change.milestone_id), None)
            if milestone is None or change.progress is None:
                raise ValueError("Progress requires a known milestone and a numeric value")
            if change.progress < milestone.progress:
                raise ValueError("Milestone progress cannot regress")
            if all(memories[key].source_type == SourceType.INFERENCE
                   for key in change.evidence_memory_ids):
                raise ValueError("A plan or inference alone is not evidence of milestone progress")
            milestone.progress = change.progress
            milestone.evidence_memory_ids = list(change.evidence_memory_ids)
        elif change.milestone_id is not None or change.progress is not None:
            raise ValueError("Only advance can update milestone progress")
        if operation == "finish" and any(m.progress < 1 for m in project.milestones):
            raise ValueError("Finish requires every milestone to be complete")
        if operation in {"resume", "suspend", "finish", "abandon"}:
            project.status = {
                "resume": "active", "suspend": "suspended",
                "finish": "finished", "abandon": "abandoned",
            }[operation]
        if change.next_step is not None:
            project.next_step = change.next_step
        if change.commitment is not None:
            project.commitment = change.commitment
        project.evidence_memory_ids = list(change.evidence_memory_ids)
        project.last_note = change.note
        project.updated_at = now
    if sum(p.status == "active" for p in state.projects) > MAX_ACTIVE_PROJECTS:
        raise ValueError("At most six projects can be active concurrently")
    if update.recall is not None:
        check_evidence(update.recall.memory_ids)
        state.recall = update.recall.model_copy(deep=True)
    if state == agent.life:
        return []
    state.revision += 1
    # An append-only self-report preserves prior direction, commitments and plan revisions.
    # These records do not assert that a planned physical action actually happened.
    memory = Memory(
        id=f"life_{uuid4().hex}",
        world_time=now,
        content=LIFE_MEMORY_PREFIX + json.dumps(update.model_dump(exclude_none=True)),
        source_type=SourceType.INFERENCE,
        source_id=agent.id,
        importance=0.8 if update.direction is not None else 0.65,
        event_type="life_plan",
    )
    agent.life = state
    agent.memories.append(memory)
    return [memory]


def restore_life_from_memories(agent: AgentState) -> None:
    """Rebuild life state after the owner loads this agent's complete durable memory history.

    Fails atomically on a malformed audit entry; does not append or persist new memories.
    Source and event type distinguish our records from quoted or overheard plan text.
    """
    replay = agent.model_copy(deep=False)
    replay.life = LifeState()
    replay.memories = []
    for memory in agent.memories:
        if (memory.event_type == "life_plan" and memory.source_id == agent.id
                and memory.source_type == SourceType.INFERENCE
                and memory.content.startswith(LIFE_MEMORY_PREFIX)):
            update = LifeUpdate.model_validate_json(memory.content[len(LIFE_MEMORY_PREFIX):])
            audit = apply_life_update(replay, update, memory.world_time)
            if audit:
                replay.memories.pop()  # Keep the original durable ID for subsequent citations.
        replay.memories.append(memory)
    agent.life = replay.life


def life_context(agent: AgentState) -> dict:
    """Return only this citizen's intentions for private planning / click inspection."""
    result = agent.life.model_dump(mode="json")
    for project in result["projects"]:
        project["progress"] = round(
            sum(item["progress"] for item in project["milestones"]) / len(project["milestones"]), 3
        )
    result["capacity"] = {"total_projects": MAX_PROJECTS, "active_projects": MAX_ACTIVE_PROJECTS}
    return result


def select_memory_context(agent: AgentState, limit: int = MEMORY_CONTEXT_LIMIT) -> dict:
    """Select recent, salient, autobiographic and project evidence without pruning raw history.

    Recall searches personal memory text only and is included in the next normal decision.
    Prompt copies cap long text and disclose truncation; raw history is never modified.
    """
    if not 8 <= limit <= 80:
        raise ValueError("Memory context limit must be between 8 and 80")
    history = agent.memories
    by_id = {memory.id: memory for memory in history}
    selected: dict[str, Memory] = {}

    def include(items: list[Memory], budget: int) -> None:
        for memory in items:
            if budget <= 0 or len(selected) >= limit:
                break
            if memory.id not in selected:
                selected[memory.id] = memory
                budget -= 1

    recall = agent.life.recall
    recalled: list[Memory] = []
    if recall:
        recalled = [by_id[key] for key in recall.memory_ids if key in by_id]
        words = set(re.findall(r"[a-z0-9]+", recall.query.lower()))
        if words:
            matches = [
                (len(words & set(re.findall(r"[a-z0-9]+", m.content.lower()))), index, m)
                for index, m in enumerate(history)
            ]
            recalled.extend(m for score, _, m in sorted(matches, key=lambda x: x[:2], reverse=True)
                            if score > 0)
    # Reserve capacity for each evidence class before filling remaining space by recency.
    include(list(reversed(history)), max(2, limit // 3))
    include(recalled, max(1, limit // 5))
    evidence_ids = []
    if agent.life.direction:
        evidence_ids.extend(agent.life.direction.evidence_memory_ids)
    for project in sorted(agent.life.projects, key=lambda p: p.status != "active"):
        evidence_ids.extend(project.evidence_memory_ids)
        for milestone in project.milestones:
            evidence_ids.extend(milestone.evidence_memory_ids)
    include([by_id[key] for key in evidence_ids if key in by_id], max(1, limit // 4))
    anchors = [m for m in history if m.event_type in {
        "biography", "autobiography", "personal_background",
    }]
    include(list(reversed(anchors)), max(1, limit // 10))
    include(sorted(history, key=lambda m: (m.importance, m.world_time), reverse=True),
            max(1, limit // 5))
    include(list(reversed(history)), limit)
    chosen = sorted(selected.values(), key=lambda m: m.world_time)
    prompt_memories = []
    truncated_ids = []
    recalled_ids = {m.id for m in recalled}
    for memory in chosen:
        item = memory.model_dump(mode="json")
        for key, max_chars in (("content", 1200), ("message", 500)):
            if item.get(key) and len(item[key]) > max_chars:
                item[key] = item[key][:max_chars]
                item[f"{key}_truncated"] = True
                if memory.id not in truncated_ids:
                    truncated_ids.append(memory.id)
        prompt_memories.append(item)
    return {
        "recent_memories": prompt_memories,
        "memory_context": {
            "total_count": len(history),
            "selected_count": len(chosen),
            "omitted_count": len(history) - len(chosen),
            "selection": "recent + recall + project evidence + autobiographic + important",
            "raw_history_preserved": True,
            "truncated_memory_ids": truncated_ids,
            "recall_query": recall.query if recall else None,
            "recall_match_count": len(recalled_ids),
            "recall_selected_ids": [m.id for m in chosen if m.id in recalled_ids],
            "recall_help": "Use life_update.recall.query or known memory_ids to recall next turn.",
        },
    }
