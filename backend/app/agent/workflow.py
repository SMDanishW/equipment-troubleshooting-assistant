from dataclasses import dataclass
from typing import Any, Callable

from app.agent.agents.cross_check import run as cross_check_node
from app.agent.agents.diagnosis import run as diagnosis_node
from app.agent.agents.final_synthesis import run as final_synthesis_node
from app.agent.agents.guardrails import run as guardrails_node
from app.agent.agents.query_understanding import run as query_understanding_node
from app.agent.agents.retrieval import run as retrieval_node
from app.agent.agents.troubleshooting import run as troubleshooting_steps_node

AgentNode = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class AgentStep:
    key: str
    graph_node: str
    display_name: str
    handler: AgentNode


WORKFLOW_STEPS = (
    AgentStep("query_understanding", "query_understanding_agent", "Query Understanding Agent", query_understanding_node),
    AgentStep("retrieval", "retrieval_agent", "Retrieval Agent", retrieval_node),
    AgentStep("diagnosis", "diagnosis_agent", "Diagnosis Agent", diagnosis_node),
    AgentStep("troubleshooting_steps", "troubleshooting_steps_agent", "Troubleshooting Steps Agent", troubleshooting_steps_node),
    AgentStep("guardrails", "guardrails_agent", "Guardrails Agent", guardrails_node),
    AgentStep("cross_check", "cross_check_agent", "Cross-Check Agent", cross_check_node),
    AgentStep("final_synthesis", "final_synthesis_agent", "Final Synthesis Agent", final_synthesis_node),
)

STEPS_BY_KEY = {step.key: step for step in WORKFLOW_STEPS}
REVISION_STEP_KEYS = ("troubleshooting_steps", "guardrails", "cross_check")


def needs_revision(state: dict[str, Any], max_revision_loops: int) -> bool:
    cross_check = state.get("cross_check", {})
    return not cross_check.get("is_grounded", False) and state.get("revision_count", 0) < max_revision_loops
