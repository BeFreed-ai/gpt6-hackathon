"""Record every supported action and key physical events using isolated engine fixtures."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.models import ActionIntent, ActionTerms, ActionType, AgentDecision, Vec2
from app.store import EventStore
from app.world import World

GROUPS = {
    "Social": "talk shout broadcast give help attack offer_housing accept_offer reject_offer address_player",
    "Daily life": "move wait take drop eat rest use_toilet seek_shelter buy cook use_item rent_home",
    "Work & trade": "work found_company offer_investment offer_job pay_dividend set_price",
    "City care": "clean repair report build demolish salvage",
}


class Scene:
    def __init__(self, path):
        self.store = EventStore(str(path))
        self.world = World(self.store, agent_count=3, seed=17)
        self.world.next_city_event = float("inf")
        self.world.objects.clear()
        self.world.events.clear()
        self.world.terrain.tiles.clear()
        self.world.terrain.protected_cells.clear()
        for x in range(30, 44):
            self.world.terrain.tiles[f"{x},19"] = {"kind":"road","builder_id":None}
        self.people = list(self.world.agents.values())
        for i, (a, name) in enumerate(zip(self.people, ("Alex Rivera", "Mira Chen", "Eli Brooks"), strict=True)):
            a.name=name; a.position=Vec2(x=700+i*35,y=390); a.home_id=None; a.workplace_id=None
            a.memories.clear(); a.inbox.clear(); a.known_places.clear(); a.known_terrain.clear()
            a.credits=100; a.hunger=75; a.energy=45; a.bladder=60; a.next_think_at=10000
            a.speech=None; a.current_action="observing"; a.last_reaction=""
        self.actor, self.other, self.witness = self.people
        self.frames=[]

    def item(self, kind, name=None, **metadata):
        return self.world._add_object(kind,name or kind.replace('_',' ').title(),700,355,35,28,metadata=metadata)

    def carry(self, kind="food"):
        self.world.urban.create_carried(self.actor,kind,{"food":"Apple","material":"Wood","coat":"Coat","route_guide":"Route guide"}[kind])
        return self.actor.inventory[-1]

    def act(self, actor, action, **kwargs):
        self.world.apply_decision(actor.id, AgentDecision(intent=ActionIntent(action=action,**kwargs)))
        if actor.last_action_result.startswith("Failed"):
            raise AssertionError(actor.last_action_result)

    def company(self):
        site=self.item("launchpad","Workshop")
        self.act(self.actor,ActionType.FOUND_COMPANY,target_id=site.id,
                 terms=ActionTerms(name="Neighborhood Kitchen",product="meals",amount=30,price=3))
        company=next(iter(self.world.economy.companies.values()))
        return company

    def capture(self, label):
        snapshot=self.world.snapshot("local")
        # Observer facts, not instructions or extra knowledge passed to any agent.
        snapshot["demo_details"]={a.id:{"credits":a.credits,"hunger":a.hunger,"energy":a.energy,
            "bladder":a.bladder,"health":a.health,"home":a.home_id,"workplace":a.workplace_id,
            "bag":[self.world.urban.carried[k].name for k in a.inventory],
            "coat":a.wearing_coat,"activity":a.activity.model_dump(mode="json") if a.activity else None,
            "action_result":a.last_action_result} for a in self.people}
        self.frames.append({"title":label,"state":snapshot})

    def finish(self):
        elapsed=0
        while any(a.activity or a.action_target for a in self.people):
            self.world.tick(.25);elapsed+=.25
            if elapsed in {.5,1,2,4,8,12,16,20}:
                self.capture("Executing the chosen action")
            if elapsed>35:
                raise AssertionError("Action did not complete")
        if self.actor.last_action_result.startswith("Failed"):
            raise AssertionError(self.actor.last_action_result)
        self.capture("Result")


def action_case(scene, action):
    s=scene; a=s.actor; b=s.other; kw={}; selected=a
    if action==ActionType.MOVE: kw={"destination":Vec2(x=790,y=390)}
    elif action in {ActionType.TALK,ActionType.SHOUT,ActionType.BROADCAST,ActionType.ADDRESS_PLAYER}:
        kw={"message":"Would anyone like to share lunch by the workshop?"}
        if action==ActionType.TALK: kw["target_id"]=b.id
        if action==ActionType.BROADCAST: s.item("radio","Neighborhood Radio",coverage_radius=120)
    elif action==ActionType.TAKE:
        food=s.item("food","Apple");kw={"target_id":food.id}
    elif action in {ActionType.EAT,ActionType.DROP,ActionType.GIVE,ActionType.USE_ITEM}:
        key=s.carry("coat" if action==ActionType.USE_ITEM else "food")
        kw={"target_id":b.id,"terms":ActionTerms(item_id=key)} if action==ActionType.GIVE else {"target_id":key}
    elif action in {ActionType.HELP,ActionType.ATTACK}:
        b.health=65;kw={"target_id":b.id}
    elif action in {ActionType.CLEAN,ActionType.REPORT}:
        target=s.item("waste","Street Waste",created_at=0);kw={"target_id":target.id}
    elif action==ActionType.REPAIR:
        target=s.item("workplace","Damaged workshop",quake_damage="fixture",structural_integrity=70,condition=70,open=False,damage_state="damaged")
        kw={"target_id":target.id}
    elif action==ActionType.WORK:
        target=s.item("workplace","Neighborhood Workshop",wage=8,capacity=2);a.workplace_id=target.id;kw={"target_id":target.id}
    elif action==ActionType.USE_TOILET:
        target=s.item("toilet","Public Restroom",condition=100,capacity=1);a.bladder=90;kw={"target_id":target.id}
    elif action in {ActionType.SEEK_SHELTER,ActionType.RENT_HOME,ActionType.OFFER_HOUSING,ActionType.ACCEPT_OFFER,ActionType.REJECT_OFFER}:
        home=s.item("home","Shared Home",rent=4,beds=3,capacity=3)
        if action!=ActionType.RENT_HOME:a.home_id=home.id
        if action==ActionType.OFFER_HOUSING: kw={"target_id":b.id}
        elif action in {ActionType.ACCEPT_OFFER,ActionType.REJECT_OFFER}:
            s.act(a,ActionType.OFFER_HOUSING,target_id=b.id)
            selected=b;kw={"target_id":list(s.world.economy.offers)[-1]}
        else:kw={"target_id":home.id}
    elif action==ActionType.BUY:
        shop=s.item("market","Market Stall",stock=8,price=3);kw={"target_id":shop.id}
    elif action==ActionType.COOK:
        kitchen=s.item("kitchen","Shared Kitchen",capacity=2);s.carry();s.carry();kw={"target_id":kitchen.id}
    elif action==ActionType.SALVAGE:
        depot=s.item("depot","Reuse Depot",stock=8,capacity=2);kw={"target_id":depot.id}
    elif action==ActionType.FOUND_COMPANY:
        site=s.item("launchpad","Workshop");kw={"target_id":site.id,"terms":ActionTerms(name="Neighborhood Kitchen",purpose="Cook meals",product="meals",amount=20,price=3)}
    elif action in {ActionType.OFFER_INVESTMENT,ActionType.OFFER_JOB,ActionType.PAY_DIVIDEND,ActionType.SET_PRICE}:
        company=s.company()
        if action==ActionType.OFFER_INVESTMENT:kw={"target_id":b.id,"terms":ActionTerms(company_id=company.id,amount=15,equity=.2)}
        elif action==ActionType.OFFER_JOB:kw={"target_id":b.id,"terms":ActionTerms(company_id=company.id,wage=3)}
        elif action==ActionType.PAY_DIVIDEND:kw={"target_id":company.id,"terms":ActionTerms(amount=5)}
        else:kw={"target_id":company.id,"terms":ActionTerms(price=4)}
    elif action in {ActionType.BUILD,ActionType.DEMOLISH}:
        destination=Vec2(x=690,y=350);a.known_terrain["34,17"]="grass"
        if action==ActionType.DEMOLISH:
            s.world.terrain.tiles["34,17"]={"kind":"wall","builder_id":a.id,"owner_id":a.id}
            a.known_terrain["34,17"]="wall"
        else:s.carry("material")
        kw={"destination":destination,"terms":ActionTerms(tile="wall")}
    for p in s.people:p.speech=None;p.current_action="observing"
    s.capture("Before")
    s.act(selected,action,**kw)
    s.capture("Chosen action")
    s.finish()
    if action==ActionType.REPORT:
        s.world.time+=15;s.world._update_city_services();s.capture("Reported hazard removed by city services")
    return {"id":action.value,"title":action.value.replace('_',' ').title(),
        "category":next(group for group,actions in GROUPS.items() if action.value in actions.split()),
        "actions":[action.value],"focus":{"x":730,"y":385},"frames":s.frames}


def hazard_case(s, kind):
    a=s.actor;b=s.other
    if kind in {"earthquake","fatal_collapse"}:
        site=s.item("workplace","Fragile Workshop")
        if kind=="fatal_collapse": a.position=site.position.model_copy()
    elif kind=="stepped_in_waste":
        waste=s.item("waste","Street Waste",created_at=0);waste.position=a.position.model_copy()
    elif kind=="street_accident":a.bladder=99;a.home_id=None
    elif kind=="health_failure":a.health=0
    s.capture("Before")
    if kind=="stepped_in_waste" or kind=="street_accident":s.world._handle_sanitation(a)
    elif kind=="health_failure":s.world._update_agents(0)
    elif kind=="fatal_collapse":s.world.intervene("earthquake",a.position,None)
    else:s.world.intervene(kind,a.position,"A new signal can be heard in the neighborhood.",target_id=a.id)
    s.capture("Event occurs")
    s.world.time+=5;s.world._handle_sanitation(a);s.capture("The physical consequences remain")
    return {"id":kind,"title":kind.replace('_',' ').title(),"category":"Physical events",
        "actions":[],"focus":{"x":730,"y":385},"frames":s.frames}


def build():
    cases=[]
    with tempfile.TemporaryDirectory(prefix="interaction-catalog-") as folder:
        specs=list(ActionType)+["street_accident","stepped_in_waste","earthquake","fatal_collapse","lightning","kill","health_failure","food","toilet","fog"]
        for index, spec in enumerate(specs):
            scene=Scene(Path(folder)/f"case-{index}.db")
            try:
                result=action_case(scene,spec) if isinstance(spec,ActionType) else hazard_case(scene,spec)
                cases.append(result)
                print(f"[catalog] {index+1}/{len(specs)} verified: {result['id']}",flush=True)
            finally:scene.store.close()
    covered={a for case in cases for a in case['actions']}
    assert covered=={a.value for a in ActionType}
    sanitation=json.loads((ROOT/'web'/'sanitation-replay-data.json').read_text())
    cases.append({"id":"housing_loss","title":"Housing Loss & Street Sanitation","category":"Physical events",
        "actions":[],"focus":sanitation['focus'],"frames":sanitation['frames']})
    output=ROOT/'web'/'interaction-catalog.json'
    output.write_text(json.dumps({"kind":"mechanics_test_replay","model_calls":0,"action_count":len(ActionType),"cases":cases}),encoding='utf-8')
    print(f"[catalog] ready: {len(cases)} cases; {len(covered)} / {len(ActionType)} actions; {output}",flush=True)


if __name__=='__main__':build()
