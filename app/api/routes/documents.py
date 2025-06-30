import logging
import uuid
from typing import Dict, List

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AwsDep, SessionDep, TokenPayloadDep
from app.aws.client import ClientError
from app.dao.file_dao import (
    cleanup_docs,
    conflicted_docs,
    create_document,
    delete_documents,
    finalize_documents,
    list_files,
    lock_documents,
)
from app.dao.models import (
    CreateDocument,
    Document,
    FinalizeDocumentReq,
    GeneratedPresignedUrls,
    GeneratePresignedUrlsReq,
    ListDocuments,
    StandardResponse,
)

router = APIRouter(prefix="/documents", tags=["Documents"])

logger = logging.getLogger(__name__)


@router.post(
    "/upload",
    response_model=GeneratedPresignedUrls,
    status_code=status.HTTP_201_CREATED,
    summary="generate presigned urls for documents that needs to be uploaded",
)
def upload_documents(
    req: GeneratePresignedUrlsReq,
    db: SessionDep,
    payload: TokenPayloadDep,
    aws_client: AwsDep,
):
    try:
        if len(req.files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="please provide files to generate the presigned urls",
            )
        list_of_documents: List[CreateDocument] = []
        url_by_filename: Dict[str, str] = {}
        for file in req.files:
            unique_id = uuid.uuid4()
            filename = f"{file}-{unique_id}"
            object_key = f"{payload.user_id}/{filename}"
            content_type = aws_client.extract_content_type(filename=file)
            url = aws_client.generate_presigned_upload_url(
                object_key=object_key, content_type=content_type
            )
            url_by_filename[filename] = url
            document = CreateDocument(
                user_id=payload.user_id, file_name=filename, object_key=object_key
            )
            list_of_documents.append(document)

        created_documents = create_document(db=db, files=list_of_documents)
        final_response: Dict[int, str] = {}

        for doc_id, filename in created_documents:
            presigned_url = url_by_filename.get(filename)
            if presigned_url:
                final_response[doc_id] = presigned_url
            else:
                logger.error(
                    f"Consistency Error: Could not find pre-signed URL for document ID {doc_id} "
                    f"with filename '{filename}'. This record will be an orphan."
                )

        return GeneratedPresignedUrls(
            message="generated presigned urls successfully", urls=final_response
        )
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception:
        logger.exception("an exception occured", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error uploading document",
        )


@router.put(
    "/finalize",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="finalized failed and successful files",
)
def post_upload_documents(req: FinalizeDocumentReq, db: SessionDep):
    if req.failed == 0 and req.successful == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide documents to finalize",
        )

    try:
        finalize_documents(db=db, successful=req.successful, failed=req.failed)
        return StandardResponse(message="succcessfully finalized the documents")
    except Exception:
        logger.exception("error finalizing document", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error finalizing documents",
        )


@router.get(
    "/list",
    response_model=ListDocuments,
    status_code=status.HTTP_200_OK,
    summary="list of documents",
)
def list_documents(
    db: SessionDep, payload: TokenPayloadDep, limit: int = 100, offset: int = 0
):
    try:
        db_documents = list_files(
            db=db, user_id=payload.user_id, limit=limit, offset=offset
        )
        if not db_documents:
            return ListDocuments(documents=[], message="none documents found")
        response_documents = [Document.model_validate(doc) for doc in db_documents]

        return ListDocuments(
            documents=response_documents, message="successfully fetched documents"
        )
    except Exception:
        logger.error("error listing documents", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error listing documents",
        )


@router.delete(
    "/delete/{file_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="delete documents",
)
def delete_file(
    db: SessionDep, payload: TokenPayloadDep, aws_client: AwsDep, file_id: int
):
    ids = [file_id]
    try:
        object_keys = lock_documents(db=db, document_ids=ids, user_id=payload.user_id)
    except Exception:
        msg = "error locking documents for deletion, please sync up"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    if len(object_keys) == 0:
        msg = "none documents found"
        logger.info(msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)

    try:
        aws_client.multiple_delete_objects(object_keys=object_keys)
    except Exception:
        msg = "error deleting objects from bucket"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    try:
        delete_documents(db=db, document_ids=ids, user_id=payload.user_id)
    except Exception:
        msg = "error deleting documents, please sync up"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    return StandardResponse(message="successfully deleted files")


@router.get(
    "/cleanup",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="cleanup successful",
)
def cleanup_files(db: SessionDep, payload: TokenPayloadDep, aws_client: AwsDep):
    conflicting_docs = conflicted_docs(db=db, user_id=payload.user_id)

    if not conflicted_docs:
        return StandardResponse(message="none conflicting files found")

    to_be_unlocked = []
    to_be_deleted = []

    for doc in conflicting_docs:
        exists: bool = aws_client.object_exists(object_key=doc.object_key)
        if not exists:
            to_be_deleted.append(doc.id)
        else:
            to_be_unlocked.append(doc.id)

    if to_be_deleted or to_be_unlocked:
        try:
            cleanup_docs(
                db=db,
                user_id=payload.user_id,
                to_be_unlocked=to_be_unlocked,
                to_be_deleted=to_be_deleted,
            )
        except Exception:
            logger.error("error cleaning up docs", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="error cleaning up docs",
            )

    return StandardResponse(message="cleanup successfully finished")
