"""CMN-C1-729 — deterministic domain services (no framework imports).

OtelGenAIKB: a seeded knowledge base of the OpenTelemetry **GenAI semantic
conventions** — the ``gen_ai.*`` span attributes, the token-usage / operation-
duration metric instruments, the opt-in content events/logs, the SDK
instrumentation setup, and the error conventions.

Retrieval is fully deterministic (keyword/tag scoring — BM25-lite) and auditable;
there is NO LLM in this template (config declares no model, pyproject pins no LLM
dependency, and no model call exists in src/). The agent answers *how to
instrument* an app against the conventions.

S-5: setup snippets are assembled from KB templates with PLACEHOLDERS only — a
real credential (e.g. an OTLP exporter token) never appears in source, state, or
output. Credential-shaped detection patterns are assembled by string
concatenation so no credential-shaped literal is committed.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# ── seeded OTel GenAI semantic-conventions KB ────────────────────────────────
# Each record: {doc_ref, area, signal, source, tags, attributes, text, snippet}
#   area  ∈ {spans, metrics, events, setup}
#   signal∈ {span, metric, log, setup}
#   attributes: [{name, type, requirement_level}]  (requirement_level per OTel spec)
KB: list[dict[str, Any]] = [
    {
        "doc_ref": "GENAI-SPAN-CORE-001",
        "area": "spans",
        "signal": "span",
        "source": "OTel Semantic Conventions — GenAI Spans",
        "tags": [
            "span",
            "trace",
            "tracing",
            "chat",
            "attribute",
            "attributes",
            "gen_ai.system",
            "gen_ai.operation.name",
            "gen_ai.request.model",
            "gen_ai.response.model",
        ],
        "attributes": [
            {"name": "gen_ai.operation.name", "type": "string", "requirement_level": "Required"},
            {"name": "gen_ai.system", "type": "string", "requirement_level": "Required"},
            {"name": "gen_ai.request.model", "type": "string", "requirement_level": "Required"},
            {"name": "gen_ai.response.model", "type": "string", "requirement_level": "Recommended"},
        ],
        "text": (
            "A GenAI client span SHOULD be named `{gen_ai.operation.name} {gen_ai.request.model}` "
            "(e.g. `chat gpt-4o`), use span kind CLIENT, and set gen_ai.system, gen_ai.operation.name "
            "and gen_ai.request.model; gen_ai.response.model is recommended once the response is known."
        ),
        "snippet": (
            "from opentelemetry import trace\n"
            'tracer = trace.get_tracer("genai.instrumentation")\n'
            'with tracer.start_as_current_span(f"chat {model}", kind=trace.SpanKind.CLIENT) as span:\n'
            '    span.set_attribute("gen_ai.system", "openai")\n'
            '    span.set_attribute("gen_ai.operation.name", "chat")\n'
            '    span.set_attribute("gen_ai.request.model", model)'
        ),
    },
    {
        "doc_ref": "GENAI-TOKEN-USAGE-002",
        "area": "metrics",
        "signal": "metric",
        "source": "OTel Semantic Conventions — GenAI Metrics",
        "tags": [
            "token",
            "tokens",
            "usage",
            "cost",
            "metric",
            "histogram",
            "gen_ai.usage.input_tokens",
            "gen_ai.usage.output_tokens",
            "gen_ai.client.token.usage",
        ],
        "attributes": [
            {"name": "gen_ai.usage.input_tokens", "type": "int", "requirement_level": "Recommended"},
            {"name": "gen_ai.usage.output_tokens", "type": "int", "requirement_level": "Recommended"},
            {"name": "gen_ai.client.token.usage", "type": "metric:histogram", "requirement_level": "Recommended"},
        ],
        "text": (
            "Token usage is captured both as span attributes (gen_ai.usage.input_tokens / "
            "gen_ai.usage.output_tokens) and as the histogram metric `gen_ai.client.token.usage` "
            "(unit `{token}`), split by gen_ai.token.type = input|output."
        ),
        "snippet": (
            'meter = metrics.get_meter("genai.instrumentation")\n'
            'token_usage = meter.create_histogram("gen_ai.client.token.usage", unit="{token}")\n'
            'token_usage.record(input_tokens, {"gen_ai.token.type": "input", "gen_ai.system": "openai"})\n'
            'token_usage.record(output_tokens, {"gen_ai.token.type": "output", "gen_ai.system": "openai"})'
        ),
    },
    {
        "doc_ref": "GENAI-OP-DURATION-003",
        "area": "metrics",
        "signal": "metric",
        "source": "OTel Semantic Conventions — GenAI Metrics",
        "tags": [
            "duration",
            "latency",
            "metric",
            "histogram",
            "performance",
            "seconds",
            "gen_ai.client.operation.duration",
        ],
        "attributes": [
            {
                "name": "gen_ai.client.operation.duration",
                "type": "metric:histogram",
                "requirement_level": "Recommended",
            },
        ],
        "text": (
            "Operation latency is recorded with the histogram metric "
            "`gen_ai.client.operation.duration` (unit `s`), carrying gen_ai.system, "
            "gen_ai.operation.name, gen_ai.request.model, and error.type on failure."
        ),
        "snippet": (
            'op_duration = meter.create_histogram("gen_ai.client.operation.duration", unit="s")\n'
            'op_duration.record(elapsed_s, {"gen_ai.system": "openai", '
            '"gen_ai.operation.name": "chat", "gen_ai.request.model": model})'
        ),
    },
    {
        "doc_ref": "GENAI-CONTENT-EVENTS-004",
        "area": "events",
        "signal": "log",
        "source": "OTel Semantic Conventions — GenAI Events",
        "tags": [
            "event",
            "events",
            "log",
            "logs",
            "prompt",
            "completion",
            "message",
            "content",
            "privacy",
            "opt-in",
            "gen_ai.content.prompt",
            "gen_ai.content.completion",
        ],
        "attributes": [
            {"name": "gen_ai.content.prompt", "type": "string", "requirement_level": "Opt-In"},
            {"name": "gen_ai.content.completion", "type": "string", "requirement_level": "Opt-In"},
        ],
        "text": (
            "Capturing prompt/completion content is OPT-IN and disabled by default for privacy. "
            "When enabled (OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true), content is "
            "emitted via events/logs as gen_ai.content.prompt and gen_ai.content.completion."
        ),
        "snippet": (
            "# Content capture is OPT-IN (privacy): enabled via environment, not hardcoded.\n"
            "# export OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true\n"
            'logger.emit(LogRecord(body=prompt, attributes={"event.name": "gen_ai.content.prompt"}))'
        ),
    },
    {
        "doc_ref": "GENAI-SDK-SETUP-005",
        "area": "setup",
        "signal": "setup",
        "source": "OTel Semantic Conventions — GenAI Instrumentation Setup",
        "tags": [
            "setup",
            "install",
            "instrument",
            "instrumentation",
            "sdk",
            "tracerprovider",
            "otlp",
            "exporter",
            "endpoint",
            "openai",
            "langchain",
            "auto-instrumentation",
        ],
        "attributes": [],
        "text": (
            "Instrument a GenAI app with the OTel SDK plus an instrumentation library "
            "(e.g. opentelemetry-instrumentation-openai-v2): configure a TracerProvider and an "
            "OTLP exporter endpoint, then the library emits gen_ai.* spans/metrics automatically. "
            "Never hardcode the exporter credential — pass it via environment/headers as a placeholder."
        ),
        "snippet": (
            "from opentelemetry.sdk.trace import TracerProvider\n"
            "from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter\n"
            "from opentelemetry.sdk.trace.export import BatchSpanProcessor\n"
            "provider = TracerProvider()\n"
            'exporter = OTLPSpanExporter(endpoint="<OTLP_ENDPOINT>", '
            'headers={"Authorization": "Bearer <OTLP_TOKEN>"})\n'
            "provider.add_span_processor(BatchSpanProcessor(exporter))\n"
            "OpenAIInstrumentor().instrument(tracer_provider=provider)"
        ),
    },
    {
        "doc_ref": "GENAI-EMBEDDINGS-006",
        "area": "spans",
        "signal": "span",
        "source": "OTel Semantic Conventions — GenAI Spans",
        "tags": ["embedding", "embeddings", "vector", "span", "gen_ai.operation.name", "gen_ai.request.model"],
        "attributes": [
            {"name": "gen_ai.operation.name", "type": "string", "requirement_level": "Required"},
            {"name": "gen_ai.request.model", "type": "string", "requirement_level": "Required"},
        ],
        "text": (
            "An embeddings operation span sets gen_ai.operation.name=embeddings and "
            "gen_ai.request.model, named `embeddings {gen_ai.request.model}`, span kind CLIENT."
        ),
        "snippet": (
            'with tracer.start_as_current_span(f"embeddings {model}", kind=trace.SpanKind.CLIENT) as span:\n'
            '    span.set_attribute("gen_ai.operation.name", "embeddings")\n'
            '    span.set_attribute("gen_ai.request.model", model)'
        ),
    },
    {
        "doc_ref": "GENAI-ERROR-007",
        "area": "spans",
        "signal": "span",
        "source": "OTel Semantic Conventions — GenAI Spans (Error handling)",
        "tags": ["error", "exception", "failure", "status", "error.type"],
        "attributes": [
            {"name": "error.type", "type": "string", "requirement_level": "Conditionally Required"},
        ],
        "text": (
            "On a failed GenAI operation, set error.type on the span (the fully-qualified "
            "exception class or a short error code) and set the span status to ERROR; the "
            "duration and token metrics also carry error.type so failures are queryable."
        ),
        "snippet": (
            'span.set_attribute("error.type", type(exc).__qualname__)\n'
            "span.set_status(trace.Status(trace.StatusCode.ERROR))"
        ),
    },
]

# valid OTel GenAI signal areas (used for classification + retrieval scoring)
_AREA_KEYWORDS: dict[str, list[str]] = {
    "spans": ["span", "trace", "tracing", "chat", "embedding", "embeddings", "attribute", "attributes", "kind"],
    "metrics": [
        "metric",
        "metrics",
        "histogram",
        "token",
        "tokens",
        "usage",
        "cost",
        "duration",
        "latency",
        "performance",
    ],
    "events": ["event", "events", "log", "logs", "prompt", "completion", "message", "content", "privacy"],
    "setup": [
        "setup",
        "install",
        "instrument",
        "instrumentation",
        "sdk",
        "tracerprovider",
        "otlp",
        "exporter",
        "endpoint",
        "auto-instrumentation",
    ],
}

# credential-shaped patterns assembled by concatenation (S-5: no literal in source)
_SK = "sk-"
_AKIA = "AKIA"
_JWT = "eyJ"
_BEARER = "Bearer "
_CRED_RE = re.compile(
    _SK
    + r"[A-Za-z0-9]{12,}|"
    + _AKIA
    + r"[0-9A-Z]{12,}|"
    + _JWT
    + r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}|"
    + _BEARER
    + r"(?!<)[A-Za-z0-9._-]{16,}"
)
_REDACTED = "<REDACTED:credential>"

_ONLY_PLACEHOLDER = re.compile(r"<[A-Z_]+>")

# ── whitelist-by-construction identifiers + provenance (S-3 defense-in-depth) ──
# A caller-supplied identifier is tokenized UNCONDITIONALLY to `<kind>:<sha8>` — there is
# NO syntactic character-class allowlist, because a bare name (`Alice` / `John.Smith` /
# `TaroYamada`) would otherwise pass such a pattern and leak. The ONLY
# Provenance (citations) is validated against the internal KB — a closed allowlist of the
# actual doc refs + source names, never any caller value (name-shaped or otherwise).
_KB_DOC_REFS = {rec["doc_ref"] for rec in KB}
_KB_SOURCES = {rec["source"] for rec in KB}

# ── S-3 whole-report PII redaction (post-serialize, pre-disclaimer) ──
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63}){0,3}\.[A-Za-z]{2,24}")
_MYNUMBER_RE = re.compile(r"(?<![\d/.])\d{12}(?![\d/.])")  # Japanese My-Number (12 digits)
# XXX-XXXX-XXXX / +CC-XX-XXXX-XXXX style phone (requires the 3-group separated shape to
# avoid over-redacting deterministic doc refs / version-like numbers).
_PHONE_RE = re.compile(r"(?<![\w])(?:\+\d{1,3}[-\s])?\d{2,4}[-\s]\d{2,4}[-\s]\d{3,4}(?![\w])")
_COMPANY_JP_RE = re.compile(
    r"(?:株式会社|有限会社|合同会社)[\wぁ-んァ-ヶ一-龠ー]{1,40}"
    r"|[\wぁ-んァ-ヶ一-龠ー]{1,40}(?:株式会社|有限会社|合同会社)"
)
# EN company suffixes: Inc/Corp/Ltd/LLC/GmbH/PLC/KK — bare "Co" excluded (over-redaction).
_COMPANY_EN_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9&.\-]*(?:\s[A-Z][A-Za-z0-9&.\-]*){0,4}\s" r"(?:Inc|Corp|Corporation|Ltd|LLC|GmbH|PLC|KK)\b\.?"
)
_PII_REDACTED = "<REDACTED:pii>"


class OtelGenAIKB:
    """Deterministic retrieval + attribute/snippet assembly over the seeded KB."""

    @staticmethod
    def opaque_id(kind: str, raw: Any) -> str:
        """Tokenize an identifier UNCONDITIONALLY to a deterministic ``<kind>:<sha8>`` surrogate
        (same input → same token, so referential integrity is kept). There is **no syntactic
        passthrough**: a caller value merely *shaped* like a surrogate (``evil:deadbeef``) is re-hashed,
        never returned unchanged, so it can never forge an internal token. Tokenization happens once at
        S-1 (pre_process). A bare name (`Alice` / `John.Smith` / `TaroYamada`) can never leak."""
        digest = hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:8]
        return f"{kind}:{digest}"

    @staticmethod
    def build_citations(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Whitelist-by-construction citations: a record is cited ONLY if its ``doc_ref`` AND
        ``source`` are exact members of the internal KB allowlists — no syntactic pattern, so a
        name-shaped (`Alice`) or otherwise caller-injected provenance value is dropped. No
        fabrication — an unciteable record is dropped so the S-3 completeness gate can fail closed."""
        out: list[dict[str, Any]] = []
        for r in retrieved:
            doc_ref = str(r.get("doc_ref", ""))
            source = str(r.get("source", ""))
            if doc_ref not in _KB_DOC_REFS:
                continue  # marker must be a real internal KB doc ref
            if source not in _KB_SOURCES:
                continue  # source must be internal KB provenance, never caller-supplied
            out.append({"marker": doc_ref, "source": source, "doc_ref": doc_ref})
        return out

    @staticmethod
    def redact_pii(text: str) -> str:
        """S-3 whole-report redaction: credential + My-Number + email + phone + JP/EN company
        names. Applied to the serialized report AFTER assembly and BEFORE the disclaimer is
        appended (the disclaimer is never redacted). Deterministic action text is preserved."""
        t = _CRED_RE.sub(_REDACTED, text or "")
        t = _MYNUMBER_RE.sub(_PII_REDACTED, t)
        t = _PHONE_RE.sub(_PII_REDACTED, t)
        t = _EMAIL_RE.sub(_PII_REDACTED, t)
        t = _COMPANY_JP_RE.sub(_PII_REDACTED, t)
        t = _COMPANY_EN_RE.sub(_PII_REDACTED, t)
        return t

    @staticmethod
    def classify_signals(query: str) -> list[dict[str, Any]]:
        """Classify the query into OTel GenAI signal areas (deterministic, keyword-based)."""
        q = (query or "").lower()
        out: list[dict[str, Any]] = []
        for area, keywords in _AREA_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score:
                signal = {"spans": "span", "metrics": "metric", "events": "log", "setup": "setup"}[area]
                out.append({"signal": signal, "area": area, "confidence": round(min(0.5 + 0.15 * score, 0.95), 2)})
        out.sort(key=lambda s: -s["confidence"])
        return out

    @staticmethod
    def retrieve(query: str, signals: list[dict[str, Any]], top_k: int = 6) -> list[dict[str, Any]]:
        """Read-only BM25-lite retrieval: +area match, +tag/attribute overlap with the query."""
        q = (query or "").lower()
        areas = {s["area"] for s in signals}
        scored: list[tuple[int, dict[str, Any]]] = []
        for rec in KB:
            score = 0
            if rec["area"] in areas:
                score += 4
            score += sum(1 for t in rec["tags"] if t.lower() in q)
            score += sum(1 for a in rec["attributes"] if a["name"].lower() in q)
            if score:
                scored.append((score, rec))
        scored.sort(key=lambda x: (-x[0], x[1]["doc_ref"]))
        out = []
        for score, rec in scored[:top_k]:
            out.append(
                {
                    "doc_ref": rec["doc_ref"],
                    "area": rec["area"],
                    "signal": rec["signal"],
                    "source": rec["source"],
                    "text": rec["text"],
                    "score": score,
                }
            )
        return out

    @staticmethod
    def attribute_map(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fold the retrieved passages into concrete gen_ai.* attributes / instruments."""
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in retrieved:
            rec = next((k for k in KB if k["doc_ref"] == r["doc_ref"]), None)
            if not rec:
                continue
            for a in rec["attributes"]:
                if a["name"] in seen:
                    continue
                seen.add(a["name"])
                out.append(
                    {
                        "attribute": a["name"],
                        "type": a["type"],
                        "requirement_level": a["requirement_level"],
                        "doc_ref": rec["doc_ref"],
                    }
                )
        return out

    @staticmethod
    def instrumentation_snippets(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Assemble snippets from KB templates — placeholders only (S-5)."""
        out = []
        for r in retrieved:
            rec = next((k for k in KB if k["doc_ref"] == r["doc_ref"]), None)
            if not rec or not rec.get("snippet"):
                continue
            out.append({"lang": "python", "snippet": OtelGenAIKB.redact(rec["snippet"]), "source_doc": rec["doc_ref"]})
        return out

    @staticmethod
    def redact(text: str) -> str:
        """S-5: replace any real credential-shaped token with a placeholder marker."""
        return _CRED_RE.sub(_REDACTED, text or "")


def snippet_is_placeholder_only(snippet: str) -> bool:
    """True if the snippet contains no real credential-shaped token (S-5 self-check)."""
    return not _CRED_RE.search(snippet or "")
