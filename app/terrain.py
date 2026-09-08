"""Editable tile world. Path planning uses personal maps; collisions use physical truth."""

from __future__ import annotations

import heapq
import math
from typing import TYPE_CHECKING

from app.models import ActionIntent, ActionType, AgentState, Vec2, WorldObject

if TYPE_CHECKING:
    from app.world import World


CELL = 20
COLS, ROWS = 70, 41
BUILD_COSTS = {
    "road": 1,
    "wall": 1,
    "floor": 1,
    "garden": 2,
    "bench": 1,
    "sign": 1,
    "kitchen": 4,
    "toilet": 3,
    "shelter": 4,
}


class Terrain:
    def __init__(self, world: World):
        self.world = world
        self.tiles: dict[str, dict] = {}
        self.revision = 0
        for x in range(COLS):
            self.tiles[f"{x},19"] = {"kind": "road", "builder_id": None}
        for y in range(ROWS):
            for x in (23, 38):
                self.tiles[f"{x},{y}"] = {"kind": "road", "builder_id": None}

    @staticmethod
    def cell(position: Vec2) -> tuple[int, int]:
        return int(position.x // CELL), int(position.y // CELL)

    @staticmethod
    def key(cell: tuple[int, int]) -> str:
        return f"{cell[0]},{cell[1]}"

    @staticmethod
    def center(cell: tuple[int, int]) -> Vec2:
        return Vec2(x=cell[0] * CELL + CELL / 2, y=cell[1] * CELL + CELL / 2)

    @staticmethod
    def valid(cell: tuple[int, int]) -> bool:
        return 0 <= cell[0] < COLS and 0 <= cell[1] < ROWS

    def blocked(self, position: Vec2) -> bool:
        cell = self.cell(position)
        return not self.valid(cell) or self.tiles.get(self.key(cell), {}).get("kind") == "wall"

    def speed_at(self, position: Vec2) -> float:
        return 1.6 if self.tiles.get(self.key(self.cell(position)), {}).get("kind") == "road" else 1

    def line_clear(
        self, start: Vec2, end: Vec2, ignore_end: bool = False, known: dict[str, str] | None = None
    ) -> bool:
        steps = max(1, math.ceil(math.hypot(end.x - start.x, end.y - start.y) / 4))
        for step in range(1, steps + 1):
            point = Vec2(
                x=start.x + (end.x - start.x) * step / steps,
                y=start.y + (end.y - start.y) * step / steps,
            )
            if ignore_end and self.cell(point) == self.cell(end):
                continue
            blocked = (
                known.get(self.key(self.cell(point))) == "wall"
                if known is not None
                else self.blocked(point)
            )
            if blocked:
                return False
        return True

    def observe(self, agent: AgentState, radius: float) -> list[dict]:
        cx, cy = self.cell(agent.position)
        reach = math.ceil(radius / CELL)
        observed = []
        for x in range(max(0, cx - reach), min(COLS, cx + reach + 1)):
            for y in range(max(0, cy - reach), min(ROWS, cy + reach + 1)):
                position = self.center((x, y))
                if (
                    math.hypot(position.x - agent.position.x, position.y - agent.position.y)
                    > radius
                ):
                    continue
                key = self.key((x, y))
                tile = self.tiles.get(key, {"kind": "grass"})
                kind = tile["kind"]
                if agent.known_terrain.get(key, "grass") != kind:
                    agent.route.clear()
                    agent.route_goal = None
                agent.known_terrain[key] = kind
                if kind == "sign" and agent.known_signs.get(key) != tile.get("message", ""):
                    agent.known_signs[key] = tile.get("message", "")
                    self.world.emit(
                        "read_sign",
                        f"{agent.name} read a sign: {tile.get('message', '')}",
                        actor_id=agent.id,
                        position=position,
                        radius=0,
                        payload={"message": tile.get("message", ""), "private": True},
                    )
                if kind != "grass":
                    observed.append({"cell": [x, y], "position": position.model_dump(), **tile})
        return observed

    def resolve_target(self, target_id: str) -> WorldObject | None:
        if not target_id.startswith("tile:"):
            return None
        try:
            x, y = map(int, target_id[5:].split(","))
        except ValueError:
            return None
        if not self.valid((x, y)):
            return None
        return WorldObject(
            id=target_id, kind="tile", name=f"tile {x},{y}", position=self.center((x, y))
        )

    def build_sites(self, agent: AgentState) -> list[dict]:
        sites = []
        for key, kind in agent.known_terrain.items():
            if kind != "grass":
                continue
            cell = tuple(int(v) for v in key.split(","))
            position = self.center(cell)
            distance = math.hypot(position.x - agent.position.x, position.y - agent.position.y)
            if distance < 20 or distance > 160:
                continue
            if any(a.alive and self.cell(a.position) == cell for a in self.world.agents.values()):
                continue
            if any(
                o.kind not in {"food", "waste", "tree", "coat", "material", "route_guide"}
                and abs(o.position.x - position.x) < o.width / 2
                and abs(o.position.y - position.y) < o.height / 2
                for o in self.world.objects.values()
            ):
                continue
            sites.append(
                {
                    "cell": list(cell),
                    "position": position.model_dump(),
                    "distance": round(distance, 1),
                }
            )
        return sorted(sites, key=lambda site: site["distance"])[:16]

    def execute(self, agent: AgentState, intent: ActionIntent) -> bool | None:
        if intent.action not in {ActionType.BUILD, ActionType.DEMOLISH}:
            return None
        if not intent.destination:
            return self.world.urban.fail(agent, intent, "Choose a destination tile to edit.")
        cell = self.cell(intent.destination)
        if not self.valid(cell) or self.key(cell) not in agent.known_terrain:
            return self.world.urban.fail(agent, intent, "Explore that location before editing it.")
        target = self.resolve_target(f"tile:{self.key(cell)}")
        if self.world._approach(agent, intent, target, 35):
            return True
        kind = (
            "grass"
            if intent.action == ActionType.DEMOLISH
            else (intent.terms.tile if intent.terms else None)
        )
        try:
            self.edit(cell, kind, agent, intent.message)
        except ValueError as error:
            return self.world.urban.fail(agent, intent, str(error))
        agent.current_action = (
            f"{'removed' if kind == 'grass' else 'built'} {kind} at {cell[0]},{cell[1]}"
        )
        agent.next_think_at = self.world.time + 6
        return True

    def edit(
        self,
        cell: tuple[int, int],
        kind: str,
        builder: AgentState | None,
        message: str | None = None,
    ):
        if not self.valid(cell) or kind not in {*BUILD_COSTS, "grass"}:
            raise ValueError("Choose an in-bounds tile and a supported building material.")
        key = self.key(cell)
        old = self.tiles.get(key)
        if kind == "grass" and not old:
            raise ValueError("This tile is already empty ground.")
        if old and kind != "grass":
            raise ValueError("Demolish the existing tile before replacing it.")
        position = self.center(cell)
        if kind == "wall" and any(
            a.alive and self.cell(a.position) == cell for a in self.world.agents.values()
        ):
            raise ValueError("Cannot place a wall on a citizen. Stand on an adjacent tile.")
        # Existing facilities remain usable landmarks; new facilities are removable objects.
        if kind != "grass" and any(
            item.kind not in {"food", "waste", "tree", "coat", "material", "route_guide"}
            and abs(item.position.x - position.x) < item.width / 2
            and abs(item.position.y - position.y) < item.height / 2
            for item in self.world.objects.values()
        ):
            raise ValueError("This footprint is occupied; choose terrain.nearby_buildable_tiles.")
        old_object = self.world.objects.get(old.get("object_id", "")) if old else None
        if old_object and self.world.urban.occupants(old_object):
            raise ValueError("Wait until the facility is unoccupied before dismantling it.")
        materials = (
            []
            if not builder
            else [
                key for key in builder.inventory if self.world.urban.carried[key].kind == "material"
            ]
        )
        cost = BUILD_COSTS.get(kind, 0)
        if builder and len(materials) < cost:
            raise ValueError(f"Need {cost} reclaimed materials; salvage them at the reuse depot.")
        if builder:
            for item_id in materials[:cost]:
                builder.inventory.remove(item_id)
                self.world.urban.carried.pop(item_id)
        if kind == "grass":
            self.tiles.pop(key)
            if old_object:
                self.world.objects.pop(old_object.id)
                for citizen in self.world.agents.values():
                    if citizen.home_id == old_object.id:
                        citizen.home_id = None
            if builder:
                if len(builder.inventory) < 8:
                    self.world.urban.create_carried(builder, "material", "Reclaimed Material")
                else:
                    self.world._add_object(
                        "material", "Reclaimed Material", position.x, position.y, 18, 18
                    )
        else:
            tile = {
                "kind": kind,
                "builder_id": builder.id if builder else None,
                "message": (message or "")[:140],
            }
            self.tiles[key] = tile
            if kind in {"kitchen", "toilet", "shelter", "bench", "garden"}:
                item = self.world._add_object(
                    kind,
                    f"{builder.name if builder else 'Community'} {kind.title()}",
                    position.x,
                    position.y,
                    36,
                    30,
                    metadata={
                        "capacity": 2 if kind != "toilet" else 1,
                        "beds": 2,
                        "hours": [0, 24],
                        "condition": 100,
                        "builder_id": tile["builder_id"],
                    },
                )
                tile["object_id"] = item.id
        self.revision += 1
        if builder:
            self.observe(builder, 80)
        event = self.world.emit(
            "construction",
            f"{builder.name if builder else 'The observer'} "
            f"{'removed ' + old['kind'] if kind == 'grass' else 'built ' + kind} "
            f"at {cell[0]},{cell[1]}.",
            actor_id=builder.id if builder else None,
            position=position,
            radius=180,
            payload={"cell": list(cell), "kind": kind, "revision": self.revision},
        )
        return event

    def path(self, agent: AgentState, target: Vec2, arrival_range: float) -> list[Vec2] | None:
        start = self.cell(agent.position)
        goal = self.cell(target)
        if not self.valid(start) or not self.valid(goal):
            return None
        known = agent.known_terrain
        candidates = {goal}
        if arrival_range > 5:
            candidates = {
                (x, y)
                for x in range(goal[0] - 2, goal[0] + 3)
                for y in range(goal[1] - 2, goal[1] + 3)
                if self.valid((x, y))
                and math.hypot(self.center((x, y)).x - target.x, self.center((x, y)).y - target.y)
                <= arrival_range
            }
        candidates = {
            c
            for c in candidates
            if known.get(self.key(c)) != "wall"
            and self.line_clear(
                self.center(c), target, ignore_end=known.get(self.key(goal)) == "wall", known=known
            )
        }
        if not candidates:
            return None

        def heuristic(cell):
            return min(abs(cell[0] - c[0]) + abs(cell[1] - c[1]) for c in candidates) / 1.6

        queue = [(heuristic(start), 0.0, start)]
        costs, previous = {start: 0.0}, {}
        while queue:
            _, cost, cell = heapq.heappop(queue)
            if cost > costs.get(cell, float("inf")):
                continue
            if cell in candidates:
                route = []
                while cell != start:
                    route.append(self.center(cell))
                    cell = previous[cell]
                route.reverse()
                route.insert(0, self.center(start))
                if arrival_range <= 5:
                    route.append(target.model_copy())
                return route
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                neighbor = cell[0] + dx, cell[1] + dy
                kind = known.get(self.key(neighbor), "grass")
                if not self.valid(neighbor) or kind == "wall":
                    continue
                next_cost = cost + (1 / 1.6 if kind == "road" else 1)
                if next_cost < costs.get(neighbor, float("inf")):
                    costs[neighbor] = next_cost
                    previous[neighbor] = cell
                    heapq.heappush(queue, (next_cost + heuristic(neighbor), next_cost, neighbor))
        return None

    def snapshot(self) -> dict:
        return {
            "cell_size": CELL,
            "revision": self.revision,
            "tiles": [
                {"cell": [int(v) for v in key.split(",")], **tile}
                for key, tile in self.tiles.items()
            ],
        }
