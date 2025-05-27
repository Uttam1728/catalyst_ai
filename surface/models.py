from sqlalchemy import String, Column, Integer, JSON
from sqlalchemy.orm import Mapped

from utils.sqlalchemy import TimestampMixin, Base


class UserPreference(Base, TimestampMixin):
    __tablename__ = "user_preference"

    id: Mapped[int] = Column(Integer, primary_key=True)
    user_email: Mapped[str] = Column(String, unique=True, index=True)
    user_id: Mapped[int] = Column(Integer, nullable=True)
    tags: Mapped[dict] = Column(JSON, default=[])
