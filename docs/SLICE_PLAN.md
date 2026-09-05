# Keel — slice plan

Fifteen vertical TDD slices in three phases. Each slice is end-to-end thin: it
adds a capability the CLI can exercise, the tests that prove it, the events it
emits, and (from slice 1 on) at least one fitness function that reads those
events. A slice is done when its tests are green, its fitness functions are
registered, and SPEC.md reflects any schema it introduced.

Hardest-to-reverse decisions are front-loaded: the event schema (slice 1) and
the Handle schema (slice 2) are the two things every later slice depends on.
Get them wrong and the cost compounds; everything else is local.

## Sequencing constraints

- **S1 before everything.** Event schema v1 is frozen at the end of S1; later
  slices add event *types*, never change existing ones.
- **S3 (permissions) before S4 (sandbox).** Exec never lands without tiers.
- **S7 → S8 → S9** in order: layout, then budget, then compaction. Compaction
  without budget events has nothing to trigger it; budget without layout has
  nothing to measure.
- **S9 before S11.** Handoff records embed CompactionState.
- **S3 + S4 before S12.** Orchestrator needs tier inheritance and sandbox
  snapshot/restore to make delegating write access tolerable.
- **S5 + S11 before S14.** The bench needs a real adapter and the resume path.
- **S13 before S14.** The bench reports through the verifier, not around it.

## Phase 1 — Loop (walking skeleton)

### S1 · FakeModel end-to-end — ✅ implemented
Goal: the smallest thing that exercises kernel, event log, one tool and spill
together, with the verifier able to read the result.
- `ports/model.py`: `ModelPort`, `Capabilities`, typed request blocks, stream events.
- `adapters/fake_model.py`: replays a scripted sequence of tool calls / final answer.
- `kernel/loop.py`: plan → assemble (trivial: concatenate) → call → dispatch → observe; stop on final answer or max turns.
- `session/events.py`, `session/log.py`: event schema v1, append-only JSONL writer, torn-line detection on read.
- `tools/builtin/read.py`: one tool; oversized result spilled to a file with a Handle (Handle schema is provisional here, frozen in S2).
- `verify/registry.py` + `verify/ff/pointer_integrity.py`.
- CLI: `keel run --model fake --script tests/fixtures/s1.yaml`.
- Done when: a scripted run produces a JSONL log, a spilled file, and `ff_pointer_integrity` passes on it; a torn last line is detected and reported, not crashed on.

### S2 · Store, handles, pull tools — ✅ implemented
- `ports/store.py`, `adapters/local_store.py`: content-addressed blobs, `Handle` frozen.
- `store/handles.py`, `store/index.py`, `store/spill.py`, `store/errors.py`; `tools/builtin/{outline,grep,read}.py` resolve only through the store.
- `store/handles.py`: `Handle` Pydantic model with id, kind, tokens, sha256, label, preview_head, preview_tail, blob_path (optional).
- `store/index.py`: `HandleIndex` with append, get, delete, list operations over JSONL.
- `store/spill.py`: Content spill to filesystem with blob_path tracking.
- `verify/ff/{pointer_integrity,secrets,sensitive_data}.py`: re-pointed at the real store with blob_path.
- Tests: path traversal attempts (`../`, symlinks, absolute paths) are rejected with an event; identical content yields identical handle id; binary content rejected; index round-trip verified.
- Fitness: `ff_pointer_integrity` re-pointed at the real store.

### S3 · Tool runtime and permission tiers — ✅ implemented
- `tools/runtime.py`, `tools/registry.py`, `tools/permissions.py`: JSON-schema args, `ToolResult` envelope with handle and redaction_labels spill fields, `large_by_nature`, tiers over normalised calls with a shipped rule table + per-project extension file.
- `tools/runtime.py`: `ToolResult` dataclass with ok, payload, tokens, error, handle, redaction_labels.
- `tools/permissions.py`: `PermissionTier` type, wildcard pattern matching (e.g., `exec:*`), `check_permission()` function.
- `tools/registry.py`: `ToolRegistry` with register and get operations.
- `keel/kernel/loop.py`: typed dispatch table (TOOL_ARGS), no dynamic inspect.signature, default tier changed to "read".
- `keel/cli.py`: `--tier` CLI flag to override default permission tier.
- Tests: `exec pytest` and `exec rm -rf` normalise to different tiers; a denied call emits `ToolDenied` and returns a typed error the model sees; non-default rule table is loaded and honored; unrecognized argument produces error.
- Fitness: none new; `ff_budget_conformance` groundwork (token counts on every ToolResult).

