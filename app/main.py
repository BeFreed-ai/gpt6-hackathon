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
        self.world = World(self.store, agent_count=agent_count)
        self.world.paused = os.environ.get("SOCIETY_START_PAUSED") == "1"
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.clients: set[WebSocket] = set()
        self.agent_tasks: dict[str, asyncio.Task] = {}
        self.loop_task: asyncio.Task | None = None
        self._last_broadcast = 0.0

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
        self.store.close()

    async def _run(self) -> None:
        previous = time.monotonic()
        while True:
            now = time.monotonic()
            elapsed = min(0.25, now - previous)
            previous = now
            if not self.world.paused:
                self.world.tick(elapsed * self.world.speed)
                self._schedule_ready_agents()
            if now - self._last_broadcast >= 0.35:
                self._last_broadcast = now
                await self.broadcast_snapshot()
            await asyncio.sleep(0.05)

    def _schedule_ready_agents(self, allow_paused: bool = False) -> None:
        for agent in self.world.agents.values():
            if (
                agent.alive
                and not agent.is_thinking
                and agent.action_target is None
                and agent.activity is None
                and self.world.time >= agent.next_think_at
            ):
                agent.is_thinking = True
                task = asyncio.create_task(
                    self._think(agent.id, allow_paused), name=f"think-{agent.id}"
                )
                self.agent_tasks[agent.id] = task
                task.add_done_callback(
                    lambda _task, agent_id=agent.id: self.agent_tasks.pop(agent_id, None)
                )

    async def _think(self, agent_id: str, allow_paused: bool = False) -> None:
        agent = self.world.agents.get(agent_id)
        if not agent:
            return
        try:
            async with self.semaphore:
                while self.world.paused and not allow_paused:
                    await asyncio.sleep(0.1)
                if not agent.alive:
                    return
                context = self.world.context_for(agent)
                version = agent.stimulus_version
                consumed = set(agent.inbox)
                decision = await self.brain.decide(agent.model_copy(deep=True), context)
            while self.world.paused and not allow_paused:
                await asyncio.sleep(0.1)
            if not agent.alive or version != agent.stimulus_version:
                agent.next_think_at = self.world.time
                return
            agent.inbox = [item for item in agent.inbox if item not in consumed]
            self.world.apply_decision(agent_id, decision)
            self.world.record_followup(agent, decision, consumed)
        except Exception as error:
            agent.last_action_result = f"Decision failed: {type(error).__name__}. Retrying."
            agent.next_think_at = self.world.time + 15
        finally:
            current = self.world.agents.get(agent_id)
            if current:
                current.is_thinking = False

    async def broadcast_snapshot(self) -> None:
        if not self.clients:
            return
        payload = json.dumps(self.snapshot(), separators=(",", ":"))
        stale: list[WebSocket] = []
        for client in tuple(self.clients):
            try:
                await client.send_text(payload)
            except Exception:
                stale.append(client)
        for client in stale:
            self.clients.discard(client)

    def snapshot(self) -> dict:
        return self.world.snapshot(self.brain.mode, self.brain.last_error)


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
        "model": os.environ.get("OPENAI_MODEL", "gpt-6-astra"),
    }


@app.get("/api/state")
async def state() -> dict:
    return service.snapshot()


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
    elif request.action == "speed" and request.speed is not None:
        service.world.speed = max(0.25, min(8.0, request.speed))
    elif request.action == "step":
        if not service.world.paused:
            raise HTTPException(status_code=409, detail="Pause the world before stepping")
        service.world.tick(1.0)
        service._schedule_ready_agents(allow_paused=True)
    else:
        raise HTTPException(status_code=400, detail="Unknown control action")
    await service.broadcast_snapshot()
    return service.snapshot()["world"]


@app.post("/api/intervene")
async def intervene(request: InterventionRequest) -> dict:
    allowed = {"food", "lightning", "kill", "toilet", "broadcast", "fog", "build"}
    if request.type not in allowed:
        raise HTTPException(status_code=400, detail="Unknown intervention")
    if request.type in {"food", "lightning", "toilet", "build"} and request.position is None:
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
