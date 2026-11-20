"""What a mapping proposal looks like, for the API and for the model."""

from typing import Literal

from pydantic import BaseModel, Field

Origin = Literal["llm", "heuristic", "user", "none"]


class FieldMapping(BaseModel):
    target: str
    source: str | None = None
    transform: str = "trim"
    params: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0, le=1)
    origin: Origin = "none"


class MappingProposal(BaseModel):
    file_id: str
    fields: list[FieldMapping]
    warnings: list[str]
    prompt_version: str
    model: str
    attempts: int


class LLMFieldMapping(BaseModel):
    """One item of the model's answer. Kept small: a 3B model follows short schemas better."""

    target: str
    source: str | None
    transform: str
    params: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)


class LLMMappingAnswer(BaseModel):
    mappings: list[LLMFieldMapping]
