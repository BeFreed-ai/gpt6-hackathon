"""Record housing loss and street sanitation in an isolated SF mechanics fixture."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.models import ActionIntent, ActionType, AgentDecision
from app.store import EventStore
from app.world import World


def build():
    frames = []
    with tempfile.TemporaryDirectory(prefix="sanitation-replay-") as folder:
        store = EventStore(str(Path(folder) / "fixture.db"))
        try:
            world = World(store, agent_count=12, scenario="sf", seed=17)
            names = ("Alex Rivera", "Mira Chen", "Eli Brooks", "Robin Park", "Casey Reed", "Morgan Lee",
                     "Taylor Bell", "Jordan Hayes", "Jamie Cruz", "Avery Stone", "Sam Patel", "Quinn Davis")
            for agent, name in zip(world.agents.values(), names, strict=True):
                agent.name = name
            person = next(a for a in world.agents.values() if a.home_id)
            person.name = "Alex Rivera"
            roads = [world.terrain.center(tuple(map(int, key.split(',')))) for key,tile in world.terrain.tiles.items() if tile['kind']=='road']
            facilities = [o for o in world.objects.values() if o.kind not in {'food','waste','tree','coat','material','route_guide'}]
            clear = [p for p in roads if all(abs(p.x-o.position.x)>70 or abs(p.y-o.position.y)>90 for o in facilities)]
            person.position = min(clear,key=lambda p:(p.x-700)**2+(p.y-400)**2).model_copy()
            focus = person.position.model_dump()
            person.credits = 0
            ledger = world.sf_economy.state["agents"][person.id]
            threshold = world.sf_economy.state["calibration"]["scenario"]["housing_loss_after_unpaid_days"]
            # Start a test case at the existing threshold boundary, not a new eviction policy.
            ledger.update(daily_support_credits=0, unpaid_days=threshold-1,
                          rent_debt_credits=round(world.sf_economy.rent_share(person)*(threshold-1), 2))
            world.time = world.day_length * (threshold-1)
            world.sf_economy.state["last_day"] = threshold-1

            def capture(title):
                frames.append({"title": title, "state": world.snapshot("local"), "evidence":
                    f"{person.name}: {person.credits:.2f} credits · {'Has a home' if person.home_id else 'No current home'} · "
                    f"{ledger['unpaid_days']} unpaid budget days · "
                    f"{sum(o.kind == 'waste' and o.metadata.get('created_by') == person.id for o in world.objects.values())} waste object created"})
                print(f"[sanitation replay] {len(frames)}: {title}", flush=True)

            capture(f"No cash, {threshold-1} unpaid days; tenancy still active")
            world.time += world.day_length
            world.sf_economy.new_day()
            assert person.home_id is None
            capture(f"Housing loss after the existing {threshold}-day scenario threshold")
            person.bladder = 99
            world._handle_sanitation(person)
            waste = next(o for o in world.objects.values() if o.metadata.get("created_by") == person.id)
            assert not any(key.startswith("step_") for key in waste.metadata)
            capture("Could not reach a restroom: squats and leaves waste")
            world.time = person.relief_until
            world._handle_sanitation(person)
            choices = [world.terrain.center(tuple(map(int, key.split(',')))) for key, tile in world.terrain.tiles.items() if tile['kind']=='road']
            nearby = [p for p in choices if 30 < world._distance_to_position(person,p) < 70 and world.terrain.line_clear(person.position,p)]
            destination = min(nearby,key=lambda p:abs(p.y-person.position.y))
            world.apply_decision(person.id, AgentDecision(intent=ActionIntent(action=ActionType.MOVE,destination=destination)))
            for _ in range(40):
                world.time += .1
                world._advance_movement(person,.1)
            assert world._distance_agent_object(person,waste) > 16
            world._update_city_services()
            assert waste.id in world.objects
            capture("A test-supplied walking decision leaves the waste behind")
        finally:
            store.close()
    output = ROOT / "web" / "sanitation-replay-data.json"
    output.write_text(json.dumps({"kind":"mechanics_test_replay","model_calls":0,"focus":focus,"frames":frames}),encoding="utf-8")
    print(f"[sanitation replay] ready: {output}; no model calls or live world changes",flush=True)


if __name__ == "__main__":
    build()
