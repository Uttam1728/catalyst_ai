from clerk_integration.utils import UserData
from fastapi import Depends, Path, Body

from mcp_configs.exceptions import (
    MCPCreationException,
    MCPDeletionException,
    MCPToggleInactiveException
)
from mcp_configs.models import MCPModel
from mcp_configs.ownership import verify_mcp_ownership
from mcp_configs.serializers import (
    MCPCreateRequest,
    MCPToggleInactiveRequest,
    MCPModelClass,
)
from mcp_configs.service import MCPService
from utils.base_view import BaseView
from utils.common import UserDataHandler
from utils.connection_handler import ConnectionHandler, get_connection_handler_for_app
from utils.serializers import ResponseData


class MCPViews(BaseView):
    """Views for MCP operations."""

    SUCCESS_MESSAGE_MCP_CREATED = "MCP record created successfully"
    SUCCESS_MESSAGE_MCP_UPDATED = "MCP record updated successfully"
    SUCCESS_MESSAGE_MCP_DELETED = "MCP record deleted successfully"
    SUCCESS_MESSAGE_MCP_INACTIVE_TOGGLED = "MCP inactive status toggled successfully"
    ERROR_MESSAGE_MCP_NOT_FOUND = "MCP record not found"
    ERROR_MESSAGE_MCP_UNAUTHORIZED = "You are not authorized to access this MCP record"

    @classmethod
    async def create_mcp(
            cls,
            request: MCPCreateRequest,
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        """Create a new MCP record."""
        try:
            mcp_service = MCPService(connection_handler=connection_handler)
            result = await mcp_service.create_mcp(
                mcp_name=request.mcp_name,
                sse_url=request.sse_url,
                user_data=user_data,
                inactive=request.inactive,
                type=request.type,
                command=request.command,
                args=request.args,
                env_vars=request.env_vars,
                source=request.source
            )

            await connection_handler.session.commit()
            return cls.construct_success_response(
                data=MCPModelClass.model_validate(result),
                message=cls.SUCCESS_MESSAGE_MCP_CREATED
            )
        except MCPCreationException as e:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp=e)
        except Exception as e:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp=e)

    @classmethod
    async def get_mcp_by_id(
            cls,
            mcp_id: str = Path(..., description="MCP record ID"),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler=Depends(get_connection_handler_for_app),
            mcp: MCPModel = Depends(verify_mcp_ownership)

    ) -> ResponseData:
        """Get MCP record by ID."""
        try:
            mcp_service = MCPService(connection_handler=connection_handler)
            # We don't need to pass user_data since ownership is already verified
            result = await mcp_service.get_mcp_by_id(mcp_id)

            return cls.construct_success_response(
                data=MCPModelClass.model_validate(result)
            )
        except Exception as e:
            return cls.construct_error_response(exp=e)

    @classmethod
    async def get_mcps_by_user(
            cls,
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        """Get all MCP records for a user."""
        try:
            mcp_service = MCPService(connection_handler=connection_handler)
            results = await mcp_service.get_mcps_by_user(user_data)

            return cls.construct_success_response(
                data={
                    "items": [MCPModelClass.model_validate(result) for result in results],
                    "count": len(results)
                }
            )
        except Exception as e:
            return cls.construct_error_response(exp=e)

    @classmethod
    async def delete_mcp(
            cls,
            mcp_id: str = Path(..., description="MCP record ID"),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app),
            mcp: MCPModel = Depends(verify_mcp_ownership)

    ):
        """Delete MCP record."""
        try:
            mcp_service = MCPService(connection_handler=connection_handler)
            # We don't need to pass user_data since ownership is already verified
            result = await mcp_service.delete_mcp(mcp_id)

            await connection_handler.session.commit()
            return cls.construct_success_response(
                message=cls.SUCCESS_MESSAGE_MCP_DELETED
            )
        except MCPDeletionException as e:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp=e)
        except Exception as e:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp=e)

    @classmethod
    async def toggle_inactive(
            cls,
            mcp_id: str = Path(..., description="MCP record ID"),
            request: MCPToggleInactiveRequest = Body(...),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app),
            mcp: MCPModel = Depends(verify_mcp_ownership)

    ):
        """Toggle inactive status."""
        try:
            mcp_service = MCPService(connection_handler=connection_handler)
            # We don't need to pass user_data since ownership is already verified
            result = await mcp_service.toggle_inactive(mcp_id, request.inactive)

            await connection_handler.session.commit()
            return cls.construct_success_response(
                data=result.rowcount,
                message=cls.SUCCESS_MESSAGE_MCP_INACTIVE_TOGGLED
            )
        except MCPToggleInactiveException as e:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp=e)
        except Exception as e:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp=e)
