import enum
from datetime import datetime
from typing import List, Optional
from uuid import UUID as PyUuid

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Boolean,
    LargeBinary,
    TIMESTAMP,
    Enum as SQLEnum,
    Index,
    UniqueConstraint,
    text,
    Identity,
)
from sqlalchemy.dialects.postgresql import UUID as pg_uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClientRoleEnum(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class OperationStatusEnum(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class EncryptionKey(Base, TimestampMixin):
    __tablename__ = "encryption_keys"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    symmetric_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    expired_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    api_keys: Mapped[List["ApiKey"]] = relationship(back_populates="encryption_key")

    __table_args__ = (
        Index("idx_encryption_keys_active", "id", postgresql_where=Column("is_active")),
    )

    def __repr__(self) -> str:
        return f"<EncryptionKey(id={self.id}, is_active={self.is_active})>"


class UserClient(Base, TimestampMixin):
    __tablename__ = "user_clients"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[ClientRoleEnum] = mapped_column(
        SQLEnum(ClientRoleEnum, name="client_roles", create_type=False), nullable=False
    )

    api_keys: Mapped[List["ApiKey"]] = relationship(
        back_populates="user_client", cascade="all, delete-orphan"
    )
    documents: Mapped[List["DocumentRegistry"]] = relationship(
        back_populates="user_client"
    )
    knowledge_bases: Mapped[List["KnowledgeBase"]] = relationship(
        back_populates="user_client"
    )

    def __repr__(self) -> str:
        return f"<UserClient(id={self.id}, email='{self.email}', role='{self.role.value}')>"


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_clients.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_id: Mapped[int] = mapped_column(
        ForeignKey("encryption_keys.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_credential: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, unique=True
    )
    key_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    user_client: Mapped["UserClient"] = relationship(back_populates="api_keys")
    encryption_key: Mapped["EncryptionKey"] = relationship(back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, user_id={self.user_id}, key_id={self.key_id})>"


class DocumentRegistry(Base, TimestampMixin):
    __tablename__ = "documents_registry"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_clients.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(100), nullable=False)
    object_key: Mapped[str] = mapped_column(String(150), nullable=False)
    lock_status: Mapped[bool] = mapped_column(Boolean, nullable=False)
    op_status: Mapped[OperationStatusEnum] = mapped_column(
        SQLEnum(OperationStatusEnum, name="operation_status", create_type=False),
        nullable=False,
        server_default=OperationStatusEnum.PENDING.value,
    )

    user_client: Mapped["UserClient"] = relationship(back_populates="documents")
    knowledge_base_associations: Mapped[List["KnowledgeBaseDocument"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "file_name", name="idx_unique_filename"),
        Index("idx_file_registry_user_id", "user_id", "lock_status", "op_status"),
    )

    def __repr__(self) -> str:
        return f"<DocumentRegistry(id={self.id}, file_name='{self.file_name}', user_id={self.user_id})>"


class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_clients.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    user_client: Mapped["UserClient"] = relationship(back_populates="knowledge_bases")
    document_associations: Mapped[List["KnowledgeBaseDocument"]] = relationship(
        back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[List["IngestionJob"]] = relationship(
        back_populates="knowledge_base", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("user_id", "name", name="idx_unique_kb_name"),)

    def __repr__(self) -> str:
        return (
            f"<KnowledgeBase(id={self.id}, name='{self.name}', user_id={self.user_id})>"
        )


class KnowledgeBaseDocument(Base, TimestampMixin):
    __tablename__ = "knowledge_base_documents"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents_registry.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        back_populates="document_associations"
    )
    document: Mapped["DocumentRegistry"] = relationship(
        back_populates="knowledge_base_associations"
    )

    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id", "document_id", name="idx_unique_kb_doc_combination"
        ),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseDocument(kb_id={self.knowledge_base_id}, doc_id={self.document_id})>"


class IngestionJob(Base, TimestampMixin):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    kb_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    resource_id: Mapped[PyUuid] = mapped_column(pg_uuid(as_uuid=True), nullable=False)
    op_status: Mapped[OperationStatusEnum] = mapped_column(
        SQLEnum(OperationStatusEnum, name="operation_status", create_type=False),
        nullable=False,
        server_default=OperationStatusEnum.PENDING.value,
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        back_populates="ingestion_jobs"
    )

    __table_args__ = (Index("idx_job_kb", "kb_id"),)

    def __repr__(self) -> str:
        return f"<IngestionJob(id={self.id}, kb_id={self.kb_id}, status='{self.op_status.value}')>"
