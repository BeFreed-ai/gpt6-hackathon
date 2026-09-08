"""Regression checks for the offline roster, source arithmetic and private runtime hooks."""

import copy
import json
import random
import socket
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

from app.employers import allocate_scenario_workplaces, load_employers
from app.population import _apportion, generate_population, generate_scenario_population
from app.store import EventStore
from app.world import World
from scripts.build_sf_population_100 import build_artifact

ROOT = Path(__file__).resolve().parents[1]


def test_hamilton_exact_fractions_and_ties():
    for count in (0, 1, 7, 100, 499):
        sizes = {"a": Fraction(1, 3), "b": Fraction(1, 3), "c": Fraction(1, 3)}
        result = _apportion(count, sizes, random.Random(17))
        assert result == _apportion(count, sizes, random.Random(17))
        assert sum(result.values()) == count
        assert all(type(n) is int and abs(n - count / 3) < 1 for n in result.values())
    for sizes in ({}, {"a": 0}, {"a": -1, "b": 2}):
        with pytest.raises(ValueError):
            _apportion(100, sizes, random.Random(17))


def test_100_population_exact_scope_and_private_lives():
    population = generate_scenario_population()
    profiles = population["profiles"]
    assert population == generate_scenario_population()
    assert len(profiles) == len({p["synthetic_id"] for p in profiles}) == 100
    assert len({p["name"] for p in profiles}) == 100
    assert Counter(p["neighborhood"] for p in profiles) == {
        "mission": 56, "soma": 27, "mission_bay": 17,
    }
    assert Counter(p["employment_status"] for p in profiles) == {
        "employed": 73, "unemployed": 3, "not_in_labor_force": 24,
    }
    assert len({tuple(p["background"]) for p in profiles}) == 100
    for p in profiles:
        assert p["age"] >= 18
        assert all(0 <= event["age"] <= p["age"] for event in p["life_history"])
        if not p.get("public_figure"):
            assert len(p["life_history"]) >= 7
            assert len(p["life_story"].split()) >= 180
            ages = [event["age"] for event in p["life_history"]]
            assert ages == sorted(ages)
        assert bool(p["workplace_assignment"]) == (p["employment_status"] == "employed")
        assert not {"race", "personality", "traits", "values", "goals", "active_goal"} & p.keys()
    assert population["report"]["geographic_scope"]["citywide_representative_sample"] is False
    assert sum(p["sampling_weight"] for p in profiles) == pytest.approx(84781)
    assert population["report"]["all_residents_estimate"] == 95839
    assert population["report"]["excluded_minors_estimate"] == 11058


@pytest.mark.parametrize("count", [0, 1, 24, 100, 499])
def test_industry_quota_and_reference_site_allocation(count):
    profiles = generate_population(count)["profiles"]
    original_groups = [p["occupation_sector"] for p in profiles]
    result = allocate_scenario_workplaces(profiles)
    report = result["report"]
    assert sum(report["industry_realized_counts"].values()) == report["employed_residents"]
    assert report["employed_residents"] + report["nonemployed_residents"] == count
    for sector, actual in report["industry_realized_counts"].items():
        assert abs(actual - report["industry_target_counts"][sector]) < 1
    catalog = {p["id"]: p for p in load_employers()}
    assigned = result["assignments"]
    for i, workplace in enumerate(assigned):
        if workplace is None:
            assert profiles[i]["employment_status"] != "employed"
        else:
            assert profiles[i]["occupation_group"] == original_groups[i]
            if workplace in catalog:
                assert catalog[workplace]["sector"] == profiles[i]["occupation_sector"]
                maximum = 3 if workplace == "openai_mission_bay" else 1
                assert assigned.count(workplace) <= maximum
            else:
                assert workplace.startswith("sector_")


def test_company_counts_never_influence_new_policy(monkeypatch):
    import app.employers as module

    profiles = generate_population(100)["profiles"]
    baseline = allocate_scenario_workplaces(copy.deepcopy(profiles))
    catalog = load_employers()
    for row in catalog:
        row.update(local_headcount=999999999, site_headcount=999999999)
    monkeypatch.setattr(module, "load_employers", lambda: catalog)
    assert allocate_scenario_workplaces(copy.deepcopy(profiles)) == baseline


def test_qcew_snapshot_denominators_and_unknown_staffing():
    data = json.loads((ROOT / "data/sf_employers.json").read_text())
    source = data["industry_calibration"]
    rows = source["rows"]
    assert len({(r["own_code"], r["industry_code"]) for r in rows}) == len(rows)
    private = [r for r in rows if r["own_code"] == "5"]
    assert abs(sum(r["annual_avg_emplvl"] for r in private) - source["private_total_jobs"]) <= 1
    assert sum(r["annual_avg_estabs"] for r in private) == source["private_total_establishments"]
    assert all(e.get("site_headcount") is None for e in load_employers())


