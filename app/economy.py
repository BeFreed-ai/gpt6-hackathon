"""Fictional, in-world companies and bilateral contracts. No external money APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.models import ActionIntent, ActionTerms, ActionType, AgentState, WorldObject

if TYPE_CHECKING:
    from app.world import World


PRODUCTS = {
    "meals": {"kind": "food", "name": "Fresh Meal", "cost": 2, "quantity": 3},
    "coats": {"kind": "coat", "name": "Fog Jacket", "cost": 3, "quantity": 1},
    "routes": {"kind": "route_guide", "name": "Neighborhood Route App", "cost": 1, "quantity": 2},
}


class Company(BaseModel):
    id: str
    name: str
    purpose: str
    founder_id: str
    product: str
    treasury: float
    price: float
    shares: dict[str, float]
    employees: dict[str, float] = Field(default_factory=dict)
    stock: int = 0
    revenue: float = 0
    raised: float = 0
    payroll: float = 0
    produced: int = 0
    cap_revision: int = 0
    operating_costs: float = 0
    insolvent_days: int = 0
    last_day_revenue: float = 0
    closed: bool = False


class Offer(BaseModel):
    id: str
    kind: str
    sender_id: str
    recipient_id: str
    subject_id: str
    amount: float
    equity: float = 0
    cap_revision: int = 0
    expires_at: float
    status: str = "pending"


class Economy:
    def __init__(self, world: World) -> None:
        self.world = world
        self.companies: dict[str, Company] = {}
        self.offers: dict[str, Offer] = {}
        self.city_balance = 0.0

    def fail(self, agent: AgentState, intent: ActionIntent, reason: str) -> bool:
        self.world._fail_action(agent, intent, reason)
        return True  # Failure has already been recorded, not an accepted action.

    def resolve_target(self, target_id: str) -> WorldObject | None:
        offer = self.offers.get(target_id)
        sender = self.world.agents.get(offer.sender_id) if offer else None
        if not offer or not sender or not sender.alive:
            return None
        return WorldObject(
            id=offer.id,
            kind="offer",
            name=f"{sender.name}'s offer",
            position=sender.position.model_copy(),
        )

    def execute(self, agent: AgentState, intent: ActionIntent) -> bool | None:
        action = intent.action
        terms = intent.terms or ActionTerms()
        if action in {ActionType.PAY_DIVIDEND, ActionType.SET_PRICE}:
            company = self.companies.get(intent.target_id or "")
            if not company or company.closed or company.founder_id != agent.id:
                return self.fail(agent, intent, "Only the founder can manage this company.")
            site = self.world.objects[company.id]
            if self.world._approach(agent, intent, site, 55):
                return True
            if action == ActionType.SET_PRICE:
                if not terms.price or terms.price < 0.01:
                    return self.fail(agent, intent, "Set a price of at least 0.01 credits.")
                company.price = round(terms.price, 2)
                result = f"set {company.name}'s price to {company.price:g}"
            else:
                amount = round(terms.amount or 0, 2)
                if amount <= 0 or amount > company.treasury:
                    return self.fail(
                        agent, intent, "The dividend must fit available company funds."
                    )
                # Allocate whole cents, giving the rounding remainder to the last holder.
                cents = round(amount * 100)
                remaining = cents
                owners = list(company.shares.items())
                for index, (owner_id, share) in enumerate(owners):
                    payout = (
                        min(remaining, round(cents * share))
                        if index < len(owners) - 1
                        else remaining
                    )
                    self.world.agents[owner_id].credits = round(
                        self.world.agents[owner_id].credits + payout / 100, 2
                    )
                    remaining -= payout
                company.treasury = round(company.treasury - amount, 2)
                result = f"distributed {amount:g} credits from {company.name} to its shareholders"
            self.sync(company)
            agent.current_action = result
            self.world.emit(
                "company_update",
                f"{agent.name} {result}.",
                actor_id=agent.id,
                target_ids=list(company.shares),
                position=site.position,
                radius=0,
            )
            return True
        if action == ActionType.FOUND_COMPANY:
            site = self.world.objects.get(intent.target_id or "")
            if not site or site.kind not in {"launchpad", "kitchen", "market", "cafe", "tech"}:
                return self.fail(agent, intent, "Choose a known launchpad, kitchen or workplace.")
            if any(c.founder_id == agent.id and not c.closed for c in self.companies.values()):
                return self.fail(agent, intent, "Manage your existing company first.")
            amount = round(terms.amount or 0, 2)
            if not (terms.name or "").strip() or terms.product not in PRODUCTS or amount < 2:
                return self.fail(
                    agent,
                    intent,
                    "Supply a name, product (meals/coats/routes), and at least 2 seed credits.",
                )
            if agent.credits < amount:
                return self.fail(
                    agent, intent, "Not enough personal credits for that seed investment."
                )
            if self.world._approach(agent, intent, site, 55):
                return True
            count = sum(c.founder_id != agent.id for c in self.companies.values())
            stall = self.world._add_object(
                "company",
                terms.name.strip(),
                max(25, min(1375, site.position.x + 55 + (count % 3) * 38)),
                max(25, min(795, site.position.y + 65 + (count // 3) * 30)),
                65,
                48,
            )
            company = Company(
                id=stall.id,
                name=stall.name,
                purpose=terms.purpose or terms.name,
                founder_id=agent.id,
                product=terms.product,
                treasury=amount,
                price=max(0.01, round(terms.price or 3, 2)),
                shares={agent.id: 1.0},
            )
            self.companies[company.id] = company
            agent.credits = round(agent.credits - amount, 2)
            self.sync(company)
            agent.known_places[stall.id] = self.world.urban.describe(stall)
            agent.current_action = f"founded {company.name}"
            self.world.emit(
                "company_founded",
                f"{agent.name} founded {company.name}: {company.purpose}.",
                actor_id=agent.id,
                position=stall.position,
                radius=160,
                payload={"company_id": company.id, "seed": amount},
            )
            return True
        if action in {ActionType.OFFER_INVESTMENT, ActionType.OFFER_JOB, ActionType.OFFER_HOUSING}:
            return self.propose(agent, intent, terms)
        if action in {ActionType.ACCEPT_OFFER, ActionType.REJECT_OFFER}:
            return self.respond(agent, intent)
        return None

    def propose(self, agent: AgentState, intent: ActionIntent, terms: ActionTerms) -> bool:
        other = self.world.agents.get(intent.target_id or "")
        if not other or not other.alive or other.id == agent.id:
            return self.fail(agent, intent, "Choose another known living citizen.")
        company = self.companies.get(terms.company_id or "")
        kind = {
            ActionType.OFFER_INVESTMENT: "investment",
            ActionType.OFFER_JOB: "job",
            ActionType.OFFER_HOUSING: "housing",
        }[intent.action]
        amount = round(terms.amount or 0, 2)
        if kind == "housing":
            if not agent.home_id:
                return self.fail(agent, intent, "You need a home before inviting a roommate.")
            subject_id = agent.home_id
        else:
            if not company or company.closed:
                return self.fail(agent, intent, "Supply a company_id you know.")
            subject_id = company.id
            if kind == "job":
                if company.founder_id != agent.id or not terms.wage or terms.wage < 0.01:
                    return self.fail(
                        agent,
                        intent,
                        "Only the founder can offer a positive wage per completed batch.",
                    )
                amount = round(terms.wage, 2)
            elif (
                company.founder_id not in {agent.id, other.id} or not terms.equity or amount < 0.01
            ):
                return self.fail(
                    agent,
                    intent,
                    "An investment needs founder and investor, positive credits "
                    "and post-money equity between 0 and 1.",
                )
        if self.world._approach(agent, intent, other, 100):
            return True
        for old in self.offers.values():
            if (
                old.status == "pending"
                and old.subject_id == subject_id
                and old.kind == kind
                and {old.sender_id, old.recipient_id} == {agent.id, other.id}
            ):
                old.status = "superseded"
        offer = Offer(
            id=f"offer_{len(self.offers) + 1:04d}",
            kind=kind,
            sender_id=agent.id,
            recipient_id=other.id,
            subject_id=subject_id,
            amount=amount,
            equity=terms.equity or 0,
            cap_revision=company.cap_revision if company else 0,
            expires_at=self.world.time + 180,
        )
        self.offers[offer.id] = offer
        detail = (
            f"{amount:g} credits for {offer.equity:.0%} post-money equity in {company.name}"
            if kind == "investment"
            else f"{amount:g} credits per completed production batch at {company.name}"
            if kind == "job"
            else "a shared room with rent divided among residents"
        )
        agent.current_action = f"offering {kind} terms to {other.name}"
        self.world.emit(
            "offer",
            f"{agent.name} offered {other.name} {detail}. Awaiting consent.",
            actor_id=agent.id,
            target_ids=[other.id],
            position=agent.position,
            radius=0,
            payload={"offer_id": offer.id, "terms": offer.model_dump(), "private": True},
        )
        return True

    def respond(self, agent: AgentState, intent: ActionIntent) -> bool:
        offer = self.offers.get(intent.target_id or "")
        if not offer or offer.recipient_id != agent.id or offer.status != "pending":
            return self.fail(agent, intent, "No pending offer addressed to you with that ID.")
        if self.world.time >= offer.expires_at:
            offer.status = "expired"
            return self.fail(agent, intent, "The offer expired; request new terms.")
        target = self.resolve_target(offer.id)
        if not target:
            return self.fail(agent, intent, "The proposer is no longer available.")
        if self.world._approach(agent, intent, target, 100):
            return True
        if intent.action == ActionType.REJECT_OFFER:
            offer.status = "rejected"
        elif offer.kind == "housing":
            sender = self.world.agents[offer.sender_id]
            home = self.world.objects.get(offer.subject_id)
            if (
                sender.home_id != offer.subject_id
                or not home
                or not self.world.urban.room_available(home)
            ):
                return self.fail(agent, intent, "The shared room is no longer available.")
            calibration = getattr(self.world, "sf_economy", None)
            if calibration:
                calibration.move_home(agent, home, sender.id)
            else:
                agent.home_id = home.id
                agent.rent_arrears = 0
            offer.status = "accepted"
        else:
            company = self.companies.get(offer.subject_id)
            if not company or company.closed:
                return self.fail(agent, intent, "The company no longer exists.")
            if offer.kind == "investment":
                if company.cap_revision != offer.cap_revision:
                    offer.status = "stale"
                    return self.fail(agent, intent, "Ownership changed; negotiate a new offer.")
                investor_id = (
                    offer.recipient_id if offer.sender_id == company.founder_id else offer.sender_id
                )
                investor = self.world.agents[investor_id]
                if not investor.alive or investor.credits < offer.amount:
                    return self.fail(agent, intent, "The investor no longer has enough credits.")
                investor.credits = round(investor.credits - offer.amount, 2)
                company.treasury = round(company.treasury + offer.amount, 2)
                company.raised = round(company.raised + offer.amount, 2)
                company.shares = {
                    key: value * (1 - offer.equity) for key, value in company.shares.items()
                }
                company.shares[investor_id] = company.shares.get(investor_id, 0) + offer.equity
                company.cap_revision += 1
            else:
                company.employees[agent.id] = offer.amount
                if getattr(self.world, "sf_economy", None):
                    agent.workplace_id = company.id
                    if agent.background:
                        agent.background.employment_status = "employed"
                        agent.background.employer_name = company.name
            offer.status = "accepted"
            self.sync(company)
        agent.current_action = f"{offer.status} {offer.kind} offer"
        self.world.emit(
            "agreement",
            f"{agent.name} {offer.status} the {offer.kind} offer "
            f"from {self.world.agents[offer.sender_id].name}.",
            actor_id=agent.id,
            target_ids=[offer.sender_id],
            position=agent.position,
            radius=0,
            payload={"offer_id": offer.id, "status": offer.status, "private": True},
        )
        return True

    def sync(self, company: Company) -> None:
        self.world.objects[company.id].metadata.update(
            {
                "founder_id": company.founder_id,
                "purpose": company.purpose,
                "product": company.product,
                "price": company.price,
                "stock": company.stock,
                "produced": company.produced,
                "revenue": company.revenue,
                "open": not company.closed
                and not self.world.objects[company.id].metadata.get("quake_damage"),
                "closed": company.closed,
                "operating_costs": company.operating_costs,
                "insolvent_days": company.insolvent_days,
            }
        )

    def context_for(self, agent: AgentState) -> dict:
        offers = [
            o.model_dump()
            for o in self.offers.values()
            if agent.id in {o.sender_id, o.recipient_id}
        ]
        owned = [
            c.model_dump()
            for c in self.companies.values()
            if agent.id in c.shares or agent.id in c.employees
        ]
        return {
            "my_businesses": owned,
            "my_offers": offers,
            "product_recipes": PRODUCTS,
            "credits_are_fictional": True,
        }

    def tick(self) -> None:
        calibration = getattr(self.world, "sf_economy", None)
        if calibration:
            calibration.tick()
        for offer in self.offers.values():
            if offer.status == "pending" and self.world.time >= offer.expires_at:
                offer.status = "expired"
