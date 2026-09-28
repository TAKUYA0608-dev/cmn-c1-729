# CMN-C1-729 — Unit tests: composite MainNode

import json

from framework.schemas.agent_status import AgentStatus

from src.nodes.main_node import MainNode
from src.nodes.pre_process_node import QueryNormalizeNode


def _validated(q):
    st = {"user_input": q, "input_context": {}, "node_history": [], "error_log": []}
    st.update(QueryNormalizeNode().execute(st))
    return st


class TestMainNode:
    def test_trust_level(self):
        assert MainNode().required_trust_level.name == "VERIFIED_EXTERNAL"

    def test_composite_full(self):
        st = _validated("how do I set gen_ai.system and gen_ai.request.model on a chat span")
        out = MainNode().execute(st)
        assert out["status"] == AgentStatus.SUCCESS.value
        assert out["retrieval_hit_count"] > 0
        assert json.loads(out["citations"])
        assert json.loads(out["attribute_mappings"])

    def test_self_skip_on_error(self):
        assert MainNode().execute({"error_code": "INJECTION_REJECTED"}) == {}

    def test_status_is_success_value(self):
        out = MainNode().execute(_validated("gen_ai token usage metric"))
        assert out["status"] == AgentStatus.SUCCESS.value
        assert out["status"] == "success"

    def test_execute_signature_config_free(self):
        # config-free execute(): execute(self, state) — no config parameter.
        import inspect
        params = list(inspect.signature(MainNode.execute).parameters.keys())
        assert params == ["self", "state"]
