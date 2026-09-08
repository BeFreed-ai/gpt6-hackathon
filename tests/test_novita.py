from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from app.brain import NovitaBrain, ResilientBrain
from app.models import AgentState, Vec2
from app.secrets import novita_api_key


def valid_output():
    return {
        "goal": "Repair the shared kitchen",
        "goal_reason": "My neighbor needs it",
        "goal_priority": 0.7,
        "goal_commitment": 0.8,
        "public_reason": "I will look for reclaimed materials.",
        "action": "wait",
        "target_id": None,
        "destination": None,
        "message": None,
        "reply_to": None,
        "terms": None,
        "expressed_values": ["care"],
        "relationship_updates": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [None, "deepseek/deepseek-v3.2"])
async def test_novita_uses_chat_schema_private_context_and_actual_source(model):
    brain = NovitaBrain("novita-test-key", model) if model else NovitaBrain("novita-test-key")
    assert str(brain.client.base_url) == "https://api.novita.ai/openai/"
    await brain.client.close()
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps(valid_output())),
                )
            ]
        )

    brain.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    agent = AgentState(id="yellow_01", name="Test", position=Vec2(x=10, y=20))
    context = {"world_time": 25, "recent_memories": [{"content": "My private history"}]}
    result = await brain.decide(agent, context)
    assert result.source == "novita"
    assert result.intent.goal.created_at == 25
    request = calls[0]
    assert request["model"] == (model or "deepseek/deepseek-v4-pro-0813")
    assert request["max_tokens"] == 8192
    if model:
        assert request["response_format"]["json_schema"]["strict"] is True
    else:
        assert request["response_format"] == {"type": "json_object"}
        assert '"additionalProperties": false' in request["messages"][0]["content"]
    assert "instructions" not in request and "prompt_cache_key" not in request
    payload = json.loads(request["messages"][1]["content"])
    assert payload["private_context"] == context
    assert payload["identity"]["id"] == agent.id


@pytest.mark.parametrize(
    "mutate",
    [
        lambda output: output.update(action="invent_money"),
        lambda output: output.update(goal_priority=5),
        lambda output: output.update(expressed_values=["a"] * 5),
        lambda output: output.update(secret_side_effect="not permitted"),
        lambda output: output.pop("goal"),
    ],
)
def test_invalid_provider_output_is_not_a_decision(mutate):
    output = valid_output()
    mutate(output)
    brain = object.__new__(NovitaBrain)
    with pytest.raises(ValidationError):
        brain.parse(json.dumps(output), {"world_time": 0})


def test_nonfinite_output_is_rejected():
    output = valid_output()
    output["goal_priority"] = float("nan")
    with pytest.raises(ValueError, match="Nonfinite"):
        object.__new__(NovitaBrain).parse(json.dumps(output), {"world_time": 0})


def test_optional_life_plan_is_parsed_without_exposing_hidden_reasoning():
    output = valid_output()
    output["life_update"] = {
        "direction": {"statement": "Make room for shared craft", "evidence_memory_ids": []},
        "create_projects": [], "project_changes": [],
        "recall": {"query": "repair kitchen", "memory_ids": []},
    }
    result = object.__new__(NovitaBrain).parse(json.dumps(output), {"world_time": 0})
    assert result.life_update.direction.statement == "Make room for shared craft"
    assert result.life_update.recall.query == "repair kitchen"
    assert result.intent.goal.statement == output["goal"]
    output["life_update"]["hidden_reasoning"] = "Not allowed"
    with pytest.raises(ValidationError):
        object.__new__(NovitaBrain).parse(json.dumps(output), {"world_time": 0})


@pytest.mark.parametrize("field,value", [
    ("create_projects", [{}] * 2),
    ("project_changes", [{}] * 3),
    ("recall", {"query": "x" * 121, "memory_ids": []}),
])
def test_provider_life_updates_obey_small_turn_limits(field, value):
    output = valid_output()
    output["life_update"] = {field: value}
    with pytest.raises(ValidationError):
        object.__new__(NovitaBrain).parse(json.dumps(output), {"world_time": 0})


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason,content", [("length", "{}"), ("stop", None)])
async def test_truncated_or_empty_novita_response_fails_closed(finish_reason, content):
    async def create(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=finish_reason,
                    message=SimpleNamespace(content=content),
                )
            ]
        )

    brain = object.__new__(NovitaBrain)
    brain.model = "deepseek/deepseek-v3.2"
    brain.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    agent = AgentState(id="test", name="Test", position=Vec2(x=0, y=0))
    with pytest.raises(ValueError):
        await brain.decide(agent, {})


@pytest.mark.asyncio
async def test_selected_provider_never_loads_openai_credentials_or_uses_rule_fallback(monkeypatch):
    monkeypatch.setenv("SOCIETY_LLM_PROVIDER", "novita")
    monkeypatch.setattr("app.brain.novita_api_key", lambda: "novita-test-key")

    def wrong_provider():
        raise AssertionError("OpenAI credentials must not be loaded")

    monkeypatch.setattr("app.brain.openai_api_key", wrong_provider)
    brain = ResilientBrain()
    assert brain.mode == "novita"
    await brain.primary.client.close()

    async def fail(*args):
        raise TimeoutError("Private provider details")

    brain.primary = SimpleNamespace(decide=fail)
    with pytest.raises(TimeoutError):
        await brain.decide(None, {})
    assert brain.last_error == "TimeoutError: Novita / DeepSeek request failed."


def test_missing_novita_key_does_not_silently_use_another_provider(monkeypatch):
    monkeypatch.setenv("SOCIETY_LLM_PROVIDER", "novita")
    monkeypatch.setattr("app.brain.novita_api_key", lambda: None)
    with pytest.raises(RuntimeError, match="Novita selected"):
        ResilientBrain()


def test_novita_secret_field_is_explicit_and_not_logged(monkeypatch, capsys):
    monkeypatch.delenv("NOVITA_API_KEY", raising=False)
    monkeypatch.setenv("NOVITA_SECRET_ID", "test/novita")
    monkeypatch.setenv("NOVITA_SECRET_FIELD", "api_key")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "SecretString": json.dumps({"api_key": "test-private-key"}),
                }
            )
        )

    monkeypatch.setattr("app.secrets.subprocess.run", run)
    assert novita_api_key() == "test-private-key"
    assert "test/novita" in calls[0]
    assert "test-private-key" not in capsys.readouterr().out


def test_novita_never_reuses_openai_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-stay-with-openai")
    monkeypatch.delenv("NOVITA_API_KEY", raising=False)
    monkeypatch.delenv("NOVITA_SECRET_ID", raising=False)
    assert novita_api_key() is None


def test_novita_decisions_are_not_counted_as_astra(tmp_path):
    from app.models import ActionIntent, ActionType, AgentDecision
    from app.store import EventStore
    from app.world import World

    store = EventStore(str(tmp_path / "counts.db"))
    try:
        world = World(store, agent_count=1)
        agent = next(iter(world.agents.values()))
        world.apply_decision(
            agent.id,
            AgentDecision(
                intent=ActionIntent(action=ActionType.WAIT),
                source="novita",
            ),
        )
        stats = world.snapshot("novita")["stats"]
        assert stats["llm_decisions"] == 1
        assert stats["astra_decisions"] == 0
    finally:
        store.close()
