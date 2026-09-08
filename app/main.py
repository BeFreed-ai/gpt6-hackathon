from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.brain import ResilientBrain
from app.checkpoint import dump_world, restore_world
from app.experiment import report as experiment_report
from app.models import ControlRequest, InterventionRequest
from app.store import EventStore
from app.world import World

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "web"
load_dotenv(ROOT / ".env")


class SimulationService:
    def __init__(self) -> None:
        db_path = os.environ.get("SOCIETY_DB_PATH", ".data/society.db")
        agent_count = int(os.environ.get("SOCIETY_AGENT_COUNT", "12"))
        max_concurrency = int(os.environ.get("SOCIETY_MAX_CONCURRENT_LLM_CALLS", "4"))
        self.store = EventStore(db_path)
        self.brain = ResilientBrain()
        saved = self.store.load_checkpoint()
        self.world = (
            restore_world(self.store, saved)
            if saved
            else World(
                self.store,
                agent_count=agent_count,
                seed=int(os.environ.get("SOCIETY_SEED", "17")),
                scenario=os.environ.get("SOCIETY_SCENARIO", "sf"),
            )
        )
        self.world.paused = os.environ.get("SOCIETY_START_PAUSED", "1") == "1"
        self.restored = saved is not None
        self.latency_aware = os.environ.get("SOCIETY_LATENCY_AWARE", "1") == "1"
        self.request_limit = max(1, int(os.environ.get("SOCIETY_REQUEST_LIMIT", "24")))
        self.allow_paid_calls = os.environ.get("SOCIETY_ALLOW_PAID_CALLS", "0") == "1"
        self.request_started: dict[str, float] = {}
        self.world.runtime_metrics = getattr(
            self.world,
            "runtime_metrics",
            {
                "requests": 0,
                "completed": 0,
                "failed": 0,
                "stale": 0,
                "latency_seconds": [],
                "consecutive_errors": 0,
                "pause_reason": None,
            },
        )
        self.world.runtime_metrics["requests"] = max(
            self.world.runtime_metrics["requests"], self.store.call_count(self.world.run_id)
        )
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.clients: set[WebSocket] = set()
        self.snapshot_sequence = 0
        self.agent_tasks: dict[str, asyncio.Task] = {}
        self.loop_task: asyncio.Task | None = None
        self._last_broadcast = 0.0
        self._last_checkpoint = 0.0
        self.save()

    def save(self) -> None:
        self.store.save_checkpoint(dump_world(self.world))
        self._last_checkpoint = time.monotonic()

    async def start(self) -> None:
        if self.loop_task is None:
            self.loop_task = asyncio.create_task(self._run(), name="society-world-loop")

    async def stop(self) -> None:
        if self.loop_task:
            self.loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.loop_task
        for task in self.agent_tasks.values():
            task.cancel()
        if self.agent_tasks:
            await asyncio.gather(*self.agent_tasks.values(), return_exceptions=True)
        self.save()
        if self.brain.primary:
            await self.brain.primary.client.close()
        self.store.close()

    async def _run(self) -> None:
        previous = time.monotonic()
        while True:
            now = time.monotonic()
            elapsed = min(0.25, now - previous)
            previous = now
            if not self.world.paused:
                if not self.clock_waiting():
                    self.world.tick(elapsed * self.world.speed)
                self._schedule_ready_agents()
            if now - self._last_checkpoint >= 5:
                self.save()
            if now - self._last_broadcast >= 0.35:
                self._last_broadcast = now
                await self.broadcast_snapshot()
            await asyncio.sleep(0.05)

    def clock_waiting(self) -> bool:
        # Wait only when nobody has a resolved physical action to perform. A slow
        # model response must not freeze a neighbor who already decided to walk.
        # Thinking citizens retain their existing per-person body-clock protection.
        return (
            self.latency_aware
            and self.world.scenario == "sf"
            and any(agent.alive and agent.is_thinking for agent in self.world.agents.values())
            and not self.has_physical_actions()
        )

    def has_physical_actions(self) -> bool:
        return any(
            a.alive and (a.action_target is not None or a.activity is not None)
            for a in self.world.agents.values()
        )

    def _schedule_ready_agents(self, allow_paused: bool = False) -> None:
        metrics = self.world.runtime_metrics
        if self.brain.mode != "local" and not self.allow_paid_calls:
            self.world.paused = True
            metrics["pause_reason"] = "Paid calls disabled; configure a request budget and opt in."
            return
        remaining = self.request_limit - metrics["requests"] - len(self.agent_tasks)
        if remaining <= 0:
            if not self.agent_tasks:
                if self.has_physical_actions():
                    metrics["pause_reason"] = (
                        "Model budget reached; finishing existing actions without new calls."
                    )
                else:
                    self.world.paused = True
                    metrics["pause_reason"] = (
                        "Request budget reached; raise SOCIETY_REQUEST_LIMIT to continue."
                    )
            return
        # Oldest due turn first: small budgets must not continually favor insertion order.
        for agent in sorted(
            self.world.agents.values(), key=lambda a: (a.next_think_at, a.decision_count, a.id)
        ):
            if (
                agent.alive
                and not agent.is_thinking
                and agent.action_target is None
                and agent.activity is None
                and self.world.time >= agent.next_think_at
                and self.world.time >= agent.relief_until
                and remaining > 0
            ):
                agent.is_thinking = True
                task = asyncio.create_task(
                    self._think(agent.id, allow_paused), name=f"think-{agent.id}"
                )
                self.agent_tasks[agent.id] = task
                remaining -= 1
                task.add_done_callback(
                    lambda _task, agent_id=agent.id: self.agent_tasks.pop(agent_id, None)
                )

    async def _think(self, agent_id: str, allow_paused: bool = False) -> None:
        agent = self.world.agents.get(agent_id)
        if not agent:
            return
        call_id = None
        try:
            async with self.semaphore:
                while self.world.paused and not allow_paused:
                    await asyncio.sleep(0.1)
                if not agent.alive:
                    return
                metrics = getattr(self.world, "runtime_metrics", None)
                if metrics is not None:
                    metrics["requests"] += 1
                    self.request_started[agent.id] = time.monotonic()
                    call_id = self.store.start_call(
                        self.world.run_id, agent.id, self.brain.mode, self.brain.model
                    )
                context = self.world.context_for(agent)
                version = agent.stimulus_version
                consumed = {event["id"] for event in context["new_events"]}
                decision = await self.brain.decide(agent.model_copy(deep=True), context)
                if call_id is not None:
                    self.store.finish_call(
                        call_id, "returned", decision.provider_usage, decision.provider_response_id
                    )
                if metrics is not None:
                    latency = time.monotonic() - self.request_started.pop(agent.id)
                    metrics["latency_seconds"] = (metrics["latency_seconds"] + [round(latency, 2)])[
                        -100:
                    ]
                    metrics["consecutive_errors"] = 0
            while self.world.paused and not allow_paused:
                await asyncio.sleep(0.1)
            if not agent.alive or version != agent.stimulus_version:
                if metrics is not None:
                    metrics["stale"] += 1
                agent.next_think_at = self.world.time
                return
            agent.inbox = [item for item in agent.inbox if item not in consumed]
            self.world.apply_decision(agent_id, decision)
            self.world.record_followup(agent, decision, consumed)
            if metrics is not None:
                metrics["completed"] += 1
        except Exception as error:
            if call_id is not None:
                self.store.finish_call(
                    call_id,
                    "failed",
                    getattr(error, "provider_usage", {}),
                    getattr(error, "provider_response_id", None),
                    type(error).__name__,
                )
            agent.last_action_result = f"Decision failed: {type(error).__name__}. Retrying."
            agent.next_think_at = self.world.time + 15
            metrics = getattr(self.world, "runtime_metrics", None)
            if metrics is not None:
                metrics["failed"] += 1
                metrics["consecutive_errors"] += 1
                if metrics["consecutive_errors"] >= 3:
                    self.world.paused = True
                    metrics["pause_reason"] = (
                        "Repeated provider failures; paused to protect the experiment."
                    )
        finally:
            current = self.world.agents.get(agent_id)
            if current:
                current.is_thinking = False
            if hasattr(self, "request_started"):
                self.request_started.pop(agent_id, None)
            if hasattr(self, "store"):
                self.save()

    async def broadcast_snapshot(self) -> None:
        if not self.clients:
            return
        payload = json.dumps(self.snapshot(), separators=(",", ":"))

        async def send(client: WebSocket) -> None:
            try:
                await asyncio.wait_for(client.send_text(payload), timeout=2)
            except Exception:
                self.clients.discard(client)

        await asyncio.gather(*(send(client) for client in tuple(self.clients)))

    def snapshot(self) -> dict:
        snapshot = self.world.snapshot(self.brain.mode, self.brain.last_error)
        self.snapshot_sequence += 1
        snapshot["sequence"] = self.snapshot_sequence
        snapshot["stats"]["brain_model"] = self.brain.model
        metrics = self.world.runtime_metrics
        latencies = sorted(metrics["latency_seconds"])
        snapshot["runtime"] = {
            **{key: value for key, value in metrics.items() if key != "latency_seconds"},
            "request_limit": self.request_limit,
            "paid_calls_enabled": self.allow_paid_calls,
            "inflight": len(self.request_started),
            "queued": max(0, len(self.agent_tasks) - len(self.request_started)),
            "clock_waiting": self.clock_waiting(),
            "latency_aware": self.latency_aware,
            "latency_p50": latencies[len(latencies) // 2] if latencies else None,
            "restored": self.restored,
            "checkpoint_age_seconds": round(time.monotonic() - self._last_checkpoint, 1),
        }
        snapshot["experiment"] = experiment_report(self.world)
        return snapshot


service = SimulationService()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await service.start()
    yield
    await service.stop()


app = FastAPI(title="Throng City", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "brain_mode": service.brain.mode,
        "model": service.brain.model,
    }


@app.get("/api/state")
async def state() -> dict:
    return service.snapshot()


@app.get("/api/experiment")
async def experiment() -> dict:
    snapshot = service.snapshot()
    return {"experiment": snapshot["experiment"], "runtime": snapshot["runtime"]}


@app.get("/api/agents/{agent_id}")
async def agent_detail(agent_id: str) -> dict:
    detail = service.world.agent_detail(agent_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return detail


@app.post("/api/control")
async def control(request: ControlRequest) -> dict:
    if request.action == "pause":
        service.world.paused = True
    elif request.action == "play":
        service.world.paused = False
        service.world.runtime_metrics["pause_reason"] = None
        service.world.runtime_metrics["consecutive_errors"] = 0
    elif request.action == "speed" and request.speed is not None:
        service.world.speed = max(0.25, min(8.0, request.speed))
    elif request.action == "step":
        if not service.world.paused:
            raise HTTPException(status_code=409, detail="Pause the world before stepping")
        service.world.tick(1.0)
        service._schedule_ready_agents(allow_paused=True)
    elif request.action == "save":
        pass  # Every successful control request writes an atomic checkpoint below.
    else:
        raise HTTPException(status_code=400, detail="Unknown control action")
    service.save()
    await service.broadcast_snapshot()
    return service.snapshot()["world"]


@app.post("/api/intervene")
async def intervene(request: InterventionRequest) -> dict:
    allowed = {
        "food",
        "lightning",
        "kill",
        "toilet",
        "broadcast",
        "fog",
        "build",
        "earthquake",
        "waste",
    }
    if request.type not in allowed:
        raise HTTPException(status_code=400, detail="Unknown intervention")
    if (
        request.type in {"food", "lightning", "toilet", "build", "earthquake", "waste"}
        and request.position is None
    ):
        raise HTTPException(status_code=400, detail="This intervention requires a position")
    if request.type == "broadcast" and not (request.message or "").strip():
        raise HTTPException(status_code=400, detail="Broadcast message must not be empty")
    try:
        receipt = service.world.intervene(
            request.type, request.position, request.message, request.tile, request.target_id
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    for agent_id in receipt["killed"]:
        task = service.agent_tasks.get(agent_id)
        if task:
            task.cancel()
    service.save()
    await service.broadcast_snapshot()
    return receipt


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    service.clients.add(websocket)
    await websocket.send_json(service.snapshot())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        service.clients.discard(websocket)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
