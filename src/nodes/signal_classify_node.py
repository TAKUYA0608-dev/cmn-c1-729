"""SignalClassifyNode — composite sub-step 1: classify OTel GenAI signal area(s)."""

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


class SignalClassifyNode(FunctionNode):
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code") or not state.get("validated_query"):
            emit_trace_event("signals_classified", {"count": 0, "skipped": True}, state)
            return {}
        signals = OtelGenAIKB.classify_signals(state["validated_query"])
        emit_trace_event("signals_classified", {"count": len(signals)}, state)
        return {"classified_signals": json.dumps(signals, ensure_ascii=False), "status": AgentStatus.SUCCESS.value}
