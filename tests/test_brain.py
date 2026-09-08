from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.brain import ACTION_SCHEMA, PROVIDER_ACTION_SCHEMA, AstraBrain, ResilientBrain
from app.models import AgentBackground, AgentState, Vec2


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
            "reply_to": None,
            "terms": None,
            "expressed_values": ["truth"],
            "relationship_updates": [],
        }
        return SimpleNamespace(output_text=json.dumps(output))


@pytest.mark.asyncio
async def test_astra_brain_uses_exact_model_and_structured_output() -> None:
    brain = AstraBrain("test-key")
    fake_responses = FakeResponses()
    brain.client = SimpleNamespace(responses=fake_responses)
    agent = AgentState(
        id="yellow_01",
        name="Mimo",
        position=Vec2(x=10, y=20),
        background=AgentBackground(
            age=42,
            neighborhood="mission",
            housing_status="renter",
            employment_status="employed",
            occupation_sector="food_service",
            biography=["I previously repaired kitchen equipment."],
        ),
    )
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
    payload = json.loads(fake_responses.arguments["input"])
    assert payload["identity"]["background"]["biography"] == agent.background.biography
    assert decision.intent.goal.statement == "Verify the radio report"
    assert decision.intent.destination == Vec2(x=200, y=300)
    assert decision.expressed_values == ["truth"]
    assert decision.life_update is None
    assert payload["life"]["projects"] == []
    assert "life_update" in fake_responses.arguments["text"]["format"]["schema"]["required"]


def test_provider_contract_is_strict_but_legacy_parse_contract_remains_compatible():
    assert "life_update" not in ACTION_SCHEMA["required"]
    assert "life_update" in PROVIDER_ACTION_SCHEMA["required"]

    def check(value):
        if isinstance(value, dict):
            assert "default" not in value
            if value.get("type") == "object":
                assert set(value["required"]) == set(value["properties"])
                assert value["additionalProperties"] is False
            for nested in value.values():
                check(nested)
        elif isinstance(value, list):
            for nested in value:
                check(nested)

    check(PROVIDER_ACTION_SCHEMA)


@pytest.mark.asyncio
async def test_exhausted_credits_are_reported_without_exposing_error_body(monkeypatch):
    monkeypatch.setattr("app.brain.openai_api_key", lambda: None)
    brain = ResilientBrain()

    class QuotaError(Exception):
        code = "credit_balance_exhausted"

    class ExhaustedProvider:
        async def decide(self, agent, context):
            raise QuotaError("Sensitive provider response must not be shown")

    brain.primary = ExhaustedProvider()
    agent = AgentState(id="test", name="Test", position=Vec2(x=0, y=0))
    with pytest.raises(QuotaError):
        await brain.decide(agent, {})
    assert "credits exhausted" in brain.last_error
    assert "Sensitive" not in brain.last_error
