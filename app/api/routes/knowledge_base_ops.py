import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep, TokenPayloadDep
from app.dao.knowledge_base_dao import (
    KnowledgeBaseAlreadyExists,
    create_kb_db,
    delete_kb_db,
    list_users_kb,
    list_kb_docs,
)
from app.dao.models import (
    CreatedKb,
    CreateKbReq,
    CreateKbInDb,
    ListedKb,
    StandardResponse,
    ListKbDocs,
)

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])

logger = logging.getLogger(__name__)


@router.post(
    "/create",
    response_model=CreatedKb,
    status_code=status.HTTP_201_CREATED,
    summary="creates a new knowledge base",
)
def create_knowledge_base(
    req: CreateKbReq, db: SessionDep, token_payload: TokenPayloadDep
):
    try:
        args = CreateKbInDb(user_id=token_payload.user_id, name=req.name)
        created_kb = create_kb_db(db=db, kb=args)
        return CreatedKb(
            message="succcessfully created knowledge base",
            id=created_kb.id,
            name=created_kb.name,
        )
    except KnowledgeBaseAlreadyExists:
        msg = "error creating knowlege base"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="knowledge base already exists"
        )
    except Exception:
        msg = "an exception occured while creating knowledge base"
        logger.exception(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )


@router.get(
    "/list",
    response_model=ListedKb,
    status_code=status.HTTP_200_OK,
    summary="list of knowledge bases",
)
def list_kb(
    db: SessionDep, payload: TokenPayloadDep, limit: int = 100, offset: int = 0
):
    listed_kb, total_count = list_users_kb(
        db=db, limit=limit, offset=offset, user_id=payload.user_id
    )
    return ListedKb(
        message="successfully knowledge bases",
        knowledge_bases=listed_kb,
        total_count=total_count,
    )


@router.get(
    "/docs/list",
    response_model=ListKbDocs,
    status_code=status.HTTP_200_OK,
    summary="list knowledge base documents",
)
def list_knowledge_base_docs(
    db: SessionDep,
    payload: TokenPayloadDep,
    kb_id: int,
    limit: int = 100,
    offset: int = 0,
):
    if kb_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide knowledge base id to list knowledge base documents",
        )
    result = list_kb_docs(
        db=db, limit=limit, offset=offset, user_id=payload.user_id, kb_id=kb_id
    )
    return result


@router.delete(
    "/delete/{kb_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="delete knowledge base",
)
def delete_kb(db: SessionDep, payload: TokenPayloadDep, kb_id: int):
    if kb_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide knowledge base id to delete",
        )
    try:
        result = delete_kb_db(db=db, user_id=payload.user_id, kb_id=kb_id)
        if result:
            return StandardResponse(message="successfully deleted")
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="cannot find knowledge base to delete",
            )
    except HTTPException:
        raise
    except Exception as e:
        msg = "an exception occurred while deleting the knowledge base"
        logger.error(msg, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )
