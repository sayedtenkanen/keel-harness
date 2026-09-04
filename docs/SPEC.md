# Keel — design spec

**Version 0.2 · reviewed, decisions recorded**

A Python harness where the context window is a cache over an addressable store,
layout and budget are policy rather than accident, and every claim about quality
is a check that runs after the fact.

| Ties | Scope v1 | Runtime | Process |
|---|---|---|---|
| Greenfield. No dependency on prior components. | Full harness. Self-improving loop deferred, hooks reserved. | Provider-agnostic model port, adapters per vendor. | Spec → adversarial review → slice plan → TDD slices. |

## 1. What "best" means

"Best agent harness ever" is not a spec; it is a slogan. The design commits to a
definition that can lose. Keel is better than a baseline harness on the same
model if, across a fixed task corpus, it produces:

| Claim | Measured as | Baseline to beat |
|---|---|---|
| Solves more | Pass rate on the corpus, verified by oracles the agent cannot see | Same model, naive loop, full-transcript context |
| Forgets less | Planted-constraint retention: constraints stated at turn 1 still honored at turn N | Same |
| Costs less per solve | Tokens (input + output + cache-miss) per passed task | Same |
| Recovers | Task resumed after forced session kill reaches the same outcome | Naive loop cannot; measured as pass rate after kill |
| Never lies green | Zero cases where the agent reports success and the oracle disagrees | Absolute, not relative |

Everything else in this document serves these five rows. A feature that does not
move one of them is out.

## 2. Principles

**The window is a cache, not the store.** Anything the agent might need lives in
addressable storage and enters the window by policy. The transcript is
disposable; the event log and the store are truth.

**Policy over in-the-moment judgment.** Where the model would otherwise decide
something about its own context — what to re-read, whether to delegate, when to
summarize — the harness decides by rule, and the rule is config that can be
tested and later mutated.

**Constraints migrate from prompts to verification.** Every "the agent should
always…" in the prompt is a candidate for a post-hoc check. Prompts stay short;
the verifier grows.

**The provider is a detail, its capabilities are not.** The model port is thin,
but it exposes what differs between providers (context size, cache semantics,
tool-call shape, reasoning blocks) as declared capabilities the assembler reads.

**Structured state survives; prose summaries do not.** Compaction and handoff
produce typed records with pointers, never free-text summaries, because a schema
cannot silently drop the one constraint that mattered.

**The verifier is human-authored and immutable.** Nothing the agent does can
change what counts as passing.

**Redaction happens at the write boundary, verification is the backstop.**
Anything about to become durable (an event log line, a spilled file) is
scanned for secrets and sensitive data and masked before the write, not
after. The corresponding fitness functions exist to catch the code path
that forgot to call the redactor, not to do the redacting themselves.

## 3. Architecture

Eleven components, three of them ports. Nothing depends on the kernel; the
verifier depends on nothing but the event log.

```
              ┌──────────────┐
              │   Verifier    │ ◀── reads event log only
              └──────────────┘
                      ▲
   ┌──────────────────┴──────────────────┐
   │              Event Log               │ ◀── append-only truth
   └──────────────────▲──────────────────┘
                      │ emits
   ┌──────────────────┴──────────────────┐
   │              Kernel (loop)           │
   │  plan → assemble → call → observe    │
   └──┬──────────┬──────────┬──────────┬──┘
      │          │          │          │
 ┌────▼────┐ ┌───▼────┐ ┌───▼─────┐ ┌──▼────────┐
 │Assembler│ │ Tools  │ │Orchestr.│ │ Session   │
 │layout + │ │runtime │ │sub-agent│ │ handoff / │
 │ budget  │ │+ spill │ │isolation│ │ resume    │
 └──┬───┬──┘ └───┬────┘ └───┬─────┘ └───────────┘
    │   │        │          │
 ┌──▼┐ ┌▼─────┐  │      (recursive Kernel)
 │Map│ │Store │◀─┘
 │cmp│ │+index│
 └───┘ └──────┘
   Ports: ModelPort · SandboxPort · StorePort
```

### 3.1 ModelPort
`complete(request) → stream of events`, where request carries an ordered list of
typed blocks (system, cached-prefix marker, message, tool result, tool schemas)
and a budget. `capabilities()` returns a declared record: max context,
cache-prefix semantics (none / explicit breakpoints / automatic), tool-call
encoding, whether reasoning blocks exist and must be echoed back, supported stop
reasons. The assembler reads capabilities to decide layout; adapters own every
vendor quirk. First adapters: Anthropic, OpenAI-compatible, and a deterministic
`FakeModel` that replays scripted tool calls.

### 3.2 Store and index
Content-addressed blobs behind `StorePort`, local-filesystem adapter first.
Every blob has a `Handle`. Pull tools: `outline(handle)`, `grep(pattern, scope)`,
`read(handle, range)`. All paths resolve through the store, never the raw
filesystem — that is where path-traversal safety lives.

