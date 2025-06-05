from sqlalchemy.orm import Session, aliased
from sqlalchemy import select
from app.dao.schema import ApiKey, UserClient
from app.dao.models import StoreApiKey, VerifiedApiKey


def store_api_key(*, db: Session, api_key_params: StoreApiKey) -> ApiKey:
    try:
        api_key = ApiKey(
            user_id=api_key_params.user_id,
            key_id=api_key_params.key_id,
            key_credential=api_key_params.key_credential,
            key_signature=api_key_params.key_signature,
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        return api_key
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"failed to store api key: {e}")


def get_api_key_for_verification(*, db: Session, api_key: bytes) -> VerifiedApiKey:
    u = aliased(UserClient)

    stmt = (
        select(ApiKey, u.email.label("email"), u.role.label("role"))
        .join(u, ApiKey.user_client)
        .where(ApiKey.key_credential == api_key)
    )

    row = db.execute(stmt).first()

    if not row:
        return None

    api_key_obj, email, role = row

    return VerifiedApiKey(
        id=api_key_obj.id,
        user_id=api_key_obj.user_id,
        user_email=email,
        user_role=role,
        key_id=api_key_obj.key_id,
        key_credential=api_key_obj.key_credential,
        key_signature=api_key_obj.key_signature,
    )
