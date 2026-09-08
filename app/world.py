from __future__ import annotations

import math
import random
import uuid
from collections import deque
from typing import Any

from app.economy import Economy
from app.lifecycle import Lifecycle
from app.models import (
    ActionIntent,
    ActionType,
    AgentDecision,
    AgentState,
    Vec2,
    WorldEvent,
    WorldObject,
)
from app.perception import PerceptionResolver, distance_between
from app.store import EventStore
from app.terrain import BUILD_COSTS, Terrain
from app.urban import UrbanSystem

WORLD_WIDTH = 1400
WORLD_HEIGHT = 820
DAY_LENGTH = 720.0


DISTRICTS = [
    {
        "id": "fogline",
        "name": "Fogline",
        "color": "#c9d6cf",
        "x": 25,
        "y": 25,
        "width": 430,
        "height": 355,
    },
    {
        "id": "circuit_hill",
        "name": "Circuit Hill",
        "color": "#c7c0dd",
        "x": 475,
        "y": 25,
        "width": 900,
        "height": 355,
    },
    {
        "id": "mission_glow",
        "name": "Mission Glow",
        "color": "#f0c68f",
        "x": 25,
        "y": 400,
        "width": 735,
        "height": 395,
    },
    {
        "id": "civic_tide",
        "name": "Civic Tide",
        "color": "#9fc7bd",
        "x": 780,
        "y": 400,
        "width": 595,
        "height": 395,
    },
]


AGENT_SEEDS = [
    ("Mimo", 0.78, 0.68, 0.26, 0, "cafe"),
    ("Piko", 0.54, 0.42, 0.71, 1, "tech"),
    ("Luma", 0.91, 0.76, 0.18, 2, "clinic"),
    ("Nono", 0.35, 0.83, 0.31, 3, "market"),
    ("Kiko", 0.68, 0.29, 0.82, 4, "radio"),
    ("Tavi", 0.47, 0.71, 0.44, 5, "public_works"),
    ("Bibi", 0.84, 0.55, 0.63, 6, "tech"),
    ("Zuzu", 0.62, 0.88, 0.15, 7, "cafe"),
    ("Orli", 0.73, 0.39, 0.58, None, "market"),
    ("Fenn", 0.29, 0.74, 0.36, None, "public_works"),
    ("Rumi", 0.88, 0.61, 0.22, 8, "clinic"),
    ("Sola", 0.57, 0.67, 0.49, 9, "radio"),
]


