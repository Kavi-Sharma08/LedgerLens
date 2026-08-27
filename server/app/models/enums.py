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


# --- Workspace authorization model ----------------------------------------
#
# Roles are fixed: OWNER, ADMIN, MEMBER, VIEWER. The OWNER always holds every
# permission. For the other roles, what each role can actually DO is a
# workspace-level, owner-controlled configuration (Workspace.role_permissions).
# This keeps the enforceable capability list on the server, never in the UI.

# Every permission an OWNER always holds. The REST of the system grants only
# permissions from this catalog; anything else is denied by default.
PERMISSIONS = frozenset({
    "view_data",              # view transactions / sources / matches / overview
    "manage_sources",         # create/manage financial sources
    "upload_files",           # upload / manage source files
    "run_reconciliation",     # start a reconciliation run
    "approve_matches",        # approve a match
    "reject_matches",         # reject a match
    "manage_exceptions",      # assign / change status / add notes on exceptions
    "invite_members",         # send invitations
    "manage_members",         # change roles / remove members
    "view_audit_log",         # read the audit feed
    "manage_workspace_settings",  # rename workspace / manage permissions
})

ALL_PERMISSIONS = PERMISSIONS  # every member of the catalog is OWNER-grantable

# Baseline grants used to seed a new workspace's role_permissions. The OWNER
# can tighten/loosen these per role. MEMBER and VIEWER start read-only:
# operational actions are only enabled when the owner explicitly grants them.
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    WorkspaceRole.ADMIN.value: [
        "view_data",
        "manage_sources",
        "upload_files",
        "run_reconciliation",
        "approve_matches",
        "reject_matches",
        "manage_exceptions",
        "invite_members",
        "manage_members",
        "view_audit_log",
    ],
    WorkspaceRole.MEMBER.value: [
        "view_data",
    ],
    WorkspaceRole.VIEWER.value: [
        "view_data",
    ],
}


def member_has_permission(
    role: WorkspaceRole | str,
    role_permissions: dict | None,
    permission: str,
) -> bool:
    """Whether a member with *role* has *permission* given the workspace's
    owner-controlled per-role grants.

    The OWNER always retains every permission. Unknown permissions are denied.
    """
    role_value = role.value if isinstance(role, WorkspaceRole) else str(role)
    if role_value == WorkspaceRole.OWNER.value:
        return permission in ALL_PERMISSIONS
    # An empty/None workspace document (pre-permission-model workspaces) falls
    # back to the baseline grants. Once the owner has configured grants the
    # stored value is authoritative — a missing role key means "no grants".
    if role_permissions is None or role_permissions == {}:
        grants = DEFAULT_ROLE_PERMISSIONS.get(role_value, []) or []
    else:
        grants = role_permissions.get(role_value, []) or []
    return permission in grants