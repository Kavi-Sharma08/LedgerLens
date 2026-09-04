"""Hermetic tests for GroqProvider.

GroqProvider talks HTTPS; these tests script it with httpx.MockTransport so no
network is ever touched. They cover the pieces the AI feature was failing on:

  - the tool loop runs until the model produces its final TEXT answer (it is
    fed tool results, never stopped after the first call);
  - no bogus "tool-results-appended" turn is ever emitted;
  - a tool call to an unadvertised tool ("JSON" etc.) is turned into the final
    answer instead of dead-looping into provider 400s;
  - provider transport failures surface as categorized AIProviderError;
  - a real tool-execution failure aborts the loop as its own category instead
    of being disguised as "no data";
  - end to end: route -> ai_service -> GroqProvider -> tools -> FakeDatabase
    returns a 200 with the model's structured answer.
"""

import asyncio
import json

import httpx
import pytest

from app.api import deps
from app.main import app
from app.services.ai import ai_service
from app.services.ai.groq_client import GroqProvider
from app.services.ai.provider import AIProviderError
from app.services.ai.tools import tool_names, tool_schemas
from tests.test_ai import FINAL_ANSWER, _client_for, _user, _seed_workspace
from tests.test_ai_tools import WS_A, OWNER_A, _seed_run

FINAL_CONTENT = json.dumps(FINAL_ANSWER)

CHAT_TOOLS = tool_schemas()

TOOL_CALL_MSG = {
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "get_transaction_context", "arguments": "{}"},
        }
    ],
}

FINAL_MSG = {"role": "assistant", "content": FINAL_CONTENT}


def _provider(handler) -> GroqProvider:
    return GroqProvider(
        api_key="test-api-key",
        base_url="https://api.groq.com/openai/v1",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Never let the route-level test leak FastAPI dependency_overrides into
    other test modules (test_health pins the real 401 boundary)."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _make_handler(script):
    """`script` is a callable(request_body: dict, round_number: int) returning
    how many tool calls the model emits; replies are built from its return
    value, and the request bodies are collected for assertions. Responses use
    the real Groq shape: choices[0].message is the model message."""
    requests = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        requests.append(body)
        calls = script(body, len(requests))
        if not calls:
            return httpx.Response(200, json={"choices": [{"message": FINAL_MSG}]})
        message = dict(TOOL_CALL_MSG)
        tool_calls = []
        for i, (name, args) in enumerate(calls):
            tool_calls.append(
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                }
            )
        message["tool_calls"] = tool_calls
        return httpx.Response(200, json={"choices": [{"message": message}]})

    return handler, requests


