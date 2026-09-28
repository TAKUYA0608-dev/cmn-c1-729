# Template Design Specification — CMN-C1-729

> **Stage ② design-only document.** This MR ships design artifacts only
> (docs/02 + `src/schemas/state.py` + the TC-06/TC-07 framework-compliance test).
> The node/graph/service/test implementation lands in the Stage ③ implementation
> MR (plan in *Open Items* below), where it has been prototyped and verified locally.

## Position in AgentCore Architecture

- **Template ID**: CMN-C1-729 (Cat 1 / CMN)
- **L1 Base**: `AgentBaseGraph` (L1 direct inheritance; per 2026-05-18 L2 deprecation) —
  not `AutonomousBaseGraph` (fixed 5-slot pipeline, no autonomous loop, no LLM budget).
- **Pattern**: Cat 1 **composite** — the `main` slot is a single composite `FunctionNode`
  that orchestrates 4 capability sub-steps via `sub.execute(state)` (same pattern as
  sibling templates). `VectorRAGAgent` is referenced only
  as a *pattern* (read-only KB retrieval), never as a base class.
- **Capability**: OpenTelemetry **GenAI Semantic Conventions instrumentation Q&A** — given
  an NL question about instrumenting a GenAI application, classify the OTel signal area
  (spans / metrics / events-logs / setup), retrieve the applicable convention passages from
  the seeded OTel GenAI semantic-conventions KB (**read-only**), map them to concrete
  `gen_ai.*` attributes with their requirement level, and assemble a **cited** instrumentation
  answer with placeholder-only setup snippets. This is an **advisory** capability: it produces
  a deliverable (guidance), it never mutates a telemetry pipeline, and the human engineer owns
  the final instrumentation decision.

## Architecture Overview

### Node Configuration

```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                     (QueryNormalize) (composite)   (S-3 cite + S-5 no-cred + S-4 audit)
```

| Slot | Class | required_trust_level | Responsibility |
|---|---|---|---|
| pre_process | `QueryNormalizeNode(FunctionNode)` | `VERIFIED_EXTERNAL` | S-1: NFKC / injection screen / size cap on the instrumentation question; capture read-only `query_context`. Rejections return **degraded SUCCESS + error_code** (never `status=ERROR` — post_process must always run) |
| main | `MainNode(FunctionNode)` — composite | `VERIFIED_EXTERNAL` | Instantiates the 4 sub-nodes in `__init__` (`self._seq`), runs them via `sub.execute(state)`; owns the single S-2/S-3/S-4 boundary; emits `instrumentation_answer_assembled` (S-4) |
| post_process | `ResponseValidateNode(FunctionNode)` | `VERIFIED_EXTERNAL` | **S-3 citation-completeness (FAIL-CLOSED)**: a grounded answer must be fully cited — an uncited claim **blocks** the deliverable (degraded `needs_review`, empty body, `error_code=CITATION_INCOMPLETE`, `citation_blocked` S-4 event). **S-5 credential redaction** + **S-3 whole-report PII redaction** (credential / My-Number / email / phone / JP+EN company names, applied to the serialized report before the disclaimer). **Whitelist-by-construction envelope** — only allowed KB-derived fields reach the output; no arbitrary caller field is copied. Mandatory disclaimer + terminal `agent_invoke_complete` audit (S-4). Runs on the degraded path too and always sets `audit_logged` |

Composite `main` sub-steps (called via `sub.execute(state)` — they do NOT appear in
`node_history`; each declares `required_trust_level` as a design-intent annotation and
self-skips on `error_code`):

| # | Sub-node | Type | Logic |
|---|---|---|---|
| 1 | `SignalClassifyNode` | deterministic (rule) | Classify the query into OTel GenAI signal areas (spans / metrics / events-logs / setup / attributes) from keyword + `gen_ai.*` matches |
| 2 | `ConventionRetrieveNode` | deterministic (RAG, BM25-lite) | Retrieve top-k convention passages for the classified areas from the seeded OTel GenAI KB; **read-only**; a 0-hit is not an error → out-of-scope safe answer |
| 3 | `AttributeMapNode` | deterministic | Fold the retrieved passages into concrete `gen_ai.*` attributes / metric instruments with their `type` and `requirement_level` (Required / Recommended / Opt-In) |
| 4 | `InstrumentationAssembleNode` | retrieval-grounded | Assemble the cited `instrumentation_answer` + placeholder-only setup snippets **from KB templates only** — no free LLM generation, no real credentials (S-5). 0-hit → in-scope safe answer, empty citations |

