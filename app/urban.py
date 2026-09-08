"""Timed urban facilities, physical goods and production with reserved resources."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.economy import PRODUCTS
from app.models import ActionIntent, ActionType, Activity, AgentState, WorldObject

if TYPE_CHECKING:
    from app.world import World


PORTABLE = {"food", "coat", "route_guide", "material"}


class UrbanSystem:
    def __init__(self, world: World) -> None:
        self.world = world
        self.carried: dict[str, WorldObject] = {}

    def seed(self) -> None:
        for item in self.world.objects.values():
            if item.kind == "home":
                item.metadata["beds"] = 2
            elif item.kind == "toilet":
                item.metadata.update(capacity=1, condition=100, hours=[0, 24])
            elif item.kind in {"market", "cafe"}:
                item.metadata.update(stock=12, price=3, hours=[7, 23], capacity=2)
        self.world._add_object(
            "dining",
            "Golden Gate Community Meals",
            670,
            540,
            130,
            78,
            metadata={"stock": 16, "price": 0, "hours": [8, 14], "capacity": 2},
        )
        self.world._add_object(
            "kitchen",
            "Mission Shared Kitchen",
            420,
            540,
            95,
            70,
            metadata={"hours": [6, 23], "capacity": 2, "condition": 100},
        )
        self.world._add_object(
            "launchpad",
            "Garage Commons",
            1190,
            125,
            120,
            85,
            metadata={"hours": [0, 24], "capacity": 4},
        )
        self.world._add_object(
            "toilet",
            "Daytime Pit Stop",
            220,
            300,
            55,
            50,
            metadata={"hours": [7, 19], "capacity": 1, "condition": 85},
        )
        self.world._add_object("coat", "Secondhand Fog Jacket", 350, 500, 20, 20)
        self.world._add_object(
            "depot",
            "City Reuse Depot",
            1010,
            350,
            90,
            62,
            metadata={"stock": 30, "capacity": 2, "hours": [0, 24]},
        )

    @property
    def hour(self) -> float:
        return (8 + self.world.time / self.world.day_length * 24) % 24

    def is_open(self, item: WorldObject) -> bool:
        if item.metadata.get("quake_damage"):
            return False
        start, end = item.metadata.get("hours", [0, 24])
        scheduled = (
            start <= self.hour < end if start < end else self.hour >= start or self.hour < end
        )
        return scheduled and item.metadata.get("open", True)

    def occupants(self, item: WorldObject) -> int:
        return sum(
            a.alive and a.activity is not None and a.activity.target_id == item.id
            for a in self.world.agents.values()
        )

    def room_available(self, item: WorldObject) -> bool:
        return sum(
            a.alive and a.home_id == item.id for a in self.world.agents.values()
        ) < item.metadata.get("beds", 2)

    def describe(self, item: WorldObject) -> dict:
        from app.disasters import structure_for

        return {
            "id": item.id,
            "kind": item.kind,
            "name": item.name,
            "position": item.position.model_dump(),
            "width": item.width,
            "height": item.height,
            "metadata": dict(item.metadata),
            "structure": structure_for(item),
            "open_now": self.is_open(item),
            "in_use": self.occupants(item),
            "observed_at": round(self.world.time, 1),
        }

    def fail(self, agent: AgentState, intent: ActionIntent, reason: str) -> bool:
        self.world._fail_action(agent, intent, reason)
        return True

    def start(
        self,
        agent: AgentState,
        intent: ActionIntent,
        target: WorldObject | None,
        duration: float,
        **resources,
    ) -> bool:
        agent.activity = Activity(
            action=intent.action,
            target_id=target.id if target else None,
            started_at=self.world.time,
            ends_at=self.world.time + duration,
            **resources,
        )
        agent.current_action = (
            f"{intent.action.value.replace('_', ' ')} at {target.name}"
            if target
            else "resting outdoors"
        )
        agent.next_think_at = self.world.time + duration
        return True

    def execute(self, agent: AgentState, intent: ActionIntent) -> bool | None:
        action = intent.action
        if action in {
            ActionType.TAKE,
            ActionType.DROP,
            ActionType.GIVE,
            ActionType.EAT,
            ActionType.USE_ITEM,
        }:
            return self.item_action(agent, intent)
        if action not in {
            ActionType.BUY,
            ActionType.COOK,
            ActionType.CLEAN,
            ActionType.REPAIR,
            ActionType.RENT_HOME,
            ActionType.WORK,
            ActionType.REST,
            ActionType.USE_TOILET,
            ActionType.SEEK_SHELTER,
            ActionType.SALVAGE,
        }:
            return None
        if action == ActionType.REST:
            clinic = self.world.objects.get(intent.target_id or "")
            if getattr(self.world, "sf_economy", None) and clinic and clinic.kind == "clinic":
                if not self.is_open(clinic):
                    return self.fail(agent, intent, "This clinic is closed.")
                if self.world._approach(agent, intent, clinic, 46):
                    return True
                if self.occupants(clinic) >= min(
                    clinic.metadata.get("capacity", 2), clinic.metadata.get("care_stock", 0)
                ):
                    return self.fail(agent, intent, "No unreserved care capacity is available.")
                return self.start(agent, intent, clinic, 12)
            return self.start(agent, intent, None, 12)
        target = self.world.objects.get(intent.target_id or "")
        if action == ActionType.WORK and not target:
            target = self.world.objects.get(agent.workplace_id or "")
        if action == ActionType.SEEK_SHELTER and not target:
            target = self.world.objects.get(agent.home_id or "")
        if not target:
            return self.fail(agent, intent, "Choose a known facility or item.")
        if action == ActionType.REPAIR:
            if not target.metadata.get("quake_damage"):
                return self.fail(
                    agent, intent, "Choose a facility with observed earthquake damage."
                )
            if self.world._approach(agent, intent, target, 45):
                return True
            return self.start(agent, intent, target, 12)
        if action == ActionType.CLEAN:
            if target.kind not in {"waste", "toilet", "kitchen"}:
                return self.fail(agent, intent, "Clean street waste, a toilet or a kitchen.")
            if self.world._approach(agent, intent, target, 45):
                return True
            return self.start(agent, intent, target, 9)
        if action == ActionType.RENT_HOME:
            if not self.is_open(target):
                return self.fail(agent, intent, "This home is closed or damaged.")
            rent = float(target.metadata.get("rent", 0))
            if target.kind != "home" or agent.home_id == target.id:
                return self.fail(agent, intent, "Choose another home with a vacant bed.")
            if not self.room_available(target):
                return self.fail(agent, intent, "No vacant bed remains.")
            if agent.credits < rent:
                return self.fail(agent, intent, "You cannot afford the first day's rent.")
            if self.world._approach(agent, intent, target, 50):
                return True
            agent.credits = round(agent.credits - rent, 2)
            self.world.economy.city_balance += rent
            calibration = getattr(self.world, "sf_economy", None)
            if calibration:
                calibration.move_home(agent, target)
                ledger = calibration.state["agents"][agent.id]
                ledger["rent_prepaid_credits"] = round(
                    ledger.get("rent_prepaid_credits", 0) + rent, 2
                )
            else:
                agent.home_id = target.id
                agent.rent_arrears = 0
            agent.current_action = f"rented a bed at {target.name}"
            self.world.emit(
                "housing",
                f"{agent.name} rented a bed at {target.name}.",
                actor_id=agent.id,
                position=target.position,
                radius=80,
            )
            return True
        if not self.is_open(target):
            return self.fail(
                agent, intent, f"{target.name} is closed; hours are {target.metadata.get('hours')}."
            )
        if (
            action == ActionType.USE_TOILET
            and target.kind != "toilet"
            and target.id != agent.home_id
        ):
            return self.fail(agent, intent, "Use a public toilet or your own home.")
        if action == ActionType.SEEK_SHELTER and (
            target.kind not in {"home", "shelter", "bench"}
            or (target.kind == "home" and target.id != agent.home_id)
        ):
            return self.fail(
                agent, intent, "A private room requires a tenancy or accepted roommate invitation."
            )
        if (
            action == ActionType.WORK
            and target.metadata.get("employment_basis") == "assigned_only"
            and agent.workplace_id != target.id
        ):
            return self.fail(agent, intent, "You do not have a job at this workplace.")
        if self.world._approach(agent, intent, target, 46):
            return True
        capacity = target.metadata.get("capacity", target.metadata.get("beds", 2))
        if self.occupants(target) >= capacity:
            return self.fail(
                agent, intent, f"{target.name} is full. Wait, ask, or choose another place."
            )
        if target.metadata.get("condition", 100) <= 10:
            return self.fail(agent, intent, f"{target.name} needs cleaning before use.")
        if action == ActionType.USE_TOILET:
            return self.start(agent, intent, target, 4)
        if action == ActionType.SEEK_SHELTER:
            return self.start(agent, intent, target, 16)
        if action == ActionType.SALVAGE:
            if target.kind != "depot" or len(agent.inventory) >= 8:
                return self.fail(agent, intent, "Choose the reuse depot with room in your bag.")
            if target.metadata.get("stock", 0) <= self.occupants(target):
                return self.fail(agent, intent, "No unreserved reclaimed materials remain today.")
            return self.start(agent, intent, target, 6)
        if action == ActionType.COOK:
            if target.kind not in {"kitchen", "home"} or (
                target.kind == "home" and target.id != agent.home_id
            ):
                return self.fail(agent, intent, "Cook at a shared kitchen or your own home.")
            food = [key for key in agent.inventory if self.carried[key].kind == "food"]
            if len(food) < 2 or len(agent.inventory) > 7:
                return self.fail(
                    agent,
                    intent,
                    "Cooking needs two carried food items and room for three meals "
                    "(bag capacity 8).",
                )
            for key in food[:2]:
                agent.inventory.remove(key)
            return self.start(agent, intent, target, 10, inputs=food[:2])
        if action == ActionType.BUY:
            return self.buy(agent, intent, target)
        if action == ActionType.WORK:
            company = self.world.economy.companies.get(target.id)
            if company:
                if company.closed:
                    return self.fail(agent, intent, "This company has closed.")
                if agent.id != company.founder_id and agent.id not in company.employees:
                    return self.fail(
                        agent, intent, "Ask the founder for a job offer and accept it first."
                    )
                wage = 0 if agent.id == company.founder_id else company.employees[agent.id]
                cost = PRODUCTS[company.product]["cost"]
                if company.treasury < cost + wage:
                    return self.fail(
                        agent,
                        intent,
                        "Company treasury cannot cover materials and the promised wage.",
                    )
                if company.stock >= 24:
                    return self.fail(
                        agent, intent, "The store is full; find customers before producing more."
                    )
                company.treasury = round(company.treasury - cost - wage, 2)
                return self.start(agent, intent, target, 14, reserved_credits=cost, wage=wage)
            if "wage" not in target.metadata:
                return self.fail(agent, intent, "This facility is not offering a paid shift.")
            calibration = getattr(self.world, "sf_economy", None)
            wage = (
                calibration.shift_wage(agent, target)
                if calibration
                else float(target.metadata["wage"])
            )
            if wage <= 0:
                return self.fail(
                    agent,
                    intent,
                    "You have completed the available paid shifts for this budget day.",
                )
            # Baseline wages are recorded external inflows, not spendable city debt.
            return self.start(agent, intent, target, 14, wage=wage)
        return False

    def buy(self, agent: AgentState, intent: ActionIntent, target: WorldObject) -> bool:
        company = self.world.economy.companies.get(target.id)
        if company and company.closed:
            return self.fail(agent, intent, "This company has closed.")
        if not company and target.kind not in {"market", "cafe", "dining"}:
            return self.fail(agent, intent, "Choose a shop, meal service or company storefront.")
        stock = company.stock if company else target.metadata.get("stock", 0)
        price = company.price if company else float(target.metadata.get("price", 3))
        if stock < 1:
            return self.fail(agent, intent, "Sold out. Ask about restocking or try another source.")
        if agent.credits < price or len(agent.inventory) >= 8:
            return self.fail(agent, intent, "Not enough credits or your bag is full (8 items).")
        agent.credits = round(agent.credits - price, 2)
        if company:
            company.stock -= 1
            company.treasury = round(company.treasury + price, 2)
            company.revenue = round(company.revenue + price, 2)
            recipe = PRODUCTS[company.product]
            kind, name = recipe["kind"], recipe["name"]
            self.world.economy.sync(company)
        else:
            target.metadata["stock"] -= 1
            self.world.economy.city_balance += price
            kind, name = "food", "Community Meal" if price == 0 else "Market Lunch"
        self.create_carried(agent, kind, name)
        agent.current_action = f"collected {name}"
        agent.next_think_at = self.world.time + 3
        self.world.emit(
            "purchase",
            f"{agent.name} collected {name} from {target.name} for {price:g} credits.",
            actor_id=agent.id,
            position=target.position,
            radius=85,
            payload={"seller_id": target.id, "price": price},
        )
        return True

    def create_carried(self, agent: AgentState, kind: str, name: str) -> None:
        item = self.world._add_object(kind, name, agent.position.x, agent.position.y, 18, 18)
        self.carried[item.id] = self.world.objects.pop(item.id)
        agent.inventory.append(item.id)

    def item_action(self, agent: AgentState, intent: ActionIntent) -> bool:
        action = intent.action
        if action == ActionType.TAKE:
            item = self.world.objects.get(intent.target_id or "")
            if not item or item.kind not in PORTABLE or len(agent.inventory) >= 8:
                return self.fail(
                    agent, intent, "Choose portable goods and keep room in your bag (8 items)."
                )
            if self.world._approach(agent, intent, item, 38):
                return True
            self.carried[item.id] = self.world.objects.pop(item.id)
            agent.inventory.append(item.id)
        elif action == ActionType.EAT and intent.target_id in self.world.objects:
            item = self.world.objects[intent.target_id]
            if item.kind != "food":
                return self.fail(agent, intent, "That object is not food.")
            if self.world._approach(agent, intent, item, 38):
                return True
            self.world.objects.pop(item.id)
            agent.hunger = max(0, agent.hunger - 48)
        else:
            requested = intent.terms.item_id if intent.terms else None
            if action in {ActionType.EAT, ActionType.DROP, ActionType.USE_ITEM}:
                requested = requested or intent.target_id
            candidates = [
                key
                for key in agent.inventory
                if action != ActionType.EAT or self.carried[key].kind == "food"
            ]
            key = requested or (candidates[0] if candidates else None)
            if key not in agent.inventory:
                return self.fail(agent, intent, "That item is not in your bag.")
            item = self.carried[key]
            if action == ActionType.EAT:
                if item.kind != "food":
                    return self.fail(agent, intent, "Only food can be eaten.")
                agent.hunger = max(0, agent.hunger - 48)
                agent.inventory.remove(key)
                self.carried.pop(key)
            elif action == ActionType.USE_ITEM:
                if item.kind == "coat":
                    agent.wearing_coat = True
                elif item.kind == "route_guide":
                    agent.route_until = self.world.time + self.world.day_length
                else:
                    return self.fail(
                        agent, intent, "Use a coat for warmth or a route app for faster travel."
                    )
                agent.inventory.remove(key)
                self.carried.pop(key)
            elif action == ActionType.DROP:
                agent.inventory.remove(key)
                self.carried.pop(key)
                item.position = agent.position.model_copy()
                self.world.objects[key] = item
            elif action == ActionType.GIVE:
                other = self.world.agents.get(intent.target_id or "")
                if (
                    not other
                    or not other.alive
                    or other.id == agent.id
                    or len(other.inventory) >= 8
                ):
                    return self.fail(agent, intent, "Recipient unavailable or their bag is full.")
                if self.world._approach(agent, intent, other, 42):
                    return True
                agent.inventory.remove(key)
                other.inventory.append(key)
                agent.current_action = f"gave {item.name} to {other.name}"
                self.world.emit(
                    "give",
                    f"{agent.name} gave {item.name} to {other.name}.",
                    actor_id=agent.id,
                    target_ids=[other.id],
                    position=agent.position,
                    radius=80,
                )
                return True
        agent.current_action = f"{action.value.replace('_', ' ')}: {item.name}"
        self.world.emit(
            action.value,
            f"{agent.name}: {agent.current_action}.",
            actor_id=agent.id,
            position=agent.position,
            radius=70,
        )
        return True

    def cancel(self, agent: AgentState) -> None:
        activity = agent.activity
        if not activity:
            return
        company = self.world.economy.companies.get(activity.target_id or "")
        if company:
            company.treasury = round(
                company.treasury + activity.reserved_credits + activity.wage, 2
            )
        agent.inventory.extend(activity.inputs)
        agent.activity = None

    def tick(self) -> None:
        for agent in self.world.agents.values():
            activity = agent.activity
            if not activity:
                continue
            if not agent.alive:
                self.cancel(agent)
                continue
            if self.world.time < activity.ends_at:
                continue
            target = self.world.objects.get(activity.target_id or "")
            if activity.target_id and not target:
                self.cancel(agent)
                self.world._fail_action(
                    agent,
                    ActionIntent(action=activity.action),
                    "The facility disappeared before completion; reservations refunded.",
                )
                continue
            if (
                target
                and not target.metadata.get("open", True)
                and activity.action != ActionType.REPAIR
            ):
                self.cancel(agent)
                self.world._fail_action(
                    agent,
                    ActionIntent(action=activity.action),
                    "The facility closed before completion; reservations refunded.",
                )
                continue
            action = activity.action
            agent.activity = None
            agent.next_think_at = self.world.time + 0.2
            if action == ActionType.SALVAGE:
                target.metadata["stock"] -= 1
                self.create_carried(agent, "material", "Reclaimed Material")
                result = f"salvaged one building material at {target.name}"
            elif action == ActionType.WORK:
                company = self.world.economy.companies.get(target.id)
                if company:
                    quantity = PRODUCTS[company.product]["quantity"]
                    company.stock += quantity
                    company.produced += quantity
                    company.payroll = round(company.payroll + activity.wage, 2)
                    self.world.economy.city_balance += activity.reserved_credits
                    self.world.economy.sync(company)
                else:
                    calibration = getattr(self.world, "sf_economy", None)
                    if calibration:
                        calibration.record_shift(agent, activity.wage)
                        calibration.produce_service(target)
                    else:
                        self.world.economy.city_balance -= activity.wage
                    if not calibration and target.kind in {"market", "cafe"}:
                        target.metadata["stock"] = min(30, target.metadata.get("stock", 0) + 3)
                agent.credits = round(agent.credits + activity.wage, 2)
                agent.energy = max(0, agent.energy - 5)
                result = (
                    f"completed a production shift at {target.name}; "
                    f"earned {activity.wage:g} credits"
                )
            elif action == ActionType.COOK:
                for key in activity.inputs:
                    self.carried.pop(key, None)
                for _ in range(3):
                    self.create_carried(agent, "food", "Shared Kitchen Meal")
                result = "cooked three meals from two food items"
            elif action == ActionType.REPAIR:
                integrity = min(100, target.metadata.get("structural_integrity", 70) + 30)
                target.metadata.update(condition=integrity, structural_integrity=integrity)
                if integrity == 100:
                    target.metadata.pop("quake_damage", None)
                    target.metadata.update(
                        damage_state="intact", open=not target.metadata.get("closed", False)
                    )
                else:
                    target.metadata.update(damage_state="rebuilding", open=False)
                result = f"repaired {target.name}: structural integrity {integrity}%"
                self.world.emit(
                    "repair",
                    f"{agent.name} {result}.",
                    actor_id=agent.id,
                    position=target.position,
                    radius=150,
                )
            elif action == ActionType.CLEAN:
                if target.kind == "waste":
                    self.world.objects.pop(target.id)
                else:
                    target.metadata["condition"] = 100
                agent.cleanliness = min(100, agent.cleanliness + 10)
                result = f"cleaned {target.name}"
            elif action == ActionType.USE_TOILET:
                agent.bladder = 4
                agent.cleanliness = min(100, agent.cleanliness + 8)
                target.metadata["condition"] = max(0, target.metadata.get("condition", 100) - 4)
                result = f"used {target.name}"
            elif action == ActionType.REST and target and target.kind == "clinic":
                target.metadata["care_stock"] = max(0, target.metadata.get("care_stock", 0) - 1)
                agent.health = min(100, agent.health + 18)
                agent.energy = min(100, agent.energy + 12)
                result = f"received care at {target.name}"
            else:
                indoors = action == ActionType.SEEK_SHELTER and target.kind != "bench"
                agent.energy = min(100, agent.energy + (38 if indoors else 16))
                agent.stress = max(0, agent.stress - (10 if indoors else 3))
                if indoors:
                    agent.warmth = min(100, agent.warmth + 20)
                result = f"rested at {target.name}" if target else "rested outdoors"
            agent.current_action = result
            agent.last_action_result = f"Completed: {result}."
            self.world.emit(
                action.value,
                f"{agent.name} {result}.",
                actor_id=agent.id,
                position=agent.position,
                radius=70,
            )

    def new_day(self) -> None:
        for item in list(self.world.objects.values()):
            if item.kind in {"dining", "market", "cafe"}:
                if "daily_external_stock" in item.metadata:
                    item.metadata["stock"] = min(
                        item.metadata["stock_capacity"],
                        item.metadata.get("stock", 0) + item.metadata["daily_external_stock"],
                    )
                else:
                    item.metadata["stock"] = 16 if item.kind == "dining" else 12
            elif item.kind == "depot":
                item.metadata["stock"] = 30
            elif item.kind == "garden":
                for offset in (-12, 12):
                    self.world._add_object(
                        "food",
                        "Community Garden Produce",
                        item.position.x + offset,
                        item.position.y + 18,
                        18,
                        18,
                    )
