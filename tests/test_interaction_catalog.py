"""Verify the replay catalog through real isolated engine actions, without a model."""
import json
from pathlib import Path

import pytest

from app.models import ActionType
from scripts.build_interaction_catalog import Scene, action_case, hazard_case


@pytest.mark.parametrize("action", list(ActionType))
def test_all_catalog_actions_execute_and_finish(tmp_path, action):
    scene = Scene(tmp_path / "case.db")
    try:
        result = action_case(scene, action)
        before, after = result["frames"][0]["state"], result["frames"][-1]["state"]
        assert result["actions"] == [action.value]
        assert not any(a.activity or a.action_target for a in scene.people)
        old, new = before["demo_details"][scene.actor.id], after["demo_details"][scene.actor.id]
        if action == ActionType.GIVE:
            assert new["bag"] == [] and after["demo_details"][scene.other.id]["bag"] == ["Apple"]
        elif action == ActionType.EAT:
            assert new["hunger"] < old["hunger"] and new["bag"] == []
        elif action == ActionType.HELP:
            assert scene.other.health > 65
        elif action == ActionType.ATTACK:
            assert scene.other.health < 65
        elif action == ActionType.WORK:
            assert new["credits"] == old["credits"] + 8
        elif action in {ActionType.REST, ActionType.SEEK_SHELTER}:
            assert new["energy"] > old["energy"]
        elif action == ActionType.USE_TOILET:
            assert new["bladder"] == 4
        elif action in {ActionType.CLEAN, ActionType.REPORT}:
            assert not any(o["kind"] == "waste" for o in after["objects"])
        elif action == ActionType.REPAIR:
            assert after["objects"][0]["metadata"]["structural_integrity"] == 100
        elif action == ActionType.ACCEPT_OFFER:
            assert scene.other.home_id == scene.actor.home_id
            assert after["economy"]["offers"][0]["status"] == "accepted"
        elif action == ActionType.REJECT_OFFER:
            assert scene.other.home_id is None
            assert after["economy"]["offers"][0]["status"] == "rejected"
        elif action in {ActionType.OFFER_JOB, ActionType.OFFER_HOUSING, ActionType.OFFER_INVESTMENT}:
            assert after["economy"]["offers"][0]["status"] == "pending"
            assert scene.other.workplace_id is None and scene.other.home_id is None
        elif action == ActionType.BUY:
            assert new["credits"] < old["credits"] and new["bag"] == ["Market Lunch"]
        elif action == ActionType.COOK:
            assert len(new["bag"]) == 3 and len(old["bag"]) == 2
        elif action == ActionType.USE_ITEM:
            assert new["coat"] and not new["bag"]
        elif action == ActionType.RENT_HOME:
            assert new["home"] and not old["home"]
        elif action == ActionType.PAY_DIVIDEND:
            assert new["credits"] == old["credits"] + 5
            assert after["economy"]["companies"][0]["treasury"] == 25
    finally:
        scene.store.close()


@pytest.mark.parametrize("kind", ["street_accident", "stepped_in_waste", "fatal_collapse", "health_failure"])
def test_physical_replays_have_real_consequences(tmp_path, kind):
    scene = Scene(tmp_path / "hazard.db")
    try:
        result = hazard_case(scene, kind)
        event_state = result["frames"][1]["state"]
        if kind == "street_accident":
            waste = next(o for o in event_state["objects"] if o["kind"] == "waste")
            assert waste["metadata"]["created_by"] == scene.actor.id
            assert not any(k.startswith("step_") for k in waste["metadata"])
            assert event_state["agents"][0]["current_action"] == "relieving themselves"
        elif kind == "stepped_in_waste":
            waste = next(o for o in event_state["objects"] if o["kind"] == "waste")
            assert f"step_{scene.actor.id}" in waste["metadata"]
        else:
            assert not scene.actor.alive
            assert any(o["kind"] == "remains" for o in event_state["objects"])
            assert event_state["agents"][0]["death_cause"] == ("earthquake" if kind == "fatal_collapse" else "health_failure")
    finally:
        scene.store.close()


def test_checked_in_catalog_covers_enum_and_preserves_left_behind_waste():
    catalog = json.loads((Path(__file__).parents[1] / "web/interaction-catalog.json").read_text())
    assert catalog["model_calls"] == 0
    assert {a for case in catalog["cases"] for a in case["actions"]} == {a.value for a in ActionType}
    assert len({case["id"] for case in catalog["cases"]}) == len(catalog["cases"]) == 45
    case = next(c for c in catalog["cases"] if c["id"] == "housing_loss")
    before, after = case["frames"][2]["state"], case["frames"][3]["state"]
    actor = after["agents"][0]
    waste = next(o for o in before["objects"] if o["metadata"].get("created_by") == actor["id"])
    assert any(o["id"] == waste["id"] for o in after["objects"])
    assert not actor["has_home"]
    assert abs(actor["position"]["x"] - waste["position"]["x"]) > 16
