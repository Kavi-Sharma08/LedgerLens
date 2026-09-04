# LedgerLens

> Financial reconciliation, without the manual investigation.

## Overview

LedgerLens is a financial reconciliation platform that helps finance teams move from spreadsheet-based matching to automated, AI-assisted investigation. Teams upload transaction data from banks, payment processors, or ERPs, and LedgerLens normalizes, matches, and classifies every record — surfacing only the exceptions that need human attention.

When transactions don't match, an AI assistant traces each exception through the actual reconciliation evidence, explains what likely happened, and recommends next steps. The result: teams spend time resolving discrepancies, not finding them.

## How It Works

```
Upload Transactions → Normalize Data → Run Reconciliation → Identify Exceptions → AI Investigation → Human Resolution
```

1. **Upload** — Import CSV or JSONL exports from your financial sources.
2. **Normalize** — Records are mapped to a consistent schema (amount, date, reference, counterparty, status).
3. **Reconcile** — A deterministic matching engine scores transaction pairs across multiple fields.
4. **Classify** — Transactions are categorized as MATCHED, LIKELY_MATCH, AMBIGUOUS, UNMATCHED, or EXCEPTION.
5. **Investigate** — The AI gathers evidence from the database and explains each exception.
6. **Resolve** — Humans review, approve, override, or escalate based on AI recommendations.

## Features

- CSV/JSONL transaction ingestion with duplicate detection
- Automated multi-field transaction reconciliation
- Match confidence scoring with score breakdowns
- Exception management with assignment and annotation
- AI-powered investigation with evidence-backed responses
- Workspace-based multi-tenant data isolation
- Role-based access control (OWNER, ADMIN, MEMBER, VIEWER)
- Audit logging for all actions
- Google OAuth and email/password authentication

## AI Investigation

The AI does **not** perform reconciliation. A deterministic engine calculates all match scores and produces the evidence. The AI retrieves that evidence — transaction data, candidate scores, exception context — and uses it to explain findings, identify likely causes, and recommend actions.

**AI recommends; humans make the final decision.**

## Reconciliation Engine

LedgerLens uses a deterministic matching engine that compares transactions using:

| Field | Weight |
|-------|--------|
| Amount | 0.35 |
| Date | 0.20 |
| Reference | 0.20 |
| Counterparty | 0.15 |
| Description | 0.10 |

Each transaction is classified into one of five states: **MATCHED** (high confidence), **LIKELY_MATCH** (probable but with caveats), **AMBIGUOUS** (multiple close candidates), **UNMATCHED** (no viable candidate), or **EXCEPTION** (requires investigation — failed transactions, zero amounts, unsupported currencies, or collisions).

## Tech Stack

**Frontend** — Next.js 16, React 19, Tailwind CSS 4, shadcn/ui, Auth.js v5

**Backend** — FastAPI, Python, Motor (async MongoDB driver), MongoDB Atlas

**AI** — Groq (configurable model, default: `openai/gpt-oss-20b`)

**Testing** — Pytest, Playwright


### Frontend

```bash
cd client
npm install
cp .env.example .env
# Fill in your environment variables
npm run dev
```

App runs at `http://localhost:3000`.

### Backend

```bash
cd server
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your environment variables
uvicorn app.main:app --reload --port 8000
```

API runs at `http://localhost:8000`.

### Environment Variables

Copy the example environment files and fill in the required values:

- `client/.env` — Auth, MongoDB, and API connection settings
- `server/.env` — MongoDB, Groq API key, CORS, and internal secret

Generate a shared `INTERNAL_API_SECRET` with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Both the client and server must use the same value.
