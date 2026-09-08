from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.brain import AstraBrain
from app.models import AgentState, Vec2


class FakeResponses:
    def __init__(self) -> None:
        self.arguments = None

    async def create(self, **kwargs):
        self.arguments = kwargs
        output = {
            "goal": "Verify the radio report",
            "goal_reason": "Secondhand claims may be false",
            "goal_priority": 0.8,
            "goal_commitment": 0.7,
            "public_reason": "I need evidence before I trust the broadcast.",
            "action": "move",
            "target_id": None,
            "destination": {"x": 200, "y": 300},
            "message": None,
            "expressed_values": ["truth"],
            "relationship_updates": [],
        }
        return SimpleNamespace(output_text=json.dumps(output))


@pytest.mark.asyncio
async def test_astra_brain_uses_exact_model_and_structured_output() -> None:
    brain = AstraBrain("test-key")
    fake_responses = FakeResponses()
    brain.client = SimpleNamespace(responses=fake_responses)
    agent = AgentState(id="yellow_01", name="Mimo", position=Vec2(x=10, y=20))
    context = {
        "world_time": 12.5,
        "time_of_day": "08:00",
        "weather": "clear",
        "nearby_objects": [],
        "nearby_agents": [],
        "recent_memories": [],
        "known_workplace": None,
        "legal_actions": ["move", "wait"],
    }

    decision = await brain.decide(agent, context)

    assert fake_responses.arguments["model"] == "gpt-6-astra"
    assert fake_responses.arguments["text"]["format"]["type"] == "json_schema"
    assert fake_responses.arguments["text"]["format"]["strict"] is True
    assert fake_responses.arguments["store"] is False
    assert decision.intent.goal.statement == "Verify the radio report"
    assert decision.intent.destination == Vec2(x=200, y=300)
    assert decision.expressed_values == ["truth"]
