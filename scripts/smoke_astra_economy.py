"""Explicitly seeded API integration test, NOT evidence of spontaneous entrepreneurship.

Makes seven real Astra requests using the configured credential, in a separate world.
"""

import asyncio
import json

from dotenv import load_dotenv

from app.brain import AstraBrain
from app.models import Goal, Vec2
from app.secrets import openai_api_key
from app.store import EventStore
from app.world import World


async def main():
    load_dotenv()
    key = openai_api_key()
    if not key:
        raise RuntimeError("Configure an OpenAI credential; this test cannot use rule demo.")
    brain = AstraBrain(key)
    store = EventStore(".data/astra-economy-check.db")
    world = World(store, agent_count=3)
    world.next_city_event = 100000
    founder, investor, customer = world.agents.values()
    for agent in world.agents.values():
        agent.credits = 100
        agent.position = Vec2(x=1190, y=125)
    site = next(o for o in world.objects.values() if o.kind == "launchpad")

    async def decide(agent, instruction, expected):
        agent.active_goal = Goal(statement=instruction, reason="Explicitly seeded integration test")
        context = world.context_for(agent)
        context["integration_test"] = {
            "purpose": "Verify your requested in-game action, not social emergence.",
            "instruction": instruction,
        }
        decision = await brain.decide(agent.model_copy(deep=True), context)
        print(
            json.dumps(
                {
                    "agent": agent.name,
                    "action": decision.intent.action,
                    "terms": decision.intent.terms.model_dump() if decision.intent.terms else None,
                }
            ),
            flush=True,
        )
        assert decision.intent.action.value == expected, decision.intent
        world.apply_decision(agent.id, decision)
        assert not agent.last_action_result.startswith("Failed"), agent.last_action_result

    try:
        await decide(
            founder,
            f"Found Fog Lunch Club at {site.id} now. Product meals, seed amount 10, "
            "unit price 3. Use found_company with these terms.",
            "found_company",
        )
        company = next(iter(world.economy.companies.values()))
        await decide(
            founder,
            f"Offer {investor.id} an investment in {company.id}: "
            "20 credits for 25% post-money equity. Use offer_investment now.",
            "offer_investment",
        )
        offer = list(world.economy.offers.values())[-1]
        await decide(
            investor,
            f"I have decided to invest 20 credits for 25% equity. "
            f"Accept offer {offer.id} now using accept_offer.",
            "accept_offer",
        )
        assert company.raised == 20 and company.shares[investor.id] == 0.25
        founder.position = world.objects[company.id].position.model_copy()
        await decide(
            founder, f"Produce the first batch at my company {company.id} using work now.", "work"
        )
        for _ in range(150):
            world.tick(0.1)
        assert company.stock == 3
        customer.position = founder.position.model_copy()
        await decide(customer, f"Buy one meal from company {company.id} now using buy.", "buy")
        assert company.revenue == 3 and company.stock == 2 and customer.inventory
        customer.position = Vec2(x=110, y=310)
        world.urban.create_carried(customer, "material", "Test Reclaimed Material")
        await decide(
            customer,
            "Build a road at destination x=130,y=310 using build and "
            "terms.tile=road. It uses my reclaimed material.",
            "build",
        )
        assert world.terrain.tiles["6,15"]["kind"] == "road"
        await decide(
            customer, "Remove the road at destination x=130,y=310 using demolish now.", "demolish"
        )
        assert "6,15" not in world.terrain.tiles
        print("PASS: seven real Astra decisions; economy and physical city editing.", flush=True)
    finally:
        await brain.client.close()
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
