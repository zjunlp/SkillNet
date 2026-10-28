"""Shared SDK data contracts for search, analysis and routing."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class SkillModel(BaseModel):
    """A source record; names are not unique and stars belong to the repository."""

    skill_name: str
    skill_description: str | None = None
    author: str | None = None
    stars: int = 0
    skill_url: str | None = None
    category: str | None = None
    evaluation: dict[str, Any] | None = None
    repo_name: str | None = Field(
        default=None, description="Source repository in owner/repository form, when known."
    )
    skill_dir: str | None = Field(
        default=None,
        description="Source directory including the owner/repository prefix, when known.",
    )


class MetaModel(BaseModel):
    """
    Pagination and query metadata.
    Contains fields for both Keyword and Vector search modes.
    """

    # Common fields
    query: str | None = None
    search_mode: str = "keyword"
    category: str | None = None
    limit: int = 20
    total: int = 0

    # Keyword mode specific fields (may be None in Vector mode)
    page: int | None = None
    min_stars: int | None = None
    sort_by: str | None = None

    # Vector mode specific fields (may be None in Keyword mode)
    threshold: float | None = None

    model_config = ConfigDict(extra="ignore")


class SearchResponse(BaseModel):
    """Wrapper for the search API response."""

    data: list[SkillModel]
    meta: MetaModel
    success: bool


class Record(BaseModel):
    """Reject undocumented fields at persistence and model-output boundaries."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Endpoint(Record):
    """One explicitly configured model endpoint; credentials never serialize in cleartext."""

    api_key: SecretStr
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_endpoint(self) -> "Endpoint":
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Endpoint needs an HTTP(S) base URL without credentials or query.")
        if not self.api_key.get_secret_value().strip():
            raise ValueError("Endpoint API key must not be empty.")
        return self


class AnalysisOptions(Record):
    """Analysis budgets and explicit JSON protocol; no automatic protocol downgrade."""

    max_workers: int = Field(default=4, ge=1)
    candidate_limit: int = Field(default=8, ge=1)
    embedding_batch_size: int = Field(default=8, ge=1)
    timeout: float = Field(default=120, gt=0, allow_inf_nan=False)
    request_retries: int = Field(default=0, ge=0)
    json_mode: Literal["on", "off"] = "on"
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None


class RouteOptions(Record):
    """Retrieval and SDK exploration budgets."""

    seed_limit: int = Field(default=24, ge=1)
    candidate_limit: int = Field(default=100, ge=1)
    max_depth: int = Field(default=2, ge=0)
    timeout: float = Field(default=300, gt=0, allow_inf_nan=False)
    max_turns: int = Field(default=24, ge=1)
    read_limit: int | None = Field(default=None, ge=1)
    reasoning_effort: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="after")
    def check_limits(self) -> "RouteOptions":
        if self.candidate_limit < self.seed_limit:
            raise ValueError("candidate_limit must be at least seed_limit")
        return self


class Citation(Record):
    """One original SKILL.md line; cite multiple lines when a claim needs them."""

    line: int = Field(ge=1, description="Original source line number, as printed before the colon.")


class GroundedField(Record):
    """A capability, condition or artifact supported by source text."""

    text: str = Field(min_length=1)
    evidence: list[Citation] = Field(min_length=1)


class Scenario(Record):
    """One concrete use case, with required and established states."""

    name: str = Field(min_length=1)
    before: list[GroundedField]
    after: list[GroundedField]


class SkillProfile(Record):
    """Gym-style scenarios and Fabric-style capabilities in a single extraction."""

    capability: GroundedField
    when_to_use: list[GroundedField]
    scenarios: list[Scenario]
    inputs: list[GroundedField]
    outputs: list[GroundedField]
    constraints: list[GroundedField]
    tools: list[GroundedField]


class SkillSource(Record):
    """Stable package identity and the exact analyzed source."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    skill_id: str
    name: str
    path: str
    source: str
    content_hash: str


class AnalyzedSkill(SkillSource):
    """Source snapshot with its extracted profile."""

    profile: SkillProfile


class RelationContext(Record):
    """A scenario-specific explanation with evidence from both endpoints."""

    scenario: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    conditions: list[str]
    source_evidence: list[Citation] = Field(min_length=1)
    target_evidence: list[Citation] = Field(min_length=1)


class Relation(Record):
    """Composition is directed; similarity uses a canonical unordered pair."""

    source: str
    target: str
    type: Literal["compose_with", "similar_to"]
    contexts: list[RelationContext] = Field(min_length=1)


class NoRelation(Record):
    """A first-class negative judgment, never materialized as a graph edge."""

    outcome: Literal["none"]
    reason: str = Field(min_length=1)


class RelatedSkills(Record):
    """A positive judgment with at least one source-supported relationship."""

    outcome: Literal["related"]
    relations: list[Relation] = Field(min_length=1)


class RelationJudgment(Record):
    """Require an explicit positive or negative decision before producing edges."""

    decision: NoRelation | RelatedSkills


class GraphSnapshot(Record):
    """The canonical input to both full Wiki rendering and task routing."""

    schema_version: Literal[1] = 1
    embedding_model: str
    embedding_base_url: str
    skills: list[AnalyzedSkill]
    relations: list[Relation]


class AnalysisResult(Record):
    """Location and summary of a successfully published analysis."""

    index_dir: Path
    skill_count: int
    relation_counts: dict[str, int]
    cache_hits: dict[str, int]


class Selection(Record):
    """One Explorer-selected skill ID and its task-specific reason."""

    skill_id: str
    reason: str = Field(min_length=1)


class SkillSelection(Record):
    """Structured output shared by the SDK backends."""

    skills: list[Selection]


class RoutedSkill(Selection):
    """Selected skill enriched with its registered package name and path."""

    name: str
    path: str


class RouteResult(Record):
    """A bounded skill set, not an execution plan."""

    skills: list[RoutedSkill]
    usage: dict[str, int | float] | None = None


@dataclass
class Exploration:
    """Structured selection and usage reported by the SDK."""

    selection: SkillSelection
    usage: dict[str, int | float] | None = None
