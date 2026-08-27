"""
Simulate the Next.js backend proxy → FastAPI chain.

Reads INTERNAL_API_SECRET from server/.env, then hits the transactions
endpoint with (and without) the trusted identity headers that the
Next.js catch-all route normally injects.
"""

import json
import os
import sys
import urllib.parse
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "http://localhost:8000"

WORKSPACE_ID = "6a8d742a3a5477b2a74477a6"       # ll-active-workspace cookie
ALT_WORKSPACE_ID = "6a8d9fbdb9477eb6e28b831b"   # different workspace to test isolation

USER_ID = "6a8c16c031b6845bc666f559"
USER_EMAIL = "thekavisharma26@gmail.com"

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def load_secret() -> str:
    """Parse INTERNAL_API_SECRET from the server .env file."""
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("INTERNAL_API_SECRET="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(f"INTERNAL_API_SECRET not found in {ENV_PATH}")


def make_headers(workspace_id: str | None, secret: str) -> dict:
    """Build the trusted identity headers the proxy would send."""
    h = {
        "Accept": "application/json",
        "X-LL-User-Id": USER_ID,
        "X-LL-User-Email": urllib.parse.quote(USER_EMAIL, safe=""),
        "X-LL-Internal-Secret": secret,
    }
    if workspace_id:
        h["X-LL-Workspace-Id"] = workspace_id
    return h


def inspect(label: str, resp: requests.Response) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"HTTP Status : {resp.status_code}")
    print(f"Body (first 500 chars):\n{resp.text[:500]}")

    if resp.status_code != 200:
        return

    try:
        data = resp.json()
    except ValueError:
        print("Response is not valid JSON.")
        return

    items = data.get("items", data if isinstance(data, list) else [])
    print(f"\nItems count : {len(items)}")
    print(f"nextCursor  : {data.get('nextCursor')}")

    if items:
        first = items[0]
        print(f"\nFirst item:")
        print(f"  id              : {first.get('id')}")
        print(f"  transactionDate : {first.get('transactionDate')}")
        print(f"  amount          : {first.get('amount')}")
        print(f"  currency        : {first.get('currency')}")
        print(f"  direction       : {first.get('direction')}")
        print(f"  description     : {first.get('description')}")
        print(f"  counterparty    : {first.get('counterparty')}")
        print(f"  status          : {first.get('status')}")


def main():
    secret = load_secret()
    print(f"Loaded INTERNAL_API_SECRET: {secret[:8]}...{secret[-4:]}")

    # ------------------------------------------------------------------
    # 1. Full proxy chain (with workspace header)
    # ------------------------------------------------------------------
    resp1 = requests.get(
        f"{BASE_URL}/api/transactions",
        params={"limit": 25},
        headers=make_headers(WORKSPACE_ID, secret),
        timeout=10,
    )
    inspect("TEST 1 — With X-LL-Workspace-Id", resp1)

    # ------------------------------------------------------------------
    # 2. Without X-LL-Workspace-Id (expect error about no workspace)
    # ------------------------------------------------------------------
    resp2 = requests.get(
        f"{BASE_URL}/api/transactions",
        params={"limit": 25},
        headers=make_headers(None, secret),
        timeout=10,
    )
    inspect("TEST 2 — WITHOUT X-LL-Workspace-Id (expect error)", resp2)

    # ------------------------------------------------------------------
    # 3. Different workspace (workspace isolation check)
    # ------------------------------------------------------------------
    resp3 = requests.get(
        f"{BASE_URL}/api/transactions",
        params={"limit": 25},
        headers=make_headers(ALT_WORKSPACE_ID, secret),
        timeout=10,
    )
    inspect("TEST 3 — Different workspace ID (isolation check)", resp3)


if __name__ == "__main__":
    main()
