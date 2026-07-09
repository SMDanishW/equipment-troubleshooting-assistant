from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models.trace import Conversation
from app.services.docker_logs import DOCKER_LOG_SERVICES, get_container_logs
from app.models.user import User
from app.schemas.admin import AdminConversationRead, AdminUserOverviewRead
from app.schemas.documents import DocumentRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/docker/services")
def list_docker_log_services(current_user: User = Depends(get_current_user)) -> dict[str, list[str]]:
    require_admin(current_user)
    return {"services": list(DOCKER_LOG_SERVICES.keys())}


@router.get("/users/overview", response_model=list[AdminUserOverviewRead])
def list_user_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AdminUserOverviewRead]:
    require_admin(current_user)
    statement = (
        select(User)
        .options(selectinload(User.documents), selectinload(User.conversations))
        .order_by(User.created_at.desc())
    )
    users = db.execute(statement).scalars().all()
    return [_build_user_overview(user) for user in users]


@router.get("/docker/logs")
def docker_logs(
    service: str = Query(default="backend"),
    tail: int = Query(default=200, ge=20, le=1000),
    current_user: User = Depends(get_current_user),
) -> dict[str, str | int]:
    require_admin(current_user)
    if service not in DOCKER_LOG_SERVICES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown Docker service.")
    try:
        logs = get_container_logs(service, tail)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"service": service, "tail": tail, "logs": logs}


def require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")


def _build_user_overview(user: User) -> AdminUserOverviewRead:
    documents = sorted(user.documents, key=lambda document: document.created_at, reverse=True)
    conversations = sorted(user.conversations, key=lambda conversation: conversation.created_at, reverse=True)
    return AdminUserOverviewRead(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        documents_count=len(documents),
        conversations_count=len(conversations),
        documents=[DocumentRead.model_validate(document) for document in documents],
        conversations=[_conversation_summary(conversation) for conversation in conversations],
    )


def _conversation_summary(conversation: Conversation) -> AdminConversationRead:
    return AdminConversationRead.model_validate(conversation)
