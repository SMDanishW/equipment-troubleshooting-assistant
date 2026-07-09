from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.crud.traces import get_conversation_by_id, get_conversation_for_user, list_conversations
from app.database import get_db
from app.models.user import User
from app.schemas.traces import ConversationTraceRead

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", response_model=list[ConversationTraceRead])
def list_traces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationTraceRead]:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")
    return [ConversationTraceRead.model_validate(conversation) for conversation in list_conversations(db)]


@router.get("/{conversation_id}", response_model=ConversationTraceRead)
def get_trace(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationTraceRead:
    conversation = (
        get_conversation_by_id(db, conversation_id)
        if current_user.is_admin
        else get_conversation_for_user(db, current_user.id, conversation_id)
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found.")
    return ConversationTraceRead.model_validate(conversation)
