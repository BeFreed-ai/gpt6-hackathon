from pathlib import Path

import pytest

from app.models import ActionIntent, ActionTerms, ActionType, AgentDecision, Vec2
from app.store import EventStore
from app.world import World


@pytest.fixture
def world(tmp_path: Path):
    store = EventStore(str(tmp_path / "economy.db"))
    world = World(store, agent_count=4)
    world.next_city_event = 100000
    for agent in world.agents.values():
        agent.position = Vec2(x=1190, y=125)
        agent.credits = 100
    yield world
    store.close()


def act(world, agent, action, target=None, **terms):
    world.apply_decision(
        agent.id,
        AgentDecision(
            intent=ActionIntent(
                action=action,
                target_id=target,
                terms=ActionTerms(**terms) if terms else None,
            )
        ),
    )


def advance(world, seconds=20):
    for _ in range(seconds * 10):
        world.tick(0.1)


def found(world, product="meals"):
    founder = world.agents["yellow_01"]
    site = next(o for o in world.objects.values() if o.kind == "launchpad")
    act(
        world,
        founder,
        ActionType.FOUND_COMPANY,
        site.id,
        name="Fog Lunch Club",
        purpose="Deliver affordable meals",
        product=product,
        amount=10,
        price=3,
    )
    return next(iter(world.economy.companies.values()))


def total_money(world):
    return (
        sum(a.credits for a in world.agents.values())
        + sum(c.treasury for c in world.economy.companies.values())
        + sum(
            a.activity.reserved_credits + a.activity.wage
            for a in world.agents.values()
            if a.activity and a.activity.target_id in world.economy.companies
        )
        + world.economy.city_balance
    )


def test_company_seed_is_transferred_not_created(world):
    before = total_money(world)
    company = found(world)
    assert company.treasury == 10
    assert world.agents[company.founder_id].credits == 90
    assert company.shares == {company.founder_id: 1}
    assert total_money(world) == pytest.approx(before)


def test_investment_requires_consent_and_dilutes_existing_ownership(world):
    company = found(world)
    founder, investor, _, _ = world.agents.values()
    before = total_money(world)
    act(
        world,
        founder,
        ActionType.OFFER_INVESTMENT,
        investor.id,
        company_id=company.id,
        amount=20,
        equity=0.25,
    )
    offer = list(world.economy.offers.values())[-1]
    assert company.treasury == 10 and investor.credits == 100
    act(world, investor, ActionType.ACCEPT_OFFER, offer.id)
    assert offer.status == "accepted"
    assert company.treasury == 30 and investor.credits == 80
    assert company.shares == {founder.id: 0.75, investor.id: 0.25}
    act(world, investor, ActionType.ACCEPT_OFFER, offer.id)
    assert company.treasury == 30
    assert total_money(world) == pytest.approx(before)


def test_dividends_follow_ownership_and_cannot_spend_reserved_payroll(world):
    company = found(world)
    founder, investor, _, _ = world.agents.values()
    act(
        world,
        founder,
        ActionType.OFFER_INVESTMENT,
        investor.id,
        company_id=company.id,
        amount=20,
        equity=0.25,
    )
    act(world, investor, ActionType.ACCEPT_OFFER, list(world.economy.offers)[-1])
    founder.position = world.objects[company.id].position.model_copy()
    before = total_money(world)
    act(world, founder, ActionType.PAY_DIVIDEND, company.id, amount=8)
    assert founder.credits == 96 and investor.credits == 82 and company.treasury == 22
    assert total_money(world) == pytest.approx(before)
    investor.position = founder.position.model_copy()
    act(world, investor, ActionType.PAY_DIVIDEND, company.id, amount=22)
    assert company.treasury == 22
    act(world, founder, ActionType.SET_PRICE, company.id, price=4.5)
    assert company.price == 4.5
    company.employees[investor.id] = 2
    act(world, investor, ActionType.WORK, company.id)
    assert company.treasury == 18
    act(world, founder, ActionType.PAY_DIVIDEND, company.id, amount=22)
    assert company.treasury == 18 and "available" in founder.last_action_result
    assert total_money(world) == pytest.approx(before)


def test_overhearing_does_not_abort_travel_but_direct_speech_does(world):
    speaker, recipient, walker, _ = world.agents.values()
    act(world, walker, ActionType.MOVE, None)
    walker.action_target = Vec2(x=1300, y=180)
    world.emit(
        "speech",
        "A private lunch invitation",
        actor_id=speaker.id,
        target_ids=[recipient.id],
        position=speaker.position,
        radius=115,
    )
    assert walker.action_target is not None and walker.inbox
    world.emit(
        "speech",
        "Will you join us?",
        actor_id=speaker.id,
        target_ids=[walker.id],
        position=speaker.position,
        radius=115,
    )
    assert walker.action_target is None


