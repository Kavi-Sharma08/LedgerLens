"""Deterministic reconciliation engine package."""

from .config import ALGORITHM_VERSION, DEFAULT_MATCHING_CONFIG, MatchingConfig
from .engine import (
    ExceptionItem,
    GroupDecision,
    ReconciliationResult,
    ScoredPair,
    reconcile,
)
from . import scorers

__all__ = [
    "ALGORITHM_VERSION",
    "DEFAULT_MATCHING_CONFIG",
    "MatchingConfig",
    "ExceptionItem",
    "GroupDecision",
    "ReconciliationResult",
    "ScoredPair",
    "reconcile",
    "scorers",
]
