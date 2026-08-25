"""Shared financial-domain enumerations.

Every status/type that persists to MongoDB lives here so collections stay
consistent and queries never depend on arbitrary strings.
"""

from enum import Enum


class SourceType(str, Enum):
    BANK = "BANK"
    PAYMENT_PROCESSOR = "PAYMENT_PROCESSOR"
    ACCOUNTING = "ACCOUNTING"
    CARD = "CARD"
    ERP = "ERP"
    MANUAL = "MANUAL"


class SourceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class FileStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"


class Direction(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class TransactionType(str, Enum):
    SALE = "SALE"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    REVERSAL = "REVERSAL"
    FEE = "FEE"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class MatchType(str, Enum):
    EXACT = "EXACT"
    FUZZY = "FUZZY"
    MANUAL = "MANUAL"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"


class ReconciliationStatus(str, Enum):
    """Per-transaction/per-group outcome of a reconciliation run."""

    MATCHED = "MATCHED"
    LIKELY_MATCH = "LIKELY_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"
    EXCEPTION = "EXCEPTION"
    MANUAL_MATCHED = "MANUAL_MATCHED"


class CandidateStatus(str, Enum):
    CONSIDERED = "CONSIDERED"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"


class ExceptionReason(str, Enum):
    UNSUPPORTED_CURRENCY = "UNSUPPORTED_CURRENCY"
    POSSIBLE_FEE = "POSSIBLE_FEE"
    STATUS_CONFLICT = "STATUS_CONFLICT"
    ZERO_AMOUNT = "ZERO_AMOUNT"
    FAILED_TRANSACTION = "FAILED_TRANSACTION"
    CANDIDATE_COLLISION = "CANDIDATE_COLLISION"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ExceptionStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class WorkspaceRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class MembershipStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    INVITED = "INVITED"


class InvitationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


# Role → permission mapping.  A role inherits all permissions from roles
# below it in the hierarchy (OWNER > ADMIN > MEMBER > VIEWER).
ROLE_HIERARCHY: dict[WorkspaceRole, int] = {
    WorkspaceRole.OWNER: 40,
    WorkspaceRole.ADMIN: 30,
    WorkspaceRole.MEMBER: 20,
    WorkspaceRole.VIEWER: 10,
}

# Named permissions.  Checked via `user_has_permission(role, perm)`.
PERMISSIONS = {
    "manage_workspace": WorkspaceRole.OWNER,
    "manage_members": WorkspaceRole.ADMIN,
    "invite_members": WorkspaceRole.ADMIN,
    "create_source": WorkspaceRole.MEMBER,
    "upload_file": WorkspaceRole.MEMBER,
    "run_reconciliation": WorkspaceRole.MEMBER,
    "approve_match": WorkspaceRole.MEMBER,
    "resolve_exception": WorkspaceRole.MEMBER,
    "view_data": WorkspaceRole.VIEWER,
    "view_audit": WorkspaceRole.ADMIN,
}


def user_has_permission(role: WorkspaceRole, permission: str) -> bool:
    """Check whether *role* grants *permission* using the hierarchy."""
    required = PERMISSIONS.get(permission)
    if required is None:
        return False
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(required, 0)
