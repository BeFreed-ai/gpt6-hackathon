import copy
import json

import pytest

from app.economy import Company
from app.models import ActionIntent, ActionType
from app.sf_economy import (
    SFEconomy,
    annual_usd_to_daily_credits,
    apply_sf_economy,
    economic_profiles,
    monthly_usd_to_daily_credits,
)
from app.store import EventStore
from app.world import World


@pytest.fixture
def world(tmp_path, monkeypatch):
    store = EventStore(str(tmp_path / "sf-economy.db"))
    world = World(store, agent_count=12, scenario="sf")
    world.next_city_event = float("inf")
    apply_sf_economy(world, 17)
    monkeypatch.setattr(world, "_approach", lambda *args: False)
    yield world
    store.close()


def finish(world, agent):
    world.time = agent.activity.ends_at
    world.urban.tick()


def test_currency_conversion_uses_same_day_for_income_and_rent():
    assert annual_usd_to_daily_credits(365 * 25) == 1
    assert monthly_usd_to_daily_credits(365 * 25 / 12) == 1
    assert monthly_usd_to_daily_credits(2476) == pytest.approx(3.256109589)
    assert annual_usd_to_daily_credits(140970) == pytest.approx(15.44876712)


def test_profiles_have_spread_without_household_income_as_each_adults_wage():
    profiles = [{"employment_status": "employed", "occupation_sector": "service"}] * 100
    result = economic_profiles(profiles, 21)
    assert result == economic_profiles(profiles, 21)
    assert len({p["hourly_gross_usd"] for p in result}) > 20
    assert min(p["hourly_gross_usd"] for p in result) >= 19.61
    assert min(p["initial_savings_credits"] for p in result) == 0
    assert max(p["initial_savings_credits"] for p in result) > 100
    assert all(p["annual_gross_wage_usd"] != 140970 for p in result)


def test_seed_is_idempotent_and_checkpoint_facade_has_no_private_state(world):
    agent = next(iter(world.agents.values()))
    agent.credits = 1.23
    original = copy.deepcopy(world.economy.sf_state)
    apply_sf_economy(world, 999)
    assert agent.credits == 1.23
    assert world.economy.sf_state == original
    world.economy.sf_state = json.loads(json.dumps(original, allow_nan=False))
    assert SFEconomy(world).context_for(agent) == world.sf_economy.context_for(agent)


def test_baseline_wages_paid_only_on_completion_and_capped(world):
    agent = next(a for a in world.agents.values() if a.workplace_id)
    target = world.objects[agent.workplace_id]
    target.metadata["hours"] = [0, 24]
    initial = agent.credits
    daily = world.sf_economy.state["agents"][agent.id]["daily_net_wage_credits"]
    intent = ActionIntent(action=ActionType.WORK, target_id=target.id)
    for _ in range(2):
        world.urban.execute(agent, intent)
        assert agent.activity
        before = agent.credits
        finish(world, agent)
        assert agent.credits > before
        paid = agent.credits
        world.urban.tick()
        assert agent.credits == paid
    assert agent.credits == pytest.approx(initial + daily)
    world.urban.execute(agent, intent)
    assert agent.activity is None
    assert agent.credits == pytest.approx(initial + daily)
    assert world.economy.city_balance >= 0
    assert world.sf_economy.report()["external_wages_credits"] == daily


def test_canceled_shift_pays_nothing_and_preserves_availability(world):
    agent = next(a for a in world.agents.values() if a.workplace_id)
    initial = agent.credits
    world.urban.execute(agent, ActionIntent(action=ActionType.WORK, target_id=agent.workplace_id))
    assert agent.activity
    world.urban.cancel(agent)
    world.urban.tick()
    assert agent.credits == initial
    assert world.sf_economy.state["agents"][agent.id]["shifts_completed"] == 0


def test_rent_partial_payment_debt_repayment_and_no_double_day_charge(world):
    agent = next(a for a in world.agents.values() if a.home_id)
    ledger = world.sf_economy.state["agents"][agent.id]
    ledger["daily_support_credits"] = 0
    rent = world.sf_economy.rent_share(agent)
    agent.credits = round(rent / 2, 2)
    expected_debt = round(rent - agent.credits, 2)
    home = agent.home_id
    world.time = world.day_length
    world.sf_economy.new_day()
    assert agent.credits == 0
    assert ledger["rent_debt_credits"] == expected_debt
    world.sf_economy.new_day()
    assert ledger["rent_debt_credits"] == expected_debt
    assert agent.home_id == home
    agent.credits = 100
    world.time += world.day_length
    world.sf_economy.new_day()
    assert agent.credits == pytest.approx(100 - rent - expected_debt)
    assert ledger["rent_debt_credits"] == agent.rent_arrears == 0
    assert all(a.credits >= 0 for a in world.agents.values())


