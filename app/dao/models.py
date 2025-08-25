import os
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
from app.dao.schema import ClientRoleEnum
from typing import List, Dict, Optional, Any
from app.constants.content_type import ALLOWED_EXTENSIONS


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
        schema_extra = {"example": {"email": "john@example.com"}}


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


class GeneratedPresignedUrls(StandardResponse):
    urls: Dict[int, str]


class GeneratePresignedUrlsReq(BaseModel):
    files: List[str] = Field(
        ..., min_length=1, description="a list of filenames to upload"
    )

    @field_validator("files", mode="each")
    @classmethod
    def check_file_extension(cls, filename: str) -> str:
        _root, extension = os.path.splitext(filename)

        if not extension:
            raise ValueError(f"File '{filename}' has no extension")

        if extension.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"file type for '{filename}' is not allowed."
                f"allowed extension are: {','.join(ALLOWED_EXTENSIONS)}"
            )
        return filename

    class Config:
        schema_extra = {"example": {"files": ["mydocument.pdf", "photo.jpg"]}}


class CreateDocument(BaseModel):
    user_id: int
    file_name: str
    object_key: str


class FinalizeDocumentReq(BaseModel):
    failed: List[int]
    successful: List[int]

    class Config:
        schema_extra = {"example": {"failed": [1, 2, 3], "successful": [1, 2, 5]}}


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

    class Config:
        schema_extra = {"example": {"name": "dummy-knowledge-base"}}


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


class FilesForIngestion(BaseModel):
    kb_doc_id: int
    file_name: int
    object_key: Optional[str] = None


class SqsMessage(BaseModel):
    ingestion_job_id: int
    job_resource_id: str
    index_kb_doc_id: Optional[List[FilesForIngestion]] = None
    delete_kb_doc_id: Optional[List[FilesForIngestion]] = None
    collection_name: str
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
        schema_extra = {"example": {"kb_id": 5, "file_ids": [1, 5, 6]}}


class CreatedIngestionJob(BaseModel):
    ingestion_id: int
    ingestion_resource_id: str
    new_kb_documents: List[int]
    object_keys: List[str]
    existing_kb_documents: List[int]


class KbDoc(BaseModel):
    id: int
    kb_doc_id: int
    file_name: str


class ListKbDocs(StandardResponse):
    docs: List[KbDoc]
    total_count: int
    knowledge_base_id: int