def test_artifact_reproducible_without_any_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline generator attempted network access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    artifact = build_artifact()
    saved = json.loads((ROOT / "data/sf_population_100.json").read_text())
    assert artifact == saved
    assert len(artifact["roster"]) == 100
    assert sum(artifact["workplace_counts"].values()) == 73
    assert artifact["workplace_counts"]["openai_mission_bay"] == 3
    assert artifact["workplace_counts"]["anthropic_sf"] == 1
    figures = [
        p for p in artifact["roster"] if p.get("character_type") == "public_figure_simulation"
    ]
    assert {p["name"] for p in figures} == {
        "Sam Altman", "Dario Amodei",
    }
    assert {p["workplace_assignment"] for p in figures} == {"openai_mission_bay", "anthropic_sf"}
    for figure in figures:
        assert len(figure["recent_experiences"]) == 3
        assert all(e["provenance"] == "fictional_simulation_history"
                   for e in figure["life_history"])
        assert figure["public_figure"]["sources"]
        assert "not the actual person" in figure["background"][0]
        assert "residence_duration_months" not in figure["assumed_metadata"]
    assert all(p["initial_placement_valid"] for p in artifact["roster"])
    assert len({p["starting_credits"] for p in artifact["roster"]}) > 20
    assert {p["housing_status"] for p in artifact["roster"]} == {"rental", "shared_rental"}


def test_100_runtime_private_histories_and_economics(tmp_path):
    store = EventStore(str(tmp_path / "new-preview.db"))
    try:
        world = World(store, agent_count=100, scenario="sf", seed=17)
        world.paused = True
        snapshot = world.snapshot("local")
        assert len(world.agents) == 100
        mission_bay = [
            a for a in world.agents.values() if a.background.neighborhood == "mission_bay"
        ]
        assert len(mission_bay) == 17
        assert all(world.objects[a.home_id].metadata["neighborhood"] == "mission_bay"
                   for a in mission_bay)
        openai = next(e for e in world.employer_catalog if e["id"] == "openai_mission_bay")
        assert openai["local_headcount"] is None
        assert world.objects[openai["object_id"]].metadata["neighborhood"] == "mission_bay"
        assert sum(a.workplace_id == openai["object_id"] for a in world.agents.values()) == 3
        public = [a for a in world.agents.values() if a.background.public_figure]
        assert len(public) == 2
        dario = next(a for a in public if a.background.public_figure["id"] == "dario_amodei")
        assert dario.background.public_figure["age_estimated"] is True
        assert "42-43" in dario.background.public_figure["age_basis"]
        for agent in public:
            assert agent.background.public_figure["sources"]
            assert agent.background.public_figure["notice"]
            assert any(m.source_type.value == "document" for m in agent.memories)
        assert not world.economy.companies
        for agent in world.agents.values():
            assert agent.background.person_reference["sources"]
            assert any(m.source_type.value == "document"
                       and m.content.startswith("Public counterpart") for m in agent.memories)
            assert not world.terrain.blocked(agent.position)
            assert agent.active_goal is None and not agent.values
            assert agent.life.direction is None and not agent.life.projects
            assert agent.background.biography == [
                m.content for m in agent.memories if m.event_type == "personal_background"
            ]
            ledger = world.sf_economy.state["agents"][agent.id]
            assert agent.credits == ledger["initial_savings_credits"]
            if agent.workplace_id:
                assert agent.workplace_id in world.objects
                assert agent.background.employment_status == "employed"
        assert "roster" not in snapshot["population"]
        assert all("background" not in a for a in snapshot["agents"])
        first, second, *_ = world.agents.values()
        marker = "A private synthetic life milestone only this person remembers."
        first.background.biography.append(marker)
        assert marker in str(world.agent_detail(first.id))
        assert marker not in str(world.context_for(second))
        assert marker not in str(world.snapshot("local"))
    finally:
        store.close()


def test_100_distinct_public_counterparts_and_fictional_recent_events():
    population = generate_scenario_population()
    profiles = population["profiles"]
    references = [p["person_reference"] for p in profiles]
    assert len({r["id"] for r in references}) == 100
    assert len({r["name"] for r in references}) == 100
    assert all(p["name"] == p["person_reference"]["name"] for p in profiles)
    assert population["report"]["person_references"]["unique_people"] == 100
    assert {p["person_reference"]["name"] for p in profiles
            if p["workplace_assignment"] == "openai_mission_bay"} == {
        "Sam Altman", "Jakub Pachocki", "Mark Chen",
    }
    catalog = json.loads((ROOT / "data/sf_person_references.json").read_text())
    assert len(catalog["people"]) == 98
    for person in catalog["people"]:
        assert len(person["public_career_facts"]) >= 2
        source = catalog["sources"][person["source_id"]]
        assert source["url"].startswith("https://") and source["accessed"] == "2026-09-08"
        assert person["actual_age"] is person["actual_residence"] is None
        assert person["actual_household"] is person["actual_finances"] is None
    assert len({tuple(e["event"] for e in p["recent_experiences"]) for p in profiles}) == 100
    for profile in profiles:
        assert len(profile["life_story"].split()) >= 300
        assert len(profile["recent_experiences"]) == 3
        assert [e["days_before_start"] for e in profile["recent_experiences"]] == sorted(
            [e["days_before_start"] for e in profile["recent_experiences"]], reverse=True,
        )
        assert all(e["provenance"] == "fictional_simulation_history"
                   and e["event"].startswith("Fictional simulation memory:")
                   for e in profile["life_history"])
