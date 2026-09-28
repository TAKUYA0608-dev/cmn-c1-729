"""CMN-C1-729 — Agent state (OpenTelemetry GenAI Semantic Conventions Instrumentation Q&A).

ADR-005: State is a flat TypedDict — never a validation/BaseModel instance.
LangGraph checkpoints use msgpack serialization; such model objects cause
silent corruption. Extend AgentState with agent-specific fields only.
Complex fields are stored as JSON strings (``NotRequired[str]`` + ``# JSON:``)
for msgpack safety; nodes ``json.dumps`` on write / ``json.loads`` on read.

S-5 / State Safety: no credentials, secrets, PII, or model weights in State.
The agent answers *how to instrument* an app against the OTel GenAI semantic
conventions — it never emits raw credentials; setup snippets are retrieval-grounded
and use placeholders only (S-3/S-5).

All agent-specific fields are NotRequired (populated progressively; absent at
empty-start invoke — only user_input is caller-provided).
"""

from __future__ import annotations


from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Agent state for the OTel GenAI instrumentation Q&A workflow."""

    # ── pre_process (S-1 validated request) ─────────────────────────────────
    validated_query: str  # NFKC-normalised, injection-screened instrumentation question
    query_context: str  # JSON: {signal_hint, language_hint, ...} caller context (read-only)

    # ── main composite (4 capability steps) ──────────────────────────────────
    classified_signals: str  # JSON: [{signal, area, confidence}] — SignalClassify
    retrieved_conventions: (
        str  # JSON: [{doc_ref, area, signal, source, text, score}] — ConventionRetrieve (OTel GenAI semconv KB)
    )
    retrieval_hit_count: int  # total KB records retrieved (0 → out-of-scope safe answer)
    attribute_mappings: str  # JSON: [{attribute, type, requirement_level, doc_ref}] — AttributeMap
    instrumentation_snippets: str  # JSON: [{lang, snippet, source_doc}] — retrieval-grounded, placeholders only
    instrumentation_answer: str  # assembled cited answer (every claim ends with an inline [<doc_ref>])
    citations: str  # JSON: [{marker, source, doc_ref}]

    # ── post_process (S-3 gate + S-4 audit) ──────────────────────────────────
    disclaimer: str  # "advisory guidance, verify against the current OTel GenAI semconv spec"
    formatted_output: str  # JSON: final response envelope (answer + attributes + citations + snippets)
    audit_logged: bool  # True once the terminal audit event is emitted

    # ── degraded-path signalling (SUCCESS + error_code, never status=ERROR) ──
    # INPUT_EMPTY | INPUT_TOO_LONG | INJECTION_REJECTED (pre_process) |
    # CITATION_INCOMPLETE (post_process S-3 fail-closed → needs_review)
    error_code: str
    error_message: str  # operator-facing detail (no credentials)
