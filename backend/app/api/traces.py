from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.infrastructure.conversations import build_conversation_service
from app.models.user import User
from app.schemas.traces import ConversationTraceRead

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", response_model=list[ConversationTraceRead])
def list_traces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationTraceRead]:
    service = build_conversation_service(db)
    try:
        conversations = service.list_for_admin(is_admin=current_user.is_admin)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")
    return [ConversationTraceRead.model_validate(conversation) for conversation in conversations]


@router.get("/{conversation_id}", response_model=ConversationTraceRead)
def get_trace(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationTraceRead:
    conversation = build_conversation_service(db).get_visible(
        user_id=current_user.id,
        is_admin=current_user.is_admin,
        conversation_id=conversation_id,
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found.")
    return ConversationTraceRead.model_validate(conversation)
