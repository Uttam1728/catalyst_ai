import uuid

from sqlalchemy import String, Column, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped

from utils.sqlalchemy import TimestampMixin, Base


class RequestLogger(TimestampMixin, Base):
    __tablename__ = "request_logger"

    id: Mapped[uuid.UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user: Mapped[str] = Column(String, unique=False)
    request_type: Mapped[str] = Column(String, unique=False)
    tokens: Mapped[int] = Column(Integer)
    url: Mapped[str] = Column(String, unique=False)
    header: Mapped[str] = Column(String, unique=False)
    body: Mapped[str] = Column(String, unique=False)
    response: Mapped[str] = Column(String, unique=False)
    model: Mapped[str] = Column(String, unique=False)
    meta: Mapped[dict] = Column(JSONB)

# intermediate table to track single pr review token
# once pr is complete, consolidate all to requestlogger

# RL = rl(RL DB Connection manager)
# rl.log_tokens(token_data)
# rl.review_pilot_intermediate_log(tokens, pr_id)
# rl.review_pilot_consolidate_tokens(pr_id)
