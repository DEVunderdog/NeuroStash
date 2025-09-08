import logging
import uuid
from fastapi import APIRouter, HTTPException, status
from app.dao.models import (
    StandardResponse,
    IngestionRequest,
    SqsMessage,
    IngestionJobStatusResponse,
    CreatedIngestionJob,
    IngestionJobStatusRequest,
)
from app.api.deps import SessionDep, TokenPayloadDep, AwsDep
from app.dao.ingestion_dao import (
    create_ingestion_job,
    get_ingestion_job_status,
    KnowledgeBaseNotFound,
    DocsNotFound,
)
from app.aws.client import SqsMessageError

router = APIRouter(prefix="/ingestion", tags=["Data Ingestion"])

logger = logging.getLogger(__name__)


@router.post(
    "/insert",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="initialize the ingestion of data from documents",
)
async def ingest_documents(
    req: IngestionRequest, db: SessionDep, payload: TokenPayloadDep, aws_client: AwsDep
):
    doc_ids = req.file_ids or []

    if req.kb_id == 0 or not req.kb_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide knowledge base id to ingest data into",
        )

    if not doc_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide 'file_ids` to start an ingestion job",
        )

    job_resource_id = uuid.uuid4()

    try:
        result: CreatedIngestionJob = await create_ingestion_job(
            db=db,
            document_ids=doc_ids,
            kb_id=req.kb_id,
            job_resource_id=job_resource_id,
            user_id=payload.user_id,
        )

        if result.documents:
            message = SqsMessage(
                ingestion_job_id=result.ingestion_id,
                index_kb_doc_id=result.documents,
                collection_name=result.collection_name,
                category=result.category,
                user_id=result.user_id,
                kb_id=result.kb_id,
            )

            aws_client.send_sqs_message(message_body=message)

        await db.commit()

        return StandardResponse(
            message=f"successfully requested ingestion for {len(result.documents)} documents"
        )

    except KnowledgeBaseNotFound as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except DocsNotFound as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except SqsMessageError as e:
        await db.rollback()
        logger.error(
            f"sqs message failed after db prep for job {job_resource_id}. Rolling back",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"coudl not queue ingestion job: {e}",
        )

    except Exception:
        await db.rollback()
        logger.error(
            "Error creating ingestion job and sending SQS message", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while starting the ingestion job.",
        )


@router.delete(
    "/delete",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="delete the ingested data",
)
async def delete_ingested_data(
    req: IngestionRequest, db: SessionDep, payload: TokenPayloadDep, aws_client: AwsDep
):
    doc_ids = req.file_ids or []

    if req.kb_id == 0 or not req.kb_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide knowledge base id to ingest data into",
        )

    if not doc_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide 'file_ids` to start an ingestion job",
        )

    job_resource_id = uuid.uuid4()

    try:
        result: CreatedIngestionJob = await create_ingestion_job(
            db=db,
            document_ids=doc_ids,
            kb_id=req.kb_id,
            job_resource_id=job_resource_id,
            user_id=payload.user_id,
        )

        if result.documents:
            message = SqsMessage(
                ingestion_job_id=result.ingestion_id,
                delete_kb_doc_id=result.documents,
                collection_name=result.collection_name,
                category=result.category,
                user_id=result.user_id,
                kb_id=result.kb_id,
            )

            aws_client.send_sqs_message(message_body=message)

        await db.commit()

        return StandardResponse(
            message="successfully requested for deletion of ingested data"
        )

    except KnowledgeBaseNotFound as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    except DocsNotFound as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except SqsMessageError as e:
        await db.rollback()
        logger.error(
            f"sqs message failed after db prep for job {job_resource_id}. Rolling back",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"coudl not queue ingestion job: {e}",
        )

    except Exception:
        await db.rollback()
        logger.error(
            "Error creating ingestion job and sending SQS message", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while starting the ingestion job.",
        )


@router.get(
    "/status",
    response_model=IngestionJobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="ingestion job status",
)
async def ingestion_job_status(
    req: IngestionJobStatusRequest,
    db: SessionDep,
    payload: TokenPayloadDep,
):
    job_status = await get_ingestion_job_status(
        db=db, ingestion_job_id=req.ingestion_job_id, user_id=payload.user_id
    )

    if job_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cannot find ingestion job with provided id: {req.ingestion_job_id}",
        )

    return IngestionJobStatusResponse(
        message="successfully fetched the job status", status=job_status.value
    )
