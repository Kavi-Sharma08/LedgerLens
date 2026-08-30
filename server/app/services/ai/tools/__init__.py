"""AI tool registry.

Tools are the ONLY way the LLM can reach LedgerLens data. Each tool:
  - receives a `ToolContext` carrying the authenticated user's workspace and
    permission profile (so every retrieval is workspace-scoped and gated);
  - returns a small, concise, JSON-safe dict of structured evidence;
  - never exposes raw Mongo documents, secrets, or engine parameters.

Every tool also declares an OpenAI-style function schema (name + description +
property schemas) so the LLM can reliably select the right tool and produce the
correct argument names on the first call — an empty `{"type": "object"}`
parameters block gives models no way to infer argument keys and produces
malformed calls or provider 400s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from bson import ObjectId


@dataclass
class ToolContext:
    """Authorized retrieval context shared by every AI tool.

    The route builds this AFTER the standard dependency chain (authenticated
    user, active workspace, membership verified, `view_data` permission at
    minimum). Tools therefore run inside the exact same authorization model as
    the rest of LedgerLens — a forged workspace id never reaches a tool.
    """

    db: Any
    workspace_id: ObjectId
    user_id: ObjectId
    # Granular permission flags resolved from the membership role/grants.
    # Used so exception/notes retrieval reflects the same capability checks.
    can_view_data: bool = True
    can_manage_exceptions: bool = False


ToolFunc = Callable[[ToolContext, dict], Any]


def _require_view(ctx: ToolContext) -> None:
    if not ctx.can_view_data:
        raise PermissionError("view_data")


def require_view(ctx: ToolContext) -> None:
    """Guard: every read tool requires the view_data capability."""
    _require_view(ctx)


_REGISTRY: dict[str, ToolFunc] = {}
_SCHEMAS: dict[str, dict] = {}


def register_tool(name: str, *, description: str = "", schema: dict | None = None):
    """Decorator factory: @register_tool("name") marks a tool function.

    `description` drives the LLM's tool selection; `schema` is the JSON-Schema
    for the tool's arguments (`{"type": "object", "properties": {...}}`).
    """

    def _decorator(fn: ToolFunc) -> ToolFunc:
        _REGISTRY[name] = fn
        _SCHEMAS[name] = {
            "description": description,
            "schema": schema
            or {"type": "object", "properties": {}, "additionalProperties": False},
        }
        return fn

    return _decorator


def get_tools() -> dict[str, ToolFunc]:
    """Import tool modules (registering them) then return the registry."""
    from . import exceptions as _exceptions  # noqa: F401
    from . import matches as _matches  # noqa: F401
    from . import reconciliation as _reconciliation  # noqa: F401
    from . import sources as _sources  # noqa: F401
    from . import transactions as _transactions  # noqa: F401

    return dict(_REGISTRY)


_TOOL_DESC_CAP = 110
_PARAM_DESC_CAP = 42


def _tidy(text: str, cap: int) -> str:
    """Condense a verbose doc string to a terse sentence for the tool schema.

    Full JSON-Schema structure (names, types, required, enums) is preserved on
    every call — this only shortens the free-text hints. Keeping these payloads
    small is essential because every request re-sends the full tool set, and the
    Groq on-demand tier has a hard per-minute token budget.
    """
    text = " ".join((text or "").split())
    if len(text) <= cap:
        return text
    return text[:cap].rsplit(" ", 1)[0].rstrip(".,;: ") + "..."


def tool_schemas() -> list[dict]:
    """OpenAI-style tool schemas describing the available AI tools.

    Descriptions are condensed to keep the per-request token footprint small
    (the full tool set is re-sent on every call and must fit the provider's
    per-minute token budget). Tool names and the JSON-Schema parameter structure
    are preserved exactly so the model can still select tools and craft correct
    arguments.
    """
    tools = get_tools()
    out = []
    for name in tools:
        meta = _SCHEMAS.get(name, {})
        schema = meta.get("schema") or {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        if isinstance(schema, dict):
            props = schema.get("properties")
            if isinstance(props, dict):
                for pname, pdef in props.items():
                    if isinstance(pdef, dict) and pdef.get("description"):
                        pdef["description"] = _tidy(pdef["description"], _PARAM_DESC_CAP)
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": _tidy(meta.get("description", ""), _TOOL_DESC_CAP),
                    "parameters": schema,
                },
            }
        )
    return out


def tool_names() -> list[str]:
    return list(get_tools())


async def execute_tool(ctx: ToolContext, name: str, args: dict) -> dict:
    """Run one tool by name.

    - Unknown tool          -> AIProviderError (the loop treats this as a
                               model error, never a fake "no data").
    - Invalid argument shape -> AIProviderError (the model must retry).
    - PermissionError       -> propagates (the route already gates, but the
                               tool enforces it too).
    - Any other exception   -> AIProviderError(category="tool_execution_failed")
                               so a real tool failure is surfaced as a distinct
                               error category instead of being silently
                               converted into "no evidence exists".
    """
    from ..provider import AIProviderError

    tools = get_tools()
    fn = tools.get(name)
    if fn is None:
        raise AIProviderError(
            f"The AI assistant requested an unknown tool '{name}'.",
            category="tool_execution_failed",
        )
    if not isinstance(args, dict):
        args = {}
    try:
        result = fn(ctx, args)
        if hasattr(result, "__await__"):
            result = await result
        return result
    except TypeError as exc:
        raise AIProviderError(
            f"The AI assistant called '{name}' with invalid arguments.",
            category="tool_execution_failed",
        ) from exc
    except AIProviderError:
        raise
    except PermissionError:
        raise
    except Exception as exc:  # noqa: BLE001 - infrastructure failure, surfaced
        raise AIProviderError(
            "The AI assistant could not retrieve the data it needed from "
            "this workspace. Please try again.",
            category="tool_execution_failed",
        ) from exc