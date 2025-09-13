import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants.content_type import ALLOWED_EXTENSIONS
from app.dao.schema import ClientRoleEnum


class StandardResponse(BaseModel):
    message: str


class GeneratedToken(StandardResponse):
    token: str


class UserClientBase(BaseModel):
    email: EmailStr
    role: ClientRoleEnum


class UserClientCreate(UserClientBase):
    pass


class RegisterUser(BaseModel):
    email: EmailStr

    class Config:
        json_schema_extra = {"example": {"email": "john@example.com"}}


class UserClientCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    api_key: str


class ApiKeyCreate(BaseModel):
    key_id: int
    key_credential: bytes
    key_signature: bytes


class StoreApiKey(ApiKeyCreate):
    user_id: int


class VerifiedApiKey(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_role: ClientRoleEnum
    key_id: int
    key_credential: bytes
    key_signature: bytes


class IndividualListedUser(BaseModel):
    id: int
    email: str
    role: ClientRoleEnum

    model_config = ConfigDict(from_attributes=True)


class ListUsers(StandardResponse):
    users: List[IndividualListedUser]


class GeneratedApiKey(StandardResponse):
    api_key: str


class GeneratedUrls(BaseModel):
    id: int
    url: str
    content_type: str


class GeneratedPresignedUrls(StandardResponse):
    urls: List[GeneratedUrls]


class GeneratePresignedUrlsReq(BaseModel):
    files: List[str] = Field(
        ..., min_length=1, description="a list of filenames to upload"
    )

    @field_validator("files", mode="before")
    @classmethod
    def check_file_extension(cls, files: List[str]) -> str:
        for filename in files:
            _root, extension = os.path.splitext(filename)

            if not extension:
                raise ValueError(f"File '{filename}' has no extension")

            if extension.lower() not in ALLOWED_EXTENSIONS:
                raise ValueError(
                    f"file type for '{filename}' is not allowed."
                    f"allowed extension are: {','.join(ALLOWED_EXTENSIONS)}"
                )

        return files

    class Config:
        json_schema_extra = {"example": {"files": ["mydocument.pdf", "photo.jpg"]}}


class CreateDocument(BaseModel):
    user_id: int
    file_name: str
    object_key: str


class FinalizeDocumentReq(BaseModel):
    failed: List[int]
    successful: List[int]

    class Config:
        json_schema_extra = {"example": {"failed": [1, 2, 3], "successful": [1, 2, 5]}}


class Document(BaseModel):
    id: int
    file_name: str

    class Config:
        from_attributes = True


class ListDocuments(StandardResponse):
    documents: List[Document]
    total_count: int

    class Config:
        from_attributes = True


class CreateKbInDb(BaseModel):
    user_id: int
    name: str
    category: str


class CreateKbReq(BaseModel):
    name: str = Field(..., min_length=5, max_length=50)
    category: str = Field(..., min_length=3, max_length=50)

    class Config:
        json_schema_extra = {
            "example": {"name": "dummy-knowledge-base", "category": "dummy-category"}
        }


class KnowledgeBaseItem(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class CreatedKb(StandardResponse, KnowledgeBaseItem):
    class Config:
        from_attributes = True


class ListedKb(StandardResponse):
    knowledge_bases: List[KnowledgeBaseItem]
    total_count: int

    class Config:
        from_attributes = True


class FileForIngestion(BaseModel):
    kb_doc_id: int
    doc_id: int
    file_name: str
    object_key: Optional[str] = None


class SqsMessage(BaseModel):
    ingestion_job_id: int
    index_kb_doc_id: Optional[List[FileForIngestion]] = None
    delete_kb_doc_id: Optional[List[FileForIngestion]] = None
    collection_name: str
    kb_id: int
    category: str
    user_id: int


class ReceivedSqsMessage(BaseModel):
    message_id: str
    receipt_handle: str
    body: SqsMessage
    attributes: Optional[Dict[str, Any]] = None
    message_attributes: Optional[Dict[str, Any]] = None


class IngestionRequest(BaseModel):
    kb_id: int
    file_ids: List[int]

    class Config:
        json_schema_extra = {
            "example": {
                "kb_id": 5,
                "file_ids": [1, 5, 6],
                "retry_kb_doc_ids": [1, 6, 9, 13],
            }
        }


class IngestionJobStatusRequest(BaseModel):
    ingestion_job_id: int


class IngestionJobStatusResponse(StandardResponse):
    status: str


class CreatedIngestionJob(BaseModel):
    ingestion_id: int
    collection_name: str
    category: str
    user_id: int
    kb_id: int
    documents: List[FileForIngestion]


class KbDoc(BaseModel):
    kb_doc_id: int
    doc_id: int
    file_name: str
    status: str


class ListKbDocs(StandardResponse):
    docs: List[KbDoc]
    total_count: int
    knowledge_base_id: int
    total_count: int
    knowledge_base_id: int


class PoolStats(StandardResponse):
    available: int
    assigned: int
    failed: int
    cleanup: int
    remote_collections: int


class SearchRequest(BaseModel):
    knowledge_base_id: int
    search_limit: int
    user_query: str


class SearchResponse(StandardResponse):
    response: List[List[dict]]
