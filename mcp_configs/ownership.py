from clerk_integration.utils import UserData
from fastapi import HTTPException, Depends

from mcp_configs.exceptions import MCPNotFoundException, MCPUnauthorizedException
from mcp_configs.service import MCPService
from utils.common import UserDataHandler
from utils.connection_handler import ConnectionHandler, get_connection_handler_for_app


class MCPOwnershipService:
    """Service for verifying MCP record ownership."""

    def __init__(self, connection_handler: ConnectionHandler):
        self.connection_handler = connection_handler
        self.mcp_service = MCPService(connection_handler=connection_handler)

    async def check_ownership(self, mcp_id: str, user_data: UserData):
        """
        Check if the user owns the MCP record.
        
        Args:
            mcp_id: The ID of the MCP record to check
            user_data: The user data to check ownership against
            
        Returns:
            The MCP record if the user owns it
            
        Raises:
            MCPNotFoundException: If the MCP record doesn't exist
            MCPUnauthorizedException: If the user doesn't own the MCP record
        """
        if not user_data:
            raise MCPUnauthorizedException()

        # Get the MCP record
        mcp = await self.mcp_service.mcp_dao.get_mcp_by_id(mcp_id)

        # Check if the MCP record exists
        if not mcp:
            raise MCPNotFoundException()

        # Check if the user owns the MCP record
        if mcp.user_id != str(user_data.userId):
            raise MCPUnauthorizedException()

        return mcp


async def verify_mcp_ownership(
        mcp_id: str,
        user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
        connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
):
    """
    Dependency for verifying MCP record ownership.
    
    Args:
        mcp_id: The ID of the MCP record to check
        user_data: The user data to check ownership against
        connection_handler: The connection handler to use
        
    Returns:
        The MCP record if the user owns it
        
    Raises:
        HTTPException: If the user doesn't own the MCP record or it doesn't exist
    """
    try:
        ownership_service = MCPOwnershipService(connection_handler)
        return await ownership_service.check_ownership(mcp_id, user_data)
    except MCPNotFoundException:
        raise HTTPException(status_code=404, detail="MCP record not found")
    except MCPUnauthorizedException:
        raise HTTPException(status_code=403, detail="Unauthorized access to this MCP record")