### Data Flow

```
[Caller: AI platform / observability engineer instrumenting a GenAI app]
  user_input (NL instrumentation question) ─→ pre_process: validate → validated_query / query_context
  ─→ main composite:
       SignalClassify         → classified_signals
       ConventionRetrieve     → retrieved_conventions, retrieval_hit_count  (0 → out-of-scope safe answer)
       AttributeMap           → attribute_mappings (gen_ai.* + requirement_level)
       InstrumentationAssemble→ instrumentation_snippets (placeholders only), instrumentation_answer, citations
  ─→ post_process: citation gate + S-5 redaction + disclaimer → formatted_output, audit_logged
[Output: cited instrumentation guidance + gen_ai.* attribute map + placeholder-only setup snippet]
```

Degraded paths (all return **`status=SUCCESS` + `error_code`**, never `status=ERROR`):
- `INPUT_EMPTY` / `INPUT_TOO_LONG` / `INJECTION_REJECTED` (pre_process) — the offending body is
  discarded, never processed; `user_input` is cleared at S-1 (earliest-possible minimization).
- `CITATION_INCOMPLETE` (post_process) — a grounded answer that cannot be fully cited is blocked
  with a `needs_review` envelope (empty body).

In every case downstream sub-nodes self-skip and post_process still audits (disclaimer + S-4).
Rationale: under the production framework `status=ERROR` short-circuits `route()` straight to
`finalize`, skipping S-3/S-4 (verified on the platform) — so rejections must be a **degraded
SUCCESS**, guaranteeing post_process always runs. A **0-hit retrieval is NOT a degraded path** —
it routes to an in-scope "insufficient grounding / out-of-scope" safe answer (no hallucinated
instrumentation advice).

### State Definition

See `src/schemas/state.py` (this MR). Flat TypedDict extending `AgentState`; complex fields are
`NotRequired[str]` JSON strings (ADR-005 msgpack safety) with `# JSON:` shape comments.
**No credentials in state** (S-5) — setup snippets are placeholder-only.

## Framework Utilization

### Shared Components Used

- `framework.graph.agent_base_graph.AgentBaseGraph` — outer graph (L1 direct)
- `framework.nodes.function_node.FunctionNode` — all nodes (the sealed S-2/S-3 gates are used
  as-is; this template extends behaviour only through node `execute()`, never by overriding
  `_security_gate_input` / `_security_gate_output` — see `tests/unit/test_framework_compliance_tc06_tc07.py`)
- `framework.schemas.trust_level.TrustLevel` — `required_trust_level: ClassVar` on every node
- `shared.utils.audit_logger.emit_trace_event` — S-4 domain events (canonical import; the local SDK stub
  fallback shim, same idiom as server.py)

### Composition Pattern

Cat 1 composite: `MainNode.__init__` builds `self._seq = [SignalClassify, ConventionRetrieve,
AttributeMap, InstrumentationAssemble]`; `execute()` folds `sub.execute(working)` deltas and
returns the changed keys + `status=AgentStatus.SUCCESS.value`. Registry alias
`OpenTelemetryGenAISemanticConventionsInstrumentationAgent = Graph` +
`src/graph/__init__.py` export (config/agent.yaml `class:` resolution).

**Determinism**: retrieval, attribute mapping, and snippet assembly are fully deterministic
(keyword/tag scoring + KB composition, no LLM). `config/agent.yaml` declares no `model`,
`pyproject.toml` pins no LLM dependency, and `src/` contains no model call — behaviour is
reproducible and auditable.

## Import Isolation Confirmation

- No `agenticstar` / Level-0 imports anywhere in `src/` (PB-4)
- Nodes import `framework.*` + `shared.*` + `src.*` only
- `OtelGenAIKB` service is pure Python (deterministic, no external calls at test time)

