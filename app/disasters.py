"""Authoritative stylized disaster physics, never scripted reactions."""

import math

from app.models import Vec2

BUILDING_KINDS = {
    "home",
    "tech",
    "workplace",
    "market",
    "cafe",
    "clinic",
    "toilet",
    "kitchen",
    "shelter",
    "depot",
    "launchpad",
    "dining",
    "company",
}


def structure_for(site):
    """Shared synthetic footprint for physical exposure and procedural 3D meshes.

    Height is in map meters; width/depth use simulation coordinates.
    These are gameplay buildings, not surveyed SF building dimensions.
    """
    if site.kind not in BUILDING_KINDS:
        return None
    seed = sum((i + 1) * ord(c) for i, c in enumerate(site.id))
    floors = (4 + seed % 4) if site.kind in {"tech", "workplace", "company"} else 2 + seed % 3
    if site.kind in {"toilet", "shelter", "depot"}:
        floors = 1
    return {
        "width": site.width * 0.8,
        "depth": site.height * 0.8,
        "height": floors * 5,
        "floors": floors,
        "seed": seed,
        "state": site.metadata.get(
            "damage_state", "damaged" if site.metadata.get("quake_damage") else "intact"
        ),
        "integrity": site.metadata.get(
            "structural_integrity", 35 if site.metadata.get("quake_damage") else 100
        ),
    }


def earthquake(world, epicenter: Vec2) -> tuple[list[str], list[str]]:
    living = [agent for agent in world.agents.values() if agent.alive]
    # Everybody feels shaking BEFORE casualties. Remote inventories stay private.
    event = world.emit(
        "earthquake",
        "The ground is shaking violently. Loose objects rattle and dust rises.",
        target_ids=[agent.id for agent in living],
        position=epicenter,
        radius=1600,
        payload={"duration": 4, "effect": "earthquake"},
    )
    damaged = []
    for site in list(world.objects.values()):
        shape = structure_for(site)
        distance = math.hypot(site.position.x - epicenter.x, site.position.y - epicenter.y)
        if not shape or distance > 240:
            continue
        loss = 100 if distance <= 90 else 65 if distance <= 170 else 30
        integrity = max(0, shape["integrity"] - loss)
        state = "collapsed" if integrity == 0 else "major" if integrity <= 40 else "damaged"
        site.metadata.update(
            quake_damage=event.id,
            condition=integrity,
            structural_integrity=integrity,
            damage_state=state,
            open=False,
        )
        damaged.append((site, shape, state))
        description = {
            "collapsed": "has collapsed into broken walls and rubble",
            "major": "has broken floors, missing walls and fallen masonry",
            "damaged": "has cracked walls and fallen fixtures",
        }[state]
        world.emit(
            "facility_damage",
            f"{site.name} {description}; it is unsafe and closed.",
            position=site.position,
            radius=150,
            payload={"object_id": site.id, "cause_event_id": event.id, "damage_state": state},
        )
    injured, killed = [], []
    for agent in living:
        agent.stress = min(100, agent.stress + 22)
        distance = world._distance_to_position(agent, epicenter)
        damage = max(0, 32 * (1 - distance / 180))
        for site, shape, state in damaged:
            # Falling masonry extends beyond the same footprint drawn on the map.
            dx = max(0, abs(agent.position.x - site.position.x) - shape["width"] / 2)
            dy = max(0, abs(agent.position.y - site.position.y) - shape["depth"] / 2)
            edge_distance = math.hypot(dx, dy)
            if edge_distance < 16:
                severity = {"collapsed": 160, "major": 60, "damaged": 18}[state]
                damage = max(damage, severity * (1 - edge_distance / 40))
        if damage <= 0:
            continue
        agent.health = max(0, agent.health - round(damage, 1))
        if agent.health <= 0:
            world.lifecycle.kill(
                agent, "earthquake", f"{agent.name} was killed by earthquake debris.", event.id
            )
            killed.append(agent.id)
        else:
            injured.append(agent.id)
            world.emit(
                "injury",
                f"{agent.name} was injured by the earthquake and falling debris.",
                target_ids=[agent.id],
                position=agent.position,
                radius=70,
                payload={"cause_event_id": event.id, "health_lost": round(damage, 1)},
            )
    return injured, killed
