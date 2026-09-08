"""Observer measurements, never an input to citizen minds or a consciousness score."""

from collections import Counter


def report(world) -> dict:
    alive = [agent for agent in world.agents.values() if agent.alive]
    balances = sorted(max(0, agent.credits) for agent in alive)
    total = sum(balances)
    count = len(balances)
    gini = (
        sum((2 * i - count - 1) * value for i, value in enumerate(balances, 1)) / (count * total)
        if total > 0 and count
        else 0
    )
    projects = [project for agent in alive for project in agent.life.projects]
    all_turns = [agent.decision_count for agent in alive]
    failures = Counter(
        agent.last_action_result
        for agent in alive
        if agent.current_action == "replanning" or agent.last_action_result.startswith("Failed")
    )
    # Relationships are directional self-reports, not validated friendship labels.
    edges = sum(len(agent.relationships) for agent in alive)
    return {
        "run_id": world.run_id,
        "simulated_days": round(world.time / world.day_length, 3),
        "population": len(world.agents),
        "alive": len(alive),
        "deaths": len(world.agents) - len(alive),
        "housed": sum(agent.home_id is not None for agent in alive),
        "hungry": sum(agent.hunger >= 70 for agent in alive),
        "exhausted": sum(agent.energy <= 20 for agent in alive),
        "residents_with_decisions": sum(turns > 0 for turns in all_turns),
        "minimum_decisions": min(all_turns, default=0),
        "maximum_decisions": max(all_turns, default=0),
        "total_memories": sum(len(agent.memories) for agent in world.agents.values()),
        "residents_with_life_direction": sum(agent.life.direction is not None for agent in alive),
        "projects": dict(Counter(project.status for project in projects)),
        "relationship_edges": edges,
        "companies": len(world.economy.companies),
        "accepted_offers": sum(
            offer.status == "accepted" for offer in world.economy.offers.values()
        ),
        "citizen_built_tiles": sum(
            bool(tile.get("builder_id")) for tile in world.terrain.tiles.values()
        ),
        "cash_gini": round(gini, 3),
        "current_action_failures": dict(failures),
        "claim": "Behavioral measurements only; not consciousness or demographic validity.",
    }