async def _run_provider(provider, execute_tool=None):
    async def _never(name, args):
        raise AssertionError(f"execute_tool should not be called for '{name}'")

    return await provider.run(
        system="sys",
        messages=[{"role": "user", "content": "analyse the transaction"}],
        tools=CHAT_TOOLS,
        execute_tool=execute_tool or _never,
        max_tool_rounds=5,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# tool loop
# ---------------------------------------------------------------------------


def test_run_tool_loop_feeds_results_until_final_text_answer():
    calls = []

    async def _exec(name, args):
        calls.append((name, args))
        return {"transaction": {"id": args["transaction_id"], "amount": "100.00"}}

    def script(body, round_number):
        if round_number == 1:
            return [("get_transaction_context", {"transaction_id": "abc123"})]
        # Round 2 carried the tool result back; the model now answers.
        return []

    handler, requests = _make_handler(script)
    provider = _provider(handler)

    turns = asyncio.run(_run_provider(provider, execute_tool=_exec))

    assert len(requests) == 2  # the loop did not stop after the first call
    assert calls == [("get_transaction_context", {"transaction_id": "abc123"})]

    # The second request carried the tool result back to the model.
    round2_roles = [m.get("role") for m in requests[1]["messages"]]
    assert round2_roles == ["system", "user", "assistant", "tool"]
    tool_msg = requests[1]["messages"][-1]
    assert tool_msg["tool_call_id"] == "call_0"
    assert 'abc123' in tool_msg["content"]

    # Final answer is the model's text, and NOT a bogus "tool-results-appended" turn.
    assert turns[-1]["role"] == "assistant"
    assert turns[-1]["content"] == FINAL_CONTENT
    assert not any(t.get("role") == "tool-results-appended" for t in turns)


def test_tool_schemas_sent_to_provider_are_property_complete():
    def script(body, round_number):
        return []  # the model answers in one round

    handler, requests = _make_handler(script)
    provider = _provider(handler)
    asyncio.run(_run_provider(provider))

    body = requests[0]
    assert body["tools"]
    names = {t["function"]["name"] for t in body["tools"]}
    assert names == set(tool_names())
    # Regression for the malformed-tools bug: every tool sent to Groq must
    # carry property schemas + descriptions (Groq validates these and rejects
    # empty `{"type": "object"}` parameter blocks).
    for t in body["tools"]:
        fn = t["function"]
        assert fn.get("description")
        assert fn["parameters"].get("type") == "object"
        assert isinstance(fn["parameters"].get("properties"), dict)


def test_unknown_tool_call_is_used_as_final_answer():
    """Models sometimes encode their JSON answer as a call to a fake 'JSON'
    tool. We must not dead-loop and must not lose the answer."""
    args = FINAL_ANSWER

    def script(body, round_number):
        return [("JSON", args)]

    handler, requests = _make_handler(script)
    provider = _provider(handler)

    turns = asyncio.run(_run_provider(provider))
    assert len(requests) == 1  # no spurious second round / no 400 spam
    assert turns[-1]["role"] == "assistant"
    assert json.loads(turns[-1]["content"]) == FINAL_ANSWER


# ---------------------------------------------------------------------------
# provider failures
# ---------------------------------------------------------------------------


def test_http_500_surfaces_as_ai_request_failed():
    def handler(request):
        return httpx.Response(500, json={"error": {"message": "upstream boom"}})

    provider = _provider(handler)
    with pytest.raises(AIProviderError) as exc:
        asyncio.run(_run_provider(provider))
    assert exc.value.category == "ai_request_failed"
    assert "try again" in str(exc.value).lower()


def test_http_429_surfaces_as_rate_limited(monkeypatch):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, headers={"Retry-After": "0.001"}, json={})

    provider = _provider(handler)
    with pytest.raises(AIProviderError) as exc:
        asyncio.run(_run_provider(provider))
    assert exc.value.category == "rate_limited"
    assert attempts == 4  # Initial attempt + 3 retries


def test_http_413_surfaces_as_request_too_large_and_is_not_retried():
    """A 413 'Payload Too Large' (input + reserved output exceeds the provider's
    per-minute token budget) must surface as a distinct, actionable category —
    NOT the misleading generic ai_request_failed — and must NOT be retried,
    since re-sending the same oversized payload cannot help."""
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            413, headers={"Content-Type": "application/json"},
            json={"error": {"message": "Request too large for model value"}},
        )

    provider = _provider(handler)
    with pytest.raises(AIProviderError) as exc:
        asyncio.run(_run_provider(provider))
    assert exc.value.category == "request_too_large"
    assert "too large" in str(exc.value).lower()
    assert attempts == 1  # no retry for an oversized payload




def test_timeout_surfaces_as_ai_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("simulated timeout")

    provider = _provider(handler)
    with pytest.raises(AIProviderError) as exc:
        asyncio.run(_run_provider(provider))
    assert exc.value.category == "ai_unavailable"
    assert "too long" in str(exc.value)


# ---------------------------------------------------------------------------
# tool execution failures
# ---------------------------------------------------------------------------


def test_tool_execution_failure_propagates_and_aborts_loop():
    def script(body, round_number):
        return [("get_transaction_context", {"transaction_id": "abc123"})]

    handler, requests = _make_handler(script)
    provider = _provider(handler)

    async def _boom(name, args):
        raise AIProviderError("tool exploded", category="tool_execution_failed")

    with pytest.raises(AIProviderError) as exc:
        asyncio.run(_run_provider(provider, execute_tool=_boom))
    assert exc.value.category == "tool_execution_failed"
    # The loop aborted before a second round: a real failure is not masked.
    assert len(requests) == 1


def test_plain_exception_in_tool_aborts_as_tool_failure():
    def script(body, round_number):
        return [("get_transaction_context", {"transaction_id": "abc123"})]

    handler, requests = _make_handler(script)
    provider = _provider(handler)

    async def _explode(name, args):
        raise RuntimeError("database is on fire")

    with pytest.raises(AIProviderError) as exc:
        asyncio.run(_run_provider(provider, execute_tool=_explode))
    assert exc.value.category == "tool_execution_failed"


