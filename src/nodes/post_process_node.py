"""CMN-C1-729 — post_process slot: ResponseValidateNode.

S-3 citation gate (fail-closed) + S-5/S-3 redaction + S-4 audit.

Responsibilities:
  1. S-3 citation-completeness — a grounded answer (retrieval_hit_count > 0) must be
     fully cited. If any claim is uncited, the deliverable is **blocked**: a degraded
     `needs_review` envelope (empty body, error_code=CITATION_INCOMPLETE) is returned.
  2. S-5 credential redaction — never emit a real credential from a setup snippet.
  3. S-3 whole-report PII redaction — credential + My-Number + email + phone + JP/EN
     company names, applied to the serialized report BEFORE the disclaimer is appended
     (whitelist-by-construction envelope: only allowed safe fields ever reach the output).
  4. Mandatory disclaimer (advisory guidance; human owns the instrumentation change).
  5. S-4 terminal agent_invoke_complete audit — ALWAYS fires (incl. degraded paths),
     surfacing error_code so injection/oversize/citation-block is auditable end-to-end.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.services.service import OtelGenAIKB, snippet_is_placeholder_only

try:  # S-4 canonical platform logger (PB-1)
    from shared.utils.audit_logger import emit_trace_event
except ImportError:  # local test env without the platform
    from src.utils.audit import emit_trace_event

_DISCLAIMER = (
    "\n\n---\nAdvisory instrumentation guidance grounded in the OpenTelemetry GenAI "
    "semantic-conventions KB; verify against the current OTel GenAI semconv spec and never "
    "hardcode a real exporter credential. The engineer owns the final instrumentation change."
)


class ResponseValidateNode(FunctionNode):
    """S-3 citation gate (fail-closed) + S-5/S-3 redaction + disclaimer + S-4 audit."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # ── degraded / rejected path (injection/oversize/empty): always audit ──
        if state.get("error_code"):
            return self._degraded(state, state["error_code"], "rejected", "response_rejected")

        hit = state.get("retrieval_hit_count", 0) or 0
        grounded = hit > 0
        # Authoritative, whitelist-by-construction citations (validated opaque provenance only).
        citations = OtelGenAIKB.build_citations(json.loads(state.get("retrieved_conventions") or "[]"))

        # ── S-3 citation-completeness gate (FAIL-CLOSED) ──
        # A grounded answer must be fully cited; an uncited claim blocks the deliverable.
        if grounded and len(citations) < hit:
            return self._degraded(state, "CITATION_INCOMPLETE", "needs_review", "citation_blocked")

        # S-5: every setup snippet must be placeholder-only.
        snippets = json.loads(state.get("instrumentation_snippets") or "[]")
        for s in snippets:
            if not snippet_is_placeholder_only(s.get("snippet", "")):
                s["snippet"] = OtelGenAIKB.redact(s["snippet"])

        answer_body = OtelGenAIKB.redact(state.get("instrumentation_answer") or "")
        validation_status = "passed" if grounded else "out_of_scope"

        # Whitelist-by-construction envelope: ONLY these allowed, KB-derived fields reach the
        # output. No arbitrary caller field is copied here.
        envelope: dict[str, Any] = {
            "answer": answer_body,
            "validation_status": validation_status,
            "citations": citations,
            "attribute_mappings": json.loads(state.get("attribute_mappings") or "[]"),
            "instrumentation_snippets": snippets,
        }
        # S-3 whole-report PII redaction: serialize → redact → re-parse (disclaimer added after).
        serialized = OtelGenAIKB.redact_pii(json.dumps(envelope, ensure_ascii=False))
        env = json.loads(serialized)
        env["answer"] = env["answer"] + _DISCLAIMER  # disclaimer appended after redaction

        emit_trace_event(
            "agent_invoke_complete",
            {"validation_status": validation_status, "citation_count": len(citations), "disclaimer_present": True},
            state,
        )
        return {
            "formatted_output": json.dumps(env, ensure_ascii=False),
            "disclaimer": _DISCLAIMER.strip(),
            "audit_logged": True,
            "status": AgentStatus.SUCCESS.value,
        }

    @staticmethod
    def _degraded(state: dict[str, Any], code: str, status_label: str, event: str) -> dict[str, Any]:
        """Degraded terminal envelope (rejected / needs_review): empty body, error_code,
        disclaimer preserved, S-4 audit always fires (surfacing error_code)."""
        # domain event (e.g. citation_blocked / response_rejected) + terminal audit, both carry error_code.
        emit_trace_event(event, {"validation_status": status_label, "error_code": code}, state)
        emit_trace_event("agent_invoke_complete", {"validation_status": status_label, "error_code": code}, state)
        return {
            "formatted_output": json.dumps(
                {
                    "answer": "",
                    "validation_status": status_label,
                    "error_code": code,
                    "disclaimer": _DISCLAIMER.strip(),
                },
                ensure_ascii=False,
            ),
            "disclaimer": _DISCLAIMER.strip(),
            "audit_logged": True,
            "status": AgentStatus.SUCCESS.value,
        }
