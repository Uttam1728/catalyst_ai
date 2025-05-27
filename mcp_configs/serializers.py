from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class MCPCreateRequest(BaseModel):
    """Request model for creating a new MCP record."""
    mcp_name: str = Field(..., description="Name of the MCP")
    sse_url: str = Field(..., description="URL for Server-Sent Events")
    inactive: Optional[bool] = Field(False, description="Inactive status flag")
    type: str = Field(..., description="Type of MCP server")
    command: Optional[str] = Field(None, description="Command to run the server")
    args: Optional[List[str]] = Field(None, description="Arguments for the command")
    env_vars: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    source: Optional[str] = Field(None, description="Origin of the MCP configuration")


class MCPUpdateRequest(BaseModel):
    """Request model for updating an MCP record."""
    mcp_name: Optional[str] = Field(None, description="Name of the MCP")
    sse_url: Optional[str] = Field(None, description="URL for Server-Sent Events")
    inactive: Optional[bool] = Field(None, description="Inactive status flag")
    type: Optional[str] = Field(None, description="Type of MCP server")
    command: Optional[str] = Field(None, description="Command to run the server")
    args: Optional[List[str]] = Field(None, description="Arguments for the command")
    env_vars: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    source: Optional[str] = Field(None, description="Origin of the MCP configuration")


class MCPToggleInactiveRequest(BaseModel):
    """Request model for toggling inactive status."""
    inactive: bool = Field(..., description="New inactive status")


class MCPModelClass(BaseModel):
    """Response model for MCP operations."""
    id: UUID
    mcp_name: str
    sse_url: str
    user_id: str
    inactive: bool
    type: str
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MCPListResponse(BaseModel):
    """Response model for listing MCP records."""
    items: List[MCPModelClass]
