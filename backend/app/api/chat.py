from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent.graph import run_troubleshooting_graph, stream_troubleshooting_graph
from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/test", response_model=ChatResponse)
def chat_test(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    return run_troubleshooting_graph(
        db=db,
        user=current_user,
        question=payload.question,
        equipment_name=payload.equipment_name,
        document_ids=payload.document_ids,
        chat_history=[item.model_dump() for item in payload.chat_history],
    )


@router.post("/stream")
def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    return StreamingResponse(
        stream_troubleshooting_graph(
            db=db,
            user=current_user,
            question=payload.question,
            equipment_name=payload.equipment_name,
            document_ids=payload.document_ids,
            chat_history=[item.model_dump() for item in payload.chat_history],
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
