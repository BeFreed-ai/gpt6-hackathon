"""Build an audited 100-adult artifact offline, using only a disposable in-memory world."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.population import generate_scenario_population  # noqa: E402
from app.store import EventStore  # noqa: E402
from app.world import World  # noqa: E402


def build_artifact(seed: int = 17) -> dict:
    """Never constructs a brain/service or opens a saved-world database."""
    population = generate_scenario_population(100, seed)
    profiles = population["profiles"]
    reference_ids = {p["person_reference"]["id"] for p in profiles}
    if len(reference_ids) != 100:
        raise ValueError("Exactly 100 distinct public counterparts are required")
    for profile in profiles:
        if not profile["person_reference"]["sources"]:
            raise ValueError(f"Missing counterpart source: {profile['synthetic_id']}")
        if len(profile["recent_experiences"]) != 3 or len(profile["life_story"].split()) < 300:
            raise ValueError(f"Incomplete private history: {profile['synthetic_id']}")
    store = EventStore(":memory:")
    try:
        world = World(store, agent_count=100, seed=seed, scenario="sf")
        world.paused = True
        agents = list(world.agents.values())
        if len(agents) != 100 or len({a.id for a in agents}) != 100:
            raise ValueError("Exactly 100 distinct runtime citizens are required")
        roster = []
        for profile, agent in zip(profiles, agents, strict=True):
            if world.terrain.blocked(agent.position):
                raise ValueError(f"Blocked initial position: {agent.id}")
            employed = agent.background.employment_status == "employed"
            if bool(agent.workplace_id) != employed:
                raise ValueError(f"Employment assignment mismatch: {agent.id}")
            workplace = world.objects.get(agent.workplace_id)
            if employed and workplace is None:
                raise ValueError(f"Unresolved workplace: {agent.id}")
            ledger = world.sf_economy.state["agents"][agent.id]
            household = world.sf_economy.state["households"].get(ledger["household_id"])
            roster.append(dict(
                profile,
                agent_id=agent.id,
                position=agent.position.model_dump(mode="json"),
                workplace_id=agent.workplace_id,
                home_id=agent.home_id,
                housing_status=agent.background.housing_status,
                background=agent.background.biography,
                starting_credits=agent.credits,
                economic_ledger=ledger,
                household=household,
                daily_rent_share_credits=world.sf_economy.rent_share(agent),
                initial_placement_valid=True,
            ))
        sources = [
            "data/sf_population.json", "data/sf_employers.json",
            "data/sf_economy.json", "data/sf_map.json",
            "data/public_figure_backgrounds.json",
            "data/sf_person_references.json",
        ]
        return {
            "schema_version": 1,
            "artifact_type": "offline synthetic roster audit; not a runtime checkpoint",
            "seed": seed,
            "count": 100,
            "source_sha256": {
                p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources
            },
            "report": world.population_report,
            "workplace_counts": population["report"]["workplace_allocation"]["workplace_counts"],
            "roster": roster,
        }
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--output", type=Path, default=ROOT / "data/sf_population_100.json")
    parser.add_argument(
        "--check", action="store_true", help="Compare with existing artifact without writing"
    )
    args = parser.parse_args()
    print(
        f"[1/3] Reading checked-in sources; seed={args.seed}; no network or model calls", flush=True
    )
    artifact = build_artifact(args.seed)
    print(
        "[2/3] Validated 100 unique adults and public counterparts, workplaces, "
        "private histories and nonblocked initial positions", flush=True
    )
    text = json.dumps(artifact, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != text:
            raise SystemExit(f"Artifact differs: {args.output}; rebuild intentionally")
        print(f"[3/3] Reproducibility verified: {args.output}", flush=True)
    else:
        # Only the explicit JSON output is written. No saved world is loaded or reset.
        if args.output.suffix != ".json":
            raise SystemExit("Output must be a JSON artifact, never a database")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"[3/3] Wrote roster and allocation audit: {args.output}", flush=True)


if __name__ == "__main__":
    main()
