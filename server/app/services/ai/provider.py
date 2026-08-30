"""AI provider abstraction.

LedgerLens talks to its LLM only through the `AIProvider` interface. Nothing
outside this package depends on a specific vendor, so a future provider (e.g.
OpenAI, Anthropic, a local model) can be added without touching the service,
tools, routes or UI.

Secrets NEVER leave the server: the API key is read from configuration inside
the provider and is never returned to callers or clients.
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Callable

logger = logging.getLogger("ledgerlens.ai")


class AIError(Exception):
    """Base class for AI provider failures.

    `category` is a short, machine-readable, user-safe bucket the routes and UI
    use to show a specific error message without exposing internals or secrets.
    """

    category = "ai_request_failed"

    def __init__(self, message: str = "", *, category: str | None = None):
        super().__init__(message)
        if category:
            self.category = category


class AIProviderError(AIError):
    """The configured provider could not fulfil the request (network, timeout,
    rate limit, malformed response). Message is user-safe (no secrets)."""


class AIUnavailableError(AIError):
    """No AI provider is configured / reachable."""

    category = "ai_unavailable"


class AIResponseError(AIError):
    """The provider returned something we could not parse as a tool response."""


@abc.abstractmethod  # pragma: no cover - abstract interface
class AIProvider:
    @abc.abstractmethod
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
        """Run a tool-capable chat completion to completion.

        The provider executes the full tool loop internally: when the model
        requests a tool call with arguments ``args`` for tool name ``name``,
        it calls ``execute_tool(name, args)`` (which may return a coroutine or
        a dict; must return a JSON-safe value) and continues until the model
        answers without tool_calls or the round budget is exhausted.

        Returns the ordered list of assistant message dicts. Raises
        AIProviderError on any provider-side failure.
        """
        raise NotImplementedError

    async def complete_once(
        self,
        *,
        system: str,
        messages: list[dict],
    ) -> str:
        """Make a single chat completion with no tool loop.

        Used when evidence has already been pre-fetched and assembled into the
        messages; the provider should produce exactly one assistant reply.
        Returns the assistant text content (raw string). Raises AIProviderError
        on any provider-side failure.
        """
        raise NotImplementedError


def get_provider() -> AIProvider:
    """Return the configured provider, or raise AIUnavailableError when none is
    usable. Uses the current settings each call so config changes apply."""
    from ...core.config import get_settings

    settings = get_settings()
    provider_name = (settings.ai_provider or "groq").strip().lower()
    if provider_name == "groq":
        if not settings.groq_api_key:
            raise AIUnavailableError(
                "AI analysis is not configured on this server yet. "
                "Ask a workspace administrator to enable it."
            )
        from .groq_client import GroqProvider

        return GroqProvider(api_key=settings.groq_api_key)

    raise AIUnavailableError(
        f"The configured AI provider '{provider_name}' is not supported."
    )
