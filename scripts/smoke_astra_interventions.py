"""Six real decisions in a staged incident, with no prescribed reaction or social goal.

This tests perception and execution, not consciousness or spontaneous social emergence.
"""

import asyncio
import json

from dotenv import load_dotenv

from app.brain import AstraBrain
from app.models import Vec2
from app.secrets import openai_api_key
from app.store import EventStore
from app.world import World


async def main():
    load_dotenv()
    key = openai_api_key()
    if not key:
        raise RuntimeError("An OpenAI credential is required. No rule fallback.")
    brain = AstraBrain(key)
    store = EventStore(".data/astra-intervention-check.db")
    world = World(store, agent_count=4)
    world.next_city_event = 100000
    for agent, x in zip(world.agents.values(), (100, 180, 400, 1300), strict=True):
        agent.position = Vec2(x=x, y=310)
        agent.memories.clear()
        agent.inbox.clear()
    victim, witness, listener, far = world.agents.values()
    receipt = world.intervene("lightning", victim.position, None)
    assert receipt["killed"] == [victim.id]
    assert any(m.event_type == "death" for m in witness.memories)
    assert all(m.event_type != "death" for m in listener.memories)
    assert not far.memories
    print("Staged strike: victim, witness, listener and uninformed citizen.", flush=True)

    async def decide(agent):
        context = world.context_for(agent)
        consumed = set(agent.inbox)
        decision = await brain.decide(agent.model_copy(deep=True), context)
        agent.inbox = [key for key in agent.inbox if key not in consumed]
        world.apply_decision(agent.id, decision)
        world.record_followup(agent, decision, consumed)
        print(json.dumps({
            "agent": agent.name, "action": decision.intent.action,
            "goal": decision.intent.goal.statement if decision.intent.goal else None,
            "message": decision.intent.message, "reason": decision.intent.public_reason,
            "result": agent.last_action_result,
        }), flush=True)

    try:
        for turn in range(2):
            print(f"Decision round {turn + 1}/2", flush=True)
            await asyncio.gather(*(decide(agent) for agent in (witness, listener, far)))
            for _ in range(200):
                world.tick(0.1)
        assert victim.decision_count == 0 and not victim.alive
        assert all(agent.decision_count >= 1 for agent in (witness, listener, far))
        print("PASS: real Astra perception/decision loop; no reaction was forced.", flush=True)
    finally:
        await brain.client.close()
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
