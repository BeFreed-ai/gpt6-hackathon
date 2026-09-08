import copy
import random

import pytest

from app import employers


def test_supplied_counts_keep_residents_and_commuters_separate():
    profiles = [
        {"employment_status": "employed", "sector": "technology", "population_role": role}
        for role in ("resident", "inbound_commuter")
        for _ in range(20)
    ]
    observation = {
        "employer_id": "salesforce_sf",
        "count": 50,
        "denominator": 100,
        "population_role": "inbound_commuter",
        "scope": "inbound_commuters",
        "source_url": "https://example.test/supplied-cross-tab",
        "as_of": "2024",
    }
    report = employers.allocate_supplied_local_counts(profiles, [observation])
    assert report["assignments"][:20] == ["sector_technology"] * 20
    assert report["assignments"][20:].count("salesforce_sf") == 10
    assert report["resident_agents"] == report["inbound_commuter_agents"] == 20
    for changes in (
        {"scope": "san_francisco_city"},
        {"count": None},
        {"count": 101},
        {"denominator": 0},
        {"source_url": None},
    ):
        with pytest.raises(ValueError):
            employers.allocate_supplied_local_counts(profiles, [dict(observation, **changes)])


def test_catalog_evidence_and_scope():
    rows = employers.load_employers()
    assert len(rows) >= 16
    assert len({row["id"] for row in rows}) == len(rows)
    assert {row["neighborhood"] for row in rows} == {"soma", "mission", "mission_bay"}
    assert {row["sector"] for row in rows} == employers.SECTORS
    assert sum(row["sector"] != "technology" for row in rows) > len(rows) / 2
    for row in rows:
        assert not row["id"].startswith("sector_")
        assert row["address"] and row["name"]
        assert 37.70 < row["latitude"] < 37.82
        assert -122.46 < row["longitude"] < -122.37
        assert row["coordinate_precision"] in {"approximate", "official_site_map_point"}
        assert row["sources"]
        for source in row["sources"]:
            assert source["url"].startswith("https://")
            assert source["title"] and source["supports"] and source["accessed_on"]
        if row["local_headcount"] is None:
            assert row["headcount_status"] == "unknown"
            assert row["headcount_scope"] == "unknown"
            assert row["headcount_year"] is None
        else:
            assert row["headcount_status"] == "estimate"
            assert type(row["local_headcount"]) is int
            assert row["local_headcount"] > 0
            assert row["headcount_scope"] == "san_francisco_city"
            assert row["headcount_year"] == 2025
            assert row["site_headcount"] is None
            assert any(
                "san_francisco_city_headcount" in source["supports"] for source in row["sources"]
            )


def test_loader_returns_independent_copies():
    rows = employers.load_employers()
    rows[0]["sources"][0]["url"] = "changed"
    assert employers.load_employers()[0]["sources"][0]["url"] != "changed"


def test_employment_eligibility_and_small_cohort():
    profiles = [
        {"employment_status": status, "occupation_sector": "technology"}
        for status in ("employed", "unemployed", "retired", "student", "Employed", None)
    ]
    assert employers.allocate_workplaces(profiles) == ["sector_technology"] + [None] * 5
    assert employers.allocate_workplaces([]) == []


def test_repeatable_sector_matching_and_generic_coverage():
    profiles = [
        {"employment_status": "employed", "occupation_sector": sector}
        for sector in sorted(employers.SECTORS)
        for _ in range(40)
    ]
    original = copy.deepcopy(profiles)
    random_state = random.getstate()
    assigned = employers.allocate_workplaces(profiles, seed=17)
    assert assigned == employers.allocate_workplaces(profiles, seed=17)
    assert assigned != employers.allocate_workplaces(profiles, seed=18)
    assert profiles == original
    assert random.getstate() == random_state
    assert sum(value.startswith("sector_") for value in assigned) >= len(profiles) * 0.75
    assert any(not value.startswith("sector_") for value in assigned)
    by_id = {row["id"]: row for row in employers.load_employers()}
    for profile, workplace in zip(profiles, assigned, strict=True):
        if workplace in by_id:
            assert by_id[workplace]["sector"] == profile["occupation_sector"]
        else:
            assert workplace == f"sector_{profile['occupation_sector']}"


def test_unrepresented_and_missing_sectors_are_generic():
    profiles = [
        {"employment_status": "employed", "occupation_sector": "construction"},
        {"employment_status": "employed", "sector": "Transport & Warehousing"},
        {"employment_status": "employed"},
        {"employment_status": "employed", "occupation_sector": "../../"},
    ]
    assert employers.allocate_workplaces(profiles) == [
        "sector_construction",
        "sector_transport_warehousing",
        "sector_other",
        "sector_other",
    ]


def test_counts_do_not_weight_or_exclude_unknown_workplaces(monkeypatch):
    rows = [
        {"id": "small", "sector": "retail", "local_headcount": 10, "headcount_scope": "site"},
        {"id": "unknown", "sector": "retail", "local_headcount": None},
    ]
    monkeypatch.setattr(employers, "load_employers", lambda: copy.deepcopy(rows))
    profiles = [{"employment_status": "employed", "sector": "retail"} for _ in range(200)]
    original = employers.allocate_workplaces(profiles)
    assert "unknown" in original
    rows[0].update(local_headcount=10000000, headcount_scope="global")
    rows[1].update(local_headcount=90000, headcount_scope="san_francisco_city")
    assert employers.allocate_workplaces(profiles) == original


def test_residential_neighborhood_does_not_assert_employer_location():
    profiles = [
        {"employment_status": "employed", "sector": "technology", "neighborhood": "mission"}
        for _ in range(20)
    ]
    assigned = employers.allocate_workplaces(profiles)
    for profile in profiles:
        profile["neighborhood"] = "soma"
    assert employers.allocate_workplaces(profiles) == assigned


def test_airbnb_global_count_is_not_local():
    airbnb = next(row for row in employers.load_employers() if row["id"] == "airbnb_brannan")
    assert airbnb["local_headcount"] is None
    observation = airbnb["headcount_observations"][0]
    assert observation["scope"] == "global"
    assert observation["used_for_allocation"] is False


def test_report_keeps_scopes_separate():
    report = employers.employer_report()
    assert report["known_headcounts_by_scope"] == {"san_francisco_city": 2}
    assert report["unknown_local_headcounts"] == report["catalog_workplaces"] - 2
    assert report["allocation"]["status"] == "scenario_assumption"
    assert employers.catalog_report() == report
    assert report["limitations"]


def test_contextual_geography_is_explicit():
    rows = employers.load_employers()
    outside = {row["id"] for row in rows if not row["within_resident_reference_area"]}
    assert outside == {"salesforce_sf", "google_spear", "sfmoma", "ybca", "anthropic_sf"}
    for row in rows:
        assert row["reference_geography_basis"]
        assert row["within_resident_reference_area"] == (
            row["reference_geography"] in {"Mission", "South of Market", "Mission Bay"}
        )
