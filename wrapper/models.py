from sqlalchemy import String, Column, Integer, Boolean

from utils.sqlalchemy import Base


class LLMModelConfig(Base):
    __tablename__ = 'model_configs'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True, index=True)
    engine = Column(String)
    api_key_name = Column(String)
    icon = Column(String)
    enabled = Column(Boolean)
    rank = Column(Integer)
    accept_image = Column(Boolean)
    max_tokens = Column(Integer, nullable=True)
    provider = Column(String)
    base_url = Column(String, nullable=True)
    is_premium = Column(Boolean, default=False)
