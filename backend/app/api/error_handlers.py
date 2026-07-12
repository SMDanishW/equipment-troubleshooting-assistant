from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.documents.errors import DocumentNotFoundError, DocumentProcessingError
from app.domain.errors import DomainError
from app.ingestion.upload_validation import InvalidPdfUpload, PdfUploadLimitExceeded


def register_domain_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, DocumentNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, DocumentProcessingError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, PdfUploadLimitExceeded):
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    elif isinstance(exc, InvalidPdfUpload):
        status_code = status.HTTP_400_BAD_REQUEST
    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message},
        headers={"X-Error-Code": exc.code},
    )