### S4 · Subprocess sandbox
Goal: OS-level enforcement behind the `write`/`exec` permission tiers. Today
`check_permission()` in `loop.py` correctly denies the call at the dispatch
boundary, but a misbehaving tool (or a future tool that touches the filesystem
directly) has no containment. S4 adds a real sandbox so that `exec` runs in a
caged subprocess and `write` writes only inside an allowed directory.

**Design.** A subprocess with cwd jail, timeout, and env allowlist — the
simplest correct thing. The `SandboxPort` protocol defines three operations:
`run(cmd, cwd, timeout, env) → ExecResult`, `snapshot() → SnapshotId`, and
`restore(snapshot_id)`. The concrete adapter (`SubprocessSandbox`) creates a
temp working directory, copies it on `snapshot()`, and restores by replacing the
cwd with the snapshot copy. No container runtime, no OS-specific syscall
filtering — just process isolation via `subprocess.Popen` with a restricted cwd
and a cleaned environment. This is provider-agnostic (works on Linux, macOS,
Windows) and has zero dependencies beyond the stdlib.

The sandbox is **not** a general-purpose security boundary — it is a "good
citizen" enforcement layer that prevents accidental side effects during
development and testing. A determined attacker could escape it; that is not the
threat model. The threat model is: an agent tool that accidentally runs `rm -rf`
or writes to the wrong directory.

**Integration with the permission tier system.** `check_permission()` remains
the gatekeeper in `kernel/loop.py` (deny → emit `ToolDenied`, continue). The
sandbox wraps tool execution *after* the permission check passes: `exec` and
`write` tools receive a `sandbox: SandboxPort` parameter and call
`sandbox.run()` or write inside the sandboxed cwd. This keeps the two concerns
separate — permission is declarative (which tier?), sandbox is imperative (what
actually happens at the OS level?).

**Files to create:**
- `ports/sandbox.py`: `SandboxPort` protocol, `ExecResult` dataclass
  (`returncode`, `stdout`, `stderr`, `timed_out`).
- `adapters/subprocess_sandbox.py`: `SubprocessSandbox` — cwd jail via temp
  dir, timeout via `subprocess.run(timeout=...)`, env allowlist via explicit
  `env` dict, `snapshot()` via `shutil.copytree`, `restore()` via
  `shutil.copytree` over cwd.
- `tools/builtin/exec.py`: `exec_tool(cmd, *, sandbox, store)` — calls
  `sandbox.run(cmd)`, returns `ToolResult`. Registered with
  `default_tier="exec"`.
- `tools/builtin/write.py`: `write_tool(path, content, *, sandbox, store)` —
  writes `content` to `path` inside sandboxed cwd, returns `ToolResult`.
  Registered with `default_tier="write"`.

**Files to modify:**
- `kernel/loop.py`: add `sandbox: SandboxPort | None = None` parameter;
  register `exec` and `write` in `REGISTRY`; add entries to `TOOL_ARGS`;
  pass `sandbox` to `exec`/`write` tool calls.
- `tools/permissions.py`: add `write:*` patterns if needed (currently only
  `exec` patterns exist in `DEFAULT_RULES`).
- `keel/cli.py`: `--sandbox-dir` option for `keel run` (overrides default
  temp dir for reproducible tests).