# ---------------------------------------------------------------------------
# end to end: route -> ai_service -> GroqProvider -> tools -> Mongo
# ---------------------------------------------------------------------------


def test_route_end_to_end_with_scripted_groq(monkeypatch):
    from tests.fakes.fake_mongo import FakeDatabase

    db = FakeDatabase()
    db.declare_standard_indexes()
    _seed_workspace(db, WS_A, OWNER_A)

    run, txn_a, txn_b, *_ = _seed_run(db, WS_A)

    def script(body, round_number):
        if round_number == 1:
            return [("get_transaction_context", {"transaction_id": str(txn_a.id)})]
        return []

    handler, requests = _make_handler(script)
    provider = _provider(handler)
    # Make the real route call our scripted provider.
    monkeypatch.setattr(ai_service, "get_provider", lambda: provider)

    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/transaction/{txn_a.id}/analyze", headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Explained"
    assert body["confidence"] == "high"
    assert body["findings"][0]["kind"] == "fact"

    # The tool loop ran against the real (fake) DB: round 2 carried the
    # workspace-scoped tool result (with the run's counts) back to the model.
    assert len([m for m in requests[0]["messages"] if m.get("role") == "user"]) == 1
    round2_tool_msgs = [m for m in requests[1]["messages"] if m.get("role") == "tool"]
    assert round2_tool_msgs, "tool result never reached the second model round"
    assert '"totalTransactions": 3' in round2_tool_msgs[0]["content"]


def test_duplicate_tool_call_reuses_result_and_adds_system_notice():
    """If the LLM calls the exact same tool with the exact same args twice,
    the execute_tool function is called ONLY ONCE, and a system notice is injected."""
    exec_count = 0

    async def _exec(name, args):
        nonlocal exec_count
        exec_count += 1
        return {"summary": "Run stats"}

    def script(body, round_number):
        if round_number in (1, 2):
            return [("get_reconciliation_summary", {"reconciliation_run_id": "run123"})]
        return []

    handler, requests = _make_handler(script)
    provider = _provider(handler)

    turns = asyncio.run(_run_provider(provider, execute_tool=_exec))

    # execute_tool called ONCE despite 2 duplicate tool call requests
    assert exec_count == 1
    assert len(requests) == 3
    # Round 3 message payload should contain the _system_notice
    round3_tool_msg = [m for m in requests[2]["messages"] if m.get("role") == "tool"][-1]
    assert "_system_notice" in round3_tool_msg["content"]


def test_max_rounds_exhaustion_triggers_fallback_synthesis_call():
    """When max rounds are hit without a final text answer, a final synthesis call
    WITHOUT tools is issued to force a text response from accumulated evidence."""
    def script(body, round_number):
        # Always request a new tool call to exhaust rounds
        return [("get_reconciliation_summary", {"reconciliation_run_id": f"run_{round_number}"})]

    requests = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        requests.append(body)
        if "tools" not in body:
            # Final synthesis call (no tools key present) -> return final text
            return httpx.Response(200, json={"choices": [{"message": FINAL_MSG}]})
        # Normal rounds return tool call
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"call_{len(requests)}",
                "type": "function",
                "function": {"name": "get_reconciliation_summary", "arguments": "{}"},
            }],
        }
        return httpx.Response(200, json={"choices": [{"message": message}]})

    provider = _provider(handler)

    async def _exec(name, args):
        return {"ok": True}

    turns = asyncio.run(_run_provider(provider, execute_tool=_exec))

    # Should attempt synthesis call after max rounds (effective cap is 3)
    assert len(requests) == 4  # 3 tool rounds + 1 synthesis round
    assert "tools" not in requests[-1]  # synthesis call had no tools
    assert turns[-1]["content"] == FINAL_CONTENT


def test_complete_once_single_shot():
    """complete_once makes a single Groq request with no tool loop."""
    requests = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "direct answer"}}]})

    provider = _provider(handler)
    res = asyncio.run(provider.complete_once(system="sys", messages=[{"role": "user", "content": "hello"}]))

    assert res == "direct answer"
    assert len(requests) == 1
    assert "tools" not in requests[0]


# ---------------------------------------------------------------------------
# reconciliation /ask path - tool loop -> final LLM text -> API response
# ---------------------------------------------------------------------------


