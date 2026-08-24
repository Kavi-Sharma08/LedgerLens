"""Financial domain models. Dataclass shapes mirroring MongoDB documents."""

from .enums import (
    CandidateStatus,
    Direction,
    ExceptionReason,
    ExceptionStatus,
    FileStatus,
    MatchType,
    ReconciliationStatus,
    RunStatus,
    SourceStatus,
    SourceType,
    TransactionStatus,
    TransactionType,
)
from .match import Match
from .match_candidate import MatchCandidate, as_decimal, decimal128
from .raw_transaction import RawTransaction
from .reconciliation_exception import ReconciliationException
from .reconciliation_run import ReconciliationRun
from .source import Source
from .source_file import SourceFile
from .transaction import Transaction

__all__ = [
    "CandidateStatus",
    "Direction",
    "ExceptionReason",
    "ExceptionStatus",
    "FileStatus",
    "MatchType",
    "ReconciliationStatus",
    "RunStatus",
    "SourceStatus",
    "SourceType",
    "TransactionStatus",
    "TransactionType",
    "Match",
    "MatchCandidate",
    "as_decimal",
    "decimal128",
    "RawTransaction",
    "ReconciliationException",
    "ReconciliationRun",
    "Source",
    "SourceFile",
    "Transaction",
]
