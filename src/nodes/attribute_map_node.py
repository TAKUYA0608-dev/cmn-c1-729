"""AttributeMapNode — composite sub-step 3: map conventions → gen_ai.* attributes.

Deterministic fold of the retrieved passages into concrete gen_ai.* attributes /
metric instruments with their type + requirement_level (Required / Recommended /
Opt-In / Conditionally Required).
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


class AttributeMapNode(FunctionNode):
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code") or state.get("retrieved_conventions") is None:
            emit_trace_event("attributes_mapped", {"count": 0, "skipped": True}, state)
            return {}
        retrieved = json.loads(state["retrieved_conventions"])
        mappings = OtelGenAIKB.attribute_map(retrieved)
        emit_trace_event("attributes_mapped", {"count": len(mappings)}, state)
        return {"attribute_mappings": json.dumps(mappings, ensure_ascii=False), "status": AgentStatus.SUCCESS.value}
