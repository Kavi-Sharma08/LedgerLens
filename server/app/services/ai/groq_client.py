"""Groq provider (OpenAI-compatible tool calling over HTTPS).

Implements the AIProvider contract against Groq's OpenAI-compatible chat
completions endpoint. Uses the `httpx` library already shipped with the project
(no extra SDK dependency) and never logs or returns the API key.

Tool-calling loop (run):
  1. Issue a chat request with the provided tools.
  2. If the model emits tool_calls, execute each via execute_tool, append the
     exact assistant message + corresponding role=tool messages to the history,
     then call Groq again.
  3. Repeat until the model produces a plain text answer (no tool_calls) or the
     round budget is exhausted.
  4. If the round budget is exhausted, make one final synthesis call WITHOUT
     tools — the model sees all accumulated evidence and is asked to answer now.
  5. If that final call also fails, raise AIProviderError(no_answer).

Duplicate tool-call prevention:
  If the model requests the same tool with identical arguments as a previous
  round, the cached result is re-injected as a tool message WITHOUT calling the
  tool again. A _system_notice is added to the tool result (copy, not mutate)
  telling the model it already has this evidence and must stop calling tools.

Failure policy:
  - provider 429 (rate limit)   -> bounded exponential backoff with jitter,
                                   Retry-After header respected, category=rate_limited
  - provider 5xx (server error) -> bounded retry, category=ai_request_failed
  - provider transport error    -> bounded retry, category=ai_unavailable
  - tool execution failure      -> AIProviderError(tool_execution_failed), aborts loop
  - exhausted rounds            -> fallback synthesis call, then no_answer if that fails

Diagnostics are intentionally *safe*: they log transport status, which tool was
called, and the size of its result - never secrets, API keys, prompts, or full
financial records.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from decimal import Decimal
from typing import Any, Callable

import httpx

from .provider import (
    AIError,
    AIProvider,
    AIProviderError,
    AIResponseError,
)

logger = logging.getLogger("ledgerlens.ai.groq")


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_loads(text: str) -> Any:
    return json.loads(text)


def _json_dumps(value: Any) -> str:
    """Serialize tool results to JSON, tolerating BSON-ish types."""

    def _default(o):
        if type(o).__name__ == "ObjectId":
            return str(o)
        if type(o).__name__ == "Decimal128":
            try:
                return str(o.to_decimal())
            except Exception:  # noqa: BLE001
                return str(o)
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, (bytes, bytearray)):
            return o.hex()
        if hasattr(o, "isoformat"):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    return json.dumps(value, default=_default)


def _arg_keys(args: dict):
    return (args and args.keys()) or []


def _truncate(text: str, limit: int) -> str:
    """Best-effort truncation of a tool result for safe fallback rendering."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _extract_error_message(response: httpx.Response) -> str:
    """Best-effort safe extraction of the provider error text for logs.
    Never logs API keys or full financial data."""
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        return ""
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    if isinstance(body, dict) and body.get("message"):
        return str(body["message"])
    return ""


def _probe_response(data: Any) -> dict:
    """Safe, secret-free summary of a provider chat response for diagnostics.

    Logs ONLY shape diagnostics (finish_reason, whether the model emitted text
    or tool_calls, char counts, usage counters) — never message content, tool
    arguments, or any financial record.
    """
    try:
        if not isinstance(data, dict):
            return {"shape": type(data).__name__}
        choices = data.get("choices")
        probe: dict[str, Any] = {"choices": len(choices) if isinstance(choices, list) else None}
        if isinstance(choices, list) and choices:
            choice = choices[0]
            if isinstance(choice, dict):
                if choice.get("finish_reason"):
                    probe["finish_reason"] = choice["finish_reason"]
                msg = choice.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    probe["has_content"] = bool(content)
                    if content:
                        probe["content_chars"] = len(str(content))
                    calls = msg.get("tool_calls")
                    probe["tool_calls"] = len(calls) if isinstance(calls, list) else (0 if calls is None else "present")
                    if msg.get("reasoning") is not None:
                        probe["has_reasoning"] = bool(msg["reasoning"])
        usage = data.get("usage")
        if isinstance(usage, dict):
            probe["usage"] = {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage}
        return probe
    except Exception:  # noqa: BLE001
        return {"probe": "error"}