def test_private_offer_is_not_overheard_even_at_same_position(world):
    company = found(world)
    founder, investor, stranger, _ = world.agents.values()
    before = len(stranger.memories)
    act(
        world,
        founder,
        ActionType.OFFER_INVESTMENT,
        investor.id,
        company_id=company.id,
        amount=20,
        equity=0.25,
    )
    assert len(stranger.memories) == before


def test_offer_private_and_cannot_be_accepted_by_third_party(world):
    company = found(world)
    founder, investor, stranger, _ = world.agents.values()
    stranger.position = Vec2(x=30, y=780)
    act(
        world,
        founder,
        ActionType.OFFER_INVESTMENT,
        investor.id,
        company_id=company.id,
        amount=20,
        equity=0.25,
    )
    offer = list(world.economy.offers.values())[-1]
    assert not world.context_for(stranger)["economy"]["my_offers"]
    assert not world.context_for(stranger)["economy"]["my_businesses"]
    act(world, stranger, ActionType.ACCEPT_OFFER, offer.id)
    assert offer.status == "pending" and company.treasury == 10


def test_changed_cap_table_invalidates_other_pending_round(world):
    company = found(world)
    founder, first, second, _ = world.agents.values()
    for investor in (first, second):
        act(
            world,
            founder,
            ActionType.OFFER_INVESTMENT,
            investor.id,
            company_id=company.id,
            amount=20,
            equity=0.25,
        )
    offers = list(world.economy.offers.values())
    act(world, first, ActionType.ACCEPT_OFFER, offers[0].id)
    act(world, second, ActionType.ACCEPT_OFFER, offers[1].id)
    assert offers[1].status == "stale"
    assert second.credits == 100
    assert sum(company.shares.values()) == pytest.approx(1)


def test_counteroffer_supersedes_old_terms_and_rejection_moves_no_money(world):
    company = found(world)
    founder, investor, _, _ = world.agents.values()
    act(
        world,
        founder,
        ActionType.OFFER_INVESTMENT,
        investor.id,
        company_id=company.id,
        amount=20,
        equity=0.25,
    )
    old = list(world.economy.offers.values())[-1]
    act(
        world,
        investor,
        ActionType.OFFER_INVESTMENT,
        founder.id,
        company_id=company.id,
        amount=15,
        equity=0.2,
    )
    new = list(world.economy.offers.values())[-1]
    assert old.status == "superseded"
    act(world, founder, ActionType.REJECT_OFFER, new.id)
    assert new.status == "rejected"
    assert investor.credits == 100 and company.treasury == 10


def test_offer_expiry_and_insufficient_investor_funds(world):
    company = found(world)
    founder, investor, _, _ = world.agents.values()
    act(
        world,
        founder,
        ActionType.OFFER_INVESTMENT,
        investor.id,
        company_id=company.id,
        amount=150,
        equity=0.25,
    )
    offer = list(world.economy.offers.values())[-1]
    act(world, investor, ActionType.ACCEPT_OFFER, offer.id)
    assert "enough credits" in investor.last_action_result
    world.time = offer.expires_at
    world.economy.tick()
    act(world, investor, ActionType.ACCEPT_OFFER, offer.id)
    assert offer.status == "expired" and company.treasury == 10


def test_paid_production_sale_and_food_use_conserve_money(world):
    company = found(world)
    founder, worker, buyer, _ = world.agents.values()
    before = total_money(world)
    act(world, founder, ActionType.OFFER_JOB, worker.id, company_id=company.id, wage=2)
    offer = list(world.economy.offers.values())[-1]
    act(world, worker, ActionType.ACCEPT_OFFER, offer.id)
    worker.position = world.objects[company.id].position.model_copy()
    act(world, worker, ActionType.WORK, company.id)
    assert worker.activity and company.stock == 0 and worker.credits == 100
    assert total_money(world) == pytest.approx(before)
    advance(world, 15)
    assert worker.credits == 102 and company.stock == 3
    buyer.position = worker.position.model_copy()
    act(world, buyer, ActionType.BUY, company.id)
    assert company.stock == 2 and company.revenue == 3 and company.treasury == 9
    buyer.hunger = 80
    act(world, buyer, ActionType.EAT, buyer.inventory[0])
    assert buyer.hunger == 32
    assert total_money(world) == pytest.approx(before)


