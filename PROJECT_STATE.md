# PROJECT_STATE.md — sre-copilot (SentinelOps)

## 1. File/folder tree (current)

sre-copilot/
├── .gitignore
├── .env                      # local only, gitignored
├── .env.example
├── requirements.txt
├── README.md                 # stub — expand in next session
├── PROJECT_STATE.md
├── smoke_test.py
├── test_plan_stage.py
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
    ├── perceive.py
    ├── plan.py
    └── tools.py

## 2. Signatures (FROZEN — flag loudly before changing)

interfaces.py
- TOOL_NAMES = Literal["check_service_health","restart_service","check_disk_space","none"]
- class PlanDecision(BaseModel): reasoning, tool_name, tool_args, resolved, summary (all defaulted; schema() = safe fallback)
- class ToolResult(BaseModel): tool_name, success, message, data
- class IncidentObservation(BaseModel): source, raw_text, service, symptoms, severity_hint, summary; safe_default(source, raw_text)
- TOOL_SIGNATURES: Dict[str, str]

llm_client.py
- class LLMProviderError(RuntimeError)
- _call_ollama(prompt) -> str   # POST /api/generate, format=json, timeout=120s
- _call_gemini(prompt) -> str   # stub
- _call_glm(prompt) -> str      # stub
- _raw_generate(prompt) -> str  # switch on LLM_PROVIDER
- _extract_json(text) -> Optional[dict]
- generate(prompt, schema=None) -> Union[T, str]  # 2 attempts + safe-default fallback

tools.py
- check_service_health(service="payments-api") -> ToolResult
- check_disk_space(mount="/var/log") -> ToolResult
- restart_service(service="payments-api") -> ToolResult  # 1st call fails by design
- reset_restart_counter() -> None
- TOOL_MAP: Dict[str, callable]

perceive.py
- SERVICE_PATTERNS: List[str]
- FILENAME_SERVICE_HINTS: Dict[str, str]
- SYMPTOM_RULES: List[Tuple[str, str]]
- _first_nonempty_line(text: str) -> str
- _extract_service(text: str) -> str
- _infer_service_from_filename(stem: str) -> str
- _extract_symptoms(text: str) -> List[str]
- _extract_severity(text: str, symptoms: List[str]) -> str
- _summarize(text: str, max_chars: int = 300) -> str
- perceive(incident_path: Union[str, Path]) -> IncidentObservation

plan.py
- VALID_TOOL_NAMES: set[str]
- _FEW_SHOT_EXAMPLES: List[dict]
- _tool_signature_block() -> str
- _few_shot_examples() -> str
- _observation_block(observation: IncidentObservation, max_raw_chars: int = 900) -> str
- build_plan_prompt(observation: IncidentObservation) -> str
- _normalize_plan(raw: Any, observation: IncidentObservation) -> PlanDecision
- plan(observation: IncidentObservation) -> PlanDecision

smoke_test.py
- test_tools()
- test_plan()
- FEW_SHOT_PROMPT

test_plan_stage.py
- main() -> None

## 3. Supabase tables
None yet.

## 4. Environment variables (names only)
LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_NUM_PARALLEL,
OLLAMA_MAX_LOADED_MODELS, GEMINI_API_KEY, GLM_API_KEY,
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

## 5. Completed this session (Cycle 1, Session 2)
- Confirmed project structure matched Session 1 PROJECT_STATE.md.
- No Session 1 frozen signatures were changed.
- Added additive shared schema IncidentObservation to interfaces.py.
- Fixed Python syntax issue caused by misplaced `from __future__ import annotations`.
- Built Perceive stage in sre_copilot/perceive.py:
  - reads one incident file,
  - extracts service, symptoms, severity hint, and summary,
  - returns safe fallback if file cannot be read.
- Built Plan stage in sre_copilot/plan.py:
  - builds short structured few-shot prompt,
  - uses llm_client.generate(prompt, schema=PlanDecision),
  - inherits retry / JSON extraction / safe fallback behavior,
  - normalizes tool_name/tool_args safely.
- Added test_plan_stage.py to run Perceive -> Plan over all 4 synthetic incidents.
- LIVE VERIFIED locally on Windows PowerShell inside `.venv`:
  - all 4 incidents processed sequentially,
  - all 4 produced valid PlanDecision-shaped outputs,
  - no safe fallback was required in this run.
- Observed plan behavior:
  - incident_01_db_timeout -> check_service_health(payments-api)
  - incident_02_memory_leak -> check_service_health(cache-worker)
  - incident_03_disk_full -> check_disk_space(/var/log)
  - incident_04_crash_loop -> check_service_health(notify-worker)

## 6. Next session task (Cycle 1, Session 3 — scoped)
1. Optional small Perceive improvement before full loop:
   - add support for `svc=...` style service extraction in perceive.py.
2. sre_copilot/loop_logger.py — JSONL per-iteration log with stage fields
   (perceive/plan/act/observe), one line per stage.
3. sre_copilot/agent.py — full Perceive -> Plan -> Act -> Observe loop using:
   - perceive()
   - plan()
   - TOOL_MAP
   - ToolResult
   - max_iterations
   - explicit success check
4. main.py — CLI:
   python main.py data/incidents/incident_01_db_timeout.txt
5. Run all 4 incidents through the full loop.
6. Write logs to logs/.
7. Expand README.md with architecture, setup/run instructions, and sample I/O.

## 7. Open issues / TODOs
- Perceive currently missed `svc=notify-worker` in incident_04 and inferred `payments-api`; Plan compensated using raw text. Candidate small parser fix in Session 3.
- README still a stub.
- Full agent loop not implemented yet.
- Supabase not started.
- ollama ps VRAM check still pending; if near 4 GB, add Modelfile num_ctx 4096.
- Continue using small incremental git commits.