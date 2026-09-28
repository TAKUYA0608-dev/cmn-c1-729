"""CMN-C1-729 — main composite node (Cat 1).

Composes the 4 capability sub-steps in fixed order:
    SignalClassify → ConventionRetrieve → AttributeMap → InstrumentationAssemble

Sub-nodes are instantiated in __init__ and called via sub.execute(state) directly
(single S-2/S-3/S-4 boundary). Each self-skips on
error_code, so an injection/oversize rejection from pre_process short-circuits the
composite while post_process still audits.
"""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.attribute_map_node import AttributeMapNode
from src.nodes.convention_retrieve_node import ConventionRetrieveNode
from src.nodes.instrumentation_assemble_node import InstrumentationAssembleNode
from src.nodes.signal_classify_node import SignalClassifyNode

try:  # S-4 canonical platform logger (PB-1)
    from shared.utils.audit_logger import emit_trace_event
except ImportError:  # local test env without the platform
    from src.utils.audit import emit_trace_event


class MainNode(FunctionNode):
    """main slot — orchestrates the instrumentation capability steps → cited answer."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self) -> None:
        super().__init__()
        self._seq: list[FunctionNode] = [
            SignalClassifyNode(),
            ConventionRetrieveNode(),
            AttributeMapNode(),
            InstrumentationAssembleNode(),
        ]

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code"):
            emit_trace_event(
                "instrumentation_answer_assembled", {"hit_count": 0, "grounded": False, "skipped": True}, state
            )
            return {}
        working = dict(state)
        deltas: dict[str, Any] = {}
        for node in self._seq:
            updates = node.execute(working) or {}
            working.update(updates)
            deltas.update(updates)

        emit_trace_event(
            "instrumentation_answer_assembled",
            {"hit_count": deltas.get("retrieval_hit_count", 0), "grounded": bool(deltas.get("retrieval_hit_count", 0))},
            state,
        )
        deltas["status"] = AgentStatus.SUCCESS.value
        return deltas
