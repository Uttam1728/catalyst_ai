import uuid

from sqlalchemy import String, Column, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped

from utils.sqlalchemy import TimestampMixin, Base


class MCPModel(TimestampMixin, Base):
    """
    MCP (Model-Controller-Persistence) model for CRUD operations.

    Properties:
    - id: UUID primary key
    - mcp_name: Name of the MCP
    - sse_url: URL for Server-Sent Events
    - user_id: User ID from UserData
    - inactive: Boolean switch for inactive status
    - type: Type of MCP server
    - command: Command to run the server
    - args: Arguments for the command (stored as JSON)
    - env_vars: Environment variables (stored as JSON)
    - source: Origin of the MCP configuration (e.g., 'vscode', 'website')
    - created_at: Timestamp for creation (from TimestampMixin)
    - updated_at: Timestamp for updates (from TimestampMixin)
    """
    __tablename__ = "mcp_model"

    id: Mapped[uuid.UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mcp_name: Mapped[str] = Column(String, nullable=False)
    sse_url: Mapped[str] = Column(String, nullable=True)
    user_id: Mapped[str] = Column(String, nullable=False)
    inactive: Mapped[bool] = Column(Boolean, default=False)
    type: Mapped[str] = Column(String, nullable=False)
    command: Mapped[str] = Column(String, nullable=True)
    args: Mapped[dict] = Column(JSON, nullable=True)
    env_vars: Mapped[dict] = Column(JSON, nullable=True)
    source: Mapped[str] = Column(String, nullable=True)
