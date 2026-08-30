"""AI tools for source evidence."""

from __future__ import annotations

from bson import ObjectId

from ....repositories import source_repository
from ..tools import register_tool, require_view

_OBJ_ID_PARAM = {"type": "string", "description": "24-character MongoDB ObjectId"}


@register_tool(
    "get_source",
    description=(
        "Retrieve a financial source's basic details (name, type, institution, "
        "account identifier, currency, status) by id."
    ),
    schema={
        "type": "object",
        "properties": {"source_id": _OBJ_ID_PARAM},
        "required": ["source_id"],
        "additionalProperties": False,
    },
)
async def get_source(ctx, args: dict) -> dict:
    """Retrieve a financial source's basic details."""
    require_view(ctx)
    source_id = args.get("source_id") or args.get("id")
    if not source_id:
        return {"error": "source_id is required."}
    try:
        source = await source_repository.get_by_id(ctx.db, ctx.workspace_id, source_id)
    except Exception:
        return {"source": {}, "message": "That source wasn't found."}
    return {
        "source": {
            "id": str(source.id),
            "name": source.name,
            "type": source.type.value if hasattr(source.type, "value") else str(source.type),
            "institution": source.institution,
            "accountIdentifier": source.account_identifier,
            "currency": source.currency,
            "status": source.status.value if hasattr(source.status, "value") else str(source.status),
        }
    }


@register_tool(
    "list_workspace_sources",
    description=("List the financial sources in the current workspace (max 50)."),
    schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
)
async def list_workspace_sources(ctx, args: dict) -> dict:
    """List sources in the current workspace."""
    require_view(ctx)
    page = await source_repository.list_sources(ctx.db, ctx.workspace_id, limit=50)
    return {
        "sources": [
            {
                "id": str(s.id),
                "name": s.name,
                "type": s.type.value if hasattr(s.type, "value") else str(s.type),
                "institution": s.institution,
                "currency": s.currency,
                "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            }
            for s in page.items
        ]
    }