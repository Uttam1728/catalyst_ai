from typing import Optional

from pydantic import BaseModel, Field


class ThreadQueryParams(BaseModel):
    user_email: str = Field(..., description="The email of the user to filter projects by")
    product: str = Field(..., description="The product to filter the threads")
    page: int = Field(default=1, ge=1, description="Page number for pagination")
    page_size: int = Field(10, ge=1, le=100, description="Number of items per page")
    search: Optional[str] = Field(None, description="Search query for thread messages")
