from fastapi import APIRouter

from app.api.routes import health
from app.api.routes import user
from app.api.routes import token
from app.api.routes import documents
from app.api.routes import knowledge_base_ops
from app.api.routes import ingestion
from app.api.routes import pool_stats

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(user.router)
api_router.include_router(token.router)
api_router.include_router(documents.router)
api_router.include_router(knowledge_base_ops.router)
api_router.include_router(ingestion.router)
api_router.include_router(pool_stats.router)
