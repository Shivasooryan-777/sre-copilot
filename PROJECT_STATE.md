# PROJECT_STATE.md — sre-copilot (SentinelOps)

## 1. File/folder tree (current)

sre-copilot/
├── .gitignore
├── .env                      # local only, gitignored
├── .env.example
├── requirements.txt
├── README.md                 # stub — expand in next closeout session
├── PROJECT_STATE.md
├── smoke_test.py
├── test_plan_stage.py
├── main.py
├── test_restart_recovery.py
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
    ├── tools.py
    ├── loop_logger.py
    └── agent.py

Generated logs are written to logs/ as:
- logs/<run_id>.jsonl
- logs/<run_id>.json

These generated logs are gitignored.

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
- _SVC_KEY_VALUE_PATTERNS: List[str]
- FILENAME_SERVICE_HINTS: Dict[str, str]
- SYMPTOM_RULES: List[Tuple[str, str]]
- _first_nonempty_line(text: str) -> str
- _extract_service(text: str) -> str
  # Internal implementation updated in Session 3 to support svc=..., service=...,
  # and service_name=... extraction. Signature unchanged.
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

loop_logger.py
- class LoopLogger:
  - __init__(run_name: str, log_dir: Union[str, Path] = "logs", incident_path: Optional[Union[str, Path]] = None)
  - log_stage(iteration: int, stage: str, payload: Dict[str, Any]) -> None
  - finish(status: str, result: Dict[str, Any]) -> Dict[str, Any]

agent.py
- _to_dict(obj: Any) -> Any
- _safe_tool_args(args: Any) -> Dict[str, Any]
- _filtered_kwargs(fn: Callable, args: Dict[str, Any]) -> Dict[str, Any]
- _coerce_tool_result(tool_name: str, value: Any, attempt: int) -> ToolResult
- execute_tool_with_recovery(tool_name: str, tool_args: Any, max_attempts: int = 2) -> Tuple[ToolResult, Dict[str, Any]]
- evaluate_success(plan_decision: PlanDecision, tool_result: ToolResult) -> Tuple[bool, str]
- observe(observation: IncidentObservation, iteration: int, plan_decision: PlanDecision, tool_result: ToolResult) -> IncidentObservation
- run_agent_loop(incident_path: Union[str, Path], max_iterations: int = 3, log_dir: Union[str, Path] = "logs", plan_override: Optional[Callable[[IncidentObservation, int], PlanDecision]] = None) -> Dict[str, Any]

main.py
- main(argv: Optional[List[str]] = None) -> int

test_restart_recovery.py
- forced_restart_plan(observation: IncidentObservation, iteration: int) -> PlanDecision
- main() -> int

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

## 5. Completed this session (Cycle 1, Session 3)
- Confirmed project structure from Session 2 PROJECT_STATE.md.
- No Session 1 or Session 2 frozen signatures were changed.
- Added small additive improvement to perceive.py:
  - _SVC_KEY_VALUE_PATTERNS added.
  - _extract_service now supports svc=..., service=..., service_name=...
  - This addresses incident_04_crash_loop.txt missing svc=notify-worker.
- Created sre_copilot/loop_logger.py:
  - JSONL event logging for run_start, stage events, and run_summary.
  - Final consolidated strict JSON report per run.
  - Logs are written to logs/<run_id>.jsonl and logs/<run_id>.json.
- Created sre_copilot/agent.py:
  - Full Perceive -> Plan -> Act -> Observe loop.
  - Act stage uses existing TOOL_MAP.
  - Bounded retry/recovery in execute_tool_with_recovery.
  - Explicit success-condition check in evaluate_success.
  - Observe stage updates IncidentObservation safely for the next iteration.
  - Hard termination via max_iterations.
  - Safe fallback behavior when planner returns none or when tools fail.
- Created main.py CLI:
  - python main.py data/incidents/incident_01_db_timeout.txt
  - supports --max-iterations
  - supports --log-dir
  - supports --reset-restart-counter
- Created test_restart_recovery.py:
  - deterministic failure drill for restart_service
  - forces restart_service using plan_override
  - verifies deliberate first-call failure recovers gracefully without crashing
- Updated .gitignore to ignore generated logs while preserving logs/.gitkeep.
- Session 3 satisfies:
  - Act stage implemented.
  - Observe stage implemented.
  - Full agent loop implemented.
  - Hard termination implemented.
  - Explicit success-condition check implemented.
  - Deliberate tool failure recovery implemented.
  - Every iteration/stage logged to JSONL and final JSON.

## 6. Next session task (Cycle 1 closeout — scoped)
1. Expand README.md:
   - problem statement
   - architecture explanation
   - architecture diagram or Mermaid diagram
   - setup instructions
   - run instructions
   - sample input/output
2. Capture sample outputs from:
   - all 4 incident runs
   - restart_service failure recovery drill
3. Add a short demo script/checklist for the 3–5 minute video.
4. Verify viva defense points:
   - why llm_client.py exists
   - why retry/fallback is deliberate robustness engineering
   - why JSONL + JSON logging was chosen
   - how max_iterations and success condition prevent runaway loops
5. Optional, only if time remains:
   - persist final run summaries to Supabase
   - this should not be started unless README/closeout is complete.

## 7. Open issues / TODOs
- README is still a stub and must be expanded before final Cycle 1 submission.
- Architecture diagram asset or Mermaid diagram still needed.
- Supabase not started.
- ollama ps VRAM check still pending; if near 4 GB, add Modelfile num_ctx 4096.
- Natural LLM runs may not always choose restart_service on the existing four incidents.
  The deterministic restart failure drill is covered by test_restart_recovery.py.
- Continue using small incremental git commits.