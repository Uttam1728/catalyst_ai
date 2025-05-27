from fastapi import APIRouter

from app.routing import CustomRequestRoute
from mcp_configs.views import MCPViews
from utils.serializers import ResponseData

mcp_view = MCPViews()
mcp_config_router_v1 = APIRouter(route_class=CustomRequestRoute)

# Create MCP record
mcp_config_router_v1.add_api_route(
    "/mcp_configs",
    methods=["POST"],
    endpoint=mcp_view.create_mcp,
    summary="Create a new MCP record",
    description="Creates a new MCP record for the user and returns its details."
)

# Get MCP record by ID
mcp_config_router_v1.add_api_route(
    "/mcp_configs/{mcp_id}",
    methods=["GET"],
    endpoint=mcp_view.get_mcp_by_id,
    summary="Get MCP record by ID",
    description="Retrieves the specified MCP record details.",
    response_model=ResponseData
)

# Get all MCP records for a user
mcp_config_router_v1.add_api_route(
    "/mcp_configs",
    methods=["GET"],
    endpoint=mcp_view.get_mcps_by_user,
    summary="Get all MCP records for a user",
    description="Retrieves all MCP records for the authenticated user."
)

# Delete MCP record
mcp_config_router_v1.add_api_route(
    "/mcp_configs/{mcp_id}",
    methods=["DELETE"],
    endpoint=mcp_view.delete_mcp,
    summary="Delete MCP record",
    description="Deletes the specified MCP record."
)

# Toggle inactive status
mcp_config_router_v1.add_api_route(
    "/mcp_configs/{mcp_id}/toggle-inactive",
    methods=["PATCH"],
    endpoint=mcp_view.toggle_inactive,
    summary="Toggle inactive status",
    description="Toggles the inactive status of the specified MCP record."
)