def test_unaccepted_job_and_underfunded_payroll_cannot_produce(world):
    company = found(world)
    _, worker, _, _ = world.agents.values()
    worker.position = world.objects[company.id].position.model_copy()
    act(world, worker, ActionType.WORK, company.id)
    assert worker.activity is None and "job offer" in worker.last_action_result
    company.employees[worker.id] = 20
    act(world, worker, ActionType.WORK, company.id)
    assert worker.activity is None and company.treasury == 10 and company.stock == 0


def test_interrupted_production_refunds_reservations(world):
    company = found(world)
    founder = world.agents[company.founder_id]
    founder.position = world.objects[company.id].position.model_copy()
    act(world, founder, ActionType.WORK, company.id)
    assert company.treasury == 8
    world.emit("lightning", "Lightning nearby", position=founder.position, radius=100)
    assert founder.activity is None and company.treasury == 10
    advance(world, 15)
    assert company.stock == 0


def test_accept_offer_approaches_sender_without_losing_offer_id(world):
    company = found(world)
    founder, investor, _, _ = world.agents.values()
    act(
        world,
        founder,
        ActionType.OFFER_INVESTMENT,
        investor.id,
        company_id=company.id,
        amount=20,
        equity=0.25,
    )
    offer = list(world.economy.offers.values())[-1]
    investor.position = Vec2(x=900, y=125)
    act(world, investor, ActionType.ACCEPT_OFFER, offer.id)
    assert investor.pending_intent.target_id == offer.id
    advance(world, 10)
    assert offer.status == "accepted"


def test_facility_hours_capacity_and_completion(world):
    first, second, _, _ = world.agents.values()
    toilet = next(o for o in world.objects.values() if o.kind == "toilet")
    first.position = second.position = toilet.position.model_copy()
    first.bladder = 80
    act(world, first, ActionType.USE_TOILET, toilet.id)
    assert first.bladder == 80
    act(world, second, ActionType.USE_TOILET, toilet.id)
    assert second.activity is None and "full" in second.last_action_result
    advance(world, 5)
    assert first.bladder < 6 and first.activity is None
    toilet.metadata["hours"] = [12, 14]
    act(world, second, ActionType.USE_TOILET, toilet.id)
    assert "closed" in second.last_action_result


def test_cooking_reserves_inputs_and_creates_actual_meals(world):
    first = world.agents["yellow_01"]
    kitchen = next(o for o in world.objects.values() if o.kind == "kitchen")
    first.position = kitchen.position.model_copy()
    for _ in range(2):
        world.urban.create_carried(first, "food", "Ingredient")
    act(world, first, ActionType.COOK, kitchen.id)
    assert not first.inventory and len(first.activity.inputs) == 2
    advance(world, 11)
    assert len(first.inventory) == 3
    assert all(world.urban.carried[key].name == "Shared Kitchen Meal" for key in first.inventory)


def test_goods_keep_identity_when_dropped_and_picked_up(world):
    first, second, _, _ = world.agents.values()
    world.urban.create_carried(first, "coat", "Warm Jacket")
    key = first.inventory[0]
    act(world, first, ActionType.DROP, key)
    assert world.objects[key].kind == "coat"
    act(world, second, ActionType.TAKE, key)
    act(world, second, ActionType.USE_ITEM, key)
    assert second.wearing_coat and key not in world.urban.carried


def test_housing_requires_invitation_and_respects_capacity(world):
    host, guest, third, _ = world.agents.values()
    home = world.objects[host.home_id]
    guest.position = home.position.model_copy()
    act(world, guest, ActionType.SEEK_SHELTER, home.id)
    assert "requires" in guest.last_action_result
    host.position = guest.position.model_copy()
    act(world, host, ActionType.OFFER_HOUSING, guest.id)
    offer = list(world.economy.offers.values())[-1]
    act(world, guest, ActionType.ACCEPT_OFFER, offer.id)
    assert guest.home_id == home.id
    third.position = home.position.model_copy()
    act(world, third, ActionType.RENT_HOME, home.id)
    assert "vacant" in third.last_action_result


def test_thinking_does_not_consume_body_budget_and_memory_snapshots_are_stable(world):
    first = world.agents["yellow_01"]
    first.hunger = 80
    first.is_thinking = True
    place = next(o for o in world.objects.values() if o.kind == "market")
    first.position = place.position.model_copy()
    context = world.context_for(first)
    observed = next(o for o in context["nearby_objects"] if o["id"] == place.id)
    place.metadata["stock"] = 0
    assert observed["metadata"]["stock"] == 12
    advance(world, 20)
    assert first.hunger == 80
