from pydantic import BaseModel, Field, field_validator


class RunCreate(BaseModel):
    sourceIds: list[str] = Field(min_length=2, max_length=10)

    @field_validator("sourceIds")
    @classmethod
    def ids_not_blank(cls, value: list[str]) -> list[str]:
        cleaned = [v.strip() for v in value]
        if any(not v for v in cleaned):
            raise ValueError("Source ids can't be empty.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Duplicate source ids in the reconciliation scope.")
        return cleaned


class RunPublic(BaseModel):
    id: str
    status: str
    sourceIds: list[str] = []
    dateFrom: str | None = None
    dateTo: str | None = None
    totalTransactions: int = 0
    matchedCount: int = 0
    likelyMatchCount: int = 0
    ambiguousCount: int = 0
    unmatchedCount: int = 0
    exceptionCount: int = 0
    algorithmVersion: str = ""
    config: dict = {}
    error: str | None = None
    startedAt: str | None = None
    completedAt: str | None = None


class MatchPublic(BaseModel):
    id: str
    reconciliationRunId: str
    transactionIds: list[str] = []
    matchType: str
    status: str
    confidence: str | None = None
    scoreBreakdown: dict = {}
    reasons: list[str] = []
    matchedFields: list[str] = []
    mismatchedFields: list[str] = []
    algorithmVersion: str = ""
    algorithmDecision: str = ""
    humanDecision: dict | None = None
    createdAt: str | None = None


class ExceptionPublic(BaseModel):
    id: str
    reconciliationRunId: str
    transactionIds: list[str] = []
    reasonCode: str
    detail: str = ""
    status: str
    resolution: dict | None = None
    createdAt: str | None = None
