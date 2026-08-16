# sre-copilot — SentinelOps: SRE/DevOps Incident Copilot

College assignment: Agentic AI Skill-Building Assignment (Cyclic Submission Track).
One coherent product across all cycles. Cycle 1 = single-agent incident triage loop.

## Current status
Cycle 1, Session 1 — scaffolding only.

## Stack (exact)
- Python 3.13
- LLM: Ollama `gemma3:4b` (local) via `requests` HTTP API
- Validation: `pydantic` 2.10.6
- Env: `python-dotenv` 1.0.1
- No agent framework in Cycle 1 (hand-rolled loop); LangGraph arrives in Cycle 3

## Setup
1. `python -m venv .venv` and activate it
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`
4. `ollama pull gemma3:4b`

