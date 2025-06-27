import logging
from fastapi import APIRouter, HTTPException, status
from app.dao.models import StandardResponse, IngestionRequest, SqsMessage
from app.api.deps import SessionDep, TokenPayloadDep, AwsDep
from app.dao.file_dao import get_object_keys_for_ingestion

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
        if req.file_based:
            if not req.file_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="please provide file ids if you wanted ingestion based on file ids",
                )
            object_keys = get_object_keys_for_ingestion(
                db=db, ids=req.file_ids, user_id=payload.user_id
            )
            if not object_keys:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="cannot find the files with provided ids",
                )
            aws_client.send_sqs_message(
                message_body=SqsMessage(object_keys=object_keys)
            )
            return StandardResponse(message="successfully requested for ingestion")
    except Exception:
        logger.error("error ingesting documents", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error ingesting documents",
        )
