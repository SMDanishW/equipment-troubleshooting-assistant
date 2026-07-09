from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_user_by_identifier(db: Session, identifier: str) -> User | None:
    normalized = identifier.strip().lower()
    statement = select(User).where((User.email == normalized) | (User.username == normalized))
    return db.execute(statement).scalar_one_or_none()


def create_user(db: Session, username: str, email: str, password: str, role: str = "user") -> User:
    user = User(
        username=username.strip().lower(),
        email=email.strip().lower(),
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
