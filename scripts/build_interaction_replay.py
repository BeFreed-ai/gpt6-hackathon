"""Build an offline mechanics replay from actual World actions, without any brain or server."""
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


def build():
    frames = []
    with tempfile.TemporaryDirectory(prefix="citizen-interaction-replay-") as directory:
        store = EventStore(str(Path(directory) / "test.db"))
        try:
            world = World(store, agent_count=3, seed=17)
            world.next_city_event = 100000
            first, second, witness = world.agents.values()
            # Use the prototype's existing street so nearby facades do not obscure the handoff.
            for person, x in zip((first, second, witness), (700, 730, 820), strict=True):
                person.position = Vec2(x=x, y=390)
                person.memories.clear()
                person.inbox.clear()
                person.speech = None
                person.last_reaction = ""
                person.current_action = "observing"
            second.health = 65

            def capture(title):
                state = world.snapshot("local")
                frames.append({"title": title, "state": state,
                    "inventory": {a.name: list(a.inventory) for a in world.agents.values()},
                    "health": {a.name: a.health for a in world.agents.values()}})
                print(f"[replay] captured {len(frames)}: {title}", flush=True)

            def act(person, action, **kwargs):
                world.time += 1
                for a in world.agents.values():
                    a.speech = None
                world.apply_decision(person.id, AgentDecision(intent=ActionIntent(action=action, **kwargs)))
                assert not person.last_action_result.startswith("Failed"), person.last_action_result

            capture("Before interaction")
            act(first, ActionType.TALK, target_id=second.id, message="I have an apple. Would you like it?")
            message = next(m for m in reversed(second.memories) if m.event_type == "speech")
            assert message.addressed_to_me
            capture("Speech reaches the named recipient")
            act(second, ActionType.TALK, target_id=first.id, message="Yes, thank you.", reply_to=message.id)
            assert world.events[-1].payload["reply_to"] == message.id
            capture("A separate recipient decision replies")
            apple = world._add_object("food", "Apple", 700, 390)
            act(first, ActionType.TAKE, target_id=apple.id)
            capture("The giver picks up an actual item")
            act(first, ActionType.GIVE, target_id=second.id, terms=ActionTerms(item_id=apple.id))
            assert apple.id not in first.inventory and apple.id in second.inventory
            capture("Giving transfers ownership between inventories")
            act(first, ActionType.HELP, target_id=second.id)
            assert second.health == 77
            capture("First aid changes the recipient's health")
            act(first, ActionType.OFFER_HOUSING, target_id=second.id)
            offer = list(world.economy.offers.values())[-1]
            old_home = second.home_id
            assert offer.status == "pending" and second.home_id == old_home
            capture("An offer waits for the recipient's decision")
            act(second, ActionType.REJECT_OFFER, target_id=offer.id)
            assert offer.status == "rejected" and second.home_id == old_home
            capture("Refusal leaves the recipient's housing unchanged")
            act(first, ActionType.ATTACK, target_id=second.id)
            assert second.health < 77 and second.alive
            capture("A confirmed attack causes injury and a brief flinch")
        finally:
            store.close()
    output = ROOT / "web" / "interaction-replay-data.json"
    output.write_text(json.dumps({"kind": "mechanics_test_replay", "model_calls": 0, "frames": frames}), encoding="utf-8")
    print(f"[replay] ready: {output}; {len(frames)} frames; zero model calls", flush=True)


if __name__ == "__main__":
    build()
