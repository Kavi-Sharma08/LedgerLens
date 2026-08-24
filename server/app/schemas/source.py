from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.enums import SourceStatus, SourceType
from ..services.normalization.money import MoneyError, validate_currency


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: SourceType
    institution: str | None = Field(default=None, max_length=160)
    accountIdentifier: str | None = Field(default=None, max_length=80)
    currency: str = "INR"

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Source name can't be empty.")
        return value.strip()

    @field_validator("currency")
    @classmethod
    def currency_valid(cls, value: str) -> str:
        try:
            return validate_currency(value)
        except MoneyError as exc:
            raise ValueError(str(exc)) from exc


class SourcePublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    type: str
    institution: str | None = None
    accountIdentifier: str | None = None
    currency: str
    status: str
    metadata: dict = {}
    createdAt: str | None = None


__all__ = ["SourceCreate", "SourcePublic", "SourceType", "SourceStatus"]
