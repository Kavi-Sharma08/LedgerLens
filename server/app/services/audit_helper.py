"""Thin helper for writing audit log entries from route handlers.

Keeps audit calls clean, consistent, and easy to grep for."""

from bson import ObjectId

from ..repositories import audit_repository


async def log_audit(
    db,
    *,
    workspace_id: ObjectId,
    user_id: ObjectId,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    details: dict | None = None,
) -> None:
    """Create an audit log entry. Failures are logged but never raised —
    audit writes must never break the calling route."""
    try:
        await audit_repository.log(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    except Exception:  # noqa: BLE001 — audit is best-effort
        import logging
        logging.getLogger("ledgerlens.audit").exception(
            "Failed to write audit log action=%s entity=%s/%s",
            action, entity_type, entity_id,
        )
