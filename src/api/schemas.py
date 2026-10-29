"""Request and response models for the API (Step 7).

The models are the API contract: a field that is not declared here never leaves the server.
There is deliberately no field for a withheld draft answer.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from src import config

SYNTHETIC_NOTICE = (
    "Policy, plan, pricing and service-terms documents are SYNTHETIC examples generated "
    "for this assignment. They are not facts about the real Telco dataset or any real company."
)
CUSTOMER_ID_PATTERN = r"^[A-Za-z0-9-]{1,20}$"

Question = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=config.API_MAX_QUESTION_CHARS)
]


def _plain(value: Any) -> Any:
    """numpy scalar -> plain Python value. JSON encoders reject numpy ints and float32."""
    return value.item() if hasattr(value, "item") else value


# ---------------------------------------------------------------- requests
class CustomerRequest(BaseModel):
    customer_id: str = Field(pattern=CUSTOMER_ID_PATTERN, examples=["7590-VHVEG"])


class AskRequest(BaseModel):
    question: Question
    k: int = Field(default=config.GEN_K, ge=1, le=config.API_MAX_K)
    mode: Literal["dense", "bm25", "hybrid"] | None = None


class AgentRequest(BaseModel):
    question: Question


# ---------------------------------------------------------------- shared pieces
class Driver(BaseModel):
    feature: str
    customer_value: Any = None
    contribution: float
    effect: str

    @field_validator("customer_value", "contribution", mode="before")
    @classmethod
    def _to_plain(cls, value: Any) -> Any:
        return _plain(value)


class Prediction(BaseModel):
    prob: float
    label: str
    top_drivers: list[Driver]

    @field_validator("prob", mode="before")
    @classmethod
    def _prob_plain(cls, value: Any) -> Any:
        return _plain(value)


class Citation(BaseModel):
    chunk_id: str
    source: str
    location: dict[str, Any]
    text: str


class DocumentResponse(BaseModel):
    """Base for every response that can quote documents: the synthetic notice is attached here, once."""

    notice: str = SYNTHETIC_NOTICE


# ---------------------------------------------------------------- responses
class HealthResponse(BaseModel):
    status: str
    has_model: bool
    has_chunks: bool
    has_index: bool
    llm_key_set: bool


class PredictResponse(Prediction):
    customer_id: str


class AskResponse(DocumentResponse):
    question: str
    answer: str
    status: str
    citations: list[str]
    citation_details: list[Citation]
    can_answer: bool
    issues: list[str]
    evidence_reason: str
    retrieved_ids: list[str]


class TraceItem(BaseModel):
    step: int
    tool: str
    arguments: dict[str, Any]
    ok: bool
    seconds: float
    result_preview: str


class AgentResponse(DocumentResponse):
    question: str
    answer: str
    status: str
    steps_used: int
    trace: list[TraceItem]
    citations: list[str]
    citation_details: list[Citation]
    issues: list[str]


class RecommendationOut(BaseModel):
    text: str
    citations: list[str]


class WithheldOut(BaseModel):
    text: str
    issues: list[str]


class ChunkOut(BaseModel):
    chunk_id: str
    text: str
    source: str = ""
    score: float | None = None
    location: dict[str, Any] = Field(default_factory=dict)

    @field_validator("score", mode="before")
    @classmethod
    def _score_plain(cls, value: Any) -> Any:
        return _plain(value)


class ReportResponse(DocumentResponse):
    customer_id: str
    profile: dict[str, str]
    prediction: Prediction
    tier: str
    status: str
    recommendations: list[RecommendationOut]
    withheld: list[WithheldOut]
    evidence: list[ChunkOut]
    notes: list[str]
    report_file: str
    markdown: str