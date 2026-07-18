from app.agent.graph import build_troubleshooting_graph
from app.agent.workflow import WORKFLOW_STEPS, needs_revision


def test_graph_compiles_with_node_names_distinct_from_state_keys():
    graph = build_troubleshooting_graph()

    assert graph is not None
    assert all(step.graph_node != step.key for step in WORKFLOW_STEPS)


def test_revision_is_bounded_and_only_runs_for_ungrounded_results():
    assert needs_revision({"cross_check": {"is_grounded": False}, "revision_count": 0}, 1)
    assert not needs_revision({"cross_check": {"is_grounded": False}, "revision_count": 1}, 1)
    assert not needs_revision({"cross_check": {"is_grounded": True}, "revision_count": 0}, 1)
    assert not needs_revision({"cross_check": {"is_grounded": False}, "revision_count": 0}, 0)
