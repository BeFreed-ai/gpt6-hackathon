"""Private clock cues, not behavioral scripts. Schedules are scenario assumptions."""


def schedule_context(world, agent) -> dict:
    absolute_hour = 8 + world.time / world.day_length * 24
    day = int(absolute_hour // 24)
    hour = absolute_hour % 24
    site = world.objects.get(agent.workplace_id or "")
    result = {
        "day": day + 1,
        "weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
            day % 7
        ],
        "local_time": world.time_of_day,
        "work": None,
        "agency": (
            "Appointments are obligations you may choose to keep, renegotiate or miss; "
            "they do not replace your life projects."
        ),
    }
    if not site:
        return result
    service = site.kind in {"market", "cafe", "clinic", "kitchen"}
    start, end = (8, 16) if service else (9, 17)
    working_day = service or day % 7 < 5
    phase = (
        "day_off"
        if not working_day
        else (
            "before_work"
            if hour < start - 1
            else "commute_due"
            if hour < start
            else "work_hours"
            if hour < end
            else "after_work"
        )
    )
    ledger = getattr(world, "sf_economy", None)
    record = ledger.state.get("agents", {}).get(agent.id, {}) if ledger else {}
    worked = (
        record.get("work_day") == int(world.time // world.day_length)
        and record.get("shifts_completed", 0) > 0
    )
    result["work"] = {
        "workplace_id": site.id,
        "name": site.name,
        "start": f"{start:02d}:00",
        "end": f"{end:02d}:00",
        "phase": phase,
        "paid_shift_completed_today": worked,
        "basis": "Synthetic service/office timetable, not this real person's schedule.",
        "pay_rule": (
            "Only completed work earns wages. This compressed simulation uses short paid "
            "work blocks, not eight-hour shifts."
        ),
    }
    return result


def update_reminders(world) -> None:
    for agent in world.agents.values():
        if not agent.alive:
            continue
        if agent.reaction_until > world.time:
            continue
        context = schedule_context(world, agent)
        work = context["work"]
        if not work or work["phase"] not in {"commute_due", "work_hours", "after_work"}:
            continue
        if work["paid_shift_completed_today"]:
            continue
        # A reminder is private and appears at most once per phase/day/workplace.
        key = f"{context['day']}:{work['workplace_id']}:{work['phase']}"
        if key in agent.routine_notices:
            continue
        agent.routine_notices = {
            k: v for k, v in agent.routine_notices.items() if k.startswith(f"{context['day']}:")
        }
        agent.routine_notices[key] = work["phase"]
        world.emit(
            "schedule_reminder",
            f"It is {context['weekday']} {context['local_time']}. My scheduled work at "
            f"{work['name']} is {work['start']}–{work['end']}. "
            f"Current phase: {work['phase']}. I have not completed a paid work block today.",
            target_ids=[agent.id],
            payload={"private": True},
        )
