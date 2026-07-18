from collections.abc import Iterator
from time import sleep
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agent.state import AgentState
from app.agent.workflow import REVISION_STEP_KEYS, STEPS_BY_KEY, WORKFLOW_STEPS, needs_revision
from app.config import settings
from app.infrastructure.conversations import build_conversation_service
from app.models.user import User
from app.schemas.chat import ChatResponse
from app.streaming.sse import chunk_text, sse_event
from app.traces.trace_logger import TraceLogger


def build_troubleshooting_graph():
    graph = StateGraph(AgentState)
    for step in WORKFLOW_STEPS:
        graph.add_node(step.graph_node, step.handler)
    graph.add_node("prepare_revision", _prepare_revision)

    graph.add_edge(START, STEPS_BY_KEY["query_understanding"].graph_node)
    for current_key, next_key in (
        ("query_understanding", "retrieval"),
        ("retrieval", "diagnosis"),
        ("diagnosis", "troubleshooting_steps"),
        ("troubleshooting_steps", "guardrails"),
        ("guardrails", "cross_check"),
    ):
        graph.add_edge(STEPS_BY_KEY[current_key].graph_node, STEPS_BY_KEY[next_key].graph_node)
    graph.add_conditional_edges(
        STEPS_BY_KEY["cross_check"].graph_node,
        _route_after_cross_check,
        {
            "revise": "prepare_revision",
            "synthesize": STEPS_BY_KEY["final_synthesis"].graph_node,
        },
    )
    graph.add_edge("prepare_revision", STEPS_BY_KEY["troubleshooting_steps"].graph_node)
    graph.add_edge(STEPS_BY_KEY["final_synthesis"].graph_node, END)
    return graph.compile()


def _prepare_revision(state: AgentState) -> dict[str, int]:
    return {"revision_count": state.get("revision_count", 0) + 1}


def _route_after_cross_check(state: AgentState) -> str:
    return "revise" if needs_revision(state, settings.max_revision_loops) else "synthesize"


def run_troubleshooting_graph(
    db: Session,
    user: User,
    question: str,
    equipment_name: str | None = None,
    document_ids: list[str] | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> ChatResponse:
    conversations = build_conversation_service(db)
    conversation = conversations.start(user_id=user.id, question=question, equipment_name=equipment_name)

    trace_logger = TraceLogger(db=db, conversation_id=conversation.id)
    graph = build_troubleshooting_graph()
    state = graph.invoke(
        {
            "db": db,
            "user_id": user.id,
            "question": question,
            "equipment_name": equipment_name,
            "document_ids": document_ids,
            "chat_history": chat_history or [],
            "conversation_id": conversation.id,
            "trace_logger": trace_logger,
            "revision_count": 0,
        }
    )

    conversations.complete(conversation, state["final_answer"])

    return ChatResponse(
        conversation_id=conversation.id,
        answer=state["final_answer"],
        citations=state.get("citations", []),
        images=state.get("images", []),
    )


def stream_troubleshooting_graph(
    db: Session,
    user: User,
    question: str,
    equipment_name: str | None = None,
    document_ids: list[str] | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> Iterator[str]:
    conversations = build_conversation_service(db)
    conversation = conversations.start(user_id=user.id, question=question, equipment_name=equipment_name)

    state: dict[str, Any] = {
        "db": db,
        "user_id": user.id,
        "question": question,
        "equipment_name": equipment_name,
        "document_ids": document_ids,
        "chat_history": chat_history or [],
        "conversation_id": conversation.id,
        "trace_logger": TraceLogger(db=db, conversation_id=conversation.id),
        "revision_count": 0,
    }

    try:
        for step in WORKFLOW_STEPS[:-1]:
            yield from _stream_step(state, step)

        while needs_revision(state, settings.max_revision_loops):
            state["revision_count"] += 1
            for step_key in REVISION_STEP_KEYS:
                yield from _stream_step(state, STEPS_BY_KEY[step_key])

        yield from _stream_step(state, STEPS_BY_KEY["final_synthesis"])

        final_answer = state["final_answer"]
        for token in chunk_text(final_answer, chunk_size=36):
            yield sse_event("token", {"content": token})
            sleep(0.015)
        yield sse_event("citation", {"citations": state.get("citations", [])})
        yield sse_event("image", {"images": state.get("images", [])})

        conversations.complete(conversation, final_answer)
        yield sse_event("done", {"conversation_id": conversation.id})
    except Exception as exc:
        conversations.fail(conversation)
        yield sse_event("error", {"message": str(exc), "conversation_id": conversation.id})


def _stream_step(state: dict[str, Any], step) -> Iterator[str]:
    yield sse_event(
        "agent_update",
        {"agent": step.key, "agent_name": step.display_name, "status": "running"},
    )
    state.update(step.handler(state))
    if step.key == "retrieval":
        yield sse_event(
            "retrieval_update",
            {
                "text_evidence_count": len(state["retrieval"]["text_evidence"]),
                "image_evidence_count": len(state["retrieval"]["image_evidence"]),
            },
        )
    yield sse_event(
        "agent_update",
        {"agent": step.key, "agent_name": step.display_name, "status": "completed"},
    )
