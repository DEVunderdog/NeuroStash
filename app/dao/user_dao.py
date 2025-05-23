from sqlalchemy.orm import Session
from app.dao.schema import UserClient, ClientRoleEnum
from app.dao.models import UserClientCreate
from app.core.config import settings


def first_admin(*, db: Session):
    user = db.query(UserClient).where(UserClient.email == settings.FIRST_ADMIN).first()
    if not user:
        first_admin_user = UserClient(
            email=settings.FIRST_ADMIN, role=ClientRoleEnum.ADMIN
        )
        db.add(first_admin_user)
        db.commit()
        db.refresh(first_admin_user)

def register_user(*, db: Session, user: UserClientCreate):
    pass
