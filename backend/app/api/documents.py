from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.document_deps import get_document_service
from app.api.deps import get_current_user
from app.application.documents.service import DocumentApplicationService
from app.schemas.documents import DocumentDetail, DocumentRead, DocumentUploadResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: Annotated[UploadFile, File()],
    equipment_name: Annotated[str, Form(min_length=1, max_length=255)],
    document_type: Annotated[str, Form(max_length=80)] = "auto",
    current_user: Any = Depends(get_current_user),
    service: DocumentApplicationService = Depends(get_document_service),
) -> DocumentUploadResponse:
    document = service.upload(
        user=current_user,
        upload=file,
        equipment_name=equipment_name,
        document_type=document_type,
    )

    return DocumentUploadResponse.model_validate(document)


@router.get("", response_model=list[DocumentRead])
def list_documents(
    current_user: Any = Depends(get_current_user),
    service: DocumentApplicationService = Depends(get_document_service),
) -> list[DocumentRead]:
    return [DocumentRead.model_validate(document) for document in service.list_for_user(current_user.id)]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str,
    current_user: Any = Depends(get_current_user),
    service: DocumentApplicationService = Depends(get_document_service),
) -> DocumentDetail:
    document = service.get_for_user(current_user.id, document_id)
    return DocumentDetail.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    current_user: Any = Depends(get_current_user),
    service: DocumentApplicationService = Depends(get_document_service),
) -> None:
    service.delete_for_user(current_user.id, document_id)
