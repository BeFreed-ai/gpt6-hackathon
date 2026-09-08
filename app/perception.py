from __future__ import annotations

import math
from collections.abc import Iterable

from app.models import AgentState, Memory, SourceType, WorldEvent


def distance_between(a_x: float, a_y: float, b_x: float, b_y: float) -> float:
    return math.hypot(a_x - b_x, a_y - b_y)


class PerceptionResolver:
    def __init__(self, namespace: str = "run") -> None:
        self._memory_counter = 0
        self.namespace = namespace

    def resolve(
        self,
        event: WorldEvent,
        agents: Iterable[AgentState],
        vision_modifier: float = 1.0,
    ) -> list[tuple[str, Memory]]:
        deliveries: list[tuple[str, Memory]] = []
        for agent in agents:
            if not agent.alive:
                continue
            source_type = self._source_for(agent, event, vision_modifier)
            if source_type is None:
                continue
            self._memory_counter += 1
            content = self._content_for(agent, event, source_type)
            confidence = {
                SourceType.DIRECT_EXPERIENCE: 1.0,
                SourceType.DIRECT_OBSERVATION: 0.95,
                SourceType.OVERHEARD: 0.72,
                SourceType.BROADCAST: 0.68,
            }.get(source_type, 0.75)
            memory = Memory(
                id=f"{self.namespace}_mem_{self._memory_counter:07d}",
                world_time=event.world_time,
                content=content,
                source_type=source_type,
                source_id=(None if source_type == SourceType.OVERHEARD
                           and event.type in {"attack", "lightning"} else event.actor_id),
                confidence=confidence,
                original_event_id=event.id,
                importance=self._importance(event.type),
                event_type=event.type,
                message=(
                    self._heard_text(event) if source_type == SourceType.OVERHEARD
                    and event.type in {"attack", "lightning"}
                    else event.payload.get("message", event.public_text)
                ),
                addressed_to_me=agent.id in event.target_ids,
                reply_to=event.payload.get("reply_to"),
                position=event.position.model_copy() if event.position else None,
            )
            deliveries.append((agent.id, memory))
        return deliveries

    def _source_for(
        self,
        agent: AgentState,
        event: WorldEvent,
        vision_modifier: float,
    ) -> SourceType | None:
        if agent.id == event.actor_id or agent.id in event.target_ids:
            return SourceType.DIRECT_EXPERIENCE
        if event.payload.get("private"):
            return None
        if event.broadcast:
            if event.position is None:
                return SourceType.BROADCAST
            signal_distance = distance_between(
                agent.position.x,
                agent.position.y,
                event.position.x,
                event.position.y,
            )
            return SourceType.BROADCAST if signal_distance <= event.radius else None
        if event.position is None:
            return None
        distance = distance_between(
            agent.position.x,
            agent.position.y,
            event.position.x,
            event.position.y,
        )
        if event.type in {"speech", "shout", "address_player"}:
            return SourceType.OVERHEARD if distance <= event.radius else None
        if distance <= event.radius * vision_modifier:
            return SourceType.DIRECT_OBSERVATION
        if event.type in {"attack", "lightning"} and distance <= event.radius * 1.6:
            return SourceType.OVERHEARD
        return None

    def _content_for(
        self,
        agent: AgentState,
        event: WorldEvent,
        source_type: SourceType,
    ) -> str:
        if source_type == SourceType.BROADCAST:
            source = event.payload.get("station", "a city broadcast")
            return f'I heard {source} report: "{event.public_text}"'
        if agent.id == event.actor_id:
            return f"I did this: {event.public_text}"
        if agent.id in event.target_ids:
            return f"This happened directly to me: {event.public_text}"
        if source_type == SourceType.OVERHEARD:
            return f"I heard nearby: {self._heard_text(event)}"
        return f"I observed: {event.public_text}"

    @staticmethod
    def _heard_text(event: WorldEvent) -> str:
        return {
            "lightning": "A loud thunderclap nearby. I could not see who, if anyone, was hit.",
            "attack": "Sounds of a struggle nearby. I could not identify who was involved.",
        }.get(event.type, event.public_text)

    @staticmethod
    def _importance(event_type: str) -> float:
        if event_type in {"death", "discovery", "player_kill", "attack", "lightning", "eviction"}:
            return 1.0
        if event_type in {
            "speech",
            "shout",
            "broadcast",
            "help",
            "player_gift",
            "player_build",
            "weather",
            "give",
            "offer",
            "agreement",
            "rent_warning",
            "address_player",
        }:
            return 0.75
        if event_type in {"waste", "stepped_in_waste", "service_report"}:
            return 0.55
        return 0.35