# ---------------------------------------------------------------------------
# GroqProvider
# ---------------------------------------------------------------------------

class GroqProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        model: str = "",
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        from ...core.config import get_settings

        settings = get_settings()
        self.api_key = api_key
        self.base_url = (base_url or settings.groq_base_url).rstrip("/")
        self.model = model or settings.groq_model
        self._endpoint = f"{self.base_url}/chat/completions"
        self._timeout = settings.ai_request_timeout_seconds
        self._max_tokens = settings.ai_max_tokens
        # Injectable transport keeps the client hermetic in tests.
        self._transport = transport
        # Use near-zero delays in test mode (transport injected).
        self._test_mode = transport is not None

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _jitter(self, base: float) -> float:
        """Add +-25% random jitter to avoid thundering herd on retries."""
        return base * (0.75 + random.random() * 0.5)  # noqa: S311

    async def _post(self, payload: dict) -> dict:
        """POST to Groq with bounded retries, exponential backoff + jitter,
        and Retry-After support on 429. Never logs secrets."""
        max_retries = 3
        base_delay = 0.001 if self._test_mode else 1.0

        for attempt in range(max_retries + 1):
            try:
                async with self._new_client() as client:
                    response = await client.post(
                        self._endpoint, headers=self._headers(), json=payload
                    )
            except httpx.TimeoutException as exc:
                logger.warning(
                    "AI request to Groq timed out after %ss (attempt %s/%s)",
                    self._timeout, attempt + 1, max_retries + 1,
                )
                if attempt == max_retries:
                    raise AIProviderError(
                        "The AI assistant took too long to respond. Please try again.",
                        category="ai_unavailable",
                    ) from exc
                await asyncio.sleep(self._jitter(base_delay * (2 ** attempt)))
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "AI request to Groq failed at transport level: %s (attempt %s/%s)",
                    type(exc).__name__, attempt + 1, max_retries + 1,
                )
                if attempt == max_retries:
                    raise AIProviderError(
                        "The AI assistant is temporarily unreachable. Please try again shortly.",
                        category="ai_unavailable",
                    ) from exc
                await asyncio.sleep(self._jitter(base_delay * (2 ** attempt)))
                continue

            logger.info(
                "AI Groq HTTP %s (attempt %s/%s)",
                response.status_code, attempt + 1, max_retries + 1,
            )

            if response.status_code == 429:
                hdr = response.headers.get("retry-after") or response.headers.get("Retry-After")
                delay = base_delay * (2 ** attempt)
                if hdr:
                    try:
                        delay = float(hdr)
                    except ValueError:
                        pass
                # Cap at 30 s in prod, near-zero in tests.
                max_wait = 0.05 if self._test_mode else 30.0
                delay = min(max(self._jitter(delay), 0.001 if self._test_mode else 0.5), max_wait)
                logger.warning(
                    "Groq rate limit (HTTP 429). Waiting %.3fs (attempt %s/%s)",
                    delay, attempt + 1, max_retries + 1,
                )
                if attempt == max_retries:
                    raise AIProviderError(
                        "LedgerLens AI is receiving high traffic right now. "
                        "Please wait a moment and try again.",
                        category="rate_limited",
                    )
                await asyncio.sleep(delay)
                continue

            if response.status_code in (500, 502, 503, 504):
                delay = self._jitter(base_delay * (2 ** attempt))
                logger.warning(
                    "Groq server error (HTTP %s). Retrying in %.3fs (attempt %s/%s)",
                    response.status_code, delay, attempt + 1, max_retries + 1,
                )
                if attempt == max_retries:
                    raise AIProviderError(
                        "The AI assistant service experienced a temporary server error. "
                        "Please try again.",
                        category="ai_request_failed",
                    )
                await asyncio.sleep(delay)
                continue

            if response.status_code == 413:
                # Request (input + reserved output) exceeds the provider's
                # per-minute token budget. Retrying the same payload cannot
                # help, so surface a distinct, actionable category instead of
                # the misleading generic "could not complete your request".
                provider_msg = _extract_error_message(response)
                logger.warning(
                    "Groq request too large (HTTP 413): %s",
                    provider_msg[:200],
                )
                raise AIProviderError(
                    "The data for this analysis was too large for the AI to "
                    "process in a single request. Try asking a more focused "
                    "question or analyzing a smaller record.",
                    category="request_too_large",
                )

            if response.status_code in (401, 403):
                raise AIProviderError(
                    "The AI assistant is not currently configured to respond. "
                    "Please contact your workspace administrator.",
                    category="ai_unavailable",
                )
            if response.status_code == 404:
                logger.warning("Groq returned 404. Check GROQ_MODEL setting.")
                raise AIProviderError(
                    "The AI assistant is misconfigured. "
                    "Please contact your workspace administrator.",
                    category="ai_request_failed",
                )
            if response.status_code >= 400:
                provider_msg = _extract_error_message(response)
                logger.warning(
                    "Groq chat error status=%s reason=%s",
                    response.status_code,
                    provider_msg[:300],
                )
                raise AIProviderError(
                    "The AI assistant could not complete your request. Please try again.",
                    category="ai_request_failed",
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise AIResponseError(
                    "The AI assistant returned an unreadable response.",
                    category="ai_request_failed",
                ) from exc
            logger.debug(
                "AI Groq OK status=%s probe=%s",
                response.status_code, _probe_response(data),
            )
            return data

        raise AIProviderError(
            "The AI assistant request could not be completed after retries.",
            category="ai_request_failed",
        )

    def _new_client(self) -> httpx.AsyncClient:
        if self._transport is not None:
            return httpx.AsyncClient(transport=self._transport, timeout=self._timeout)
        return httpx.AsyncClient(timeout=self._timeout)

    # ------------------------------------------------------------------
    # complete_once - single completion, evidence already in context
    # ------------------------------------------------------------------

    async def complete_once(
        self,
        *,
        system: str,
        messages: list[dict],
    ) -> str:
        """Single chat completion with no tool loop.

        Used by the reconciliation pre-fetch path: all evidence has been
        assembled into the messages, so exactly one Groq request is needed.
        Returns the assistant text content. Raises AIProviderError on failure.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.1,
            "max_tokens": self._max_tokens,
        }
        data = await self._post(payload)
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            raise AIResponseError(
                "The AI assistant returned an unexpected response shape.",
                category="ai_request_failed",
            ) from exc

        message = choice.get("message") or {}
        content = message.get("content") or ""
        if not content:
            raise AIResponseError(
                "The AI assistant returned an empty response.",
                category="no_answer",
            )
        logger.info(
            "AI complete_once OK finish_reason=%s content_bytes=%s",
            choice.get("finish_reason"), len(content),
        )
        return content

    # ------------------------------------------------------------------
    # run - full tool-calling loop
    # ------------------------------------------------------------------

    async def run(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict],
        execute_tool: Callable[[str, dict], Any],
        max_tool_rounds: int,
        timeout: int,
    ) -> list[dict]:
        """Execute the Groq tool-calling loop.

        Correctly preserves the full message history in the format:
          system
          user
          assistant (tool_calls=[...])
          tool (tool_call_id=..., content=JSON)
          [assistant + tool pairs for more rounds]
          assistant (final text content)

        Returns the ordered list of assistant turns.
        Raises AIProviderError on unrecoverable failures.
        """
        working: list[dict] = [{"role": "system", "content": system}, *messages]
        turns: list[dict] = []

        tool_names_list = [t.get("function", {}).get("name") for t in tools]
        tool_name_set = {n for n in tool_names_list if n}
        effective_rounds = min(max(1, max_tool_rounds), 3)

        logger.info(
            "AI run start model=%s tools=%s msg_count=%s max_rounds=%s",
            self.model, tool_names_list, len(working), effective_rounds,
        )

        # Cache: (tool_name, sorted_args_json) -> result dict
        # Prevents re-executing the same tool with identical arguments.
        past_tool_calls: dict[tuple[str, str], dict] = {}

        for round_index in range(effective_rounds):
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": working,
                "temperature": 0.1,
                "max_tokens": self._max_tokens,
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            try:
                data = await self._post(payload)
            except AIError as exc:
                # A provider failure mid-loop (e.g. 429, timeout, 5xx) must NOT
                # hard-fail when we have already collected tool evidence. Switch
                # to final synthesis so the user still gets an answer grounded in
                # what we retrieved, instead of "AI unavailable".
                if past_tool_calls:
                    logger.warning(
                        "AI tool round %s failed (%s); evidence already collected "
                        "-> switching to final synthesis",
                        round_index + 1, getattr(exc, "category", type(exc).__name__),
                    )
                    final_turn = await self._final_synthesis(working)
                    turns.append(final_turn)
                    return turns
                raise

            try:
                choice = data["choices"][0]
            except (KeyError, IndexError) as exc:
                raise AIResponseError(
                    "The AI assistant returned an unexpected response shape.",
                    category="ai_request_failed",
                ) from exc

            message = choice.get("message") or {}
            content = message.get("content")
            tool_calls = message.get("tool_calls")

            logger.info(
                "AI round=%s finish_reason=%s tool_calls=%s has_content=%s",
                round_index,
                choice.get("finish_reason"),
                len(tool_calls) if tool_calls else 0,
                bool(content),
            )

            # Build the assistant turn preserving the original tool_calls array
            # so downstream tool messages can reference the IDs correctly.
            #
            # For reasoning models (e.g. GPT-OSS) the response may carry a
            # `reasoning` field. Groq requires this to be echoed back verbatim
            # on the assistant message when we resume the conversation — dropping
            # it makes a later round fail with 400 `Failed to parse tool call
            # arguments as JSON`. We also re-serialize every tool_call's
            # `arguments` to canonical JSON so Groq can re-validate the round
            # trip even if the model emitted slightly malformed arguments.
            assistant: dict[str, Any] = {"role": "assistant"}
            # Keep any provider-specific fields the model returned (e.g.
            # `reasoning`) so the exact assistant turn is preserved on resume.
            for _k in ("content", "reasoning", "refusal"):
                if message.get(_k) is not None:
                    assistant[_k] = message[_k]
            turns.append(assistant)

            # Final text answer - no tool_calls means model is done.
            if not tool_calls:
                logger.info("AI final answer after %s round(s)", round_index + 1)
                working.append(assistant)
                return turns

            # Guard: cap how many tool calls are honoured in a single round so a
            # runaway model cannot fan out and blow the provider rate limit.
            MAX_CALLS_PER_ROUND = 4
            tool_calls = tool_calls[:MAX_CALLS_PER_ROUND]

            # Normalise each tool call's arguments to canonical JSON and keep
            # the parsed args keyed by tool_call_id for execution.
            parsed_by_id: dict[str, dict] = {}
            clean_calls: list[dict] = []
            for call in tool_calls:
                fn = call.get("function") or {}
                raw_args = fn.get("arguments") or "{}"
                try:
                    parsed = _json_loads(raw_args)
                    if not isinstance(parsed, dict):
                        parsed = {}
                except ValueError:
                    parsed = {}
                parsed_by_id[call.get("id", "")] = parsed
                clean_calls.append({
                    **call,
                    "function": {**fn, "arguments": json.dumps(parsed)},
                })

            if clean_calls:
                assistant["tool_calls"] = clean_calls
            working.append(assistant)

            # Unknown tool -> treat its arguments as the final answer.
            # Models sometimes encode their JSON answer as a fake tool call.
            unknown_calls = [
                c for c in clean_calls
                if (c.get("function") or {}).get("name") not in tool_name_set
            ]
            if unknown_calls:
                uc = unknown_calls[0]
                uc_name = (uc.get("function") or {}).get("name", "unknown")
                raw_args = (uc.get("function") or {}).get("arguments") or "{}"
                logger.warning(
                    "Model called unknown tool '%s'; treating arguments as final answer",
                    uc_name,
                )
                final_turn: dict[str, Any] = {"role": "assistant"}
                try:
                    final_turn["content"] = _json_dumps(_json_loads(raw_args))
                except Exception:  # noqa: BLE001
                    final_turn["content"] = raw_args
                turns.append(final_turn)
                return turns

            # Execute each tool and append role=tool messages.
            for call in clean_calls:
                fn = call.get("function") or {}
                name = fn.get("name", "")
                tool_id = call.get("id", "")
                args = parsed_by_id.get(tool_id, {})

                try:
                    cache_key = (name, json.dumps(args, sort_keys=True))
                except Exception:  # noqa: BLE001
                    cache_key = (name, str(args))

                is_duplicate = cache_key in past_tool_calls
                if is_duplicate:
                    # Build a COPY of the cached result - never mutate the cache.
                    cached = past_tool_calls[cache_key]
                    result_payload = {**cached, "_system_notice": (
                        "IMPORTANT: You already retrieved this data. "
                        "Do NOT call any more tools. "
                        "You have sufficient evidence - output the final JSON answer NOW."
                    )}
                    logger.warning("Duplicate tool '%s' detected; reusing cached result", name)
                else:
                    logger.info("AI tool call -> '%s' args=%s", name, list(_arg_keys(args)))
                    try:
                        result = execute_tool(name, args)
                        if hasattr(result, "__await__"):
                            result = await result
                        result_payload = result
                    except PermissionError:
                        raise
                    except AIProviderError:
                        logger.warning("AI tool '%s' execution FAILED - aborting loop", name)
                        raise
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "AI tool '%s' raised %s - aborting loop",
                            name, type(exc).__name__,
                        )
                        raise AIProviderError(
                            "The AI assistant could not retrieve the data it needed. "
                            "Please try again.",
                            category="tool_execution_failed",
                        ) from exc
                    logger.info("AI tool '%s' succeeded", name)
                    if not isinstance(result_payload, dict):
                        result_payload = {"result": result_payload}
                    # Only cache successful real executions.
                    past_tool_calls[cache_key] = result_payload

                if not isinstance(result_payload, dict):
                    result_payload = {"result": result_payload}

                try:
                    serialized = _json_dumps(result_payload)
                except TypeError:
                    serialized = _json_dumps({"error": "The tool returned an unreadable result."})

                logger.info("AI tool '%s' result bytes=%s", name, len(serialized))

                # Append the role=tool message with the exact tool_call_id.
                # One tool message per tool_call in the assistant turn.
                working.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": serialized,
                })

        # Max rounds exhausted: force final synthesis without tools, using all
        # collected tool results (already in `working` as role=tool messages).
        logger.warning(
            "AI tool loop exhausted after %s rounds - forcing final synthesis call",
            effective_rounds,
        )
        final_turn = await self._final_synthesis(working)
        turns.append(final_turn)
        return turns

    # ------------------------------------------------------------------
    # final synthesis - guaranteed non-empty terminal answer
    # ------------------------------------------------------------------

    async def _final_synthesis(self, working: list[dict]) -> dict:
        """Force the model to produce a terminal TEXT answer from the evidence
        already gathered, WITHOUT any tools.

        Bounded: at most 2 Groq attempts. It never raises and never returns an
        empty answer:
          - if the model emits a tool call anyway (no tools were offered), its
            arguments are treated as the answer;
          - if every attempt returns empty or fails at the provider level, a
            structured answer is auto-compiled from the collected tool evidence
            so the user is NEVER sent away with "AI unavailable" or an empty
            response.
        """
        attempts = 0
        while attempts < 2:
            attempts += 1
            synthesis_messages = working + [{
                "role": "user",
                "content": (
                    "You have already retrieved all available evidence from "
                    "LedgerLens. Do NOT call any tools or functions. "
                    "Produce the final structured JSON answer ONLY, grounded in "
                    "the evidence already present in this conversation. "
                    "If evidence is incomplete, say so - never invent figures."
                ),
            }]
            synthesis_payload: dict[str, Any] = {
                "model": self.model,
                "messages": synthesis_messages,
                "temperature": 0.1,
                "max_tokens": self._max_tokens,
                # No tools key -> forces a plain reply.
            }
            try:
                synth_data = await self._post(synthesis_payload)
                synth_choice = synth_data["choices"][0]
                synth_msg = synth_choice.get("message") or {}
                synth_content = synth_msg.get("content") or ""
                if not synth_content and synth_msg.get("tool_calls"):
                    # Should not happen without tools, but treat the first
                    # tool-call's arguments as the final answer rather than lose
                    # it (the model sometimes encodes JSON answers that way).
                    args = (
                        (synth_msg["tool_calls"][0].get("function") or {})
                        .get("arguments") or "{}"
                    )
                    synth_content = args
                if synth_content and synth_content.strip():
                    logger.info(
                        "AI final synthesis produced answer (attempt %s) bytes=%s",
                        attempts, len(synth_content),
                    )
                    return {"role": "assistant", "content": synth_content}
                logger.warning(
                    "AI final synthesis returned empty content (attempt %s)",
                    attempts,
                )
            except AIError as exc:
                logger.warning(
                    "AI final synthesis failed (attempt %s): category=%s",
                    attempts, getattr(exc, "category", type(exc).__name__),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "AI final synthesis unexpected error (attempt %s): %s",
                    attempts, type(exc).__name__,
                )

        logger.warning("AI final synthesis could not produce text; compiling evidence fallback")
        return self._evidence_fallback_turn(working)

    def _evidence_fallback_turn(self, working: list[dict]) -> dict:
        """Auto-compile a guaranteed non-empty structured answer from the tool
        evidence already collected, so the user always receives a real answer."""
        tool_msgs = [m for m in working if m.get("role") == "tool"]
        findings = []
        for m in tool_msgs:
            try:
                data = _json_loads(m.get("content") or "{}")
                text = _json_dumps(data) if isinstance(data, (dict, list)) else str(data)
            except Exception:  # noqa: BLE001
                text = str(m.get("content") or "")
            findings.append({
                "kind": "fact",
                "text": _truncate(text, 600),
                "detail": [],
            })

        if findings:
            summary = (
                f"LedgerLens successfully retrieved {len(tool_msgs)} piece(s) of "
                "reconciliation evidence for this question. The synthesis step was "
                "interrupted, so this answer reflects the retrieved evidence directly."
            )
        else:
            findings.append({
                "kind": "fact",
                "text": "Reconciliation data was retrieved for the active run.",
                "detail": [],
            })
            summary = "LedgerLens retrieved reconciliation data for this workspace."

        answer = {
            "title": "Reconciliation evidence (LedgerLens)",
            "summary": summary,
            "findings": findings,
            "evidence": [],
            "likely_causes": [],
            "recommendations": ["Review the retrieved reconciliation evidence for the active run."],
            "confidence": "medium",
            "limitations": [
                "The AI synthesis step was interrupted; this answer reflects the "
                "raw retrieved tool evidence.",
            ],
        }
        return {"role": "assistant", "content": _json_dumps(answer)}