## Design Decision Record

| # | Decision | Rationale |
|---|---|---|
| D-01 | Cat 1 composite (FunctionNode-in-main), not GraphNode | Single capability (instrumentation Q&A); the 4 sub-steps are facets of one retrieval-answer pipeline, not a business workflow |
| D-02 | `InstrumentationAssemble` = KB-sourced snippets with placeholders only, no free LLM generation | S-5: never emit a real OTLP token / credential; retrieval-grounded snippets keep answers auditable and safe |
| D-03 | Degraded paths return `SUCCESS + error_code` (body discarded); 0-hit is an in-scope safe answer | Production framework routes `ERROR` to finalize, skipping post_process S-3/S-4; 0-hit must not hallucinate convention advice |
| D-04 | `required_trust_level = VERIFIED_EXTERNAL` on all nodes (incl. sub-nodes) | Matches `config/agent.yaml`; satisfies the S-1 CI gate (`check_trust_level.py`) |
| D-05 | S-4 `emit_trace_event` in **every** node's `execute()` (incl. sub-nodes and skip paths) | TC-05: every execute() path emits ≥1 domain event; terminal `agent_invoke_complete` fires on the degraded path too |
| D-06 | Advisory / read-only boundary; human owns the instrumentation change | The agent emits guidance + a deliverable, never mutates a telemetry pipeline or exporter config |
| D-07 | S-3 citation-completeness is **fail-closed** (grounded-but-uncited → `needs_review`, not a flagged pass) | A cited deliverable is a hard contract; `OtelGenAIKB.build_citations` validates provenance (opaque `doc_ref` + internal-KB source allowlist) so an uncited/fabricated ref is dropped and the gate blocks |
| D-08 | Output is **whitelist-by-construction** + S-3 whole-report PII redaction (credential / My-Number / email / phone / JP+EN company); caller identifiers are **unconditionally tokenized** to `<kind>:<sha8>` (no syntactic allowlist), citation provenance is validated against the internal KB allowlists | Only allowed KB-derived fields reach the envelope; no arbitrary caller field is copied. A bare name (`Alice` / `John.Smith` / `TaroYamada`) must not pass a loose character-class allowlist — pass-through is limited to already-tokenized surrogates; the whole-report redactor is defense-in-depth (post-serialize, pre-disclaimer) |

## Open Items (Stage ③ implementation plan)

Lands in the Stage ③ implementation MR (already prototyped locally):

1. `src/nodes/` — `pre_process_node.py` (`QueryNormalizeNode`), composite `main_node.py`
   (`MainNode`) + 4 sub-node modules (`signal_classify_node.py`, `convention_retrieve_node.py`,
   `attribute_map_node.py`, `instrumentation_assemble_node.py`), `post_process_node.py`
   (`ResponseValidateNode`) — all rtl-declared config-free `execute(self, state)`, S-4 emit each.
2. `src/services/service.py` — `OtelGenAIKB` (seeded OTel GenAI semantic-conventions passages:
   spans / token & duration metrics / content events / SDK setup / embeddings / error), attribute
   table with requirement levels, placeholder-only snippet templates, credential redaction.
3. `src/utils/audit.py` — S-4 `emit_trace_event` shim (platform logger + stderr fallback).
4. `src/graph/graph.py` — register_nodes + `OpenTelemetryGenAISemanticConventionsInstrumentationAgent = Graph`
   alias + `__init__` export.
5. `config/agent.yaml` — id/category/class wiring (`gate-cat-consistency`).
6. `tests/` — unit (per sub-node), integration (composed pipeline incl. degraded + 0-hit +
   real `Graph().invoke()` injection/oversize paths), PB adjustments.
7. `docs/03_test_spec.md` — TC/PB matrix (incl. TC-05 per-node emit + real-invoke injection/oversize
   error_code assertion + S-5 no-credential-in-output negative test).
8. `docs/07_operation_guide.md` (at STG) — KB curation note (change-controlled via engineer MR) +
   attribute-table maintenance.
