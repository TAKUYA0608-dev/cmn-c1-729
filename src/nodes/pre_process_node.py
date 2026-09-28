"""CMN-C1-729 — pre_process slot: QueryNormalizeNode (S-1).

Validates + normalizes the NL instrumentation question. Rejections (empty /
oversize / prompt-injection) return **degraded SUCCESS + error_code** (never
status=ERROR) and DISCARD the offending body, so post_process always runs the
S-3 gate + terminal S-4 audit (production framework routes ERROR straight to
finalize, skipping S-3/S-4 — verified on the platform).
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.services.service import OtelGenAIKB

try:  # S-4 canonical platform logger (PB-1)
    from shared.utils.audit_logger import emit_trace_event
except ImportError:  # local test env without the platform
    from src.utils.audit import emit_trace_event

_MAX_LEN = 5_000
_INJECTION = re.compile(
    r"ignore\s+(?:all\s+)?previous\s+instructions|system\s+prompt\s*:|disregard\s+(?:all\s+)?(?:prior|above)",
    re.I,
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# caller `input_context` is projected to an allowlist only — no arbitrary caller field is copied.
_SAFE_SIGNAL_HINTS = {"spans", "metrics", "events", "setup"}


class QueryNormalizeNode(FunctionNode):
    """S-1: validate + normalize the instrumentation question."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code"):
            return {}
        raw = state.get("user_input") or ""
        text = str(raw)
        if not text.strip():
            return self._reject(state, "INPUT_EMPTY", "QueryNormalizeNode: question is empty")
        if len(text) > _MAX_LEN:
            return self._reject(state, "INPUT_TOO_LONG", f"QueryNormalizeNode: exceeds {_MAX_LEN} chars")
        if _INJECTION.search(text):
            # S-1: discard the injection body entirely — never normalize/process it.
            return self._reject(state, "INJECTION_REJECTED", "QueryNormalizeNode: prompt-injection pattern rejected")

        normalized = unicodedata.normalize("NFKC", text)
        normalized = _CONTROL.sub("", normalized).strip()
        normalized = re.sub(r"\s+", " ", normalized)
        # Allowlist projection of caller context — no arbitrary caller field reaches State:
        # signal_hint is constrained to a safe enum, language_hint is passed through the
        # opaque-id tokenizer (free text / PII is deterministically tokenized).
        ic = state.get("input_context") or {}
        query_context: dict[str, str] = {}
        signal_hint = ic.get("signal_hint")
        if signal_hint in _SAFE_SIGNAL_HINTS:
            query_context["signal_hint"] = signal_hint
        if ic.get("language_hint"):
            query_context["language_hint"] = OtelGenAIKB.opaque_id("lang", ic.get("language_hint"))
        emit_trace_event("query_normalized", {"length": len(normalized)}, state)
        return {
            "validated_query": normalized,
            "query_context": json.dumps(query_context, ensure_ascii=False),
            "user_input": "",  # earliest-possible minimization: raw body not retained past S-1
            "status": AgentStatus.SUCCESS.value,
        }

    @staticmethod
    def _reject(state: dict[str, Any], code: str, message: str) -> dict[str, Any]:
        emit_trace_event("query_rejected", {"error_code": code}, state)
        # discard the raw body (injection/oversize/empty) from State — never processed/retained.
        return {"error_code": code, "error_message": message, "user_input": "", "status": AgentStatus.SUCCESS.value}
