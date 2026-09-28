# Test Specification — CMN-C1-729

> Stage ④ artifact. Coverage target 80%+. Measured: **98%** on the domain code
> (40 passed, 2 skipped) with `--cov=src` (server.py HTTP adapter + examples/ omitted —
> not template logic, exercised at STG). Determinism: no LLM — retrieval, attribute
> mapping and snippet assembly are pure Python (keyword/tag scoring + KB composition).

## 1. Unit Tests (tests/unit/)

| TC | Target | Assertion |
|---|---|---|
| U-01 | QueryNormalize trust | required_trust_level == VERIFIED_EXTERNAL (TC-08) |
| U-02 | Empty → degraded | INPUT_EMPTY + **status=SUCCESS** (never ERROR) |
| U-03 | Oversize → degraded | INPUT_TOO_LONG + status=SUCCESS |
| U-04 | **Injection → degraded + body discarded** | INJECTION_REJECTED + status=SUCCESS; `validated_query` never set (injection body not processed) |
| U-05 | Normalization | NFKC + whitespace collapse |
| U-06 | Grounded pipeline (span) | spans area classified, gen_ai.system in cited answer |
| U-07 | Attribute map requirement level | gen_ai.request.model mapped as `Required` |
| U-08 | Token metric area | metrics area classified for `gen_ai.client.token.usage` query |
| U-09 | **S-5 snippet placeholder-only** | every setup snippet has no real credential + uses `<OTLP_TOKEN>` placeholder |
| U-10 | **0-hit out-of-scope** | retrieval_hit_count=0, no error_code, in-scope safe answer, empty citations |
| U-11 | PostProcess rejected path | audit_logged=True + error_code in envelope + status=SUCCESS |
| U-12 | PostProcess grounded | validation=passed + citations + disclaimer |
| U-13 | **S-5 redaction negative test** | a leaked real credential in a snippet is redacted out of the envelope |
| U-14 | Out-of-scope status | validation_status="out_of_scope" |
| U-15 | **S-3 citation-completeness FAIL-CLOSED** | hit>0 + no valid citations → validation=**needs_review**, error_code=CITATION_INCOMPLETE, **empty body**, audit_logged (not a flagged pass) |
| U-16 | **TC-05 per-node emit** | monkeypatch emit_trace_event; every node's execute() emits ≥1 event (6 nodes) |
| U-17 | **Skip-path emit** | every sub-node skip guard emits a count-only event before `return {}` (4 sub-nodes) |
| U-18/19/20 | Services | redact / multi-area classify / no-area for unrelated query |
| U-21..25 | Composite MainNode | full pipeline / self-skip / status=SUCCESS.value / config-free `execute(self, state)` signature |
| U-26 | **opaque-id tokenize** | safe id passes allowlist; PII-laden id → deterministic `<kind>:<sha8>` |
| U-27 | **S-3 whole-report PII redactor** | credential / My-Number / email / phone / JP+EN company all redacted |
| U-28 | Redactor no over-redaction | doc refs / attribute names / requirement levels preserved verbatim |
| U-29 | **build_citations whitelist** | invalid opaque doc_ref OR non-KB source dropped (fail-closed feed) |

## 2. Integration Tests (tests/integration/) — real `Graph().invoke()`

| TC | Scenario | Assertion |
|---|---|---|
| I-01 | Grounded (span attributes) | validation=passed, citations, attribute_mappings |
| I-02 | **0-hit out-of-scope** | validation=out_of_scope, empty citations |
| I-03 | **S-5 never emits real credential** | fake credential never appears in output envelope |
| I-04 | node_history slots | Initialize→QueryNormalize→Main→ResponseValidate→Finalize |
| I-05 | **Injection via real invoke** | degraded SUCCESS; envelope validation=rejected + error_code=INJECTION_REJECTED; **ResponseValidateNode in node_history** (post ran); injection body absent from output; **error_code surfaced in the terminal S-4 audit event** (monkeypatched emit capture) |
| I-06 | **Oversize via real invoke** | degraded SUCCESS; error_code=INPUT_TOO_LONG; error_code in terminal S-4 audit |
| I-07 | **Empty via real invoke** | degraded SUCCESS; error_code=INPUT_EMPTY; error_code in terminal S-4 audit |
| I-08 | **Citation fail-closed via real invoke** | grounded answer w/o citations → validation=needs_review + error_code=CITATION_INCOMPLETE + empty body; ResponseValidateNode in node_history; `citation_blocked` S-4 event carries error_code |
| I-09 | **PII whitelist via real invoke** | PII in user_input + arbitrary caller fields (account_id / note / my_number) → none reach the output envelope; grounded answer still validation=passed |

## 3. Proof-of-Boundary (tests/proof_of_boundary/) + framework compliance

| PB / TC | Test | Note |
|---|---|---|
| PB-2/PB-5 | test_state_safety.py | scaffold-shipped; state primitives only |
| PB-4 | test_import_isolation.py | scaffold-shipped; no Level-0 (`agenticstar`) imports |
| PB-6 | test_pb_invoke_order.py | scaffold discovery-based order check; env-skips on the local SDK stub, runs on the real SDK in CI |
| PB-7 | test_pb7_hitl_interrupt_propagation.py | conditional stub (hitl disabled → SKIPPED); untouched |
| TC-06/07 | test_framework_compliance_tc06_tc07.py | S-2/S-3 sealed gates cannot be overridden (only `_extra_*`); validated against the real SDK in CI |

## 4. TC-05 (S-4 per-node emit)

Every node's execute() path emits ≥1 domain event: query_normalized / query_rejected,
signals_classified, conventions_retrieved, attributes_mapped, instrumentation_answer_built,
instrumentation_answer_assembled (composite), citation_blocked / response_rejected (degraded),
agent_invoke_complete (terminal — fires on the degraded path too and surfaces `error_code`).
**Skip guards emit a count-only event before `return {}`** (no silent empty return). Verified by
U-16 / U-17 and the invoke-path S-4 capture in I-05..08.

## 5. Local vs CI

The core domain suite (unit + integration + import-isolation + state-safety) runs green on
the local SDK stub: **40 passed, 2 skipped, 98% cov**. `test_pb_invoke_order.py` and
`test_framework_compliance_tc06_tc07.py` require the real SDK's runtime gate / `emit_trace_event`
enforcement and are green in CI (which installs `agenticstar-agentcore`), env-different on
local SDK-stub — same behaviour as the released reference templates.
