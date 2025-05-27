from typing import List, Dict, Any

from clerk_integration.utils import UserData

from config.logging import get_logger
from mcp_configs.dao import MCPDao
from mcp_configs.exceptions import (
    MCPNotFoundException,
    MCPUnauthorizedException,
    MCPCreationException,
    MCPUpdateException,
    MCPDeletionException,
    MCPToggleInactiveException
)
from mcp_configs.serializers import MCPModelClass
from utils.connection_handler import ConnectionHandler

logger = get_logger(__name__)


class MCPService:
    """Service for MCP operations."""

    def __init__(self, connection_handler: ConnectionHandler):
        self.connection_handler = connection_handler
        self.mcp_dao = MCPDao(session=self.connection_handler.session)

    async def create_mcp(self, mcp_name: str, sse_url: str, user_data: UserData,
                         inactive: bool = False, type: str = None, command: str = None,
                         args: List[str] = None, env_vars: Dict[str, str] = None, source: str = None):
        """Create a new MCP record."""
        try:
            user_id = str(user_data.userId)
            mcp = self.mcp_dao.add_object(
                mcp_name=mcp_name,
                sse_url=sse_url,
                user_id=user_id,
                inactive=inactive,
                type=type,
                command=command,
                args=args,
                env_vars=env_vars,
                source=source
            )
            return mcp
        except Exception as e:
            logger.error(f"Error in create_mcp service: {e}")
            raise MCPCreationException() from e

    async def get_mcp_by_id(self, mcp_id: str, user_data: UserData = None):
        """Get MCP record by ID."""
        try:
            mcp = await self.mcp_dao.get_mcp_by_id(mcp_id)
            if not mcp:
                return None

            # If user_data is provided, we're doing an ownership check
            if user_data and mcp.user_id != str(user_data.userId):
                logger.warning(
                    f"User {user_data.userId} attempted to access MCP record {mcp_id} belonging to user {mcp.user_id}")
                raise MCPUnauthorizedException()

            return mcp
        except Exception as e:
            logger.error(f"Error in get_mcp_by_id service: {e}")
            raise

    async def get_mcps_by_user(self, user_data: UserData):
        """Get all MCP records for a user."""
        try:
            user_id = str(user_data.userId)
            mcps = await self.mcp_dao.get_mcps_by_user_id(user_id)
            return mcps
        except Exception as e:
            logger.error(f"Error in get_mcps_by_user service: {e}")
            raise

    async def update_mcp(self, mcp_id: str, update_data: Dict[str, Any], user_data: UserData = None):
        """Update MCP record."""
        try:
            # Get the MCP record - ownership will be checked by the ownership service
            existing_mcp = await self.mcp_dao.get_mcp_by_id(mcp_id)
            if not existing_mcp:
                logger.warning(f"MCP record {mcp_id} not found")
                raise MCPNotFoundException()

            # Filter out any fields that shouldn't be updated
            valid_fields = {"mcp_name", "sse_url", "inactive", "type", "command", "args", "env_vars", "source"}
            filtered_data = {k: v for k, v in update_data.items() if k in valid_fields}

            updated_mcp = await self.mcp_dao.update_mcp(mcp_id, filtered_data)
            return updated_mcp
        except (MCPNotFoundException, MCPUnauthorizedException) as e:
            raise
        except Exception as e:
            logger.error(f"Error in update_mcp service: {e}")
            raise MCPUpdateException() from e

    async def delete_mcp(self, mcp_id: str, user_data: UserData = None):
        """Delete MCP record."""
        try:
            # Get the MCP record - ownership will be checked by the ownership service
            existing_mcp = await self.mcp_dao.get_mcp_by_id(mcp_id)
            if not existing_mcp:
                logger.warning(f"MCP record {mcp_id} not found")
                raise MCPNotFoundException()

            return await self.mcp_dao.delete_mcp(mcp_id)
        except (MCPNotFoundException, MCPUnauthorizedException) as e:
            raise
        except Exception as e:
            logger.error(f"Error in delete_mcp service: {e}")
            raise MCPDeletionException() from e

    async def toggle_inactive(self, mcp_id: str, inactive: bool, user_data: UserData = None):
        """Toggle inactive status."""
        try:
            # Get the MCP record - ownership will be checked by the ownership service
            existing_mcp = await self.mcp_dao.get_mcp_by_id(mcp_id)
            if not existing_mcp:
                logger.warning(f"MCP record {mcp_id} not found")
                raise MCPNotFoundException()

            updated_mcp = await self.mcp_dao.toggle_inactive(mcp_id, inactive)
            return updated_mcp
        except (MCPNotFoundException, MCPUnauthorizedException) as e:
            raise e
        except Exception as e:
            logger.error(f"Error in toggle_inactive service: {e}")
            raise MCPToggleInactiveException() from e

    @staticmethod
    async def get_mcps_by_user_operation(
            connection_handler: ConnectionHandler,
            user_data,
    ):
        """Get all MCP records for a user."""
        mcp_service = MCPService(connection_handler=connection_handler)
        results = await mcp_service.get_mcps_by_user(user_data)

        return [MCPModelClass.model_validate(result) for result in results]
