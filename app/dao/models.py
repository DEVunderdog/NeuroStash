from pydantic import BaseModel, EmailStr, ConfigDict
from app.dao.schema import ClientRoleEnum
from typing import List, Dict, Optional, Any


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

    model_config = ConfigDict(from_attributes=True)


class ListUsers(StandardResponse):
    users: List[IndividualListedUser]


class GeneratedApiKey(StandardResponse):
    api_key: str


class GeneratedPresignedUrls(StandardResponse):
    urls: Dict[int, str]


class GeneratePresignedUrlsReq(BaseModel):
    files: List[str]


class CreateDocument(BaseModel):
    user_id: int
    file_name: str
    object_key: str


class FinalizeDocumentReq(BaseModel):
    failed: List[int]
    successful: List[int]


class Document(BaseModel):
    id: int
    file_name: str

    class Config:
        from_attributes = True


class ListDocuments(StandardResponse):
    documents: List[Document]

    class Config:
        from_attributes = True


class CreateKbInDb(BaseModel):
    user_id: int
    name: str


class CreatedKb(StandardResponse):
    id: int
    kb_name: str

    class Config:
        from_attributes = True


class ListedKb(CreatedKb):
    knowledge_bases: List[CreatedKb]


class SqsMessage(BaseModel):
    ingestion_job_id: int
    job_resource_id: str
    new_kb_doc_id: Optional[List[int]] = None
    new_object_keys: Optional[List[str]] = None


class ReceivedSqsMessage(BaseModel):
    message_id: str
    receipt_handle: str
    body: SqsMessage
    attributes: Optional[Dict[str, Any]] = None
    message_attributes: Optional[Dict[str, Any]] = None


class IngestionRequest(BaseModel):
    kb_id: int
    file_ids: List[int]


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
