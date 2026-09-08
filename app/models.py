from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    DIRECT_EXPERIENCE = "direct_experience"
    DIRECT_OBSERVATION = "direct_observation"
    OVERHEARD = "overheard"
    TESTIMONY = "testimony"
    BROADCAST = "broadcast"
    DOCUMENT = "document"
    INFERENCE = "inference"


class ActionType(StrEnum):
    MOVE = "move"
    EAT = "eat"
    TAKE = "take"
    DROP = "drop"
    GIVE = "give"
    WORK = "work"
    REST = "rest"
    TALK = "talk"
    SHOUT = "shout"
    BROADCAST = "broadcast"
    USE_TOILET = "use_toilet"
    SEEK_SHELTER = "seek_shelter"
    HELP = "help"
    ATTACK = "attack"
    REPORT = "report"
    WAIT = "wait"
    BUY = "buy"
    COOK = "cook"
    CLEAN = "clean"
    REPAIR = "repair"
    RENT_HOME = "rent_home"
    OFFER_HOUSING = "offer_housing"
    FOUND_COMPANY = "found_company"
    OFFER_INVESTMENT = "offer_investment"
    OFFER_JOB = "offer_job"
    ACCEPT_OFFER = "accept_offer"
    REJECT_OFFER = "reject_offer"
    USE_ITEM = "use_item"
    PAY_DIVIDEND = "pay_dividend"
    SET_PRICE = "set_price"
    BUILD = "build"
    DEMOLISH = "demolish"
    SALVAGE = "salvage"
    ADDRESS_PLAYER = "address_player"


class Vec2(BaseModel):
    x: float
    y: float


class Goal(BaseModel):
    statement: str
    reason: str
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    commitment: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: float = 0.0


class Memory(BaseModel):
    id: str
    world_time: float
    content: str
    source_type: SourceType
    source_id: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    original_event_id: str | None = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    event_type: str = ""
    message: str | None = None
    addressed_to_me: bool = False
    reply_to: str | None = None
    position: Vec2 | None = None


class WorldEvent(BaseModel):
    id: str
    world_time: float
    type: str
    actor_id: str | None = None
    target_ids: list[str] = Field(default_factory=list)
    position: Vec2 | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    public_text: str
    radius: float = 130.0
    broadcast: bool = False


class ActionTerms(BaseModel):
    company_id: str | None = None
    name: str | None = Field(default=None, max_length=48)
    purpose: str | None = Field(default=None, max_length=200)
    product: str | None = None
    amount: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    equity: float | None = Field(default=None, gt=0, lt=1, allow_inf_nan=False)
    wage: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    price: float | None = Field(default=None, gt=0, le=1000, allow_inf_nan=False)
    item_id: str | None = None
    tile: str | None = None
    civic_action: Literal["grant_consent", "petition", "endorse", "dispute"] | None = None
    grantee_id: str | None = None


class ActionIntent(BaseModel):
    action: ActionType
    target_id: str | None = None
    destination: Vec2 | None = None
    message: str | None = None
    public_reason: str = ""
    goal: Goal | None = None
    reply_to: str | None = None
    terms: ActionTerms | None = None


class Activity(BaseModel):
    action: ActionType
    target_id: str | None = None
    ends_at: float
    started_at: float
    reserved_credits: float = 0
    wage: float = 0
    inputs: list[str] = Field(default_factory=list)


LifeID = Annotated[str, Field(min_length=1, max_length=48, pattern=r"^[a-zA-Z0-9_-]+$")]
LifeText = Annotated[str, Field(min_length=1, max_length=240)]
EvidenceIDs = Annotated[list[LifeID], Field(max_length=8)]


class LifeRecord(BaseModel):
    """Explicit intentions and evidence, never hidden model reasoning."""

    model_config = ConfigDict(extra="forbid")


class LifeDirection(LifeRecord):
    statement: LifeText
    evidence_memory_ids: EvidenceIDs = Field(default_factory=list)


class MilestonePlan(LifeRecord):
    id: LifeID
    statement: LifeText


class LifeMilestone(MilestonePlan):
    progress: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    evidence_memory_ids: EvidenceIDs = Field(default_factory=list)


class ProjectCreate(LifeRecord):
    id: LifeID
    title: Annotated[str, Field(min_length=1, max_length=80)]
    goal: LifeText
    next_step: LifeText
    milestones: list[MilestonePlan] = Field(min_length=1, max_length=6)
    commitment: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence_memory_ids: EvidenceIDs = Field(min_length=1)