### 3.3 Ingest and spill
User material over a threshold is ingested to the store and replaced by a
labeled handle with head/tail preview. Tool results over the threshold are
spilled the same way. Threshold is config (default 2 000 tokens). Previews carry
token count and kind.

### 3.4 Map compiler
Generates the always-loaded layer from the store: repository skeleton, entry
points, test targets, invariants from files tagged as specs, a table of large
reference material with handles. Hard size cap (default 1 500 tokens);
regenerates on store change; emits `MapBuilt` with its own hash. Every map line
carries a provenance handle; extractors omit rather than guess. Human preamble is
appended, never merged.

### 3.5 Assembler
Takes `SessionState`, map, retrieval results and the live instruction; produces a
window per a fixed `LayoutPolicy`: stable prefix (system, map, tool schemas)
marked for caching; labeled retrieved blocks with one-line framing each; history;
instruction and critical fresh facts last. `BudgetController` enforces
per-category ceilings (map, retrieved, tool results, history, reserve). On
overrun: spill → structured compaction → evict oldest retrieved. Every escalation
is an event.

### 3.6 Kernel
Thin. `plan → assemble → call → dispatch tools → observe → repeat`, ending on a
stop condition or budget wall. Hooks (`before_assemble`, `after_tool`,
`on_compaction`) are how later work attaches without the kernel growing.

### 3.7 Tool runtime
Typed tools with JSON-schema args, a permission tier over the *normalised call*
(tool + argument pattern), and a `ToolResult` envelope with spill support. Tools
declare `large_by_nature` so the runtime spills before the model sees the
payload. Every denial is an event. The kernel uses a typed dispatch table
(TOOL_ARGS) for argument validation rather than dynamic introspection. Default
permission tier is "read"; CLI `--tier` flag allows override.

### 3.8 SandboxPort
`run(cmd, cwd, timeout, env) → ExecResult`, plus `snapshot()` / `restore()` so a
sub-agent's writes can be discarded. Adapters: subprocess with cwd jail (v1),
container (v1.x).

### 3.9 Orchestrator
Sub-agents as context isolation. `DelegationPolicy` decides by rule when a task
runs in a fresh window (large input, contractually small output). The child gets
a `DelegationContract` and returns a typed result; the parent pays for contract
and result only. Children are full kernels, depth-capped, and inherit the
parent's permission tiers capped, never widened.

### 3.10 Session and handoff
Sessions end by writing a `HandoffRecord`. Resume boots from map + handoff +
event log tail, never from a transcript. Forced kill mid-turn is first-class: a
torn last JSONL line is detectable, discardable, and marks the resume point.

### 3.12 Security: redaction and injection heuristics
`security/patterns.py`, `security/redact.py`: pattern-based `scan`/`redact` over
text about to be logged or spilled — secrets (cloud provider keys, private key
blocks, JWTs, generic `key=`/`token=` assignments) and sensitive data (email,
SSN, Luhn-checked card numbers, phone numbers), each tagged with a category so
the two can be reported on independently. `security/injection.py`: heuristics
for prompt-injection phrasing and unsafe shell patterns (fork bombs, `curl | sh`,
`rm -rf /`), used by the verifier now and by the tool runtime once slice 4 adds
exec. None of this is a substitute for a real DLP or security product — it is
the harness's own backstop over its own logs and store, deliberately biased
toward false positives over false negatives.

### 3.11 Verifier
Registry of fitness functions with stable IDs, each a pure function over the
event log (and, for oracles, sandbox end state). Runs post-session, in CI, or on
demand. The only place "best" is defined; not writable from any agent path.

## 4. Key schemas

Pydantic v2, versioned under `keel/schemas/vN/`, migration test per bump.

```python
Handle(id, kind: Literal["file","tool_result","paste","handoff","map","memory"],
       tokens, sha256, label, preview_head, preview_tail, blob_path: str | None = None)

ContextBudget(total, map, retrieved, tool_results, history, reserve)

CompactionState(open_tasks: list[Task], decisions: list[Decision],   # Decision has bounded rationale
                constraints: list[Constraint],                        # verbatim
                unresolved_errors: list[ErrorRef],
                handles_in_play: list[Handle], compacted_range: tuple[int, int])

HandoffRecord(session_id, map_hash, state: CompactionState,
              last_event_seq, partial: bool, next_step: str | None)

DelegationContract(question, scope: list[Handle], result_schema, budget, depth)

ToolResult(ok, payload: bytes, tokens, error: str | None, handle: Handle | None,
           redaction_labels: list[str] | None)
```

## 5. Package layout

```
keel/
  ports/          model.py  sandbox.py  store.py
  adapters/       anthropic.py  openai_compat.py  fake_model.py
                  local_store.py  subprocess_sandbox.py
  store/          handles.py  index.py  ingest.py  spill.py
  mapc/           compiler.py  extractors/
  context/        assembler.py  layout_policy.py  budget.py  compaction.py
  kernel/         loop.py  hooks.py  stop.py
  tools/          runtime.py  registry.py  permissions.py  builtin/
  orchestrate/    policy.py  contract.py  runner.py
  session/        events.py  log.py  index.py  handoff.py  resume.py
  verify/         registry.py  report.py  ff/
  schemas/        v1/
tests/            unit/  learning/  corpus/
bench/            tasks/  oracles/  baseline_harness.py
```

