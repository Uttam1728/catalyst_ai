from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel


class SurfaceRequest(BaseModel):
    action_id: int
    data: Union[list, str, dict]
    model: Optional[str]
    stream: bool = False
    rag: str = "url_scrape"
    user_id: Optional[str] = None
    requested_by: Optional[str]
    metadata: Optional[dict]
    product: str = "co_pilot"
    thread_id: Optional[UUID] = None
    regenerate: Optional[bool] = False