def test_households_do_not_split_one_apartment_rent_across_entire_building(world):
    households = world.sf_economy.state["households"]
    for household_id, household in households.items():
        members = [
            a
            for a in world.agents.values()
            if world.sf_economy.state["agents"][a.id]["household_id"] == household_id
        ]
        assert 1 <= len(members) <= 3
        assert sum(world.sf_economy.rent_share(a) for a in members) == pytest.approx(
            household["daily_rent_credits"], abs=0.02
        )


def test_housing_move_keeps_debt_and_first_day_is_prepaid(world):
    agent = next(iter(world.agents.values()))
    ledger = world.sf_economy.state["agents"][agent.id]
    ledger.update(rent_debt_credits=2.0, daily_support_credits=0)
    target = next(o for o in world.objects.values() if o.kind == "home" and o.id != agent.home_id)
    target.metadata["beds"] = 100
    agent.credits = 100
    rent = target.metadata["rent"]
    world.urban.execute(agent, ActionIntent(action=ActionType.RENT_HOME, target_id=target.id))
    assert ledger["rent_debt_credits"] == 2
    assert agent.credits == 100 - rent
    world.time = world.day_length
    world.sf_economy.new_day()
    assert agent.credits == pytest.approx(100 - rent - 2)


def test_closed_workplace_causes_job_loss_and_no_wage(world):
    agent = next(a for a in world.agents.values() if a.workplace_id)
    site = world.objects[agent.workplace_id]
    world.urban.execute(agent, ActionIntent(action=ActionType.WORK, target_id=site.id))
    initial = agent.credits
    site.metadata["open"] = False
    world.economy.tick()
    assert agent.activity is None
    assert agent.workplace_id is None
    assert agent.background.employment_status == "unemployed"
    assert agent.credits == initial


def test_only_insolvent_companies_close_and_employees_lose_job(world):
    founder, employee, *_ = world.agents.values()
    site = world._add_object("company", "Test Kitchen", 500, 500)
    company = Company(
        id=site.id,
        name=site.name,
        purpose="meals",
        founder_id=founder.id,
        product="meals",
        treasury=0,
        price=3,
        shares={founder.id: 1},
        employees={employee.id: 2},
    )
    world.economy.companies[site.id] = company
    employee.workplace_id = site.id
    for day in (1, 2):
        world.time = world.day_length * day
        world.sf_economy.new_day()
        assert not company.closed
    world.time = world.day_length * 3
    world.sf_economy.new_day()
    assert company.closed and company.treasury == 0
    assert not company.employees
    assert employee.workplace_id is None
    assert site.metadata["open"] is False


def test_working_capital_or_actual_sales_prevent_forced_closure(world):
    founder = next(iter(world.agents.values()))
    for index, treasury in enumerate((20, 0)):
        site = world._add_object("company", f"Test Shop {index}", 500, 500)
        world.economy.companies[site.id] = Company(
            id=site.id,
            name=site.name,
            purpose="meals",
            founder_id=founder.id,
            product="meals",
            treasury=treasury,
            price=3,
            shares={founder.id: 1},
            stock=5,
        )
    funded, selling = world.economy.companies.values()
    for day in range(1, 5):
        selling.revenue += 3
        selling.treasury += 3
        world.time = world.day_length * day
        world.sf_economy.new_day()
    assert not funded.closed and not selling.closed
    assert funded.insolvent_days == selling.insolvent_days == 0


def test_essential_service_output_is_consumable(world):
    clinic = next(o for o in world.objects.values() if o.kind == "clinic")
    clinic.metadata.update(care_stock=0, hours=[0, 24])
    agent = next(iter(world.agents.values()))
    agent.health = 60
    intent = ActionIntent(action=ActionType.REST, target_id=clinic.id)
    world.urban.execute(agent, intent)
    assert agent.activity is None
    world.sf_economy.produce_service(clinic)
    assert clinic.metadata["care_stock"] == 6
    world.urban.execute(agent, intent)
    finish(world, agent)
    assert agent.health == 78 and clinic.metadata["care_stock"] == 5
    outlets = [o for o in world.objects.values() if o.kind in {"market", "cafe", "dining"}]
    for site in outlets:
        site.metadata.update(stock=0, hours=[0, 24])
    world.sf_economy.produce_service(outlets[0])
    stocked = next(o for o in outlets if o.metadata["stock"])
    agent.credits = 10
    world.urban.execute(agent, ActionIntent(action=ActionType.BUY, target_id=stocked.id))
    assert agent.inventory and stocked.metadata["stock"] == 5


def test_reports_keep_denominators_and_private_finances_separate(world):
    report = world.sf_economy.report()
    assert report["resident_agents"] == 12 and report["inbound_commuter_agents"] == 0
    assert "agents" not in report and "households" not in report
    agent, other, *_ = world.agents.values()
    context = world.sf_economy.context_for(agent)
    assert other.id not in json.dumps(context)
    assert report["sources"][0]["used_as"].startswith("Citywide reference anchors")
    assert "not resident workers" in report["sources"][1]["denominator"]
