import json
from typing import AsyncGenerator, Dict, List, Any, Optional, Union

from openai.types.chat import ChatCompletionChunk

from mcp_client.chunks import OpenAICompatibleChunk, create_llm_chunk, AnthropicCompatibleChunk
from mcp_client.client_manager import MultipleMCPClientManager
from mcp_client.constants import BUILTIN_MCP_SERVERS
from mcp_client.helper import MCPHelper
from mcp_client.streams import CustomAsyncStream
from mcp_configs.service import MCPService
from surface.constants import MessageType
from utils.base_view import BaseView
from utils.connection_handler import execute_db_operation


class MCPChatProcessor:
    def __init__(
            self,
            model: str,
            messages: List[Dict],
            stream: bool,
            client: Any,
            max_turns: int = 3,
            user_data: Dict = None,
            temperature: Optional[float] = None,
            stream_options: Optional[Dict] = None,
            system_message: Optional[str] = None,
            max_tokens: Optional[int] = None
    ):
        self.model = model
        self.messages = messages
        self.temperature = temperature
        self.stream = stream
        self.stream_options = stream_options
        self.client = client
        self.max_turns = max_turns
        self.user_data = user_data
        self.client_manager = None
        self.tool_map = None
        self.tools = None
        self.chat_messages = None
        self.system_message = system_message
        self.max_tokens = max_tokens

    async def setup_client(self, provider: str = 'openai') -> None:
        """Set up the MCP client and retrieve available tools."""
        stdio_server_map = {}

        # Get user-specific MCP servers
        user_sse_server_map = await execute_db_operation(MCPService.get_mcps_by_user_operation, self.user_data)

        # Combine user servers with default servers (user servers take precedence)
        sse_server_map = BUILTIN_MCP_SERVERS + user_sse_server_map

        self.client_manager = MultipleMCPClientManager(stdio_server_map, sse_server_map)
        await self.client_manager.initialize()

        self.tool_map, tool_objects = await self.client_manager.list_tools()
        self.tools = MCPHelper.format_tools_object_for_llm_call(tool_objects, provider)
        self.chat_messages = self.messages[:]

    async def process_tool_calls(self, final_tool_calls: Dict, provider: str = 'openai') -> AsyncGenerator[
        Union[OpenAICompatibleChunk, AnthropicCompatibleChunk], None]:
        """Process tool calls and update chat messages."""
        if not final_tool_calls:
            return

        for i, tool_call in enumerate(final_tool_calls.values()):
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])

            yield create_llm_chunk(MessageType.PROGRESS, f"Executing tool: {tool_name}...",
                                   provider=provider)

            observation = await self.client_manager.call_tool(
                tool_name, tool_args, self.tool_map
            )

            tool_result_message = MCPHelper.create_tool_result_message(tool_call["id"], str(observation), provider)
            self.chat_messages.append(tool_result_message)

            yield create_llm_chunk(MessageType.PROGRESS, f"Tool {tool_name} execution complete.",
                                   provider=provider)

        yield create_llm_chunk(MessageType.PROGRESS, "All tools executed successfully.",
                               provider=provider)

    @classmethod
    def create_openai_stream(cls, **kwargs) -> CustomAsyncStream[ChatCompletionChunk]:
        """
        Create and return a custom stream object for MCP chat processing.

        Parameters:
        - model: str - The model to use for chat completions
        - messages: List[Dict] - The messages to process
        - stream: bool - Whether to stream the response
        - stream_options: Dict - Options for streaming
        - client: Any - The OpenAI client
        - max_turns: int (optional) - Maximum number of tool call turns (default: 3)
        - user_data: Dict (optional) - User data for MCP client (default: {})
        - temperature: float (optional) - Temperature for model generation (default: None)

        Returns:
        - CustomAsyncStream[ChatCompletionChunk] - A stream of chat completion chunks
        """
        processor = cls(**kwargs)
        return CustomAsyncStream[ChatCompletionChunk](processor.process_openai_stream_chat)

    @classmethod
    def create_openai_non_stream(cls, **kwargs) -> Any:
        """
        Create and process a non-streaming MCP chat.

        Parameters:
        - model: str - The model to use for chat completions
        - messages: List[Dict] - The messages to process
        - client: Any - The OpenAI client
        - max_turns: int (optional) - Maximum number of tool call turns (default: 3)
        - user_data: Dict (optional) - User data for MCP client (default: {})
        - temperature: float (optional) - Temperature for model generation (default: None)

        Returns:
        - The final chat completion response
        """
        processor = cls(**kwargs, stream=False, stream_options={})
        return processor.process_openai_non_stream_chat()

    async def process_openai_stream_chat(self) -> AsyncGenerator[OpenAICompatibleChunk, None]:
        """Process the chat with MCP tools."""
        try:
            yield create_llm_chunk(MessageType.PROGRESS, "Warming up the thinking engine...",
                                   provider='openai')
            await self.setup_client()

            for turn in range(self.max_turns):
                # Create initial completion with tools
                if turn == 0:
                    yield create_llm_chunk(MessageType.PROGRESS,
                                           "Analyzing your question and determining next steps...",
                                           provider='openai')
                completion_params = {
                    "model": self.model,
                    "messages": self.chat_messages,
                    "tools": self.tools,
                    "stream": self.stream,
                    "stream_options": self.stream_options
                }

                # Only add temperature if it's provided
                if self.temperature is not None:
                    completion_params["temperature"] = self.temperature

                stream_response = await self.client.chat.completions.create(**completion_params)

                # Collect tool calls while streaming response
                final_tool_calls = {}
                async for chunk in stream_response:
                    try:
                        if hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'delta'):
                            delta = chunk.choices[0].delta
                            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                                for tool_call in delta.tool_calls:
                                    index = tool_call.index
                                    if index not in final_tool_calls:
                                        final_tool_calls[index] = {
                                            "id": tool_call.id,
                                            "type": "function",
                                            "function": {
                                                "name": tool_call.function.name,
                                                "arguments": tool_call.function.arguments
                                            },
                                            "index": index
                                        }
                                    else:
                                        final_tool_calls[index]["function"]["arguments"] += tool_call.function.arguments
                        yield chunk
                    except IndexError as e:
                        BaseView.construct_error_response(f"Index error in stream processing: {str(e)}")

                # Process tool calls from the response
                if final_tool_calls:

                    yield create_llm_chunk(MessageType.PROGRESS,
                                           "Using MCP tools to gather information...",
                                           provider='openai')

                    self.chat_messages.append(
                        {"role": "assistant", "content": None,
                         "tool_calls": MCPHelper.convert_to_openai_tool_format(final_tool_calls)}
                    )

                    async for tool_progress in self.process_tool_calls(final_tool_calls, provider='openai'):
                        yield tool_progress

                    yield create_llm_chunk(MessageType.PROGRESS,
                                           "Information gathered. Formulating complete response...",
                                           provider='openai')

                    follow_up_params = {
                        "model": self.model,
                        "messages": self.chat_messages,
                        "stream": self.stream,
                        "stream_options": self.stream_options
                    }

                    # Only add temperature if it's provided
                    if self.temperature is not None:
                        follow_up_params["temperature"] = self.temperature

                    result = await self.client.chat.completions.create(**follow_up_params)

                    async for chunk in result:
                        yield chunk
                else:
                    # No tool calls, so we're done
                    break

            await self.client_manager.close()
        except Exception as e:
            BaseView.construct_error_response(e)

    async def process_openai_non_stream_chat(self) -> Any:
        """Process the chat with MCP tools without streaming."""
        try:
            await self.setup_client()

            for _ in range(self.max_turns):
                # Create initial completion with tools
                completion_params = {
                    "model": self.model,
                    "messages": self.chat_messages,
                    "tools": self.tools,
                    "stream": False
                }

                # Only add temperature if it's provided
                if self.temperature is not None:
                    completion_params["temperature"] = self.temperature

                # First LLM call to determine which tool to use
                response = await self.client.chat.completions.create(**completion_params)

                # Check if the model wants to use tools
                message = response.choices[0].message
                if message.tool_calls:
                    # Convert tool calls to the format expected by process_tool_calls
                    final_tool_calls = {
                        i: tool_call for i, tool_call in enumerate(message.tool_calls)
                    }

                    # Process tool calls and update chat messages
                    await self.process_tool_calls(final_tool_calls)

                    follow_up_params = {
                        "model": self.model,
                        "messages": self.chat_messages,
                        "stream": False
                    }

                    # Only add temperature if it's provided
                    if self.temperature is not None:
                        follow_up_params["temperature"] = self.temperature

                    response = await self.client.chat.completions.create(**follow_up_params)
                return response
            await self.client_manager.close()
        except Exception as e:
            return BaseView.construct_error_response(e)

    async def process_anthropic_stream_chat(self) -> AsyncGenerator[AnthropicCompatibleChunk, None]:
        """Process the chat with MCP tools."""
        try:
            yield create_llm_chunk(MessageType.PROGRESS, "Warming up the thinking engine...",
                                   provider='anthropic')
            await self.setup_client(provider="anthropic")

            for turn in range(self.max_turns):
                # Create initial completion with tools
                if turn == 0:
                    yield create_llm_chunk(MessageType.PROGRESS,
                                           "Analyzing your question and determining next steps...",
                                           provider='anthropic')
                completion_params = {
                    "model": self.model,
                    "messages": self.chat_messages,
                    "tools": self.tools,
                    "max_tokens": self.max_tokens,
                    "system": self.system_message
                }

                stream_response = await self.client.messages.stream(**completion_params).__aenter__()

                # Collect tool calls while streaming response
                final_tool_calls = {}
                tool_index = 0
                current_tool_index = None

                async for chunk in stream_response:
                    try:
                        # Anthropic format
                        if hasattr(chunk, 'type'):
                            if chunk.type == "content_block_start" and chunk.content_block.type == "tool_use":
                                # Start a new tool
                                index = tool_index
                                tool_index += 1
                                final_tool_calls[index] = {
                                    "id": chunk.content_block.id,
                                    "type": "function",
                                    "function": {
                                        "name": chunk.content_block.name,
                                        "arguments": ""
                                    }
                                }
                                # Store the current tool index being processed
                                current_tool_index = index
                            elif chunk.type == "content_block_delta" and hasattr(chunk.delta,
                                                                                 "type") and chunk.delta.type == "input_json_delta":
                                # Update the current tool being processed
                                if current_tool_index is not None and current_tool_index in final_tool_calls:
                                    final_tool_calls[current_tool_index]["function"][
                                        "arguments"] += chunk.delta.partial_json
                        yield chunk
                    except IndexError as e:
                        BaseView.construct_error_response(f"Index error in stream processing: {str(e)}")

                # Process tool calls from the response
                if final_tool_calls:
                    self.chat_messages.append({
                        "role": "assistant",
                        "content": MCPHelper.convert_to_anthropic_tool_format(final_tool_calls)
                    })

                    yield create_llm_chunk(MessageType.PROGRESS,
                                           "Using MCP tools to gather information...",
                                           provider='anthropic')
                    async for tool_progress in self.process_tool_calls(final_tool_calls, provider='anthropic'):
                        yield tool_progress

                    yield create_llm_chunk(MessageType.PROGRESS,
                                           "Information gathered. Formulating complete response...",
                                           provider='anthropic')

                    follow_up_params = {
                        "model": self.model,
                        "messages": self.chat_messages,
                        "max_tokens": self.max_tokens,
                        "system": self.system_message
                    }

                    result = await self.client.messages.stream(**follow_up_params).__aenter__()

                    async for chunk in result:
                        yield chunk
                else:
                    # No tool calls, so we're done
                    break

            await self.client_manager.close()
        except Exception as e:
            BaseView.construct_error_response(e)

    @classmethod
    def create_anthropic_stream(cls, **kwargs) -> CustomAsyncStream[AnthropicCompatibleChunk]:
        """
        Create and return a custom stream object for MCP chat processing.

        Parameters:
        - model: str - The model to use for chat completions
        - messages: List[Dict] - The messages to process
        - stream: bool - Whether to stream the response
        - stream_options: Dict - Options for streaming
        - client: Any - The OpenAI client
        - max_turns: int (optional) - Maximum number of tool call turns (default: 3)
        - user_data: Dict (optional) - User data for MCP client (default: {})
        - temperature: float (optional) - Temperature for model generation (default: None)

        Returns:
        - CustomAsyncStream[AnthropicCompatibleChunk] - A stream of chat completion chunks
        """
        processor = cls(**kwargs)
        return CustomAsyncStream[AnthropicCompatibleChunk](processor.process_anthropic_stream_chat)