Zero required dependencies beyond pydantic and the vendor SDK for the adapter in
use. `bench/` ships with the repo because a harness without its baseline cannot
make the claims in §1.

## 6. Fitness functions (initial registry)

| ID | Checks | Serves |
|---|---|---|
| ff_pointer_integrity | Every handle in any assembled window resolves in the store | Recovers, Forgets less |
| ff_budget_conformance | No category exceeded its ceiling without a preceding spill/compaction event | Costs less |
| ff_constraint_retention | Planted constraints appear verbatim in every CompactionState and HandoffRecord | Forgets less |
| ff_no_green_lies | Agent-reported success implies oracle success | Never lies green |
| ff_compaction_lossless | Open tasks and unresolved errors before compaction ⊆ after | Forgets less |
| ff_resume_equivalence | Killed-and-resumed run reaches same oracle verdict as uninterrupted | Recovers |
| ff_delegation_economy | Parent tokens for a delegated task ≤ contract + result + ε | Costs less |
| ff_map_provenance | Every session references exactly one map hash and it exists | Recovers |
| ff_instruction_last | Live instruction is the final block in every assembled window | Forgets less |
| ff_cache_stability | Stable prefix hash unchanged across turns unless map changed | Costs less |
| ff_budget_gaming | Actions do not correlate with visible budget headroom beyond what the task explains | Never lies green |
| ff_memory_provenance | Every `memory/` blob carries a writer session id and map hash that exist in the log | Recovers |
| ff_no_secret_leak | No unredacted secret (API key, private key, JWT, ...) reaches the log or a spilled file | Never lies green |
| ff_no_sensitive_data_leak | No unredacted PII (email, SSN, card number, phone) reaches the log or a spilled file | Never lies green |
| ff_no_unsafe_tool_call | No tool call or model output matches a known unsafe-shell or prompt-injection pattern | Never lies green |

## 7. Adversarial review

**Risk: provider-agnosticism leaks where it matters.** Cache semantics, tool-call
encoding and reasoning blocks differ per vendor and affect layout directly.
*Position:* thin port, declared capabilities, assembler branches on capabilities
in exactly one module, learning tests per adapter. A third adapter forcing a
fourth branch is the signal to revisit.

**Risk: structured compaction drops nuance.** *Position:* bounded `rationale`
per Decision, not a session summary; ff_compaction_lossless is the tripwire. No
free-text summary field pre-emptively.

**Risk: policy fights the model.** *Position:* the model can always pull; policy
decides only what is pushed. Delegation is rule-triggered but model-requestable.
Thresholds are config so the deferred self-improvement layer can tune them.

**Risk: the map compiler produces confident garbage.** *Position:* provenance
per line, conservative extractors, human preamble for judgment, a bench task for
map quality.

**Risk: delegation overhead eats the savings.** *Position:* bench records total
cost, not just parent-side; threshold set from measurement. Expect break-even
well above 10k input tokens.

**Risk: the bench is the soft underbelly.** *Position:* competent baseline,
hidden human-authored oracles, long-horizon tasks that require kill-and-resume.
Corpus growth is a standing slice.

**Reversed: SQLite as primary event log.** The log's defining requirement is a
cheap, obvious resume point after a killed process; a JSONL line boundary is
that. *Position:* JSONL writes, SQLite as a deletable, rebuildable projection.

**Reversed: permission tiers per tool.** Granularity was the real axis: under
per-tool tiers `pytest` and `rm -rf` are both `exec`. *Position:* tiers over
normalised calls with a shipped, extensible rule table.

**Risk: this becomes a framework.** *Position:* slice 1 is a working loop on
FakeModel with store + spill + log and nothing else. Every later component earns
its place by moving a §1 row on the bench.

## 8. Decisions

| Question | Decision | Rule |
|---|---|---|
| Event log storage | JSONL write format; SQLite is a derived, rebuildable index giving the verifier its read API | Nothing reads SQLite to make a decision the JSONL could not reconstruct |
| Budget visibility | Agent sees per-category used/ceiling; escalation order hidden | ff_budget_gaming watches for headroom-correlated behavior |
| Cross-session memory | Store blobs under reserved `memory/` prefix, labeled distinctly by the map compiler | Each blob carries writer session id and map hash |
| Permissions | Static tiers in v1 over normalised calls; runtime hook reserved | Children inherit capped; every denial is an event |
| Name | Keel | Check PyPI before first publish; don't extend the metaphor until it earns it |

## 9. Non-goals for v1

The self-improving loop (genome, A/B, promotion gate) — hooks reserved,
machinery not built. Multi-user or hosted operation. UI beyond CLI and verifier
report. Streaming token-level UX. Adapters beyond Anthropic, OpenAI-compatible,
Fake. Vector retrieval — grep and outline first. A general-purpose DLP or security
product — `security/` is a harness-scoped backstop, not a replacement for one.
