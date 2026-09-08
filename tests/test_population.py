from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import pytest

from app.population import generate_population


@pytest.mark.parametrize("count", [0, 1, 2, 3, 12, 101, 1000])
def test_exact_count_reproducible_and_json_compatible(count: int) -> None:
    population = generate_population(count)
    assert population == generate_population(count, seed=17)
    assert len(population["profiles"]) == count
    assert population["report"]["realized_count"] == count
    assert json.loads(json.dumps(population, allow_nan=False)) == population
    assert len({profile["synthetic_id"] for profile in population["profiles"]}) == count


@pytest.mark.parametrize("count", [-1, -100])
def test_negative_count_rejected(count: int) -> None:
    with pytest.raises(ValueError):
        generate_population(count)


@pytest.mark.parametrize("count", [True, 1.5, "12", None])
def test_noninteger_count_rejected(count: object) -> None:
    with pytest.raises(TypeError):
        generate_population(count)


def test_seed_is_local_and_changes_individuals() -> None:
    before = random.getstate()
    first = generate_population(12, 1)
    assert random.getstate() == before
    assert first["profiles"] != generate_population(12, 2)["profiles"]
    with pytest.raises(TypeError):
        generate_population(12, True)


def test_economic_assumptions_do_not_change_resident_weights():
    population = generate_population(100)
    for profile in population["profiles"]:
        economics = profile["economic_profile"]
        assert economics["population_role"] == "resident"
        assert economics["initial_savings_credits"] >= 0
        assert (economics["annual_gross_wage_usd"] > 0) == (
            profile["employment_status"] == "employed"
        )
        assert economics["basis"] == "source_level_with_scenario_spread"
    assert sum(p["sampling_weight"] for p in population["profiles"]) == pytest.approx(70568)


def test_source_counts_and_adult_denominators_reconcile() -> None:
    data = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "sf_population.json").read_text()
    )
    report = generate_population(12)["report"]
    assert report["vintage"] == "2019-2023 ACS 5-year estimates"
    assert report["all_residents_estimate"] == 79129
    assert report["adult_residents_estimate"] == 70568
    assert report["excluded_minors_estimate"] == 8561
    assert report["citywide_context"]["used_for_neighborhood_calibration"] is False
    for key, name in data["geography"]["neighborhoods"].items():
        rows = [row for row in data["source_rows"] if row["geography_name"] == name]
        ages = [row for row in rows if row["demographic_category"] == "age"]
        all_ages = next(row["estimate"] for row in rows if row["demographic_category"] == "all")
        assert sum(row["estimate"] for row in ages) == all_ages
        expected_adults = sum(row["estimate"] for row in ages if int(row["acs_code"]) >= 4)
        assert report["neighborhoods"][key]["adult_residents_estimate"] == expected_adults
        assert all(row["moe"] > 0 for row in rows)


@pytest.mark.parametrize("count", [0, 1, 12, 47, 1000])
def test_largest_remainder_quotas_and_report_match_profiles(count: int) -> None:
    population = generate_population(count, 5)
    report = population["report"]
    realized = Counter((p["neighborhood"], p["age_band"]) for p in population["profiles"])
    for key, neighborhood in report["neighborhoods"].items():
        assert abs(neighborhood["target_sample_count"] - neighborhood["realized_count"]) < 1
        assert neighborhood["realized_count"] == sum(
            n for (k, _), n in realized.items() if k == key
        )
    for stratum in report["strata"]:
        actual = realized[stratum["neighborhood"], stratum["age_band"]]
        assert actual == stratum["realized_count"]
        assert abs(stratum["conditional_target_sample_count"] - actual) < 1
        if actual:
            assert stratum["residents_per_agent"] * actual == pytest.approx(
                stratum["adult_residents_estimate"]
            )
        else:
            assert stratum["residents_per_agent"] is None
    weights = report["sampling_weights"]
    assert (
        weights["represented_adults_estimate"] + weights["unrepresented_adults_estimate"] == 70568
    )
    assert sum(p["sampling_weight"] for p in population["profiles"]) == pytest.approx(
        weights["represented_adults_estimate"]
    )


def test_default_small_sample_discloses_missing_strata() -> None:
    report = generate_population(12)["report"]
    assert {k: v["realized_count"] for k, v in report["neighborhoods"].items()} == {
        "mission": 8,
        "soma": 4,
    }
    assert report["sampling_weights"]["unrepresented_strata"] == [
        {"neighborhood": "soma", "age_band": "55-64"}
    ]
    assert report["sampling_weights"]["unrepresented_adults_estimate"] == 2460
    assert report["sampling_weights"]["probability_sample"] is False


def test_profiles_are_adults_with_assumed_circumstances_and_no_behavior_mapping() -> None:
    ranges = {"18-34": (18, 34), "35-54": (35, 54), "55-64": (55, 64), "65+": (65, 100)}
    profiles = generate_population(1000)["profiles"]
    for profile in profiles:
        low, high = ranges[profile["age_band"]]
        assert low <= profile["age"] <= high
        assert profile["neighborhood"] in {"mission", "soma"}
        assert profile["synthetic"] is True
        assert profile["housing_status"] == "unspecified"
        assert profile["employment_status"] in {"employed", "unemployed", "not_in_labor_force"}
        assert (profile["occupation_sector"] is not None) == (
            profile["employment_status"] == "employed"
        )
        assert all(isinstance(item, str) and item for item in profile["background"])
        assert len(profile["background"]) == 5
        assert 1 <= profile["assumed_metadata"]["residence_duration_months"] <= profile["age"] * 12
        forbidden = {"race", "personality", "traits", "values", "goals", "active_goal"}
        assert not forbidden & profile.keys()
    assert len({tuple(p["background"]) for p in profiles}) > 900


@pytest.mark.parametrize("count", [0, 1, 12, 1000])
def test_employment_proxy_denominators_and_realized_marginals(count: int) -> None:
    population = generate_population(count)
    report = population["report"]["employment_calibration"]
    assert report["vintage"] == "2016-2020 ACS 5-year estimates"
    assert "16 and over" in report["source_population"]
    assert report["source_moe"] is None
    for key, neighborhood in report["neighborhoods"].items():
        profiles = [p for p in population["profiles"] if p["neighborhood"] == key]
        shares = neighborhood["status_target_shares_proxy"]
        raw = neighborhood["source_values"]
        assert shares["unemployed"] == float(raw["Unemployment Rate"])
        assert shares["employed"] == pytest.approx(
            float(raw["Labor Force Participation Rate"]) - float(raw["Unemployment Rate"])
        )
        assert sum(shares.values()) == pytest.approx(1)
        realized = Counter(p["employment_status"] for p in profiles)
        assert realized == Counter(neighborhood["status_realized_counts"])
        for status, target in neighborhood["status_target_sample_counts"].items():
            assert abs(realized[status] - target) < 1
        sectors = Counter(p["occupation_sector"] for p in profiles if p["occupation_sector"])
        assert all(
            sectors[sector] == number
            for sector, number in neighborhood["occupation_realized_counts"].items()
        )
    if count == 12:
        assert sum(p["employment_status"] == "employed" for p in population["profiles"]) == 9
