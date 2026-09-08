"""Connect researched population inputs to source-grounded streets and synthetic sites."""

from __future__ import annotations

from collections import Counter
from random import Random
from typing import TYPE_CHECKING

from app.employers import employer_report, load_employers
from app.models import AgentBackground, AgentState, Memory, SourceType, Vec2
from app.population import generate_scenario_population
from app.sf_map import CELL, SFMap

if TYPE_CHECKING:
    from app.world import World


NEIGHBORHOOD_NAMES = {"mission": "Mission", "soma": "SoMa", "mission_bay": "Mission Bay"}
SECTOR_KINDS = {
    "technology": "tech",
    "professional_services": "workplace",
    "healthcare": "clinic",
    "education": "workplace",
    "food_service": "cafe",
    "retail": "market",
    "arts": "workplace",
    "public_service": "workplace",
}
def seed_sf_scenario(world: World, count: int, seed: int) -> None:
    """Weights describe sample coverage; physical agents never execute weighted actions."""
    population = generate_scenario_population(count, seed)
    profiles = [dict(profile) for profile in population["profiles"]]
    assignments = [profile["workplace_assignment"] for profile in profiles]
    if len(profiles) != count or len(assignments) != count:
        raise ValueError("Population and workplace allocation must match requested agent count")

    world.sf_map = SFMap()
    world.terrain.install_sf_map(world.sf_map)
    # Labels are approximate points. Do not invent rectangular official boundaries.
    world.districts = []
    homes: dict[str, list] = {key: [] for key in NEIGHBORHOOD_NAMES}
    # The original prototype seed has two housing clusters. Mission Bay needs
    # actual homes and services, not just a label or offices in the renderer.
    for index in range(4):
        world._add_object(
            "home", f"Mission Bay Sample Housing {index + 1}", 0, 0, 20, 20,
            metadata={"neighborhood": "mission_bay", "beds": 2, "rent": 0},
        )
    for kind, label, metadata in (
        ("market", "Market", {"stock": 12, "price": 3, "hours": [0, 24]}),
        ("dining", "Dining", {"stock": 12, "price": 0, "hours": [0, 24]}),
        ("toilet", "Restroom", {"capacity": 4, "condition": 1.0}),
    ):
        world._add_object(
            kind, f"Mission Bay Community {label}", 0, 0, 20, 20,
            metadata={"neighborhood": "mission_bay", **metadata},
        )
    for item in world.objects.values():
        neighborhood = item.metadata.get("neighborhood") or (
            "soma" if item.position.y < 400 else "mission"
        )
        world.sf_map.place(item, neighborhood)
        if item.kind not in {"food", "waste", "tree", "coat", "material", "route_guide"}:
            world.terrain.register_facility(item)
        else:
            item.position = Vec2(**item.metadata["entrance"])
        if item.kind == "home":
            homes[neighborhood].append(item)
            item.name = (
                f"{NEIGHBORHOOD_NAMES[neighborhood]} Sample Housing {len(homes[neighborhood])}"
            )
        if "wage" in item.metadata:
            # Existing generic facilities remain small open-shift opportunities, not fake firms.
            item.metadata["employment_basis"] = "scenario_open_shift"
            label = item.kind.replace("_", " ").title()
            item.name = f"{NEIGHBORHOOD_NAMES[neighborhood]} Community {label}"

    catalog = load_employers()
    entries = {entry["id"]: dict(entry, is_generic=False) for entry in catalog}
    for index, employer_id in enumerate(assignments):
        if employer_id is None or employer_id in entries:
            continue
        if not employer_id.startswith("sector_"):
            raise ValueError(f"Unknown employer allocation: {employer_id}")
        profile = profiles[index]
        sector = profile.get("occupation_sector") or "other"
        neighborhood = profile["neighborhood"]
        entries[employer_id] = {
            "id": employer_id,
            "name": (
                f"{NEIGHBORHOOD_NAMES[neighborhood]} {sector.replace('_', ' ').title()} Workplace"
            ),
            "neighborhood": neighborhood,
            "sector": sector,
            "is_generic": True,
            "local_headcount": None,
            "headcount_scope": "scenario_only",
            "headcount_year": None,
            "confidence": "scenario",
            "sources": [],
        }

    workplace_objects = {}
    for employer in entries.values():
        neighborhood = employer["neighborhood"]
        kind = SECTOR_KINDS.get(employer["sector"], "workplace")
        assigned_count = assignments.count(employer["id"])
        item = world._add_object(
            kind,
            employer["name"],
            0,
            0,
            20,
            20,
            metadata={
                "employer_id": employer["id"],
                "neighborhood": neighborhood,
                "sector": employer["sector"],
                "employment_basis": "assigned_only",
                "geography_status": "synthetic_street_adjacent",
                "address": employer.get("address"),
                "address_type": employer.get("address_type", "workplace_reference"),
                "wage": 4,
                "wage_basis": "scenario_credits_not_real_salary",
                "capacity": max(1, assigned_count),
                "hours": [0, 24],
                "stock": 12,
                "price": 3,
            },
        )
        world.sf_map.place(item, neighborhood)
        world.terrain.register_facility(item)
        workplace_objects[employer["id"]] = item
        employer["object_id"] = item.id
        employer.setdefault(
            "headcount_status",
            (
                "scenario"
                if employer["is_generic"]
                else "unknown"
                if employer.get("local_headcount") is None
                else "estimate"
                if employer.get("confidence") == "estimate"
                else "verified"
            ),
        )
        world.employer_catalog.append(employer)

    # Spawn independently of housing and traits. Reloads restore saved positions.
    spawn_random = Random(f"sf-street-spawn:{seed}")
    spawn_points = {}
    for neighborhood, local_count in Counter(p["neighborhood"] for p in profiles).items():
        candidates = [
            Vec2(x=x * CELL + CELL / 2, y=y * CELL + CELL / 2)
            for x, y in sorted(world.sf_map.road_cells)
            if world.sf_map.in_catchment((x, y), neighborhood)
            and not world.terrain.blocked(Vec2(x=x * CELL + CELL / 2, y=y * CELL + CELL / 2))
        ]
        spawn_random.shuffle(candidates)
        if len(candidates) < local_count:
            # Larger samples may share a road cell, never an exact spawn point.
            extra = [
                Vec2(x=p.x + dx, y=p.y + dy)
                for p in candidates
                for dx, dy in ((-5, -5), (-5, 5), (5, -5), (5, 5))
            ]
            spawn_random.shuffle(extra)
            candidates.extend(extra)
        if len(candidates) < local_count:
            raise ValueError(f"Not enough distinct walkable spawn points in {neighborhood}")
        spawn_points[neighborhood] = candidates[:local_count]

    home_occupancy: Counter = Counter()
    for index, profile in enumerate(profiles):
        neighborhood = profile["neighborhood"]
        local_homes = homes[neighborhood]
        housing_status = profile["housing_status"]
        home = None
        if housing_status not in {"unhoused", "unsheltered", "sheltered", "homeless"}:
            home = min(local_homes, key=lambda item: home_occupancy[item.id])
            home_occupancy[home.id] += 1
            home.metadata["beds"] = max(2, home_occupancy[home.id])
            home.metadata["capacity_basis"] = "sample_capacity_not_actual_housing_units"
        workplace = workplace_objects.get(assignments[index])
        biography = list(profile["background"])
        if workplace:
            biography.append(
                f"At the start of this run, my assigned workplace is {workplace.name}."
            )
        if home:
            biography.append(f"At the start of this run, I have a room at {home.name}.")
        background = AgentBackground(
            age=profile["age"],
            neighborhood=neighborhood,
            housing_status=housing_status,
            employment_status=profile["employment_status"],
            occupation_sector=profile.get("occupation_sector"),
            occupation_group=profile.get("occupation_group"),
            workplace_assignment_basis=(
                "2025 SF QCEW industry proxy; illustrative named site or generic residual; "
                "not an observed resident-to-employer link"
                if workplace
                else None
            ),
            biography=biography,
            employer_name=workplace.name if workplace else None,
            public_figure=(
                {
                    key: profile["public_figure"].get(key)
                    for key in ("id", "name", "age_basis", "age_estimated", "sources", "notice")
                }
                if profile.get("public_figure") else None
            ),
            person_reference=profile.get("person_reference"),
        )
        anchor = spawn_points[neighborhood].pop()
        agent = AgentState(
            id=f"yellow_{index + 1:02d}",
            name=profile["name"],
            position=anchor.model_copy(),
            background=background,
            home_id=home.id if home else None,
            workplace_id=workplace.id if workplace else None,
            credits=profile["economic_profile"]["initial_savings_credits"],
            traits={
                key: round(world.random.uniform(0.15, 0.85), 2)
                for key in ("curiosity", "empathy", "risk_tolerance", "aggression")
            },
            next_think_at=world.random.uniform(0.2, 4.5),
        )
        for place in (home, workplace):
            if place:
                agent.known_places[place.id] = world.urban.describe(place)
        world.agents[agent.id] = agent
        for memory_index, content in enumerate(biography):
            memory = Memory(
                id=f"{world.run_id}_{agent.id}_background_{memory_index}",
                world_time=0,
                content=content,
                source_type=(
                    SourceType.DOCUMENT
                    if content.startswith(("Public counterpart", "Public career fact")) or (
                        profile.get("public_figure") and (
                        content in profile["public_figure"]["biography"]
                        or content.startswith("Public history source:")
                        )
                    )
                    else SourceType.DIRECT_EXPERIENCE
                ),
                source_id=agent.id,
                event_type="personal_background",
                importance=0.8,
            )
            agent.memories.append(memory)
            world.store.append_memory(agent.id, memory)

    report = dict(population["report"])
    report["geography_details"] = report.get("geography")
    report.update(
        scenario="Mission + SoMa + Mission Bay adult resident scenario",
        agent_count=count,
        neighborhood_counts=dict(Counter(p["neighborhood"] for p in profiles)),
        seed=seed,
        geography="SF Analysis Neighborhoods: Mission, South of Market and Mission Bay",
        resident_population=report.get("all_residents_estimate"),
        adult_population=report.get("adult_residents_estimate"),
        source_year=report.get("vintage"),
        sources=[{"name": "DataSF ACS neighborhood population", "url": report["source_url"]}],
        employer_calibration=employer_report(),
    )
    labor = report.get("employment_calibration", {})
    employer_calibration = report["employer_calibration"]
    allocation_report = population["report"]["workplace_allocation"]
    employer_calibration["legacy_allocation"] = employer_calibration["allocation"]
    employer_calibration["allocation"] = allocation_report["policy"]
    report["employer_calibration"]["limitations"] = [
        note for note in report["employer_calibration"]["limitations"] if "25%" not in note
    ] + population["report"]["workplace_allocation"]["limitations"]
    report["sources"].append({
        "name": "BLS 2025 SF County QCEW industry jobs and establishments",
        "url": population["report"]["workplace_allocation"]["industry_source"]["source_url"],
    })
    if labor.get("source_url"):
        report["sources"].append(
            {
                "name": "SF Planning resident employment and occupation profile",
                "url": labor["source_url"],
            }
        )
    report["sampling_note"] = (
        "Adult-only synthetic sample; weights are descriptive, never multiplied physical actions. "
        "Small samples omit some demographic groups. Each citizen chooses their own goals."
    )
    report["limitations"] = list(report.get("limitations", [])) + [
        "This is a resident sample; inbound commuters are not yet simulated.",
        "Employer assignments are scenarios, not observed resident-to-employer links.",
        "Industry quotas use citywide workplace jobs as a resident proxy; the occupation-industry "
        "joint distribution and named-employer membership are scenario assumptions.",
        "The broader employer reference catalog may include offices outside the resident areas.",
        "Playable streets use official DataSF centerlines with an exaggerated east-west scale; "
        "buildings and entrances are synthetic street-adjacent sites, not actual parcels.",
        "Housing capacities, starting credits, wages and schedules are game assumptions.",
        "Public career counterparts are individually sourced; private histories and recent events "
        "are labeled fiction, not reconstructed facts about actual people.",
    ]
    world.population_report = report
