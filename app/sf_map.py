"""Offline official street geometry with explicitly synthetic playable building sites."""

from __future__ import annotations

import copy
import json
import math
from collections import deque
from pathlib import Path

from app.models import Vec2

MAP_PATH = Path(__file__).resolve().parents[1] / "data/sf_map.json"
CELL = 20


def _clip(a, b, bounds):
    """Liang-Barsky segment clipping; never clamp outside streets onto the border."""
    west, south, east, north = bounds
    dx, dy = b[0] - a[0], b[1] - a[1]
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, a[0] - west), (dx, east - a[0]), (-dy, a[1] - south), (dy, north - a[1])):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            lo = max(lo, q / p)
        else:
            hi = min(hi, q / p)
    if lo > hi:
        return None
    return [(a[0] + lo * dx, a[1] + lo * dy), (a[0] + hi * dx, a[1] + hi * dy)]


class SFMap:
    def __init__(self, path: Path = MAP_PATH):
        self.data = json.loads(path.read_text())
        self.bounds = self.data["bounds"]
        self.streets = []
        self.road_cells: dict[tuple[int, int], set[str]] = {}
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        for segment in self.data["segments"]:
            for index, (a, b) in enumerate(
                zip(segment["coordinates"], segment["coordinates"][1:], strict=False)
            ):
                clipped = _clip(a, b, self.bounds)
                if not clipped or clipped[0] == clipped[1]:
                    continue
                points = [self.project(*point) for point in clipped]
                self.streets.append({"name": segment["name"], "points": points})
                node_ids = []
                for coordinate, point in zip(clipped, points, strict=True):
                    node_id = f"{coordinate[0]:.7f},{coordinate[1]:.7f}"
                    node_ids.append(node_id)
                    self.nodes[node_id] = {"id": node_id, "position": point}
                self.edges.append(
                    {
                        "id": f"{segment['id']}:{index}",
                        "source_cnn": segment["id"].split(":")[0],
                        "name": segment["name"],
                        "nodes": node_ids,
                    }
                )
                self._raster(points, segment["name"])
        # Retain only the connected tile street network for playable entrances.
        remaining = set(self.road_cells)
        components = []
        while remaining:
            first = min(remaining)
            seen, queue = {first}, deque([first])
            while queue:
                cell = queue.popleft()
                for neighbor in self.neighbors(cell):
                    if neighbor in remaining and neighbor not in seen:
                        seen.add(neighbor)
                        queue.append(neighbor)
            remaining -= seen
            components.append(seen)
        largest = max(components, key=len)
        self.disconnected_road_cells = len(self.road_cells) - len(largest)
        self.road_cells = {cell: self.road_cells[cell] for cell in sorted(largest)}
        self._sites: dict[str, list[tuple[tuple[int, int], tuple[int, int]]]] = {}
        self._used: set[tuple[int, int]] = set()
        for neighborhood in ("soma", "mission", "mission_bay"):
            candidates = []
            for y in range(3, 38):
                for x in range(3, 67):
                    cell = (x, y)
                    local = self.in_catchment(cell, neighborhood)
                    entrances = [n for n in self.neighbors(cell) if n in self.road_cells]
                    if local and cell not in self.road_cells and entrances:
                        candidates.append((cell, min(entrances)))
            # Deterministic spatial scatter without touching the world's random state.
            candidates.sort(key=lambda site: (site[0][0] * 73856093) ^ (site[0][1] * 19349663))
            self._sites[neighborhood] = candidates

    def in_catchment(self, cell: tuple[int, int], neighborhood: str) -> bool:
        """Approximate gameplay catchments, not official neighborhood polygons."""
        lon, lat = self.unproject(cell[0] * CELL + CELL / 2, cell[1] * CELL + CELL / 2)
        return {
            "soma": lat >= 37.770 and -122.420 <= lon < -122.397,
            "mission": lat < 37.769 and lon < -122.407,
            "mission_bay": 37.764 <= lat < 37.776 and -122.397 <= lon < -122.384,
        }[neighborhood]

    @staticmethod
    def neighbors(cell):
        x, y = cell
        return ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))

    def project(self, lon: float, lat: float) -> dict:
        west, south, east, north = self.bounds
        return {
            "x": round(40 + (lon - west) / (east - west) * 1320, 3),
            "y": round(40 + (north - lat) / (north - south) * 740, 3),
        }

    def unproject(self, x: float, y: float) -> tuple[float, float]:
        west, south, east, north = self.bounds
        return west + (x - 40) / 1320 * (east - west), north - (y - 40) / 740 * (north - south)

    def _raster(self, points, name):
        a, b = points
        steps = max(1, math.ceil(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) / 3))
        previous = None
        for step in range(steps + 1):
            cell = (
                int((a["x"] + (b["x"] - a["x"]) * step / steps) // CELL),
                int((a["y"] + (b["y"] - a["y"]) * step / steps) // CELL),
            )
            self.road_cells.setdefault(cell, set()).add(name)
            if previous and previous[0] != cell[0] and previous[1] != cell[1]:
                self.road_cells.setdefault((cell[0], previous[1]), set()).add(name)
            previous = cell

    def place(self, item, neighborhood: str) -> None:
        """Allocate a one-cell synthetic facility with an adjacent public-road entrance."""
        candidates = self._sites[neighborhood]
        site = next(
            (
                s
                for s in candidates
                if s[0] not in self._used
                and all(abs(s[0][0] - c[0]) + abs(s[0][1] - c[1]) > 2 for c in self._used)
            ),
            None,
        )
        if site is None:
            site = next((s for s in candidates if s[0] not in self._used), None)
        if site is None:
            raise ValueError(f"No remaining synthetic building sites in {neighborhood}")
        cell, entrance = site
        self._used.add(cell)
        item.position = Vec2(x=cell[0] * CELL + 10, y=cell[1] * CELL + 10)
        item.width = item.height = CELL
        item.metadata.update(
            neighborhood=neighborhood,
            geography_status="synthetic_street_adjacent",
            footprint_cell=list(cell),
            entrance={"x": entrance[0] * CELL + 10, "y": entrance[1] * CELL + 10},
            street_names=sorted(self.road_cells[entrance]),
            coordinate_basis="Synthetic gameplay site; catalog address is not a geocode",
        )

    def snapshot(self) -> dict:
        # Graph topology is exposed separately to avoid shipping it on every frame.
        labels = []
        for name in sorted({street["name"] for street in self.streets}):
            segments = [s for s in self.streets if s["name"] == name]
            segment = max(
                segments,
                key=lambda s: math.dist(
                    tuple(s["points"][0].values()), tuple(s["points"][1].values())
                ),
            )
            a, b = segment["points"]
            angle = math.degrees(math.atan2(b["y"] - a["y"], b["x"] - a["x"]))
            if angle > 90:
                angle -= 180
            elif angle < -90:
                angle += 180
            labels.append(
                {
                    "text": name,
                    "x": (a["x"] + b["x"]) / 2,
                    "y": (a["y"] + b["y"]) / 2,
                    "angle": angle,
                }
            )
        return {
            "id": self.data["id"],
            "bounds": list(self.bounds),
            "source": copy.deepcopy(self.data["source"]),
            "projection": copy.deepcopy(self.data["projection"]),
            "limitations": list(self.data["limitations"]),
            "streets": copy.deepcopy(self.streets),
            "labels": labels,
            "landmarks": [
                {**row, "position": self.project(*row["coordinates"])}
                for row in self.data["landmarks"]
            ],
            "landmark_status": self.data["landmark_status"],
            "district_labels": [
                {"name": "SOMA", **self.project(-122.408, 37.781)},
                {"name": "MISSION", **self.project(-122.418, 37.760)},
                {"name": "MISSION BAY", **self.project(-122.389, 37.770)},
            ],
            "road_cell_count": len(self.road_cells),
            "road_cells": [list(cell) for cell in self.road_cells],
            "disconnected_road_cells_omitted": self.disconnected_road_cells,
        }

    def graph(self) -> dict:
        return {
            "nodes": copy.deepcopy(list(self.nodes.values())),
            "edges": copy.deepcopy(self.edges),
            "basis": "Clipped source centerline vertices, not a pedestrian accessibility claim",
        }
