import datetime
import uuid

from mcp_configs.serializers import MCPModelClass

# Default SSE servers configuration as MCPModel instances
BUILTIN_MCP_SERVERS = [
    MCPModelClass(
        id=uuid.UUID("06401f27-8067-4db7-890e-016cb7e21218"),
        mcp_name="web_search",
        sse_url="https://mcp.composio.dev/composio/server/06401f27-8067-4db7-890e-016cb7e21218",
        user_id="system",
        inactive=False,
        type="sse",
        command=None,
        args=None,
        env_vars=None,
        source="system",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    ),
]
