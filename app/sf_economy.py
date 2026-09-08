"""Offline SF anchors and explicit simulation assumptions, never real personal finances."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import TYPE_CHECKING

from app.economy import PRODUCTS

if TYPE_CHECKING:
    from app.models import AgentState, WorldObject
    from app.world import World

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sf_economy.json"
WAGE_PROXIES = {
    "technology": "computer_mathematical",
    "professional_services": "business_financial",
    "healthcare": "healthcare_practitioners",
    "education": "education_library",
    "arts": "arts_media",
    "food_service": "food_service",
    "retail": "sales",
    "public_service": "cleaning_maintenance",
    "management_business_science_arts": "business_financial",
    "service": "food_service",
    "sales_office": "office_support",
    "natural_resources_construction_maintenance": "construction",
    "production_transportation_material_moving": "transportation",
}


def load_calibration() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def annual_usd_to_daily_credits(annual_usd: float, data: dict | None = None) -> float:
    mapping = (data or load_calibration())["mapping"]
    return (
        annual_usd
        * mapping["real_days_per_game_day"]
        / (mapping["days_per_year"] * mapping["usd_per_credit"])
    )


def monthly_usd_to_daily_credits(monthly_usd: float, data: dict | None = None) -> float:
    data = data or load_calibration()
    return annual_usd_to_daily_credits(monthly_usd * data["mapping"]["months_per_year"], data)


def economic_profiles(profiles: list[dict], seed: int = 17) -> list[dict]:
    """Synthetic individual wage/support and cash spread, independent of identity/values.

    Household income is deliberately not assigned to each adult as an individual wage.
    This does not fit ACS income/rent distributions: only source levels are anchors.
    """
    data = load_calibration()
    mapping, assumptions = data["mapping"], data["scenario"]
    means = data["sources"][1]["mean_hourly_usd"]
    floor = data["sources"][2]["standard_hourly_usd"]
    rng = random.Random(f"sf-economy:{seed}")
    result = []
    for profile in profiles:
        employed = profile.get("employment_status") == "employed"
        sector = profile.get("occupation_group") or profile.get("occupation_sector")
        proxy = WAGE_PROXIES.get(sector, "all")
        low, high = assumptions["wage_multiplier_bounds"]
        multiplier = min(high, max(low, rng.lognormvariate(0, assumptions["wage_log_sigma"])))
        hourly = round(max(floor, means[proxy] * multiplier), 2) if employed else 0
        annual = round(hourly * mapping["work_hours_per_week"] * mapping["weeks_per_year"], 2)
        support = (
            0
            if employed
            else rng.choices(
                assumptions["nonlabor_annual_support_usd"],
                assumptions["nonlabor_support_weights"],
            )[0]
        )
        days = rng.choices(
            assumptions["initial_savings_days"], assumptions["initial_savings_weights"]
        )[0]
        daily = annual_usd_to_daily_credits(annual, data) * mapping["take_home_fraction"]
        support_daily = annual_usd_to_daily_credits(support, data)
        result.append(
            {
                "population_role": "resident",
                "basis": "source_level_with_scenario_spread",
                "wage_proxy": proxy,
                "hourly_gross_usd": hourly,
                "annual_gross_wage_usd": annual,
                "daily_net_wage_credits": round(daily, 2),
                "annual_nonlabor_support_usd": support,
                "daily_support_credits": round(support_daily, 2),
                "initial_savings_credits": round(max(daily + support_daily, 1) * days, 2),
                "savings_basis": "assumed liquid cash reserve, not measured wealth",
            }
        )
    return result


class SFEconomy:
    """Facade; every mutable value is in Economy.sf_state for JSON checkpointing."""

    def __init__(self, world: World) -> None:
        self.world = world

    @property
    def state(self) -> dict:
        return self.world.economy.sf_state

    @property
    def day(self) -> int:
        return int(self.world.time // self.world.day_length)

    def rent_share(self, agent: AgentState) -> float:
        ledger = self.state["agents"][agent.id]
        household = self.state["households"].get(ledger.get("household_id"))
        if not household or agent.home_id != household["home_id"]:
            return 0
        members = [
            a
            for a in self.world.agents.values()
            if a.alive
            and a.home_id == household["home_id"]
            and self.state["agents"].get(a.id, {}).get("household_id") == ledger["household_id"]
        ]
        members.sort(key=lambda a: a.id)
        cents = round(household["daily_rent_credits"] * 100)
        quotient, remainder = divmod(cents, max(1, len(members)))
        index = next((i for i, member in enumerate(members) if member.id == agent.id), 0)
        return (quotient + (index < remainder)) / 100

    def move_home(
        self, agent: AgentState, home: WorldObject, roommate_id: str | None = None
    ) -> None:
        """A voluntary move changes tenancy without erasing old debt."""
        ledger = self.state["agents"][agent.id]
        roommate = self.state["agents"].get(roommate_id, {})
        household_id = roommate.get("household_id")
        if household_id not in self.state["households"]:
            household_id = f"tenancy_{agent.id}_{self.world.event_counter}"
            self.state["households"][household_id] = {
                "home_id": home.id,
                "daily_rent_credits": float(home.metadata["rent"]),
                "monthly_rent_usd": home.metadata.get("monthly_rent_usd"),
            }
        ledger["household_id"] = household_id
        agent.home_id = home.id
        if agent.background:
            agent.background.housing_status = "shared_rental" if roommate_id else "rental"

    def shift_wage(self, agent: AgentState, target: WorldObject) -> float:
        ledger = self.state["agents"][agent.id]
        if ledger.get("work_day") != self.day:
            ledger.update(work_day=self.day, shifts_completed=0)
        limit = self.state["calibration"]["mapping"]["baseline_shifts_per_day"]
        if ledger["shifts_completed"] >= limit:
            return 0
        daily = ledger["daily_net_wage_credits"] if agent.workplace_id == target.id else 0
        daily = daily or float(target.metadata.get("daily_wage_credits", 0))
        # Allocate cents without accumulating rounding error over the two shifts.
        cents = round(daily * 100)
        index = ledger["shifts_completed"]
        return (cents // limit + (index < cents % limit)) / 100

    def record_shift(self, agent: AgentState, wage: float) -> None:
        ledger = self.state["agents"][agent.id]
        # Completion owns payment accounting, never the day-boundary routine.
        if ledger.get("work_day") != self.day:
            ledger.update(work_day=self.day, shifts_completed=0)
        ledger["shifts_completed"] += 1
        ledger["wages_received_credits"] = round(ledger["wages_received_credits"] + wage, 2)
        self.state["external_wages_credits"] = round(self.state["external_wages_credits"] + wage, 2)

    def produce_service(self, target: WorldObject) -> None:
        quantity = self.state["calibration"]["scenario"]["service_batch_units"]
        sector = target.metadata.get("sector")
        if target.kind in {"market", "cafe", "dining", "kitchen"} or sector in {
            "food_service",
            "retail",
        }:
            outlets = [
                o
                for o in self.world.objects.values()
                if o.kind in {"market", "cafe", "dining"} and self.world.urban.is_open(o)
            ]
            if outlets:
                outlet = min(outlets, key=lambda o: (o.metadata.get("stock", 0), o.id))
                outlet.metadata["stock"] = min(
                    outlet.metadata.get("stock_capacity", 100),
                    outlet.metadata.get("stock", 0) + quantity,
                )
        elif target.kind == "public_works" or sector == "public_service":
            facilities = [o for o in self.world.objects.values() if o.kind in {"toilet", "kitchen"}]
            if facilities:
                facility = min(facilities, key=lambda o: o.metadata.get("condition", 100))
                facility.metadata["condition"] = min(
                    100, facility.metadata.get("condition", 100) + 25
                )
        elif target.kind == "clinic" or sector == "healthcare":
            # A shift replenishes care capacity; using that supply requires a separate action.
            target.metadata["care_stock"] = min(30, target.metadata.get("care_stock", 0) + quantity)
        target.metadata["service_shifts_completed"] = (
            target.metadata.get("service_shifts_completed", 0) + 1
        )

    def new_day(self) -> None:
        if self.state["last_day"] >= self.day:
            return
        elapsed = self.day - self.state["last_day"]
        self.state["last_day"] = self.day
        assumptions = self.state["calibration"]["scenario"]
        for agent in self.world.agents.values():
            if not agent.alive:
                continue
            ledger = self.state["agents"][agent.id]
            support = round(ledger["daily_support_credits"] * elapsed, 2)
            agent.credits = round(agent.credits + support, 2)
            self.state["external_support_credits"] += support
            rent = self.rent_share(agent)
            rent_due = round(rent * elapsed, 2)
            prepaid = min(rent_due, ledger.get("rent_prepaid_credits", 0))
            ledger["rent_prepaid_credits"] = round(
                ledger.get("rent_prepaid_credits", 0) - prepaid, 2
            )
            owed = round(ledger["rent_debt_credits"] + rent_due - prepaid, 2)
            paid = round(min(max(0, agent.credits), owed), 2)
            agent.credits = round(max(0, agent.credits - paid), 2)
            self.world.economy.city_balance = round(self.world.economy.city_balance + paid, 2)
            ledger["rent_debt_credits"] = round(owed - paid, 2)
            ledger["unpaid_days"] = ledger["unpaid_days"] + elapsed if owed > paid else 0
            agent.rent_arrears = ledger["unpaid_days"]
            if ledger["unpaid_days"] and agent.home_id:
                agent.stress = min(100, agent.stress + min(3, ledger["unpaid_days"] / 10))
                self.world.emit(
                    "rent_warning",
                    f"{agent.name} has {ledger['rent_debt_credits']:g} credits of housing arrears.",
                    actor_id=agent.id,
                    position=agent.position,
                    radius=0,
                    payload={"private": True, "arrears_credits": ledger["rent_debt_credits"]},
                )
                if ledger["unpaid_days"] >= assumptions["housing_loss_after_unpaid_days"]:
                    agent.home_id = None
                    if agent.background:
                        agent.background.housing_status = "housing_insecure"
                    self.world.emit(
                        "housing",
                        f"{agent.name} lost their tenancy after sustained unpaid housing costs.",
                        actor_id=agent.id,
                        position=agent.position,
                        radius=0,
                        payload={"private": True, "basis": "scenario_threshold_not_legal_process"},
                    )
        self._company_day(elapsed)

    def _company_day(self, elapsed: int) -> None:
        assumptions = self.state["calibration"]["scenario"]
        for company in self.world.economy.companies.values():
            if company.closed:
                continue
            paid = min(company.treasury, assumptions["company_daily_overhead_credits"] * elapsed)
            company.treasury = round(company.treasury - paid, 2)
            company.operating_costs = round(company.operating_costs + paid, 2)
            self.world.economy.city_balance = round(self.world.economy.city_balance + paid, 2)
            viable = (
                company.treasury >= PRODUCTS[company.product]["cost"]
                or company.revenue > company.last_day_revenue
            )
            company.last_day_revenue = company.revenue
            company.insolvent_days = 0 if viable else company.insolvent_days + elapsed
            reserved = any(
                a.activity and a.activity.target_id == company.id
                for a in self.world.agents.values()
            )
            if (
                company.insolvent_days >= assumptions["company_insolvent_days_before_close"]
                and not reserved
            ):
                company.closed = True
                affected = set(company.employees)
                for agent in self.world.agents.values():
                    if agent.workplace_id == company.id:
                        agent.workplace_id = None
                        if agent.background:
                            agent.background.employment_status = "unemployed"
                            agent.background.employer_name = None
                        affected.add(agent.id)
                company.employees.clear()
                self.world.emit(
                    "company_closed",
                    f"{company.name} closed after sustained inability to fund production.",
                    target_ids=sorted(affected),
                    position=self.world.objects[company.id].position,
                    radius=100,
                    payload={"company_id": company.id},
                )
            self.world.economy.sync(company)

    def tick(self) -> None:
        # Observed closure/intervention at an assigned external employer causes actual job loss.
        for agent in self.world.agents.values():
            site = self.world.objects.get(agent.workplace_id or "")
            if agent.workplace_id and (
                site is None
                or (site.metadata.get("open") is False and not site.metadata.get("quake_damage"))
            ):
                if agent.activity and agent.activity.target_id == agent.workplace_id:
                    self.world.urban.cancel(agent)
                agent.workplace_id = None
                if agent.background:
                    agent.background.employment_status = "unemployed"
                    agent.background.employer_name = None
                self.world.emit(
                    "job_loss",
                    f"{agent.name}'s workplace is no longer operating.",
                    actor_id=agent.id,
                    position=agent.position,
                    radius=0,
                    payload={"private": True},
                )

    def context_for(self, agent: AgentState) -> dict:
        ledger = self.state["agents"][agent.id]
        rent = self.rent_share(agent)
        income = ledger["daily_support_credits"]
        if agent.workplace_id:
            income += ledger["daily_net_wage_credits"]
        return dict(
            ledger,
            liquid_savings_credits=agent.credits,
            daily_rent_share_credits=rent,
            potential_daily_income_credits=income,
            rent_to_potential_income=round(rent / income, 3) if income else None,
            daily_budget_after_rent_credits=round(income - rent, 2),
            wage_rule="Earn wages by completing at most two baseline shifts per budget day.",
        )

    def report(self) -> dict:
        agents = [a for a in self.world.agents.values() if a.alive]
        return {
            "sources": self.state["calibration"]["sources"],
            "mapping": self.state["calibration"]["mapping"],
            "assumptions": self.state["calibration"]["scenario"],
            "resident_agents": len(agents),
            "inbound_commuter_agents": 0,
            "resident_workers": sum(a.workplace_id is not None for a in agents),
            "synthetic_households": len(
                {self.state["agents"][a.id].get("household_id") for a in agents if a.home_id}
            ),
            "housing_insecure_agents": sum(not a.home_id or a.rent_arrears > 0 for a in agents),
            "rent_arrears_credits": round(
                sum(self.state["agents"][a.id]["rent_debt_credits"] for a in agents), 2
            ),
            "external_wages_credits": self.state["external_wages_credits"],
            "external_support_credits": round(self.state["external_support_credits"], 2),
            "denominator_note": (
                "Physical sample counts; household, citywide PIT and metro jobs are separate. "
                "No resident weights multiply money or service actions."
            ),
        }


def apply_sf_economy(world: World, seed: int = 17) -> SFEconomy:
    """Call after SF placement; idempotent and never resets an existing ledger."""
    runtime = SFEconomy(world)
    world.sf_economy = runtime
    if getattr(world.economy, "sf_state", None):
        return runtime
    data = load_calibration()
    rng = random.Random(f"sf-households:{seed}")
    assumptions, mapping = data["scenario"], data["mapping"]
    agents = list(world.agents.values())
    profiles = [a.background.model_dump() if a.background else {} for a in agents]
    economics = economic_profiles(profiles, seed)
    world.economy.sf_state = {
        "calibration": data,
        "agents": {},
        "households": {},
        "last_day": runtime.day,
        "external_wages_credits": 0.0,
        "external_support_credits": 0.0,
    }
    for agent, profile in zip(agents, economics, strict=True):
        agent.credits = profile["initial_savings_credits"]
        runtime.state["agents"][agent.id] = dict(
            profile,
            household_id=None,
            rent_debt_credits=0.0,
            unpaid_days=0,
            wages_received_credits=0.0,
            work_day=runtime.day,
            shifts_completed=0,
            rent_prepaid_credits=0.0,
        )
    for home in [o for o in world.objects.values() if o.kind == "home"]:
        low, high = assumptions["monthly_rent_bounds_usd"]
        monthly = round(
            min(
                high,
                max(
                    low,
                    data["sources"][0]["measures"]["median_gross_monthly_rent_usd"]
                    * rng.lognormvariate(0, assumptions["rent_log_sigma"]),
                ),
            ),
            2,
        )
        daily = round(monthly_usd_to_daily_credits(monthly, data), 2)
        home.metadata.update(
            rent=daily,
            monthly_rent_usd=monthly,
            rent_basis="per synthetic household; citywide anchor with assumed spread",
        )
        residents = [a for a in agents if a.home_id == home.id]
        rng.shuffle(residents)
        while residents:
            number = rng.choices(
                assumptions["household_adults"], assumptions["household_adult_weights"]
            )[0]
            members, residents = residents[:number], residents[number:]
            household_id = f"household_{len(runtime.state['households']) + 1:04d}"
            runtime.state["households"][household_id] = {
                "home_id": home.id,
                "monthly_rent_usd": monthly,
                "daily_rent_credits": daily,
            }
            for agent in members:
                runtime.state["agents"][agent.id]["household_id"] = household_id
                if agent.background:
                    agent.background.housing_status = (
                        "shared_rental" if len(members) > 1 else "rental"
                    )
    food_sites = [o for o in world.objects.values() if o.kind in {"market", "cafe", "dining"}]
    daily_food = math.ceil(len(agents) * assumptions["external_food_units_per_resident_day"])
    for index, site in enumerate(food_sites):
        supply = daily_food // len(food_sites) + (index < daily_food % len(food_sites))
        site.metadata.update(
            daily_external_stock=supply,
            stock=max(2, supply * 2),
            stock_capacity=max(12, supply * 4),
            price=0
            if site.kind == "dining"
            else assumptions["food_price_usd"] / mapping["usd_per_credit"],
        )
    for site in world.objects.values():
        if "wage" in site.metadata:
            mean = data["sources"][1]["mean_hourly_usd"].get(
                WAGE_PROXIES.get(site.metadata.get("sector")), 24.97
            )
            daily = round(
                annual_usd_to_daily_credits(mean * 2080, data) * mapping["take_home_fraction"], 2
            )
            site.metadata.update(
                daily_wage_credits=daily,
                wage=round(daily / 2, 2),
                wage_basis="USD proxy converted to two daily baseline shifts",
            )
        if site.kind == "dining":
            site.metadata["hours"] = [0, 24]
        if site.kind == "clinic":
            site.metadata.update(care_stock=2, care_action="rest", care_basis="scenario care units")
        if site.kind in {"toilet", "dining", "kitchen"}:
            site.metadata["capacity"] = max(2, math.ceil(len(agents) / 10))
    for agent in agents:
        # Basic assistance and paid open shifts are known resources, never hidden survival gates.
        for site in world.objects.values():
            if (
                site.id in {agent.home_id, agent.workplace_id}
                or site.kind in {"dining", "toilet", "shelter", "clinic"}
                or site.metadata.get("employment_basis") == "scenario_open_shift"
            ):
                agent.known_places[site.id] = world.urban.describe(site)
    if world.population_report is not None:
        world.population_report["economy_calibration"] = runtime.report()
    return runtime
