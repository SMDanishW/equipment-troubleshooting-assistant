from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password
from app.crud.users import get_user_by_identifier
from app.models.user import User


def run_startup_bootstrap(db: Session) -> None:
    seed_admin_user(db)


def seed_admin_user(db: Session) -> None:
    if not settings.admin_password:
        return

    admin = get_user_by_identifier(db, settings.admin_email) or get_user_by_identifier(db, settings.admin_username)
    if admin:
        admin.username = settings.admin_username.strip().lower()
        admin.email = settings.admin_email.strip().lower()
        admin.hashed_password = hash_password(settings.admin_password)
        admin.role = "admin"
        admin.is_active = True
    else:
        admin = User(
            username=settings.admin_username.strip().lower(),
            email=settings.admin_email.strip().lower(),
            hashed_password=hash_password(settings.admin_password),
            role="admin",
            is_active=True,
        )
        db.add(admin)
    db.commit()
