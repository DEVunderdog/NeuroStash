from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from app.dao.schema import SearchingBatchJobs, OperationStatusEnum


class SearchJobNotFound(Exception):
    def __init__(self, job_id: int):
        super().__init__(f"searching batch job not found with id: {job_id}")


async def create_batch_job(*, db: AsyncSession, user_id: int, search_query: str) -> int:
    search_batch_jobs = SearchingBatchJobs(
        user_id=user_id,
        search_query=search_query,
        op_status=OperationStatusEnum.PENDING,
    )
    db.add(search_batch_jobs)
    try:
        await db.flush()
        job_id = search_batch_jobs.id
        await db.commit()
        return job_id
    except:
        await db.rollback()
        raise


async def get_batch_job_status(*, db: AsyncSession, job_id: int) -> OperationStatusEnum:
    try:
        stmt = select(SearchingBatchJobs.op_status).where(SearchingBatchJobs.id)
        result = await db.execute(stmt)
        status = result.scalar_one()
        return status
    except NoResultFound:
        raise SearchJobNotFound(job_id=job_id)
    except SQLAlchemyError:
        raise
    except Exception:
        raise
