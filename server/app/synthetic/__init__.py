"""Synthetic data package: deterministic dataset + ground truth."""

from .dataset import (
    ACCOUNTING,
    BANK,
    GATEWAY,
    SOURCE_NAMES,
    RecordSpec,
    accounting_records,
    all_records,
    bank_records,
    gateway_records,
    records_for_source,
)
from .ground_truth import GROUND_TRUTH, expected_for

__all__ = [
    "ACCOUNTING",
    "BANK",
    "GATEWAY",
    "SOURCE_NAMES",
    "RecordSpec",
    "accounting_records",
    "all_records",
    "bank_records",
    "gateway_records",
    "records_for_source",
    "GROUND_TRUTH",
    "expected_for",
]
