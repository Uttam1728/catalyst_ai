from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from config.logging import get_logger
from mcp_configs.models import MCPModel
from utils.dao import BaseDao

logger = get_logger(__name__)


class MCPDao(BaseDao):
    """Data Access Object for MCP model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=MCPModel)

    async def get_mcp_by_id(self, mcp_id: str):
        """Get MCP record by ID."""
        try:
            query = select(MCPModel).where(MCPModel.id == mcp_id)
            result = await self.session.execute(query)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting MCP record by ID {mcp_id}: {e}")
            raise

    async def get_mcps_by_user_id(self, user_id: str):
        """Get all MCP records for a user."""
        try:
            query = select(MCPModel).where(MCPModel.user_id == user_id)
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting MCP records for user {user_id}: {e}")
            raise

    async def update_mcp(self, mcp_id: str, update_data: dict):
        """Update MCP record."""
        try:
            query = update(MCPModel).where(MCPModel.id == mcp_id).values(**update_data)
            result = await self.session.execute(query)
            return result
        except Exception as e:
            logger.error(f"Error updating MCP record {mcp_id}: {e}")
            raise

    async def delete_mcp(self, mcp_id: str):
        """Delete MCP record."""
        try:
            query = delete(MCPModel).where(MCPModel.id == mcp_id)
            await self.session.execute(query)
            return True
        except Exception as e:
            logger.error(f"Error deleting MCP record {mcp_id}: {e}")
            raise

    async def toggle_inactive(self, mcp_id: str, inactive: bool):
        """Toggle inactive status."""
        try:

            return await self.update_mcp(mcp_id, {"inactive": inactive})
        except Exception as e:
            logger.error(f"Error toggling inactive status for MCP record {mcp_id}: {e}")
            raise
