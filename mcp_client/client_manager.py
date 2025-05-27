from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from config.logging import logger


class MultipleMCPClientManager:
    def __init__(self, stdio_server_map, sse_server_map):
        self.stdio_server_map = stdio_server_map
        self.sse_server_map = sse_server_map
        self.sessions = {}
        self.exit_stack = AsyncExitStack()

    async def initialize(self):
        # Initialize stdio connections
        for server_name, params in self.stdio_server_map.items():
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions[server_name] = session

        # Initialize SSE connections
        for mcp in self.sse_server_map:
            sse_transport = await self.exit_stack.enter_async_context(
                sse_client(url=mcp.sse_url)
            )
            read, write = sse_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions[mcp.mcp_name] = session

    async def list_tools(self):
        tool_map = {}
        consolidated_tools = []

        for server_name, session in self.sessions.items():
            tools = await session.list_tools()

            # Only add tools that don't already exist in the tool_map
            for tool in tools.tools:
                if tool.name not in tool_map:
                    tool_map[tool.name] = server_name
                    consolidated_tools.append(tool)

        return tool_map, consolidated_tools

    async def call_tool(self, tool_name, arguments, tool_map):
        server_name = tool_map.get(tool_name)
        if not server_name:
            logger.error(f"Tool '{tool_name}' not found.")
            return

        session = self.sessions.get(server_name)
        if session:
            result = await session.call_tool(tool_name, arguments=arguments)
            return result.content[0].text
        return

    async def close(self):
        await self.exit_stack.aclose()
