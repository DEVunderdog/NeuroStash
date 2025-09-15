import logging
from fastapi import APIRouter, status, HTTPException
from app.api.deps import SearchOpsDep, SessionDep, TokenPayloadDep
from app.dao.models import SearchResponse, SearchRequest, StandardResponse
from app.dao.knowledge_base_dao import get_kb_collection, KnowledgeBaseNotFound

router = APIRouter(prefix="/search", tags=["document retrieval"])

logger = logging.getLogger(__name__)


@router.post(
    "/query",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="searching through documents",
)
async def search(
    req: SearchRequest,
    db: SessionDep,
    search_ops: SearchOpsDep,
    payload: TokenPayloadDep,
):
    try:
        if req.knowledge_base_id == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="please provide knowledge base id",
            )

        collection_name = await get_kb_collection(
            db=db, user_id=payload.user_id, kb_id=req.knowledge_base_id
        )

        search_result = search_ops.perform_hybrid_search(
            collection_name=collection_name,
            query=req.user_query,
            limit=req.search_limit,
        )

        return SearchResponse(
            message="successfully fetch the search results", response=search_result
        )

    except KnowledgeBaseNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e)


@router.post(
    "/batch",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="batch searching jobs",
)
async def batch_search():
    pass
