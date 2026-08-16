# PROJECT_STATE.md — sre-copilot (SentinelOps)

## 1. File/folder tree (current)

sre-copilot/
├── .gitignore
├── .env                      (local only, gitignored)
├── .env.example
├── requirements.txt
├── README.md                 (stub — expand in Session 2)
├── PROJECT_STATE.md
├── smoke_test.py             (Session 1 reproducible test harness)
├── logs/
│   └── .gitkeep
├── data/
│   └── incidents/
│       ├── incident_01_db_timeout.txt
│       ├── incident_02_memory_leak.txt
│       ├── incident_03_disk_full.txt
│       └── incident_04_crash_loop.txt
└── sre_copilot/
    ├── __init__.py
    ├── interfaces.py
    ├── llm_client.py
    └── tools.py

## 2. Signatures (FROZEN — flag loudly before changing)

interfaces.py
- TOOL_NAMES = Literal["check_service_health","restart_service","check_disk_space","none"]
- class PlanDecision(BaseModel): reasoning, tool_name, tool_args, resolved, summary (all defaulted; schema() = safe fallback)
- class ToolResult(BaseModel): tool_name, success, message, data
- TOOL_SIGNATURES: Dict[str, str]

llm_client.py
- class LLMProviderError(RuntimeError)
- _call_ollama(prompt) -> str   (POST /api/generate, format=json, timeout=120s)
- _call_gemini(prompt) -> str   (stub)
- _call_glm(prompt) -> str      (stub)
- _raw_generate(prompt) -> str  (switch on LLM_PROVIDER)
- _extract_json(text) -> Optional[dict]
- generate(prompt, schema=None) -> Union[T, str]  (2 attempts + safe-default fallback)

tools.py
- check_service_health(service="payments-api") -> ToolResult
- check_disk_space(mount="/var/log") -> ToolResult
- restart_service(service="payments-api") -> ToolResult (1st call fails by design)
- reset_restart_counter() -> None
- TOOL_MAP: Dict[str, callable]

smoke_test.py
- test_tools() / test_plan() / FEW_SHOT_PROMPT

## 3. Supabase tables
None yet.

## 4. Environment variables (names only)
LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_NUM_PARALLEL,
OLLAMA_MAX_LOADED_MODELS, GEMINI_API_KEY, GLM_API_KEY,
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

## 5. Completed this session (Cycle 1, Session 1)
- venv + pinned deps: python-dotenv==1.0.1, pydantic==2.10.6, requests==2.32.3
- .env/.env.example/.gitignore from commit #1 (no secrets)
- llm_client.py per Master §3 (ollama live; gemini/glm stubbed; retry+fallback)
- interfaces.py single source of truth; 3 tool stubs; 4 synthetic incidents
- Ollama installed; gemma3:4b pulled; limits OLLAMA_NUM_PARALLEL=1, OLLAMA_MAX_LOADED_MODELS=1 set
- LIVE VERIFIED: tools stubs (False→True), raw generate, schema-validated
  PlanDecision with few-shot prompt (TOOL=check_service_health)
- Fallback path verified separately (weak prompt → safe default, no crash)
- CONFIRMED RULE: gemma3:4b schema calls require few-shot JSON examples in prompt

## 6. Next session task (Cycle 1, Session 2 — scoped)
1. sre_copilot/loop_logger.py — JSONL per-iteration log with stage fields
   (perceive/plan/act/observe), one line per stage.
2. sre_copilot/agent.py — Perceive→Plan→Act→Observe loop over ONE incident
   file; hard termination = max_iterations AND explicit success check
   (PlanDecision.resolved or health ok); dispatch via TOOL_MAP; tool-failure
   observed → plan retry (recovery demo via restart_service).
3. main.py — CLI: python main.py data/incidents/incident_01_db_timeout.txt
4. Run all 4 incidents; logs land in logs/; update README (architecture,
   setup, sample I/O).

## 7. Open issues / TODOs
- First git commit pending (doing now).
- README still a stub.
- ollama ps VRAM check pending; if near 4 GB, add Modelfile num_ctx 4096.
- Supabase not started (later cycle).