class World:
    def __init__(
        self,
        store: EventStore,
        agent_count: int = 12,
        seed: int = 17,
        scenario: str = "prototype",
    ) -> None:
        if scenario not in {"prototype", "sf"}:
            raise ValueError("Unknown scenario; choose sf or prototype")
        if not 1 <= agent_count <= 500:
            raise ValueError("Agent count must be between 1 and 500")
        self.store = store
        self.scenario = scenario
        self.population_report: dict[str, Any] | None = None
        self.employer_catalog: list[dict[str, Any]] = []
        self.districts = DISTRICTS
        self.run_id = uuid.uuid4().hex[:10]
        self.random = random.Random(seed)
        self.time = 0.0
        self.weather = "clear"
        self.paused = False
        self.speed = 1.0
        self.event_counter = 0
        self.object_counter = 0
        self.last_day_charged = 0
        self.next_city_event = 42.0
        self.next_food_growth = 25.0
        self.events: deque[WorldEvent] = deque(maxlen=160)
        self.interventions: deque[dict] = deque(maxlen=30)
        self.player_messages: deque[dict] = deque(maxlen=40)
        self.perception = PerceptionResolver(self.run_id)
        self.objects: dict[str, WorldObject] = {}
        self.agents: dict[str, AgentState] = {}
        self.day_length = DAY_LENGTH
        self.economy = Economy(self)
        self.urban = UrbanSystem(self)
        self.terrain = Terrain(self)
        self.lifecycle = Lifecycle(self)
        self._create_city()
        self.urban.seed()
        if scenario == "sf":
            from app.sf_economy import apply_sf_economy
            from app.sf_scenario import seed_sf_scenario

            seed_sf_scenario(self, agent_count, seed)
            apply_sf_economy(self, seed)
        else:
            self._create_agents(agent_count)
        self.emit(
            "broadcast",
            "Good morning, SoMa and Mission. This is neighborhood public radio."
            if scenario == "sf"
            else "Good morning, Throng City. Fog is clearing over the eastern hills.",
            position=Vec2(x=1125, y=535),
            payload={"station": "KTHR Public Radio"},
            radius=1600,
            broadcast=True,
        )

    def _create_city(self) -> None:
        buildings = [
            ("home", "Fogline Apartments", 95, 110, 150, 95, {"rent": 6}),
            ("home", "Juniper House", 290, 245, 125, 88, {"rent": 5}),
            ("home", "Circuit Lofts", 540, 90, 145, 100, {"rent": 11}),
            ("home", "Skyglass Condos", 740, 85, 155, 105, {"rent": 14}),
            ("home", "Dolores Flats", 120, 500, 145, 96, {"rent": 7}),
            ("home", "Sunbeam Co-op", 325, 635, 150, 98, {"rent": 4}),
            ("home", "Lantern Rooms", 550, 515, 135, 90, {"rent": 6}),
            ("home", "Harbor Studios", 1200, 655, 135, 92, {"rent": 8}),
            ("home", "Mint House", 825, 635, 125, 90, {"rent": 5}),
            ("home", "Civic Residences", 1010, 680, 140, 88, {"rent": 7}),
            ("cafe", "Fog & Foam", 275, 75, 105, 72, {"wage": 3}),
            ("tech", "Astra Systems", 980, 80, 180, 110, {"wage": 6}),
            ("clinic", "Open Door Clinic", 810, 470, 145, 92, {"wage": 4}),
            ("market", "Glow Market", 505, 680, 125, 78, {"wage": 3}),
            (
                "radio",
                "KTHR Public Radio",
                1080,
                475,
                150,
                95,
                {"wage": 4, "power": 1, "coverage_radius": 950},
            ),
            ("public_works", "Street Services", 1210, 260, 135, 86, {"wage": 4}),
            ("shelter", "Harbor Night Center", 865, 255, 155, 88, {"beds": 4}),
            ("toilet", "Public Restroom", 650, 350, 62, 58, {"open": True}),
            ("park", "Signal Park", 330, 430, 180, 115, {}),
        ]
        for kind, name, x, y, width, height, metadata in buildings:
            self._add_object(kind, name, x, y, width, height, metadata=metadata)

        for x, y in [(185, 420), (245, 455), (430, 600), (610, 445), (720, 620), (1160, 400)]:
            self._add_object("tree", "Fruit Tree", x, y, 32, 42)
        for x, y in [(205, 440), (444, 620), (625, 465), (735, 640), (1180, 420)]:
            self._add_object("food", "Street Apple", x, y, 18, 18)

    def _create_agents(self, count: int) -> None:
        homes = [item.id for item in self.objects.values() if item.kind == "home"]
        workplaces = {
            item.kind: item.id
            for item in self.objects.values()
            if item.kind in {"cafe", "tech", "clinic", "market", "radio", "public_works"}
        }
        for index in range(count):
            seed = AGENT_SEEDS[index % len(AGENT_SEEDS)]
            name, curiosity, empathy, risk, home_index, work_kind = seed
            if index >= len(AGENT_SEEDS):
                name = f"Citizen {index + 1}"
            home_id = (
                homes[home_index] if home_index is not None and home_index < len(homes) else None
            )
            x = self.random.uniform(110, 1280)
            y = self.random.uniform(120, 710)
            agent = AgentState(
                id=f"yellow_{index + 1:02d}",
                name=name,
                position=Vec2(x=x, y=y),
                home_id=home_id,
                workplace_id=workplaces.get(work_kind),
                credits=round(self.random.uniform(12, 65), 2),
                stress=self.random.uniform(8, 28) + (15 if home_id is None else 0),
                traits={
                    "curiosity": curiosity,
                    "empathy": empathy,
                    "risk_tolerance": risk,
                    "aggression": round(self.random.uniform(0.05, 0.55), 2),
                },
                next_think_at=self.random.uniform(0.2, 4.5),
            )
            self.agents[agent.id] = agent

    def _add_object(
        self,
        kind: str,
        name: str,
        x: float,
        y: float,
        width: float = 32,
        height: float = 32,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> WorldObject:
        self.object_counter += 1
        item = WorldObject(
            id=f"obj_{self.object_counter:04d}",
            kind=kind,
            name=name,
            position=Vec2(x=x, y=y),
            width=width,
            height=height,
            metadata=metadata or {},
        )
        self.objects[item.id] = item
        return item

    def emit(
        self,
        event_type: str,
        public_text: str,
        *,
        actor_id: str | None = None,
        target_ids: list[str] | None = None,
        position: Vec2 | None = None,
        payload: dict[str, Any] | None = None,
        radius: float = 130,
        broadcast: bool = False,
    ) -> WorldEvent:
        self.event_counter += 1
        event = WorldEvent(
            id=f"{self.run_id}_evt_{self.event_counter:07d}",
            world_time=self.time,
            type=event_type,
            actor_id=actor_id,
            target_ids=target_ids or [],
            position=position,
            payload=payload or {},
            public_text=public_text,
            radius=radius,
            broadcast=broadcast,
        )
        self.events.append(event)
        self.store.append_event(event)
        vision_modifier = 0.58 if self.weather == "fog" else 1.0
        for agent_id, memory in self.perception.resolve(
            event,
            self.agents.values(),
            vision_modifier,
        ):
            agent = self.agents[agent_id]
            agent.memories.append(memory)
            self.store.append_memory(agent_id, memory)
            if memory.importance >= 0.7 and agent_id != event.actor_id:
                agent.inbox.append(memory.id)
                if event.type == "speech" and agent_id not in event.target_ids:
                    # Overheard conversation is remembered without repeatedly aborting travel.
                    continue
                agent.stimulus_version += 1
                agent.last_reaction = {
                    "earthquake": "Ground shaking!",
                    "facility_damage": "Damage nearby",
                    "injury": "Injured!" if agent_id in event.target_ids else "Someone is hurt",
                    "stepped_in_waste": (
                        "Stepped in waste!"
                        if agent_id in event.target_ids
                        else "Saw someone step in waste"
                    ),
                    "schedule_reminder": "Checking the time",
                    "broadcast": "Heard a broadcast",
                    "speech": "Heard a neighbor",
                    "lightning": "Startled by lightning",
                    "death": "Witnessed a death",
                    "discovery": "Found someone dead",
                    "player_kill": "Witnessed a fatal intervention",
                    "player_gift": "Noticed food",
                    "player_build": "Noticed a new restroom",
                    "weather": "Noticed the weather",
                }.get(event.type, "Noticed something")
                agent.reaction_until = self.time + 8
                if agent.activity and event.type not in {
                    "attack",
                    "lightning",
                    "death",
                    "player_kill",
                    "discovery",
                    "earthquake",
                    "facility_damage",
                    "injury",
                    "stepped_in_waste",
                }:
                    # Remember speech immediately, finish the short physical task first.
                    continue
                self.urban.cancel(agent)
                # Interrupt the current route; the next decision can explicitly resume it.
                agent.action_target = None
                agent.pending_intent = None
                agent.route.clear()
                agent.current_action = (
                    "listening"
                    if event.type in {"speech", "broadcast", "shout"}
                    else "reconsidering"
                )
                agent.next_think_at = min(agent.next_think_at, self.time + 0.2)
        event.payload["delivered_to"] = [
            a.id
            for a in self.agents.values()
            if a.memories and a.memories[-1].original_event_id == event.id
        ]
        self.store.append_event(event)
        return event

    def tick(self, delta_seconds: float) -> None:
        self.time += delta_seconds
        self._update_day_cycle()
        self._update_agents(delta_seconds)
        self.urban.tick()
        self.economy.tick()
        self._update_city_services()
        self._grow_food()
        self._maybe_city_event()
        if self.scenario == "sf":
            from app.routines import update_reminders

            update_reminders(self)

    def _grow_food(self) -> None:
        if self.time < self.next_food_growth:
            return
        self.next_food_growth = self.time + 25
        for tree in list(self.objects.values()):
            if tree.kind != "tree":
                continue
            nearby = sum(
                item.kind == "food"
                and distance_between(
                    item.position.x, item.position.y, tree.position.x, tree.position.y
                )
                < 55
                for item in self.objects.values()
            )
            if nearby < 3:
                self._add_object(
                    "food", "Ripe Apple", tree.position.x + 18, tree.position.y + 18, 18, 18
                )

    def _update_day_cycle(self) -> None:
        day = int(self.time // self.day_length)
        if day <= self.last_day_charged:
            return
        self.last_day_charged = day
        self.urban.new_day()
        if getattr(self, "sf_economy", None):
            self.sf_economy.new_day()
            return
        for agent in self.agents.values():
            if not agent.alive:
                continue
            if agent.home_id:
                residents = sum(
                    a.alive and a.home_id == agent.home_id for a in self.agents.values()
                )
                rent = round(
                    float(self.objects[agent.home_id].metadata.get("rent", 6)) / max(1, residents),
                    2,
                )
                if agent.credits >= rent:
                    agent.credits = round(agent.credits - rent, 2)
                    self.economy.city_balance += rent
                    agent.rent_arrears = 0
                elif agent.rent_arrears == 0:
                    agent.rent_arrears = 1
                    self.emit(
                        "rent_warning",
                        f"{agent.name} missed rent. "
                        "They have one day to recover before losing the room.",
                        actor_id=agent.id,
                        position=agent.position,
                        radius=0,
                    )
                else:
                    old_home = self.objects[agent.home_id].name
                    agent.home_id = None
                    agent.stress = min(100, agent.stress + 25)
                    self.emit(
                        "eviction",
                        f"{agent.name} lost their room at {old_home} after missing rent.",
                        actor_id=agent.id,
                        position=agent.position,
                        radius=150,
                    )

    def _update_agents(self, delta: float) -> None:
        for agent in self.agents.values():
            if not agent.alive:
                continue
            if agent.health <= 0:
                self.lifecycle.kill(agent, "health_failure", f"{agent.name} died.")
                continue
            body_delta = 0 if agent.is_thinking else delta
            agent.hunger = min(100, agent.hunger + body_delta * 0.07)
            agent.bladder = min(100, agent.bladder + body_delta * 0.08)
            agent.energy = max(0, agent.energy - body_delta * 0.045)
            indoors = (
                agent.activity
                and agent.activity.action == ActionType.SEEK_SHELTER
                and self.objects.get(agent.activity.target_id or "")
                and self.objects[agent.activity.target_id].kind != "bench"
            )
            exposed = self.weather == "fog" and agent.position.x < 780 and not indoors
            agent.warmth = max(
                0,
                min(
                    100,
                    agent.warmth
                    + body_delta * (-0.09 if exposed and not agent.wearing_coat else 0.05),
                ),
            )
            agent.cleanliness = max(0, agent.cleanliness - body_delta * 0.008)
            if agent.home_id is None:
                agent.stress = min(100, agent.stress + delta * 0.035)
            else:
                agent.stress = max(0, agent.stress - delta * 0.012)
            if agent.hunger >= 96:
                agent.health = max(0, agent.health - body_delta * 0.10)
            elif agent.hunger < 70:
                agent.health = min(100, agent.health + body_delta * 0.015)
            if agent.health <= 0:
                self.lifecycle.kill(agent, "health_failure", f"{agent.name} died.")
                continue
            self._advance_movement(agent, delta)
            self._handle_sanitation(agent)
            if agent.speech and self.time >= agent.speech_until:
                agent.speech = None

    def _advance_movement(self, agent: AgentState, delta: float) -> None:
        if self.time < agent.relief_until:
            return
        pending = agent.pending_intent
        if pending and pending.target_id:
            other = (
                self.agents.get(pending.target_id)
                or self.objects.get(pending.target_id)
                or self.economy.resolve_target(pending.target_id)
                or self.terrain.resolve_target(pending.target_id)
            )
            if other is None or (isinstance(other, AgentState) and not other.alive):
                self._fail_action(agent, pending, "The target is no longer available.")
                return
            entrance = getattr(other, "metadata", {}).get("entrance")
            agent.action_target = Vec2(**entrance) if entrance else other.position.model_copy()
        if agent.action_target and self.time - agent.action_started_at > 90:
            self._fail_action(
                agent,
                pending or ActionIntent(action=ActionType.MOVE),
                "The route timed out; choose another plan.",
            )
            return
        target = agent.action_target
        if target is None:
            return
        dx = target.x - agent.position.x
        dy = target.y - agent.position.y
        distance = math.hypot(dx, dy)
        arrival_range = 30 if pending else 5
        ignores_end = bool(
            pending
            and (
                pending.action in {ActionType.BUILD, ActionType.DEMOLISH}
                or pending.action == ActionType.TALK
                and pending.terms
                and pending.terms.civic_action
            )
        )
        if distance <= arrival_range and self.terrain.line_clear(
            agent.position, target, ignores_end
        ):
            if not pending:
                agent.position = target.model_copy()
            agent.action_target = None
            agent.pending_intent = None
            agent.current_action = "idle"
            agent.next_think_at = min(agent.next_think_at, self.time + 0.2)
            if pending and not self._execute(agent, pending):
                self._fail_action(agent, pending, "The action could not be completed on arrival.")
            elif pending and agent.current_action != "replanning":
                agent.last_action_result = f"Completed {pending.action.value} on arrival."
                if agent.activity:
                    agent.last_action_result = (
                        f"Started {pending.action.value}; completing the physical task."
                    )
            return
        self.terrain.observe(agent, 80)
        if (
            agent.route_goal != target
            or agent.route_revision != self.terrain.revision
            or not agent.route
        ):
            route = self.terrain.path(agent, target, arrival_range)
            if route is None:
                self._fail_action(
                    agent,
                    pending or ActionIntent(action=ActionType.MOVE),
                    "No passable route on your current map. Explore or remove an obstruction.",
                )
                return
            agent.route = route
            agent.route_goal = target.model_copy()
            agent.route_revision = self.terrain.revision
        if not agent.route:
            return
        waypoint = agent.route[0]
        dx, dy = waypoint.x - agent.position.x, waypoint.y - agent.position.y
        distance = math.hypot(dx, dy)
        if distance < 0.1:
            agent.route.pop(0)
            return
        speed = 46.0 * max(0.45, agent.energy / 100)
        speed *= (1.25 if agent.route_until > self.time else 1) * (0.8 if agent.warmth < 25 else 1)
        speed *= self.terrain.speed_at(agent.position)
        movement = min(distance, speed * delta)
        next_position = Vec2(
            x=agent.position.x + dx / distance * movement,
            y=agent.position.y + dy / distance * movement,
        )
        if not self.terrain.line_clear(agent.position, next_position):
            self.terrain.observe(agent, 80)
            agent.route.clear()
            agent.route_goal = None
            return
        agent.position = next_position

    def _handle_sanitation(self, agent: AgentState) -> None:
        if not agent.alive:
            return
        if agent.relief_until and self.time >= agent.relief_until:
            agent.relief_until = 0
            if agent.current_action == "relieving themselves":
                agent.current_action = "observing"
        using_toilet = agent.activity and agent.activity.action == ActionType.USE_TOILET
        if agent.bladder >= 99 and not using_toilet and self.time >= agent.relief_until:
            self.urban.cancel(agent)
            agent.action_target = None
            agent.pending_intent = None
            agent.route.clear()
            agent.route_goal = None
            agent.stimulus_version += 1
            # Physical relief takes 2.4 simulated seconds; subsequent decisions remain autonomous.
            agent.relief_until = self.time + 2.4
            agent.next_think_at = agent.relief_until + 0.2
            agent.current_action = "relieving themselves"
            agent.bladder = 8
            waste = self._add_object(
                "waste",
                "Street Waste",
                agent.position.x + self.random.uniform(-10, 10),
                agent.position.y + self.random.uniform(-10, 10),
                16,
                13,
                metadata={"created_at": self.time, "created_by": agent.id},
            )
            agent.stress = min(100, agent.stress + 9)
            self.emit(
                "waste",
                f"{agent.name} could not reach a restroom in time.",
                actor_id=agent.id,
                position=waste.position,
                payload={"object_id": waste.id, "duration_seconds": 2.4},
                radius=85,
            )
        for item in self.objects.values():
            if item.kind != "waste":
                continue
            # Creation is not a footstep. Others may still step in the fresh hazard.
            if item.metadata.get("created_by") == agent.id and self.time - float(item.metadata.get("created_at", -100)) < 3:
                continue
            last_step = float(item.metadata.get(f"step_{agent.id}", -100))
            if self.time - last_step < 25:
                continue
            if self._distance_agent_object(agent, item) < 16:
                item.metadata[f"step_{agent.id}"] = self.time
                agent.stress = min(100, agent.stress + 12)
                agent.cleanliness = max(0, agent.cleanliness - 15)
                self.emit(
                    "stepped_in_waste",
                    f"{agent.name} stepped in street waste and recoiled in disgust.",
                    target_ids=[agent.id],
                    position=agent.position,
                    payload={"object_id": item.id},
                    radius=75,
                )

    def _update_city_services(self) -> None:
        to_remove: list[str] = []
        for item in self.objects.values():
            if item.kind != "waste" or "reported_at" not in item.metadata:
                continue
            if self.time - float(item.metadata["reported_at"]) >= 14:
                to_remove.append(item.id)
        for item_id in to_remove:
            item = self.objects.pop(item_id)
            self.emit(
                "cleanup",
                "Street Services cleaned a reported sanitation hazard.",
                position=item.position,
                radius=100,
            )

    def _maybe_city_event(self) -> None:
        if self.scenario == "sf":
            # Prototype shocks are scripted fiction, not calibrated SF event rates.
            return
        if self.time < self.next_city_event:
            return
        self.next_city_event = self.time + self.random.uniform(38, 62)
        event = self.random.choice(["fog", "layoffs", "street_fair", "rent_news"])
        if event == "fog":
            self.weather = "fog" if self.weather != "fog" else "clear"
            message = (
                "Dense fog rolled through the city, narrowing everyone's view."
                if self.weather == "fog"
                else "The fog lifted and the city became visible again."
            )
            self.emit("weather", message, position=Vec2(x=700, y=400), radius=1600)
        elif event == "layoffs":
            affected = [
                a
                for a in self.agents.values()
                if a.workplace_id and self.objects[a.workplace_id].kind == "tech"
            ]
            if affected:
                agent = self.random.choice(affected)
                agent.workplace_id = None
                agent.stress = min(100, agent.stress + 24)
                self.emit(
                    "job_loss",
                    f"{agent.name} was laid off by Astra Systems.",
                    actor_id=agent.id,
                    position=agent.position,
                    radius=120,
                )
        elif event == "street_fair":
            self.emit(
                "broadcast",
                "Mission Glow will hold a night market. "
                "Neighbors are invited to bring food and stories.",
                position=Vec2(x=1080, y=475),
                payload={"station": "KTHR Public Radio"},
                radius=1600,
                broadcast=True,
            )
        else:
            self.emit(
                "broadcast",
                "Landlords across Circuit Hill are discussing another rent increase.",
                position=Vec2(x=1080, y=475),
                payload={"station": "KTHR Public Radio"},
                radius=1600,
                broadcast=True,
            )

    def context_for(self, agent: AgentState) -> dict[str, Any]:
        from app.life import life_context, select_memory_context
        from app.routines import schedule_context

        sight = 0.58 if self.weather == "fog" else 1.0
        self.lifecycle.observe_remains(agent, sight)
        nearby_objects = []
        for item in self.objects.values():
            distance = self._distance_agent_object(agent, item)
            if distance <= 380 * sight:
                nearby_objects.append(
                    {
                        **self.urban.describe(item),
                        "distance": round(distance, 1),
                    }
                )
        nearby_objects.sort(key=lambda item: item["distance"])
        for item in nearby_objects:
            if item["kind"] not in {"food", "waste", "coat", "route_guide", "material"}:
                agent.known_places[item["id"]] = item.copy()
        nearby_agents = []
        for other in self.agents.values():
            if other.id == agent.id or not other.alive:
                continue
            distance = self._distance_agents(agent, other)
            if distance <= 230 * sight:
                nearby_agents.append(
                    {
                        "id": other.id,
                        "name": other.name,
                        "position": other.position.model_dump(),
                        "health": round(other.health, 1),
                        "distance": round(distance, 1),
                        "visible_action": other.current_action,
                        "visible_speech": other.speech,
                    }
                )
        nearby_agents.sort(key=lambda item: item["distance"])
        workplace = self.objects.get(agent.workplace_id or "")
        return {
            "world_time": round(self.time, 1),
            "scenario": self.scenario,
            "personal_background": agent.background.model_dump() if agent.background else None,
            "time_of_day": self.time_of_day,
            "personal_schedule": schedule_context(self, agent),
            "weather": self.weather,
            "terrain": {
                "cell_size": 20,
                "nearby_tiles": self.terrain.observe(agent, 380 * sight),
                "building_costs": BUILD_COSTS,
                "nearby_buildable_tiles": self.terrain.build_sites(agent),
                "civic": self.terrain.civic_for(agent),
            },
            "nearby_objects": nearby_objects[:24],
            "nearby_agents": nearby_agents[:12],
            **select_memory_context(agent),
            "life": life_context(agent),
            "personal_economy": self.sf_economy.context_for(agent)
            if getattr(self, "sf_economy", None)
            else None,
            "new_events": [
                memory.model_dump(mode="json")
                for memory in agent.memories
                if memory.id in agent.inbox
            ][-40:],
            "position": agent.position.model_dump(),
            "inventory": [self.urban.carried[key].model_dump() for key in agent.inventory],
            "economy": self.economy.context_for(agent),
            "housing": {"home_id": agent.home_id, "rent_warning": agent.rent_arrears > 0},
            "known_places": list(agent.known_places.values()),
            "last_action_result": agent.last_action_result,
            "known_workplace": workplace.position.model_dump() if workplace else None,
            "current_workplace": (
                {"id": workplace.id, "name": workplace.name} if workplace else None
            ),
            "legal_actions": [item.value for item in ActionType],
            "action_help": {
                "disaster_response": (
                    "Earthquakes interrupt activities. Choose your own response using local "
                    "observations: MOVE to an observed safe place, HELP an injured neighbor, "
                    "REST at an open clinic, REPAIR a damaged facility, TALK/SHOUT to coordinate, "
                    "or resume your own project. REPAIR takes 12 seconds and restores 30 points "
                    "of structural integrity; collapsed buildings need repeated work. Services "
                    "reopen only at 100. This simplified repair uses no materials. Dead citizens "
                    "cannot be revived. You do not know remote damage until told or observed."
                ),
                "civic_talk": (
                    "To record civic consent/petition/endorsement/dispute, choose talk with "
                    "terms.civic_action grant_consent/petition/endorse/dispute, destination at an "
                    "observed tile, target_id null, message explaining the request, and "
                    "terms.grantee_id for owner consent. Public tile removal needs the local "
                    "scenario quorum; a dispute alone grants no permission. This is an explicit "
                    "recording action, not arbitrary conversation text changing permissions."
                ),
                "sf_livelihood": (
                    "REST at a known clinic consumes care supply and provides medical help. "
                    "Assigned baseline jobs pay for at most two completed shifts per budget day. "
                    "Read personal_economy for your rent, remaining shifts, benefits and budget."
                ),
                "address_player": (
                    "message required; speak toward whoever may be outside this world. "
                    "The observer receives it; nearby citizens can hear it, distant ones cannot. "
                    "No reply, obedience or effect on reality is guaranteed."
                ),
                "move": "destination required; walk to a position you choose.",
                "talk": (
                    "target_id and message required; approach then speak. "
                    "Use reply_to for the memory ID you answer."
                ),
                "shout": "message required; everyone in earshot may hear it.",
                "broadcast": "message required; approach a radio and transmit within coverage.",
                "eat": "target food on the ground or in your bag; food lowers hunger by 48.",
                "take": "target portable food, a coat or route app; bag capacity is 8.",
                "give": "target a known person; terms.item_id selects a carried item to give.",
                "drop": "target a carried item to leave it at your position.",
                "work": (
                    "target a workplace for a 14-second paid shift, or your company to produce "
                    "stock. Employees need an accepted job offer. "
                    "Company treasury pays materials and wages."
                ),
                "rest": "rest outdoors for 12 seconds; lower recovery than a bed.",
                "use_toilet": "target a visible restroom or your own home; approach and use it.",
                "seek_shelter": "approach your home or a known shelter and rest.",
                "help": "approach a known injured person and give first aid.",
                "attack": "approach a known person and hurt them; causes injury and social harm.",
                "report": "target visible street waste to request cleanup.",
                "wait": "observe briefly; no forced speech.",
                "buy": (
                    "target a shop, company or dining room. Receive one item in your bag; "
                    "eat or use it separately. Dining meals are free during opening hours; "
                    "stock is finite."
                ),
                "cook": "at a kitchen or home, turn 2 carried foods into 3 meals in 10 seconds.",
                "clean": "target waste, a toilet or kitchen; 9 seconds removes waste or dirt.",
                "rent_home": "target a vacant home bed; pay first-day rent. Residents share rent.",
                "offer_housing": "target a citizen to invite them to share your home and rent.",
                "found_company": (
                    "target a launchpad, kitchen, market, cafe or tech building. terms: name, "
                    "purpose, product (meals/coats/routes), amount (at least 2 seed credits), "
                    "price. You own the initial shares; one company per founder. "
                    "Founding alone creates no revenue."
                ),
                "offer_investment": (
                    "target another citizen; terms.company_id, amount and equity "
                    "(post-money fraction, e.g. 0.2). One party must be the founder. "
                    "Both founder pitches and investor counteroffers are supported. "
                    "No money moves until the recipient accepts."
                ),
                "offer_job": (
                    "founder targets a citizen; terms.company_id and wage per completed batch. "
                    "Recipient must accept before working. Wages require available company funds."
                ),
                "accept_offer": (
                    "target an offer ID from economy.my_offers addressed to you; "
                    "approach proposer and accept exact terms. Review costs and dilution."
                ),
                "reject_offer": "target an offer addressed to you; decline or propose new terms.",
                "use_item": "target a coat for warmth or route app for faster travel for one day.",
                "pay_dividend": (
                    "founder targets own company; terms.amount is a total cash distribution "
                    "from treasury, divided by share ownership. Preserve operating funds."
                ),
                "set_price": "founder targets own company; terms.price sets the unit sale price.",
                "salvage": "target reuse depot; spend 6 seconds collecting one building material.",
                "build": (
                    "destination is the center of a previously seen 20x20 tile; terms.tile selects "
                    "road/wall/floor/garden/bench/sign/kitchen/toilet/shelter. Costs reclaimed "
                    "materials in your bag (see terrain.building_costs). Empty ground required. "
                    "Roads speed travel; walls block routes; facilities are usable. "
                    "For signs, message is the sign text. Lay several tiles over multiple turns."
                ),
                "demolish": (
                    "destination identifies a tile; remove its road, wall or citizen-built "
                    "facility and reclaim one material. Occupied facilities cannot be removed."
                ),
            },
        }

    def apply_decision(self, agent_id: str, decision: AgentDecision) -> None:
        agent = self.agents.get(agent_id)
        if not agent or not agent.alive:
            return
        intent = decision.intent
        if agent.activity:
            return
        context = self.context_for(agent)
        known_ids = {item["id"] for item in context["nearby_objects"]}
        known_ids.update(item["id"] for item in context["nearby_agents"])
        known_ids.update(agent.known_places)
        known_ids.update(m.source_id for m in agent.memories if m.source_id)
        known_ids.update(agent.inventory)
        known_ids.update([agent.home_id, agent.workplace_id])
        known_ids.update(o["id"] for o in context["economy"]["my_offers"])
        known_ids.update(o["subject_id"] for o in context["economy"]["my_offers"])
        known_ids.update(c["id"] for c in context["economy"]["my_businesses"])
        if intent.target_id and intent.target_id not in known_ids:
            self._fail_action(agent, intent, "That target is not known from your own experience.")
            return
        if intent.terms and intent.terms.company_id and intent.terms.company_id not in known_ids:
            self._fail_action(agent, intent, "That company is not known from your own experience.")
            return
        if intent.terms and intent.terms.grantee_id and intent.terms.grantee_id not in known_ids:
            self._fail_action(agent, intent, "That citizen is not known from your experience.")
            return
        from app.life import apply_life_update

        try:
            for memory in apply_life_update(agent, decision.life_update, self.time):
                self.store.append_memory(agent.id, memory)
        except ValueError:
            self.emit(
                "life_update_rejected",
                "My plan update was rejected: use valid personal memory and project IDs.",
                actor_id=agent.id,
                position=agent.position,
                radius=0,
                payload={"private": True},
            )
        if intent.goal and (
            not agent.active_goal or intent.goal.statement != agent.active_goal.statement
        ):
            agent.active_goal = intent.goal
        agent.last_decision_source = decision.source
        agent.decision_count += 1
        agent.action_target = None
        agent.pending_intent = None
        agent.route.clear()
        agent.route_goal = None
        agent.next_think_at = self.time + 5
        agent.thought = intent.public_reason[:140] or "I am deciding what matters next."
        for value in decision.expressed_values:
            value = value.strip()[:40]
            if value and value not in agent.values:
                agent.values.append(value)
        agent.values = agent.values[-6:]
        for other_id, change in decision.relationship_updates.items():
            if other_id in known_ids and other_id in self.agents and other_id != agent.id:
                current = agent.relationships.get(other_id, 0.0)
                agent.relationships[other_id] = max(-1.0, min(1.0, current + change))
        accepted = self._execute(agent, intent)
        if not accepted:
            self._fail_action(
                agent, intent, "Target missing, inaccessible, or action prerequisites not met."
            )
        elif agent.current_action != "replanning":
            agent.last_action_result = f"Accepted {intent.action.value}: {agent.current_action}."

    def _fail_action(self, agent: AgentState, intent: ActionIntent, reason: str) -> None:
        agent.action_target = None
        agent.pending_intent = None
        agent.current_action = "replanning"
        agent.next_think_at = self.time + 1
        agent.last_action_result = f"Failed {intent.action.value}: {reason}"
        self.emit(
            "action_failed",
            f"{agent.name}: {agent.last_action_result}",
            actor_id=agent.id,
            position=agent.position,
            radius=0,
        )

    def _approach(
        self, agent: AgentState, intent: ActionIntent, target: Any, radius: float
    ) -> bool:
        entrance = getattr(target, "metadata", {}).get("entrance")
        destination = Vec2(**entrance) if entrance else target.position
        if self._distance_to_position(agent, destination) <= radius and self.terrain.line_clear(
            agent.position,
            destination,
            intent.action in {ActionType.BUILD, ActionType.DEMOLISH},
        ):
            return False
        agent.pending_intent = intent.model_copy(deep=True)
        agent.pending_intent.target_id = target.id
        agent.action_target = destination.model_copy()
        agent.action_started_at = self.time
        agent.current_action = f"going to {target.name} to {intent.action.value}"
        return True

    def _execute(self, agent: AgentState, intent: ActionIntent) -> bool:
        terrain_result = self.terrain.execute(agent, intent)
        if terrain_result is not None:
            return terrain_result
        economic_result = self.economy.execute(agent, intent)
        if economic_result is not None:
            return economic_result
        urban_result = self.urban.execute(agent, intent)
        if urban_result is not None:
            return urban_result
        action = intent.action
        if action == ActionType.MOVE:
            if intent.destination is None:
                return False
            agent.action_target = self._clamp(intent.destination)
            agent.action_started_at = self.time
            agent.current_action = "walking"
            return True
        if action == ActionType.WAIT:
            agent.current_action = "observing"
            agent.next_think_at = self.time + 6
            return True
        if action == ActionType.ADDRESS_PLAYER:
            message = (intent.message or "").strip()[:180]
            if not message:
                return False
            agent.current_action = "addressing the sky"
            agent.speech = message
            agent.speech_until = self.time + 10
            event = self.emit(
                "address_player",
                f'{agent.name} addressed the sky: "{message}"',
                actor_id=agent.id,
                position=agent.position,
                radius=115,
                payload={"message": message, "reply_to": intent.reply_to},
            )
            self.player_messages.append(event.model_dump(mode="json"))
            agent.next_think_at = self.time + 10
            return True
        if action in {ActionType.TALK, ActionType.SHOUT, ActionType.BROADCAST}:
            return self._execute_communication(agent, intent)
        if action == ActionType.REPORT:
            item = self.objects.get(intent.target_id or "")
            if not item or item.kind != "waste":
                return False
            item.metadata.setdefault("reported_at", self.time)
            self.emit(
                "service_report",
                f"{agent.name} filed a sanitation service request.",
                actor_id=agent.id,
                position=agent.position,
                radius=90,
            )
            agent.next_think_at = self.time + 8
            return True
        if action == ActionType.HELP:
            target = self.agents.get(intent.target_id or "")
            if not target or not target.alive:
                return False
            if self._approach(agent, intent, target, 48):
                return True
            target.health = min(100, target.health + 12)
            target.stress = max(0, target.stress - 7)
            self.emit(
                "help",
                f"{agent.name} stopped to help {target.name}.",
                actor_id=agent.id,
                target_ids=[target.id],
                position=agent.position,
                radius=110,
            )
            return True
        if action == ActionType.ATTACK:
            target = self.agents.get(intent.target_id or "")
            if not target or not target.alive:
                return False
            if self._approach(agent, intent, target, 42):
                return True
            damage = 8 + 12 * agent.traits.get("aggression", 0.2)
            target.health = max(0, target.health - damage)
            target.stress = min(100, target.stress + 35)
            agent.stress = min(100, agent.stress + 12)
            event = self.emit(
                "attack",
                f"{agent.name} attacked {target.name}. Nearby citizens may respond.",
                actor_id=agent.id,
                target_ids=[target.id],
                position=agent.position,
                radius=180,
            )
            if target.health <= 0:
                self.lifecycle.kill(
                    target, "attack", f"{target.name} died after {agent.name}'s attack.", event.id
                )
            return True
        return False

    def _execute_communication(self, agent: AgentState, intent: ActionIntent) -> bool:
        message = (intent.message or "").strip()[:180]
        if not message:
            return False
        if intent.action == ActionType.BROADCAST:
            station = self._nearest_object(agent, {"radio"})
            if not station:
                return False
            if self._approach(agent, intent, station, 60):
                return True
            agent.speech = message
            agent.speech_until = self.time + 10
            self.emit(
                "broadcast",
                message,
                actor_id=agent.id,
                position=station.position,
                payload={
                    "station": f"{station.name}, voiced by {agent.name}",
                    "message": message,
                    "reply_to": intent.reply_to,
                },
                radius=float(station.metadata.get("coverage_radius", 950)),
                broadcast=True,
            )
            agent.next_think_at = self.time + 10
            return True
        targets = []
        radius = 260 if intent.action == ActionType.SHOUT else 115
        if intent.action == ActionType.TALK:
            target = self.agents.get(intent.target_id or "")
            if not target or not target.alive or target.id == agent.id:
                return False
            if self._approach(agent, intent, target, radius):
                return True
            targets = [target.id]
            agent.current_action = f"talking to {target.name}"
        else:
            agent.current_action = "shouting"
        agent.speech = message
        agent.speech_until = self.time + 9
        verb = "shouted" if intent.action == ActionType.SHOUT else "said"
        self.emit(
            "shout" if intent.action == ActionType.SHOUT else "speech",
            f'{agent.name} {verb}: "{message}"',
            actor_id=agent.id,
            target_ids=targets,
            position=agent.position,
            radius=radius,
            payload={"message": message, "reply_to": intent.reply_to},
        )
        agent.next_think_at = self.time + 9
        return True

    def intervene(
        self,
        intervention_type: str,
        position: Vec2 | None,
        message: str | None,
        tile: str | None = None,
        target_id: str | None = None,
    ) -> dict:
        before = self.event_counter
        killed = []
        injured = []
        if position:
            position = self._clamp(position)
        if intervention_type == "build" and position:
            self.terrain.edit(self.terrain.cell(position), tile, None, message)
        elif intervention_type == "food" and position:
            for _ in range(5):
                self._add_object(
                    "food",
                    "Sky Apple",
                    position.x + self.random.uniform(-28, 28),
                    position.y + self.random.uniform(-28, 28),
                    18,
                    18,
                )
            self.emit(
                "player_gift",
                "Five apples appeared from beyond the sky.",
                position=position,
                radius=180,
            )
        elif intervention_type == "earthquake" and position:
            from app.disasters import earthquake

            injured, killed = earthquake(self, position)
        elif intervention_type == "waste" and position:
            self._add_object(
                "waste",
                "Street Waste",
                position.x,
                position.y,
                16,
                13,
                metadata={"created_at": self.time},
            )
            self.emit(
                "waste", "Street waste appeared on the pavement.", position=position, radius=75
            )
        elif intervention_type == "lightning" and position:
            event = self.emit(
                "lightning",
                "A bolt of lightning struck from the sky without warning.",
                position=position,
                radius=230,
            )
            for agent in self.agents.values():
                if not agent.alive:
                    continue
                distance = self._distance_to_position(agent, position)
                if distance > 70:
                    continue
                agent.health = max(0, agent.health - (100 if distance <= 24 else 35))
                agent.stress = min(100, agent.stress + 38)
                if agent.health <= 0:
                    self.lifecycle.kill(
                        agent,
                        "lightning",
                        f"{agent.name} was killed by the lightning strike.",
                        event.id,
                    )
                    killed.append(agent.id)
                else:
                    injured.append(agent.id)
        elif intervention_type == "kill":
            agent = self.agents.get(target_id or "")
            if not agent or not agent.alive:
                raise ValueError("Choose a living citizen to kill.")
            self.lifecycle.kill(
                agent,
                "player_kill",
                f"A narrow beam descended from the sky and killed {agent.name}.",
            )
            killed.append(agent.id)
        elif intervention_type == "toilet" and position:
            item = self._add_object("toilet", "Portable Restroom", position.x, position.y, 48, 54)
            self.emit(
                "player_build",
                "A public restroom appeared from beyond the sky.",
                position=item.position,
                radius=160,
            )
        elif intervention_type == "broadcast":
            self.emit(
                "broadcast",
                (message or "The observer is watching.")[:180],
                position=Vec2(x=1080, y=475),
                payload={"station": "an unknown signal"},
                radius=1600,
                broadcast=True,
            )
        elif intervention_type == "fog":
            self.weather = "fog" if self.weather != "fog" else "clear"
            text = (
                "A dense artificial fog covered the city."
                if self.weather == "fog"
                else "The artificial fog vanished."
            )
            self.emit("weather", text, position=Vec2(x=700, y=400), radius=1600)
        else:
            raise ValueError("Unknown intervention or missing position.")
        events = [e for e in self.events if int(e.id.rsplit("_", 1)[1]) > before]
        receipt = {
            "accepted": True,
            "event_id": events[0].id,
            "event_ids": [e.id for e in events],
            "delivered_to": sorted({a for e in events for a in e.payload.get("delivered_to", [])}),
            "killed": killed,
            "injured": injured,
            "paused": self.paused,
        }
        self.interventions.append(
            {
                **receipt,
                "type": intervention_type,
                "world_time": self.time,
                "followups": [],
            }
        )
        return receipt

    def record_followup(self, agent: AgentState, decision: AgentDecision, consumed: set[str]):
        """Observer-only timing evidence. A subsequent decision is not proof of causation."""
        memories = {m.id: m.original_event_id for m in agent.memories}
        read_events = {memories[key] for key in consumed if key in memories}
        for intervention in self.interventions:
            if read_events.intersection(intervention["event_ids"]):
                intervention["followups"].append(
                    {
                        "agent_id": agent.id,
                        "world_time": self.time,
                        "action": decision.intent.action.value,
                        "source": decision.source,
                        "reply_to_event_id": memories.get(decision.intent.reply_to),
                        "result": agent.last_action_result,
                    }
                )

    @property
    def time_of_day(self) -> str:
        hour = int(self.urban.hour)
        minute = int((self.urban.hour - hour) * 60)
        return f"{hour:02d}:{minute:02d}"

    def snapshot(self, brain_mode: str, last_error: str | None = None) -> dict[str, Any]:
        living = sum(1 for agent in self.agents.values() if agent.alive)
        unhoused = sum(1 for agent in self.agents.values() if agent.alive and agent.home_id is None)
        return {
            "world": {
                "experiment_id": self.run_id,
                "width": WORLD_WIDTH,
                "height": WORLD_HEIGHT,
                "time": round(self.time, 1),
                "time_of_day": self.time_of_day,
                "day_length": self.day_length,
                "weather": self.weather,
                "paused": self.paused,
                "speed": self.speed,
                "districts": self.districts,
                "scenario": self.scenario,
            },
            "stats": {
                "population": living,
                "unhoused": unhoused,
                "waste": sum(1 for item in self.objects.values() if item.kind == "waste"),
                "events": self.event_counter,
                "companies": len(self.economy.companies),
                "capital_raised": round(sum(c.raised for c in self.economy.companies.values()), 2),
                "brain_mode": brain_mode,
                "brain_error": last_error,
                "llm_decisions": sum(
                    a.decision_count
                    for a in self.agents.values()
                    if a.last_decision_source in {"astra", "novita"}
                ),
                "astra_decisions": sum(
                    a.decision_count
                    for a in self.agents.values()
                    if a.last_decision_source == "astra"
                ),
            },
            "agents": [self._public_agent(agent) for agent in self.agents.values()],
            "objects": [
                {**item.model_dump(mode="json"), **self.urban.describe(item)}
                for item in self.objects.values()
            ],
            "economy": {
                "companies": [c.model_dump() for c in self.economy.companies.values()],
                "offers": [o.model_dump() for o in self.economy.offers.values()],
                "city_balance": round(self.economy.city_balance, 2),
            },
            "terrain": self.terrain.snapshot(),
            "population": self.population_report,
            "calibration": self.sf_economy.report() if getattr(self, "sf_economy", None) else None,
            "employers": [
                {
                    **employer,
                    "simulated_workers": sum(
                        a.alive and a.workplace_id == employer.get("object_id")
                        for a in self.agents.values()
                    ),
                }
                for employer in self.employer_catalog
            ],
            "interventions": list(self.interventions),
            "player_messages": list(self.player_messages),
            "events": [event.model_dump(mode="json") for event in list(self.events)[-35:]],
        }

    def agent_detail(self, agent_id: str) -> dict[str, Any] | None:
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        detail = agent.model_dump(mode="json", exclude={"memories"})
        detail["inventory_items"] = [
            self.urban.carried[key].model_dump() for key in agent.inventory
        ]
        detail["economy"] = self.economy.context_for(agent)
        detail["personal_economy"] = (
            self.sf_economy.context_for(agent) if getattr(self, "sf_economy", None) else None
        )
        from app.life import life_context

        detail["life"] = life_context(agent)
        detail["memory_total"] = len(agent.memories)
        detail["memories"] = [memory.model_dump(mode="json") for memory in agent.memories[-80:]]
        detail["home"] = self.objects[agent.home_id].name if agent.home_id in self.objects else None
        detail["workplace"] = (
            self.objects[agent.workplace_id].name if agent.workplace_id in self.objects else None
        )
        detail["relationships"] = [
            {
                "id": other_id,
                "name": self.agents[other_id].name,
                "value": round(value, 2),
            }
            for other_id, value in agent.relationships.items()
            if other_id in self.agents
        ]
        return detail

    def _public_agent(self, agent: AgentState) -> dict[str, Any]:
        return {
            "id": agent.id,
            "name": agent.name,
            "position": agent.position.model_dump(),
            "health": round(agent.health, 1),
            "current_action": agent.current_action,
            "speech": agent.speech,
            "is_thinking": agent.is_thinking,
            "alive": agent.alive,
            "death_cause": agent.death_cause if not agent.alive else None,
            "has_home": agent.home_id is not None,
            "reaction": agent.last_reaction if agent.reaction_until > self.time else "",
            "decision_source": agent.last_decision_source,
            "decision_count": agent.decision_count,
        }

    def _nearest_object(self, agent: AgentState, kinds: set[str]) -> WorldObject | None:
        matches = [item for item in self.objects.values() if item.kind in kinds]
        return min(matches, key=lambda item: self._distance_agent_object(agent, item), default=None)

    @staticmethod
    def _distance_agents(first: AgentState, second: AgentState) -> float:
        return distance_between(
            first.position.x,
            first.position.y,
            second.position.x,
            second.position.y,
        )

    @staticmethod
    def _distance_agent_object(agent: AgentState, item: WorldObject) -> float:
        return distance_between(
            agent.position.x, agent.position.y, item.position.x, item.position.y
        )

    @staticmethod
    def _distance_to_position(agent: AgentState, position: Vec2) -> float:
        return distance_between(agent.position.x, agent.position.y, position.x, position.y)

    @staticmethod
    def _clamp(position: Vec2) -> Vec2:
        return Vec2(
            x=max(35, min(WORLD_WIDTH - 35, position.x)),
            y=max(45, min(WORLD_HEIGHT - 35, position.y)),
        )
