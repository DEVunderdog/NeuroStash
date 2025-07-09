import logging
import uuid
from fastapi import APIRouter, HTTPException, status
from app.dao.models import StandardResponse, IngestionRequest, SqsMessage
from app.api.deps import SessionDep, TokenPayloadDep, AwsDep
from app.dao.ingestion_dao import create_ingestion_job

router = APIRouter(prefix="/ingestion", tags=["Data Ingestion"])

logger = logging.getLogger(__name__)


@router.post(
    "/start",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="initialize the ingestion of data from documents",
)
def ingest_documents(
    req: IngestionRequest, db: SessionDep, payload: TokenPayloadDep, aws_client: AwsDep
):
    try:
        if len(req.file_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="please provide file ids to ingest documents",
            )

        if req.kb_id == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="please provide knowledge base kb_id to ingest documents",
            )
        job_resource_id = str(uuid.uuid4())
        result = create_ingestion_job(
            db=db,
            document_ids=req.file_ids,
            kb_id=req.kb_id,
            job_resource_id=job_resource_id,
            user_id=payload.user_id,
        )
        if (
            not result.new_kb_documents and not result.object_keys
        ) and not result.existing_kb_documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot find any documents based on provided ids",
            )

        if result.existing_kb_documents or (
            not result.new_kb_documents and not result.object_keys
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="already exists documents in knowledge base",
            )

        message = SqsMessage(
            ingestion_job_id=result.ingestion_id,
            job_resource_id=result.ingestion_resource_id,
        )

        if result.new_kb_documents and result.object_keys:
            message.new_kb_doc_id = result.new_kb_documents
            message.new_object_keys = result.object_keys

        aws_client.send_sqs_message(message_body=message)
        return StandardResponse(message="successfully requested for ingestion")
    except HTTPException:
        raise
    except Exception:
        logger.error("error ingesting documents", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error ingesting documents",
        )
