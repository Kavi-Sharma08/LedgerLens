"""Structured AI response schemas.

Phase 3 keeps LLM output controlled rather than free-form. Every AI analysis
is returned through these shapes so the UI can render distinct, clearly-labelled
sections (findings, evidence, likely causes, recommendations) and the system
always distinguishes a database FACT from an INFERENCE and a RECOMMENDATION.
"""

from pydantic import BaseModel, Field


class AIFinding(BaseModel):
    """A single structured finding from the analysis."""

    kind: str = Field(
        description='"fact" | "inference" | "recommendation"'
    )
    text: str = Field(description="Human-readable statement")
    detail: list[str] = Field(
        default_factory=list,
        description="Optional supporting details / sub-points",
    )


class AIEvidence(BaseModel):
    """A piece of data directly retrieved from LedgerLens that grounds the AI."""

    label: str = Field(description="Short label, e.g. 'Candidate #2'")
    value: str = Field(description="Concise rendered value")
    source: str = Field(
        default="",
        description='Which tool/data produced it, e.g. "get_match_candidates"',
    )
    entity_type: str = Field(
        default="",
        description='Optional entity type for UI action link ("transaction" | "match" | "exception" | "reconciliation")',
    )
    entity_id: str = Field(
        default="",
        description="Optional entity ObjectId string for UI action link",
    )


class AIResponse(BaseModel):
    """Controlled output schema for every AI analysis / answer.

    The model is instructed to never present an inference as a confirmed fact,
    to say when evidence is insufficient, and to keep recommendations advisory.
    """

    title: str = ""
    summary: str = ""
    findings: list[AIFinding] = Field(default_factory=list)
    evidence: list[AIEvidence] = Field(default_factory=list)
    likely_causes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    confidence: str = Field(
        default="low",
        description='"low" | "medium" | "high" relating to the available evidence',
    )
    limitations: list[str] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    role: str = Field(description='"user" | "assistant"')
    content: str = Field(default="", max_length=2000)


class AskRequest(BaseModel):
    """Body for the controlled 'Ask LedgerLens' endpoint."""

    question: str = Field(min_length=1, max_length=600)
    # Optional grounding reference: allows the UI to pre-bind specific entities
    # so the model can anchor its tools. Authorization applies per-entity.
    transaction_id: str | None = None
    reconciliation_run_id: str | None = None
    exception_id: str | None = None
    match_id: str | None = None
    history: list[ConversationTurn] | None = None

