"""AI orchestration service.

Wire-up: route -> ai_service -> AIProvider (LLM) -> tool registry -> authorized
repositories -> MongoDB. The LLM never touches MongoDB directly; every piece of
evidence arrives through a workspace-scoped, permission-gated tool.

This module owns building the tool context from the authenticated route deps,
driving the provider tool loop, and coercing the LLM's final structured JSON
into the controlled AIResponse schema. Business logic on the data is not
recomputed here — the engine remains authoritative.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from bson import ObjectId

from ...core.config import get_settings
from ...models.enums import member_has_permission
from ...repositories import workspace_member_repository as member_repo
import json as _json

from . import prompts
from .provider import (
    AIError,
    AIProviderError,
    AIResponseError,
    AIUnavailableError,
    get_provider,
)
from .schemas import AIFinding, AIEvidence, AIResponse, AskRequest
from .tools import execute_tool, get_tools, tool_schemas

logger = logging.getLogger("ledgerlens.ai.service")

EMPTY_RESPONSE = AIResponse(
    title="Analysis unavailable",
    summary="No analysis could be produced for this record.",
    findings=[
        AIFinding(
            kind="inference",
            text="There was not enough retrieved evidence to analyse this record.",
        )
    ],
    limitations=["The AI could not produce an analysis."],
)


class AIAnalysisError(AIError):
    """Raised when an AI analysis cannot be produced (surfaced to routes).

    Carries a `category` (ai_unavailable | ai_request_failed |
    tool_execution_failed | no_answer) that the routes map to a stable error
    code the UI can present without exposing internals.
    """

    def __init__(self, message: str = "", *, category: str | None = None):
        super().__init__(message)
        if category:
            self.category = category


async def analyze_transaction(db, *, workspace_id, user_id, transaction_id, can_view, can_manage_exceptions):
    context = _build_context(db, workspace_id, user_id, can_view, can_manage_exceptions)
    prompt = _seed_with_transaction_guidance(transaction_id)
    return await _run(context, system=prompts.TRANSACTION_ANALYSIS, prompt=prompt)


async def analyze_match(db, *, workspace_id, user_id, match_id, can_view, can_manage_exceptions):
    context = _build_context(db, workspace_id, user_id, can_view, can_manage_exceptions)
    prompt = {"role": "user", "content": f"Analyse the match with id {match_id}. Retrieve its details and explain it."}
    return await _run(context, system=prompts.MATCH_ANALYSIS, prompt=prompt)


async def analyze_exception(db, *, workspace_id, user_id, exception_id, can_view, can_manage_exceptions):
    context = _build_context(db, workspace_id, user_id, can_view, can_manage_exceptions)
    prompt = {"role": "user", "content": f"Analyse the exception with id {exception_id}. Retrieve its context and explain it."}
    return await _run(context, system=prompts.EXCEPTION_ANALYSIS, prompt=prompt)


async def analyze_reconciliation(db, *, workspace_id, user_id, run_id, can_view, can_manage_exceptions):
    context = _build_context(db, workspace_id, user_id, can_view, can_manage_exceptions)

    # Pre-assemble a bounded slice of the run's evidence via the same
    # permission-gated tools, then make a SINGLE Groq request (no tool loop,
    # no tool schemas) so a reconciliation explanation stays well within the
    # provider's per-minute token budget and completes in a predictable time.
    try:
        evidence = await _assemble_reconciliation_evidence(context, run_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reconciliation evidence assembly failed: %s", type(exc).__name__)
        evidence = {"error": str(exc)[:300]}

    message = {
        "role": "user",
        "content": (
            f"Analyse the reconciliation run with id {run_id}.\n\n"
            "Here is the evidence retrieved from LedgerLens:\n"
            f"{json.dumps(evidence, default=str)}"
        ),
    }
    return await _run_once(system=prompts.RECONCILIATION_INLINE, message=message)


async def _assemble_reconciliation_evidence(context, run_id: str) -> dict:
    """Gather bounded reconciliation evidence by calling the existing tools.

    Reuses the exact evidence-shaping and permission gating of the tool layer so
    the analysis is grounded and workspace-scoped, without spinning up the full
    multi-round tool loop.
    """
    from .tools import execute_tool

    async def _call(name: str, args: dict) -> Any:
        result = execute_tool(context, name, args)
        if hasattr(result, "__await__"):
            result = await result
        return result

    summary = await _call("get_reconciliation_summary", {"reconciliation_run_id": run_id})

    matches, unmatched, exceptions = {}, {}, {}
    try:
        matches = await _call(
            "list_run_matches",
            {"reconciliation_run_id": run_id, "limit": 10},
        )
    except Exception:  # noqa: BLE001
        matches = {}

    try:
        unmatched = await _call(
            "list_run_unmatched",
            {"reconciliation_run_id": run_id, "sort_by": "amount", "order": "desc", "limit": 15},
        )
    except Exception:  # noqa: BLE001
        unmatched = {}

    try:
        exceptions = await _call(
            "list_run_exceptions",
            {"reconciliation_run_id": run_id, "limit": 15},
        )
    except Exception:  # noqa: BLE001
        exceptions = {}

    evidence = {"run": summary, "matches": matches.get("matches", []), "unmatched": unmatched.get("unmatched", []), "exceptions": exceptions.get("exceptions", [])}
    if matches.get("message"):
        evidence["matchesMessage"] = matches["message"]
    if unmatched.get("message"):
        evidence["unmatchedMessage"] = unmatched["message"]
    if exceptions.get("message"):
        evidence["exceptionsMessage"] = exceptions["message"]
    return evidence


async def ask(db, *, workspace_id, user_id, request: AskRequest, can_view, can_manage_exceptions):
    context = _build_context(db, workspace_id, user_id, can_view, can_manage_exceptions)
    guidance_parts = []
    if request.reconciliation_run_id:
        guidance_parts.append(f"CURRENT RECONCILIATION RUN ID: {request.reconciliation_run_id}")
    if request.transaction_id:
        guidance_parts.append(f"CURRENT TRANSACTION ID: {request.transaction_id}")
    if request.match_id:
        guidance_parts.append(f"CURRENT MATCH ID: {request.match_id}")
    if request.exception_id:
        guidance_parts.append(f"CURRENT EXCEPTION ID: {request.exception_id}")

    context_str = ""
    if guidance_parts:
        context_str = (
            "\n[ACTIVE CONTEXT: "
            + " | ".join(guidance_parts)
            + "]\nImportant: When answering questions about 'this reconciliation', 'unmatched transactions', or 'exceptions', pass the active reconciliation_run_id to tool calls."
        )

    history_messages = []
    if request.history:
        for turn in request.history[-6:]:
            if turn.role in ("user", "assistant") and turn.content:
                history_messages.append({"role": turn.role, "content": turn.content})

    current_message = {
        "role": "user",
        "content": f"{request.question}{context_str}\nRetrieve the necessary tool evidence for this active reconciliation before answering.",
    }
    messages = history_messages + [current_message]
    return await _run(context, system=prompts.ASK_SYSTEM, messages=messages)



# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _seed_with_transaction_guidance(transaction_id: str) -> dict:
    return {
        "role": "user",
        "content": (
            f"Analyse the transaction with id {transaction_id}. Start by retrieving it "
            "with get_transaction_context, which returns its matches, candidates, "
            "exceptions and runs in one call — use that before individual lookups. "
            "Produce the structured JSON."
        ),
    }


def _build_context(db, workspace_id: ObjectId, user_id: ObjectId, can_view: bool, can_manage: bool):
    from .tools import ToolContext

    return ToolContext(
        db=db,
        workspace_id=workspace_id,
        user_id=user_id,
        can_view_data=can_view,
        can_manage_exceptions=can_manage,
    )


async def _run(context, *, system: str, prompt: dict | None = None, messages: list[dict] | None = None) -> AIResponse:
    settings = get_settings()
    try:
        provider = get_provider()
    except AIUnavailableError as exc:
        raise AIAnalysisError(str(exc), category=exc.category) from exc

    tools = tool_schemas()

    async def _execute(name: str, args: dict) -> dict:
        return await execute_tool(context, name, args)

    exec_messages = messages if messages is not None else ([prompt] if prompt else [])

    try:
        turns = await provider.run(
            system=system,
            messages=exec_messages,
            tools=tools,
            execute_tool=_execute,
            max_tool_rounds=settings.ai_max_tool_rounds,
            timeout=settings.ai_request_timeout_seconds,
        )
    except AIError as exc:
        raise AIAnalysisError(str(exc), category=getattr(exc, "category", "ai_request_failed")) from exc

    return _parse_response(turns)


async def _run_once(*, system: str, message: dict) -> AIResponse:
    """Make a single Groq completion with pre-assembled evidence — no tool loop.

    Used by analyze_reconciliation to guarantee exactly one Groq API request
    per reconciliation explanation, regardless of how many data points the run has.
    """
    try:
        provider = get_provider()
    except AIUnavailableError as exc:
        raise AIAnalysisError(str(exc), category=exc.category) from exc

    # Reasoning models occasionally return a reasoning-only response with an
    # empty `content` field. Retry once (the response is non-deterministic) so a
    # single transient empty answer does not surface as a hard failure.
    raw_content = ""
    last_exc: AIError | None = None
    for attempt in range(2):
        try:
            raw_content = await provider.complete_once(
                system=system,
                messages=[message],
            )
            break
        except AIError as exc:
            # Only a transient empty answer is retried; anything else surfaces
            # immediately, always wrapped as AIAnalysisError so the route can
            # map it to a stable error code.
            if getattr(exc, "category", None) != "no_answer":
                raise AIAnalysisError(
                    str(exc), category=getattr(exc, "category", "ai_request_failed")
                ) from exc
            last_exc = exc
            logger.warning("AI single-completion returned no answer; retrying (attempt %s)", attempt + 2)

    if not raw_content:
        if last_exc is not None:
            raise AIAnalysisError(str(last_exc), category=getattr(last_exc, "category", "no_answer")) from last_exc
        raise AIAnalysisError("The AI did not generate an answer. Please try again.", category="no_answer")

    # Wrap in a single turns list so _parse_response works unchanged
    turns = [{"role": "assistant", "content": raw_content}]
    return _parse_response(turns)


def _parse_response(turns: list[dict]) -> AIResponse:
    """Extract the final assistant content and coerce it to AIResponse.

    If the model produced no usable structured answer (no content at all, or
    content that isn't parseable JSON), this raises an AIAnalysisError with the
    `no_answer` category so the UI can present a specific, non-generic message.
    """
    # Find the last assistant message that carries content (the model's final
    # structured answer after any tool calls).
    content_candidates = [t.get("content") for t in turns if t.get("role") == "assistant" and t.get("content")]
    if not content_candidates:
        raise AIAnalysisError(
            "The AI did not generate an answer. Please try again.",
            category="no_answer",
        )
    raw = content_candidates[-1]
    data = _extract_json(raw)
    if data is None:
        # The model answered but not as parseable JSON.
        raise AIAnalysisError(
            "The AI did not generate an answer. Please try again.",
            category="no_answer",
        )
    return _coerce(data)


def _extract_json(raw: str) -> dict | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    # Allow the model to wrap JSON in ```json fences or prose.
    if raw.startswith("```"):
        raw = raw.strip("`")
        first_line, _, rest = raw.partition("\n")
        if first_line.strip().lower() in ("json", "```json"):
            raw = rest
        else:
            raw = raw[len(first_line):]
        raw = raw.strip()
    # Try direct parse
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else None
    except ValueError:
        pass
    # Try to find the outermost {...} block.
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            result = json.loads(raw[start : end + 1])
            return result if isinstance(result, dict) else None
        except ValueError:
            return None
    return None


def _coerce(data: dict) -> AIResponse:
    def _findings(raw: Any) -> list[AIFinding]:
        if not isinstance(raw, list):
            return []
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "inference")).lower()
            if kind not in ("fact", "inference", "recommendation"):
                kind = "inference"
            out.append(
                AIFinding(
                    kind=kind,
                    text=str(item.get("text", "")),
                    detail=[str(d) for d in (item.get("detail") or []) if d],
                )
            )
        return out

    def _evidence(raw: Any) -> list[AIEvidence]:
        if not isinstance(raw, list):
            return []
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            out.append(
                AIEvidence(
                    label=str(item.get("label", "")),
                    value=str(item.get("value", "")),
                    source=str(item.get("source", "")),
                    entity_type=str(item.get("entity_type", "") or item.get("entityType", "")),
                    entity_id=str(item.get("entity_id", "") or item.get("entityId", "")),
                )
            )
        return out


    confidence = str(data.get("confidence", "low")).lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "low"

    findings = _findings(data.get("findings"))
    summary = str(data.get("summary", "")).strip()
    if not summary and findings:
        summary = findings[0].text
    title = str(data.get("title", "") or "Analysis").strip()

    # A response with literally nothing usable is NOT "analysis unavailable" —
    # it means the model returned junk. Fail distinctly so the UI can say
    # "please retry" instead of inventing a no-evidence story.
    usable = summary or title or findings or _evidence(data.get("evidence"))
    if not usable:
        raise AIAnalysisError(
            "The AI did not produce a usable answer. Please try again.",
            category="no_answer",
        )

    return AIResponse(
        title=title,
        summary=summary,
        findings=findings,
        evidence=_evidence(data.get("evidence")),
        likely_causes=[str(c) for c in (data.get("likely_causes") or []) if c],
        recommendations=[str(r) for r in (data.get("recommendations") or []) if r],
        confidence=confidence,
        limitations=[str(l) for l in (data.get("limitations") or []) if l],
    )


def resolve_capabilities(db, workspace_id: ObjectId, user_id: ObjectId, role, role_permissions: dict) -> tuple[bool, bool]:
    """Resolve the AI-relevant permission flags for the current membership.

    Reuses the SAME member_has_permission logic as the whole backend — no
    second permission system is created."""
    can_view = member_has_permission(role, role_permissions, "view_data")
    can_manage_exceptions = member_has_permission(role, role_permissions, "manage_exceptions")
    return can_view, can_manage_exceptions