**Event additions:**
- `SandboxSnapshot(snapshot_id)` — emitted when snapshot is taken.
- `SandboxRestored(snapshot_id)` — emitted when restore completes.
- The existing `timeout` field on `ExecResult` maps to a `tool_resulted` event
  with `ok=False` and an error message; no new event kind needed for timeout
  itself (it's already representable).

**Fitness function:**
- `ff_sandbox_isolation`: for every `tool_resulted` event where `ok=True` and
  the tool is `exec` or `write`, assert that no files were created outside the
  sandboxed cwd (walk the cwd, compare against a pre-exec snapshot). For
  `tool_resulted(ok=False)` on exec, assert the cwd is unchanged.

**Tests:**
- Cwd jail: `exec("ls /")` with sandbox cwd set to a temp dir — output must not
  contain root filesystem contents.
- Timeout: `exec("sleep 30")` with `timeout=1` — must emit `tool_resulted` with
  `ok=False` and `timed_out=True` in the error; no orphaned subprocess.
- Env allowlist: `exec("echo $SECRET")` with `SECRET` not in allowlist — output
  must not contain the secret.
- Snapshot/restore: write a file via `write`, call `snapshot()`, write another
  file, call `restore()` — second file must be gone.
- Permission tier: `exec` at `read` tier is denied (covered by S3, but verify
  integration still works with sandbox present).
- Escape attempt: `exec("cd ../../.. && pwd")` — cwd must remain inside jail.

**Sequencing note.** The SLICE_PLAN currently places S4 before S6 (ingest).
This is **not strictly required** — S6 uses `store.put()` which is a local
filesystem write inside `.keel/store/`, not a sandboxed exec/write. However,
keeping S4 before S6 is still correct because: (a) it closes the enforcement
gap before any new write-path tools land, and (b) S12 (orchestrator) needs
`snapshot()`/`restore()` which S4 introduces. The ordering is right as given.

**Done when:** `keel run` with an exec tool call runs the command inside a
sandboxed subprocess; `ff_sandbox_isolation` passes; timeout kills the process
and emits a clean error; `snapshot()`/`restore()` round-trips correctly; escape
attempts are contained.

### S5 · Real adapters + learning tests
- `adapters/anthropic.py`, `adapters/openai_compat.py` with declared `Capabilities` (cache semantics, tool encoding, reasoning-block echo rules).
- `tests/learning/`: pin the exact behaviors the assembler will rely on in S7 (prefix caching boundaries, tool_use/tool_result pairing, stop reasons).
- Done when: S1's scripted task runs against a live model behind a flag, log shape identical to FakeModel's.

### S1a · Secrets, sensitive data, unsafe tool calls — ✅ implemented (retrofitted)
Goal: prevention at the write boundary plus a verification backstop, requested
directly and built ahead of its natural slot because leaking a secret into a
durable log is not the kind of mistake you want sitting in the corpus while
later slices are still being built. This deliberately breaks "work only on the
current slice" — noted here rather than silently.
- `security/patterns.py`, `security/redact.py`: categorized regex scan + redact,
  Luhn-checked card numbers.
- `security/injection.py`: prompt-injection phrases and unsafe-shell patterns.
- Wired into `tools/builtin/read.py` (spill) and `kernel/loop.py` (tool-call args,
  final-answer text) before each reaches the event log. A new event kind,
  `RedactionApplied`, records that a redaction happened without recording what
  was redacted — consistent with the slice 1 rule that later slices add event
  kinds but never change existing ones.
- `verify/ff/{secrets,sensitive_data,unsafe_tool_calls}.py`: the backstop —
  scans the log and any spilled file for anything that should have been caught
  at the write boundary and wasn't.
- CI: gitleaks over the repo, bandit over `keel/`, both in `.github/workflows/ci.yml`
  as a separate `security` job. `.gitleaks.toml` allowlists `tests/` because the
  redaction tests intentionally contain fake-secret-shaped fixtures.
- Not done here, deferred to when exec exists (S4) and orchestration exists (S12):
  actually blocking a call, versus just flagging it after the fact.

### S1b · Inspector CLI — ✅ implemented
Goal: read-only views over session artifacts so the harness's real data is
visible without hand-parsing JSONL/JSON. Additive tooling, not a core-loop
slice; no writes to the store or log.
- `inspector/reader.py`: pure readers — `discover_sessions()`,
  `build_timeline()`, `load_store_index()`, `find_session_log()`.
- `inspector/cli.py`: `keel inspect` subcommand with four sub-subcommands:
  `sessions` (list), `timeline` (event replay), `store` (list/show handles),
  `verify` (run fitness functions).
- Wired into `keel/cli.py` as `keel inspect {sessions,timeline,store,verify}`.
- `keel inspect verify` is a thin session-ID-aware wrapper around the existing
  `run_on_log()` from `keel/verify/registry.py`; `keel verify <path>` remains
  the path-based entry point. Both share one implementation.
- Fixture logs: `tests/fixtures/inspect_{clean,torn,denial,spill}.jsonl` —
  covers clean session, torn last line, permission denial, and spilled/redacted
  content.
- Tests: 34 unit + integration tests covering human-readable and `--json`
  output paths, torn-line warnings, store list/show, and verify findings.

## Phase 2 — Context

### S6 · Ingest
- `store/ingest.py`: user-supplied material over threshold → blob + Handle with previews; below threshold passes through with a label.
- CLI: `keel run --attach path`.
- Tests: threshold boundary (exactly at, one over); preview carries token count and kind.

### S7 · Assembler and layout policy
- `context/assembler.py`, `context/layout_policy.py`: stable prefix (hashed), labeled retrieved blocks with framing lines, history, instruction last. Branches on `Capabilities` in this one module only.
- Fitness: `ff_instruction_last`, `ff_cache_stability`.
- Tests: identical inputs → identical prefix hash; map change → hash change; capability variants produce vendor-appropriate block shapes.

### S8 · Budget controller
- `context/budget.py`: `ContextBudget`, per-category accounting, escalation order spill → compact → evict, each an event. Agent-visible budget line (used/ceiling per category); escalation order not exposed.
- Fitness: `ff_budget_conformance`.
- Tests: overrun in each category triggers the right first escalation; budget line present in every assembled window; escalation policy string never appears in a window.

### S9 · Structured compaction
- `context/compaction.py`: history → `CompactionState` (open tasks, decisions with bounded rationale, verbatim constraints, unresolved errors, handles in play). Compaction is model-assisted but schema-validated; a compaction that fails validation is rejected and retried once, then falls back to evict.
- Fitness: `ff_compaction_lossless`, `ff_constraint_retention` (planted-constraint fixtures).
- Tests: planted constraint survives three compactions verbatim; open task count never decreases across compaction.

### S10 · Map compiler
- `mapc/compiler.py`, `mapc/extractors/{skeleton,entrypoints,tests,specs,references}.py`: conservative extractors, provenance handle per line, size cap, human preamble appended, `MapBuilt` event with hash.
- Fitness: `ff_map_provenance`.
- Tests: map for this repo names `uv run pytest` as the test command; a bogus extractor guess is omitted, not emitted; cap enforced by dropping lowest-priority section, never by truncating mid-line.

### S11 · Handoff and resume
- `session/handoff.py`, `session/resume.py`: `HandoffRecord` at session end and on kill (partial=True); resume from map + handoff + log tail; the torn-line detector from S1 becomes the resume boundary.
- Fitness: `ff_resume_equivalence` (FakeModel makes this deterministic).
- Tests: kill after every event index in a scripted run; every resume reaches the scripted end state.
- CLI: `keel resume <session_id>`.

### S12 · Orchestrator
- `orchestrate/{policy,contract,runner}.py`: `DelegationPolicy` (input-size × output-shape rule), `DelegationContract`, recursive kernel with own log, depth cap, tier inheritance capped, sandbox snapshot around child writes.
- Fitness: `ff_delegation_economy`.
- Tests: child cannot hold a tier the parent lacks; parent window contains contract + result only; depth cap enforced; child's discarded writes are gone after restore.

## Phase 3 — Verification

### S13 · Verifier surface and SQLite index
- `session/index.py`: SQLite projection built from JSONL, deletable and rebuildable; `verify/report.py`: typed report; CLI `keel verify <session|dir>`.
- Tests: delete index → rebuild → identical query results; no module outside `verify/` and `session/index.py` imports sqlite3 (a test asserts this).
- Guard: a test walks the import graph and asserts `keel/verify/` is imported by nothing under `keel/kernel/`, `keel/tools/`, `keel/orchestrate/`.

### S14 · Bench v0
- `bench/baseline_harness.py`: competent naive loop, same ModelPort, full-transcript context. `bench/tasks/` (≥ 12 tasks incl. ≥ 3 requiring kill-and-resume and ≥ 3 with planted constraints), `bench/oracles/` hidden from the agent's store.
- Fitness: `ff_no_green_lies`.
- Done when: `keel bench` produces the five-row table from SPEC §1 for Keel vs baseline on FakeModel (deterministic) and, behind a flag, on a live adapter.

### S15 · Memory prefix, gaming watch, hooks
- `memory/` store prefix with writer session id + map hash; map compiler labels it distinctly.
- `ff_memory_provenance`, `ff_budget_gaming` (correlation over the log between visible headroom and read/re-read actions, task-normalised).
- Kernel hooks (`before_assemble`, `after_tool`, `on_compaction`) documented with a no-op example; this is the seam the deferred self-improving layer attaches to.

## Standing slices (never done)

- **Corpus growth.** Every real failure observed in use becomes a bench task.
- **Learning tests.** Every adapter bump re-runs them; a contract change is a
  named test failure, not a mid-slice rollback.
- **Fitness registry.** Every new "the agent should always…" becomes a
  candidate ff before it becomes prompt text.
