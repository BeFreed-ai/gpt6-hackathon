from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import AgentState

if TYPE_CHECKING:
    from app.world import World


class Lifecycle:
    """Authoritative death and locally discoverable physical evidence, never scripted grief."""

    def __init__(self, world: World) -> None:
        self.world = world

    def kill(self, agent: AgentState, cause: str, text: str, cause_event_id: str | None = None):
        if not agent.alive:
            return None
        world = self.world
        world.urban.cancel(agent)
        agent.health = 0
        agent.alive = False
        agent.died_at = world.time
        agent.death_cause = cause
        agent.stimulus_version += 1
        agent.action_target = None
        agent.pending_intent = None
        agent.route.clear()
        agent.route_goal = None
        agent.speech = None
        agent.current_action = "dead"
        agent.last_action_result = text
        agent.is_thinking = False
        # Refund interrupted production/cooking before releasing possessions.
        for key in list(agent.inventory):
            item = world.urban.carried.pop(key)
            item.position = agent.position.model_copy()
            world.objects[key] = item
        agent.inventory.clear()
        for offer in world.economy.offers.values():
            if offer.status == "pending" and agent.id in {offer.sender_id, offer.recipient_id}:
                offer.status = "void_death"
        # Credits and shares remain on the deceased account; inheritance is not simulated.
        remains = world._add_object(
            "remains", f"Remains of {agent.name}", agent.position.x, agent.position.y, 24, 16
        )
        remains.metadata = {"citizen_id": agent.id, "citizen_name": agent.name}
        event = world.emit(
            "death", text, position=agent.position, radius=180,
            payload={"victim_id": agent.id, "cause_event_id": cause_event_id},
        )
        for citizen_id in event.payload["delivered_to"]:
            world.agents[citizen_id].discovered_remains.append(remains.id)
        return event

    def observe_remains(self, agent: AgentState, sight: float) -> None:
        for item in list(self.world.objects.values()):
            if item.kind != "remains" or item.id in agent.discovered_remains:
                continue
            if self.world._distance_agent_object(agent, item) > 180 * sight:
                continue
            agent.discovered_remains.append(item.id)
            self.world.emit(
                "discovery",
                f"{agent.name} found the remains of {item.metadata['citizen_name']}. "
                "They are dead; the cause cannot be established from the remains alone.",
                target_ids=[agent.id], position=item.position, radius=0,
                payload={"private": True, "victim_id": item.metadata["citizen_id"]},
            )
