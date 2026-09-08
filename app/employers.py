"""Verified workplace locations and explicitly synthetic, offline assignments.

Headcounts describe the source's geography, never a building capacity. See
docs/sf-employer-sources.md for coverage, dates and allocation assumptions.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "sf_employers.json"
NAMED_WORKPLACE_SHARE = 0.25  # Scenario assumption; not an observed commuting share.
SECTORS = frozenset(
    {
        "technology",
        "healthcare",
        "food_service",
        "retail",
        "education",
        "arts",
        "public_service",
        "professional_services",
    }
)


def load_employers() -> list[dict]:
    """Return fresh records from the checked-in catalog, with no network or cache.

    A null headcount means unknown, including when only broader or qualitative
    evidence exists. A san_francisco_city count is not a site headcount.
    """
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    return catalog["employers"]


def _sector(profile: dict) -> str:
    value = profile.get("occupation_sector") or profile.get("sector")
    if not isinstance(value, str):
        return "other"
    # Preserve unrepresented sectors in generic IDs, without generating unsafe IDs.
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "other"


def allocate_workplaces(profiles: list[dict], seed: int = 17) -> list[str | None]:
    """Assign employed profiles to sector workplaces and a small named sample.

    At most floor(25% of profiles with a matching catalog sector) get a named
    site. The rest get sector_<sector>; missing sectors get sector_other.
    This 25% ceiling and uniform within-sector example selection are scenario
    assumptions, not job estimates. No headcount, global total, residential
    neighborhood or per-company guessed weight enters the draw. In particular,
    an unknown headcount never becomes zero and does not exclude a named site.

    Non-employed profiles receive None. Input order and seed determine output;
    inputs and Python's global random state are unchanged. Small cohorts with
    fewer than four sector-matched employed profiles receive generic IDs only.
    """
    by_sector: dict[str, list[str]] = {}
    for employer in sorted(load_employers(), key=lambda row: row["id"]):
        by_sector.setdefault(employer["sector"], []).append(employer["id"])

    assignments: list[str | None] = [None] * len(profiles)
    candidates: list[int] = []
    for index, profile in enumerate(profiles):
        if profile.get("employment_status") != "employed":
            continue
        sector = _sector(profile)
        assignments[index] = f"sector_{sector}"
        if sector in by_sector:
            candidates.append(index)

    rng = random.Random(seed)
    named_count = int(len(candidates) * NAMED_WORKPLACE_SHARE)
    for index in rng.sample(candidates, named_count):
        assignments[index] = rng.choice(by_sector[_sector(profiles[index])])
    return assignments


def employer_report() -> dict:
    """Summarize evidence coverage without summing incompatible headcounts."""
    employers = load_employers()
    return {
        "catalog_workplaces": len(employers),
        "by_neighborhood": dict(Counter(row["neighborhood"] for row in employers)),
        "by_sector": dict(Counter(row["sector"] for row in employers)),
        "known_headcounts_by_scope": dict(
            Counter(
                row["headcount_scope"] for row in employers if row["local_headcount"] is not None
            )
        ),
        "unknown_local_headcounts": sum(row["local_headcount"] is None for row in employers),
        "contextual_workplaces_outside_resident_reference_area": [
            row["id"] for row in employers if row.get("within_resident_reference_area") is False
        ],
        "allocation": {
            "status": "scenario_assumption",
            "named_workplace_share_ceiling": NAMED_WORKPLACE_SHARE,
            "basis": "uniform named examples within matching sectors; no headcount weighting",
            "fallback": "sector_<sector>",
            "supplied_counts_interface": "allocate_supplied_local_counts",
        },
        "limitations": [
            "Curated locations, not a census of establishments or jobs.",
            "SF-city reported estimates are not site counts or current payroll audits.",
            "Broad workplace catchment differs from resident analysis neighborhoods.",
            "25% named example ceiling and uniform sector sampling are scenario assumptions.",
            "No observed resident-to-employer or commuting allocation is inferred.",
        ],
    }


def allocate_supplied_local_counts(
    profiles: list[dict], observations: list[dict], seed: int = 17
) -> dict:
    """Allocate only explicit resident-worker/commuter cross-tabs supplied by a caller.

    Each observation requires employer_id, count, population_role (resident or
    inbound_commuter), denominator, source_url, as_of, and scope matching the role
    (resident_workers or inbound_commuters). Counts are NOT read from the catalog:
    citywide company estimates do not tell us which workers reside in the sample.
    Zero is measured zero; null is unknown and never silently zero-filled.
    """
    catalog = {row["id"]: row for row in load_employers()}
    assignments = [
        f"sector_{_sector(p)}" if p.get("employment_status") == "employed" else None
        for p in profiles
    ]
    rng = random.Random(seed)
    reports = []
    for role, scope in (
        ("resident", "resident_workers"),
        ("inbound_commuter", "inbound_commuters"),
    ):
        rows = [row for row in observations if row.get("population_role") == role]
        if not rows:
            continue
        for row in rows:
            if row.get("scope") != scope or not row.get("source_url") or not row.get("as_of"):
                raise ValueError(
                    "Supplied counts require matching population scope, source and date"
                )
            if row.get("employer_id") not in catalog:
                raise ValueError("Unknown employer_id")
            if type(row.get("count")) is not int or row["count"] < 0:
                raise ValueError("Count must be a known nonnegative integer; unknown stays null")
            if type(row.get("denominator")) is not int or row["denominator"] <= 0:
                raise ValueError("A positive matching worker denominator is required")
        denominators = {row["denominator"] for row in rows}
        if len(denominators) != 1 or len({r["employer_id"] for r in rows}) != len(rows):
            raise ValueError("Counts must share one denominator and have no duplicate employers")
        denominator = rows[0]["denominator"]
        if sum(row["count"] for row in rows) > denominator:
            raise ValueError("Employer counts exceed the worker denominator")
        eligible = [
            i
            for i, p in enumerate(profiles)
            if p.get("employment_status") == "employed"
            and p.get("population_role", "resident") == role
        ]
        rng.shuffle(eligible)
        for row in sorted(rows, key=lambda row: row["employer_id"]):
            target = int(Fraction(len(eligible) * row["count"], denominator))
            matches = [
                i
                for i in eligible
                if assignments[i].startswith("sector_")
                and _sector(profiles[i]) == catalog[row["employer_id"]]["sector"]
            ]
            selected = matches[:target]
            for index in selected:
                assignments[index] = row["employer_id"]
            reports.append(
                dict(
                    row,
                    sample_target=target,
                    realized_count=len(selected),
                    unfilled_due_to_sector=len(selected) < target,
                )
            )
    if any(
        row.get("population_role") not in {"resident", "inbound_commuter"} for row in observations
    ):
        raise ValueError("Separate resident workers and inbound commuters explicitly")
    return {
        "assignments": assignments,
        "observations": reports,
        "method": (
            "Floor each explicit count/worker-denominator quota, "
            "then sector match; residual generic"
        ),
        "resident_agents": sum(
            p.get("population_role", "resident") == "resident" for p in profiles
        ),
        "inbound_commuter_agents": sum(
            p.get("population_role") == "inbound_commuter" for p in profiles
        ),
    }


def catalog_report() -> dict:
    """Integration alias for the evidence and scenario coverage report."""
    return employer_report()


def allocate_scenario_workplaces(profiles: list[dict], seed: int = 17) -> dict:
    """Assign exact industry quotas, requested example seats and reference sites.

    Mutates only occupation_sector/occupation_group on the caller-owned profiles.
    Site coverage is a scenario rule; neither establishment counts nor company
    headcounts are interpreted as resident-worker shares. Nonworkers stay unassigned.
    """
    from app.population import _apportion

    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    source = data["industry_calibration"]
    weights: Counter = Counter()
    for row in source["rows"]:
        weights[row["sector"]] += row["annual_avg_emplvl"]
    rng = random.Random(f"sf-industry:{seed}")
    eligible = [i for i, p in enumerate(profiles) if p.get("employment_status") == "employed"]
    counts = _apportion(len(eligible), dict(weights), rng)
    sectors = [sector for sector, n in counts.items() for _ in range(n)]
    rng.shuffle(sectors)
    assignments: list[str | None] = [None] * len(profiles)
    for index, sector in zip(eligible, sectors, strict=True):
        profile = profiles[index]
        profile["occupation_group"] = (
            profile.get("occupation_group") or profile.get("occupation_sector")
        )
        profile["occupation_sector"] = sector
        assignments[index] = f"sector_{sector}_{profile['neighborhood']}"
    catalog = load_employers()
    requested = data["scenario_allocation_policy"].get("requested_example_quotas", {})
    quota_audit = {}
    for sector in sorted(counts):
        candidates = [i for i in eligible if profiles[i]["occupation_sector"] == sector]
        sites = sorted(
            e["id"] for e in catalog if e["sector"] == sector and e["id"] not in requested
        )
        rng.shuffle(candidates)
        priority_sites = sorted(
            e["id"] for e in catalog if e["sector"] == sector and e["id"] in requested
        )
        for site in priority_sites:
            selected, candidates = candidates[:requested[site]], candidates[requested[site]:]
            for index in selected:
                assignments[index] = site
            quota_audit[site] = {"requested": requested[site], "realized": len(selected)}
        rng.shuffle(sites)
        for index, site in zip(candidates, sites, strict=False):
            assignments[index] = site
    return {
        "assignments": assignments,
        "report": {
            "policy": data["scenario_allocation_policy"],
            "requested_example_quota_audit": quota_audit,
            "industry_source": source,
            "industry_job_denominator": sum(weights.values()),
            "industry_weights": dict(weights),
            "employed_residents": len(eligible),
            "nonemployed_residents": len(profiles) - len(eligible),
            "industry_target_counts": {
                sector: len(eligible) * number / sum(weights.values())
                for sector, number in weights.items()
            },
            "industry_realized_counts": counts,
            "workplace_counts": dict(sorted(Counter(a for a in assignments if a).items())),
            "named_assignments": sum(
                a is not None and not a.startswith("sector_") for a in assignments
            ),
            "unassigned_nonworkers": sum(a is None for a in assignments),
            "method": (
                "Hamilton industry quotas; seeded independent occupation pairing; "
                "requested example quotas first; one seat per other named site; generic residual"
            ),
            "limitations": [
                "City workplace jobs are a proxy for resident industries, "
                "not a commuting cross-tab.",
                "QCEW covers employer jobs; self-employed residents and "
                "multiple jobholders differ.",
                "Annual average sector rows may differ from published totals due to rounding.",
                "Industry and occupation are assigned independently; "
                "their joint distribution is not fitted.",
                "Named seats illustrate verified sites; "
                "they are not measured or estimated company staff counts.",
            ],
        },
    }


if __name__ == "__main__":
    print(json.dumps(employer_report(), indent=2))