def _ask_client(db):
    """Seed a workspace + reconciliation run and return a test client that can
    call /api/ai/ask with that run bound as active context."""
    from tests.fakes.fake_mongo import FakeDatabase
    from tests.test_ai import _client_for, _seed_workspace, _user
    from tests.test_ai_tools import _seed_run

    _seed_workspace(db, WS_A, OWNER_A)
    run, *_ = _seed_run(db, WS_A)
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    return c, headers, run


def _response_body(message):
    return httpx.Response(200, json={"choices": [{"message": message}]})


def test_ask_reconciliation_tool_loop_produces_final_text(monkeypatch):
    """The acceptance path: user question + reconciliation_run_id ->
    Groq keeps requesting reconciliation tools -> final tool-loop synthesis
    returns the final structured TEXT -> FastAPI returns 200 with the answer
    (the request NEVER ends in 'AI unavailable' / 'no_answer' / empty)."""
    from tests.fakes.fake_mongo import FakeDatabase

    db = FakeDatabase()
    db.declare_standard_indexes()
    c, headers, run = _ask_client(db)
    run_id = str(run.id)

    requests = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        requests.append(body)
        # Normal tool rounds: model keeps requesting reconciliation tools in
        # separate rounds (summary, then exceptions, then matches).
        if "tools" in body:
            names = ["get_reconciliation_summary", "list_run_exceptions", "list_run_matches"]
            idx = min(len(requests) - 1, len(names) - 1)
            return _response_body({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": f"call_{len(requests)}",
                    "type": "function",
                    "function": {"name": names[idx], "arguments": json.dumps({"reconciliation_run_id": run_id})},
                }],
            })
        # Final synthesis (no tools) -> the model produces the final structured text.
        return _response_body({"role": "assistant", "content": FINAL_CONTENT})

    provider = _provider(handler)
    monkeypatch.setattr(ai_service, "get_provider", lambda: provider)

    payload = {
        "question": "Explain this reconciliation run, including matched, unmatched and exceptions.",
        "reconciliation_run_id": run_id,
    }
    with c:
        r = c.post("/api/ai/ask", json=payload, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Explained"
    assert body["confidence"] == "high"
    assert body["findings"][0]["kind"] == "fact"

    # The tool loop ran against real seeded run data, exhausted its rounds,
    # and the final synthesis (no tools) returned the answer.
    tool_msgs = [m for m in requests[-1]["messages"] if m.get("role") == "tool"]
    assert tool_msgs, "collected tool results were not passed back for synthesis"
    assert "tools" not in requests[-1]
    assert r.status_code == 200


def test_ask_never_fails_with_ai_unavailable_when_synthesis_hits_429(monkeypatch):
    """When the model exhausts the tool loop AND the final synthesis request is
    rate-limited (429), the provider must NOT surface 'AI unavailable' if tool
    evidence was already collected - it auto-compiles a structured answer from
    that evidence so /api/ai/ask still returns 200 with a non-empty answer."""
    from tests.fakes.fake_mongo import FakeDatabase

    db = FakeDatabase()
    db.declare_standard_indexes()
    c, headers, run = _ask_client(db)
    run_id = str(run.id)

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        if "tools" in body:
            return _response_body({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_reconciliation_summary", "arguments": json.dumps({"reconciliation_run_id": run_id})},
                }],
            })
        # Final synthesis -> persistent 429 (bounded retries exhausted).
        return httpx.Response(429, headers={"Retry-After": "0.001"}, json={})

    provider = _provider(handler)
    monkeypatch.setattr(ai_service, "get_provider", lambda: provider)

    payload = {
        "question": "Explain this reconciliation run, including matched, unmatched and exceptions.",
        "reconciliation_run_id": run_id,
    }
    with c:
        r = c.post("/api/ai/ask", json=payload, headers=headers)

    assert r.status_code == 200, r.text
    body = r.json()
    # A real, non-empty structured answer was compiled from the collected evidence,
    # presented in plain human terms (no raw IDs / JSON, no internal wording).
    assert body["title"] == "Reconciliation outcome: 1 matched, 1 unmatched, 1 exception"
    assert body["summary"]
    assert body["findings"]
    # It must NOT be one of the forbidden terminal states.
    assert body["title"] not in {"AI unavailable", "Analysis unavailable"}
    assert "could not complete" not in body["summary"].lower()
    # No raw field names / JSON / internal synthesis wording leaks into the answer.
    assert "tool" not in body["summary"].lower()
    assert "LedgerLens successfully retrieved" not in body["summary"]