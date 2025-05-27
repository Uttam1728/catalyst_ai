from typing import Optional

from pydantic import BaseModel


class CreateModelConfigRequest(BaseModel):
    name: str
    slug: str
    engine: str
    api_key_name: str
    icon: str
    enabled: bool | None = None  # Optional field for enabling/disabling
    rank: int
    accept_image: bool
    max_tokens: int = 16384
    provider: str
    base_url: Optional[str] = ""
    is_premium: Optional[bool] = False


class UpdateModelConfigRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    engine: Optional[str] = None
    api_key_name: Optional[str] = None
    icon: Optional[str] = None
    enabled: Optional[bool] = None
    rank: Optional[int] = None
    accept_image: Optional[bool] = None
    max_tokens: Optional[int] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
