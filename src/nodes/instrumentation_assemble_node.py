"""InstrumentationAssembleNode — composite sub-step 4: assemble the cited answer.

Assembles the cited instrumentation_answer + placeholder-only setup snippets from
KB templates. A 0-hit retrieval yields an in-scope "out-of-scope / insufficient
grounding" safe answer (no hallucinated instrumentation advice).
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.services.service import OtelGenAIKB

try:  # S-4 canonical platform logger (PB-1)
    from shared.utils.audit_logger import emit_trace_event
except ImportError:  # local test env without the platform
    from src.utils.audit import emit_trace_event


class InstrumentationAssembleNode(FunctionNode):
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code") or state.get("retrieved_conventions") is None:
            emit_trace_event("instrumentation_answer_built", {"grounded": False, "skipped": True}, state)
            return {}
        retrieved = json.loads(state["retrieved_conventions"])
        mappings = json.loads(state.get("attribute_mappings") or "[]")
        snippets = OtelGenAIKB.instrumentation_snippets(retrieved)

        if not retrieved:
            answer = (
                "This question is outside the current OpenTelemetry GenAI semantic-conventions "
                "knowledge base (spans / token & duration metrics / content events / SDK setup / "
                "embeddings / error conventions). No grounded instrumentation guidance is available "
                "for this request."
            )
            citations: list[dict[str, Any]] = []
        else:
            areas = ", ".join(sorted({r["area"] for r in retrieved}))
            lines = [f"OpenTelemetry GenAI instrumentation guidance ({areas}):"]
            for r in retrieved:
                lines.append(f"- {r['text']} [{r['doc_ref']}]")
            if mappings:
                lines.append("- Attributes / instruments to set:")
                for m in mappings:
                    lines.append(f"    - {m['attribute']} ({m['type']}, {m['requirement_level']}) [{m['doc_ref']}]")
            answer = "\n".join(lines)
            # Single citation authority: validated, whitelist-by-construction provenance only
            # (re-validated in post_process for the S-3 completeness gate).
            citations = OtelGenAIKB.build_citations(retrieved)

        emit_trace_event(
            "instrumentation_answer_built", {"snippet_count": len(snippets), "grounded": bool(retrieved)}, state
        )
        return {
            "instrumentation_snippets": json.dumps(snippets, ensure_ascii=False),
            "instrumentation_answer": OtelGenAIKB.redact(answer),
            "citations": json.dumps(citations, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
