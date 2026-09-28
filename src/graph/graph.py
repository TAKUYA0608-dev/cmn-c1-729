"""CMN-C1-729 — outer graph (Cat 1 composite).

L1 direct inheritance from AgentBaseGraph (fixed 5-slot pipeline). The `main`
slot is a single composite FunctionNode (MainNode) that runs the 4 instrumentation
capability sub-steps in order — this is Cat 1 composition (FunctionNode-in-main),
not a Cat 2 GraphNode-in-main workflow.
"""

from typing import Any

from framework.graph.agent_base_graph import AgentBaseGraph
from src.nodes.main_node import MainNode
from src.nodes.post_process_node import ResponseValidateNode
from src.nodes.pre_process_node import QueryNormalizeNode
from src.schemas.state import State


class Graph(AgentBaseGraph):
    """Fixed-pipeline graph."""

    @property
    def name(self) -> str:
        return "OpenTelemetryGenAISemanticConventionsInstrumentationAgent"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        # super() injects "initialize" and "finalize" slots automatically.
        super().register_nodes()  # injects InitializeNode + FinalizeNode

        # Domain pipeline slots (required — fill all three):
        self._nodes["pre_process"] = QueryNormalizeNode()
        self._nodes["main"] = MainNode()
        self._nodes["post_process"] = ResponseValidateNode()

    def get_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Framework default, plus the guarantee that a success is never empty.

        The Marketplace runner rejects a successful invocation whose output is
        missing — verified on a deployed Pod — and a degraded run
        (SUCCESS + error_code) produces no artefact for the framework default
        to surface. Report the degradation instead: this states what happened,
        it does not invent an answer.

        Only on SUCCESS. A request refused by the framework's S-2 gate (status
        ERROR) must keep publishing nothing — answering a hostile input with a
        notice would undo the refusal, and the runner treats a non-success
        invocation as a failure regardless, so there is nothing to rescue.
        """
        out: dict[str, Any] = super().get_output(state)
        if not out.get("output") and str(state.get("status", "")).lower().endswith("success"):
            code = state.get("error_code") or "NO_CONTENT"
            out["output"] = (
                "This request could not be completed "
                f"(error_code={code}). No content was produced; "
                "see error_code and error_log for the degradation cause."
            )
        return out


# AgentRegistry / config/agent.yaml `class:` resolution requires a module-level alias.
OpenTelemetryGenAISemanticConventionsInstrumentationAgent = Graph
