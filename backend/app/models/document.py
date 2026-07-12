from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.documents.entities import DocumentStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_chunks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    images_extracted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False),
        default=DocumentStatus.PROCESSING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user = relationship("User", back_populates="documents")
    text_chunks = relationship("TextChunk", back_populates="document", cascade="all, delete-orphan")
    images = relationship("DocumentImage", back_populates="document", cascade="all, delete-orphan")


class TextChunk(Base):
    __tablename__ = "text_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index", name="uq_text_chunk_document_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document = relationship("Document", back_populates="text_chunks")


class DocumentImage(Base):
    __tablename__ = "document_images"
    __table_args__ = (UniqueConstraint("document_id", "content_hash", name="uq_document_image_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    nearby_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document = relationship("Document", back_populates="images")