class ProjectChange(LifeRecord):
    project_id: LifeID
    operation: Literal["advance", "revise", "suspend", "resume", "finish", "abandon"]
    note: LifeText
    evidence_memory_ids: EvidenceIDs = Field(min_length=1)
    next_step: LifeText | None = None
    milestone_id: LifeID | None = None
    progress: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    commitment: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class LifeProject(LifeRecord):
    id: LifeID
    title: Annotated[str, Field(min_length=1, max_length=80)]
    goal: LifeText
    next_step: LifeText
    milestones: list[LifeMilestone] = Field(min_length=1, max_length=6)
    status: Literal["active", "suspended", "finished", "abandoned"] = "active"
    commitment: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence_memory_ids: EvidenceIDs
    last_note: str = ""
    created_at: float
    updated_at: float


class MemoryRecall(LifeRecord):
    query: Annotated[str, Field(max_length=120)] = ""
    memory_ids: EvidenceIDs = Field(default_factory=list)


class LifeUpdate(LifeRecord):
    direction: LifeDirection | None = None
    create_projects: list[ProjectCreate] = Field(default_factory=list, max_length=1)
    project_changes: list[ProjectChange] = Field(default_factory=list, max_length=2)
    recall: MemoryRecall | None = None


class LifeState(LifeRecord):
    direction: LifeDirection | None = None
    projects: list[LifeProject] = Field(default_factory=list, max_length=24)
    recall: MemoryRecall | None = None
    revision: int = 0


class AgentDecision(BaseModel):
    intent: ActionIntent
    expressed_values: list[str] = Field(default_factory=list, max_length=4)
    relationship_updates: dict[str, float] = Field(default_factory=dict)
    source: str = "unknown"
    life_update: LifeUpdate | None = None
    provider_usage: dict[str, Any] = Field(default_factory=dict)
    provider_response_id: str | None = None


class AgentBackground(BaseModel):
    """Private synthetic starting history, not a personality or a mandated life plan."""

    age: int = Field(ge=18, le=110)
    neighborhood: str
    housing_status: str
    employment_status: str
    occupation_sector: str | None = None
    occupation_group: str | None = None
    workplace_assignment_basis: str | None = None
    biography: list[str] = Field(default_factory=list)
    employer_name: str | None = None
    synthetic: bool = True
    public_figure: dict[str, Any] | None = None
    person_reference: dict[str, Any] | None = None


class AgentState(BaseModel):
    id: str
    name: str
    position: Vec2
    background: AgentBackground | None = None
    home_id: str | None = None
    workplace_id: str | None = None
    credits: float = 10.0
    health: float = Field(default=100.0, ge=0.0, le=100.0)
    hunger: float = Field(default=15.0, ge=0.0, le=100.0)
    energy: float = Field(default=85.0, ge=0.0, le=100.0)
    bladder: float = Field(default=10.0, ge=0.0, le=100.0)
    stress: float = Field(default=15.0, ge=0.0, le=100.0)
    traits: dict[str, float] = Field(default_factory=dict)
    values: list[str] = Field(default_factory=list)
    active_goal: Goal | None = None
    life: LifeState = Field(default_factory=LifeState)
    current_action: str = "idle"
    action_target: Vec2 | None = None
    pending_intent: ActionIntent | None = None
    action_started_at: float = 0.0
    inbox: list[str] = Field(default_factory=list)
    stimulus_version: int = 0
    routine_notices: dict[str, str] = Field(default_factory=dict)
    last_decision_source: str = "none"
    decision_count: int = 0
    last_reaction: str = ""
    reaction_until: float = 0.0
    last_action_result: str = "No action yet."
    known_places: dict[str, dict[str, Any]] = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
    activity: Activity | None = None
    warmth: float = 85.0
    cleanliness: float = 90.0
    relief_until: float = 0.0
    wearing_coat: bool = False
    route_until: float = 0.0
    known_terrain: dict[str, str] = Field(default_factory=dict)
    known_signs: dict[str, str] = Field(default_factory=dict)
    route: list[Vec2] = Field(default_factory=list)
    route_goal: Vec2 | None = None
    route_revision: int = -1
    rent_arrears: int = 0
    memories: list[Memory] = Field(default_factory=list)
    relationships: dict[str, float] = Field(default_factory=dict)
    thought: str = "Taking in the city."
    speech: str | None = None
    speech_until: float = 0.0
    next_think_at: float = 0.0
    is_thinking: bool = False
    alive: bool = True
    died_at: float | None = None
    death_cause: str | None = None
    discovered_remains: list[str] = Field(default_factory=list)


class WorldObject(BaseModel):
    id: str
    kind: str
    name: str
    position: Vec2
    width: float = 32.0
    height: float = 32.0
    quantity: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class InterventionRequest(BaseModel):
    type: str
    position: Vec2 | None = None
    message: str | None = None
    tile: str | None = None
    target_id: str | None = None


class ControlRequest(BaseModel):
    action: str
    speed: float | None = None
