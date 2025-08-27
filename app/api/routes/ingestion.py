import logging
import uuid
from fastapi import APIRouter, HTTPException, status
from app.dao.models import StandardResponse, IngestionRequest, SqsMessage
from app.api.deps import SessionDep, TokenPayloadDep, AwsDep
from app.dao.ingestion_dao import create_ingestion_job, KnowledgeBaseNotFound
from app.dao.models import CreatedIngestionJob
from app.aws.client import SqsMessageError

router = APIRouter(prefix="/ingestion", tags=["Data Ingestion"])

logger = logging.getLogger(__name__)


@router.post(
    "/insert",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="initialize the ingestion of data from documents",
)
def ingest_documents(
    req: IngestionRequest, db: SessionDep, payload: TokenPayloadDep, aws_client: AwsDep
):
    doc_ids = req.file_ids or []
    retry_ids = req.retry_kb_doc_ids or []

    if req.kb_id == 0 or not req.kb_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide knowledge base id to ingest data into",
        )

    if not doc_ids and not retry_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide 'file_ids` or 'retry_kb_doc_ids' to start an ingestion job",
        )

    job_resource_id = uuid.uuid4()

    try:
        result: CreatedIngestionJob = create_ingestion_job(
            db=db,
            document_ids=doc_ids,
            retry_kb_doc_ids=retry_ids,
            kb_id=req.kb_id,
            job_resource_id=job_resource_id,
            user_id=payload.user_id,
        )

        if result.documents:
            message = SqsMessage(
                ingestion_job_id=result.ingestion_id,
                job_resource_id=result.ingestion_resource_id,
                index_kb_doc_id=result.documents,
                collection_name=result.collection_name,
                category=result.category,
                user_id=result.user_id,
            )

            aws_client.send_sqs_message(message_body=message)

        db.commit()

        return StandardResponse(
            message=f"successfully requested ingestion for {len(result.documents)} documents"
        )

    except KnowledgeBaseNotFound as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except SqsMessageError as e:
        db.rollback()
        logger.error(
            f"sqs message failed after db prep for job {job_resource_id}. Rolling back",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"coudl not queue ingestion job: {e}",
        )

    except Exception:
        db.rollback()
        logger.error(
            "Error creating ingestion job and sending SQS message", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while starting the ingestion job.",
        )


@router.post(
    "/delete",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="delete the ingested data",
)
def delete_ingested_data(
    req: IngestionRequest, db: SessionDep, payload: TokenPayloadDep, aws_client: AwsDep
):
    doc_ids = req.file_ids or []
    retry_ids = req.retry_kb_doc_ids or []

    if req.kb_id == 0 or not req.kb_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide knowledge base id to ingest data into",
        )

    if not doc_ids and not retry_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide 'file_ids` or 'retry_kb_doc_ids' to start an ingestion job",
        )

    job_resource_id = uuid.uuid4()

    try:
        result: CreatedIngestionJob = create_ingestion_job(
            db=db,
            document_ids=doc_ids,
            retry_kb_doc_ids=retry_ids,
            kb_id=req.kb_id,
            job_resource_id=job_resource_id,
            user_id=payload.user_id,
        )

        if result.documents:
            message = SqsMessage(
                ingestion_job_id=result.ingestion_id,
                job_resource_id=result.ingestion_resource_id,
                delete_kb_doc_id=result.documents,
                collection_name=result.collection_name,
                category=result.category,
                user_id=result.user_id,
            )

            aws_client.send_sqs_message(message_body=message)

        db.commit()

        return StandardResponse(
            message="successfully requested for deletion of ingested data"
        )

    except KnowledgeBaseNotFound as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except SqsMessageError as e:
        db.rollback()
        logger.error(
            f"sqs message failed after db prep for job {job_resource_id}. Rolling back",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"coudl not queue ingestion job: {e}",
        )

    except Exception:
        db.rollback()
        logger.error(
            "Error creating ingestion job and sending SQS message", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while starting the ingestion job.",
        )
