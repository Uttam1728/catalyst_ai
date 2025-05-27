import json
from typing import Dict


class MCPHelper:
    @staticmethod
    def filter_mcp_input_schema(input_schema):
        """
        Processes and standardizes an input schema for MCP tools.
        
        Args:
            input_schema: The schema to process
            
        Returns:
            The processed schema with standardized required fields and type handling
        """
        if "properties" in input_schema:
            # Ensure all properties are in the required list
            if "required" not in input_schema or not isinstance(
                    input_schema["required"], list
            ):
                input_schema["required"] = list(input_schema["properties"].keys())
            else:
                for key in input_schema["properties"].keys():
                    if key not in input_schema["required"]:
                        input_schema["required"].append(key)

            for key, value in input_schema["properties"].items():
                # Remove default values
                if "default" in value:
                    del value["default"]

                # Handle array of types (convert to string with nullable flag)
                if "type" in value and isinstance(value["type"], list):
                    if "null" in value["type"]:
                        # If one of the types is 'null', use the other type and set nullable
                        other_types = [t for t in value["type"] if t != "null"]
                        if other_types:
                            value["type"] = other_types[0]  # Use the first non-null type
                            value["nullable"] = True
                    else:
                        # If no 'null' in types, use the first type
                        value["type"] = value["type"][0]

            # Set additionalProperties to false if not specified
            if "additionalProperties" not in input_schema:
                input_schema["additionalProperties"] = False

        return input_schema

    @staticmethod
    def convert_to_openai_tool_format(tool_calls):
        """
        Converts a dict_values of ChoiceDeltaToolCall objects into OpenAI tool_calls format.

        Args:
            tool_calls: dict_values or iterable of ChoiceDeltaToolCall objects

        Returns:
            List of tool call dictionaries formatted for OpenAI API.
        """
        tool_calls = tool_calls.values()
        tool_calls_formatted = []
        for call in tool_calls:
            # Handle both dictionary and object formats
            if isinstance(call, dict):
                # Dictionary format
                tool_calls_formatted.append({
                    "id": call["id"],
                    "type": call["type"],
                    "function": {
                        "name": call["function"]["name"],
                        "arguments": call["function"]["arguments"]
                    }
                })
            else:
                # Object format
                tool_calls_formatted.append({
                    "id": call.id,
                    "type": call.type,
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments
                    }
                })

        return tool_calls_formatted

    @staticmethod
    def convert_to_anthropic_tool_format(final_tool_calls):
        """
        Convert OpenAI-style tool calls to Anthropic-style tool_use format.
        
        Args:
            final_tool_calls: Dictionary of OpenAI-style tool calls
            
        Returns:
            List of Anthropic-style tool_use objects
        """
        return [
            {
                "type": "tool_use",
                "id": tool_call["id"],
                "name": tool_call["function"]["name"],
                "input": json.loads(tool_call["function"]["arguments"])
            } for tool_call in final_tool_calls.values()
        ]

    @staticmethod
    def create_tool_result_message(tool_call_id: str, observation: str, provider: str) -> Dict:
        """
        Create a tool result message in the format appropriate for the specified provider.

        Args:
            tool_call_id: The ID of the tool call
            observation: The result of the tool call
            provider: The provider format to use ('openai' or 'anthropic')

        Returns:
            A formatted message dictionary
        """
        if provider.lower() == "anthropic":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": observation
                    }
                ]
            }
        else:  # openai
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": observation
            }

    @staticmethod
    def format_tools_object_for_llm_call(tool_objects, provider):
        """
        Format tool objects based on the provider (anthropic or openai).
        
        Args:
            tool_objects: List of tool objects with name, description, and inputSchema
            provider: String indicating the provider ('anthropic' or 'openai')
        
        Returns:
            List of formatted tools for the specified provider
        """
        if provider == 'anthropic':
            return [{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            } for tool in tool_objects]
        elif provider == "openai":
            return [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "strict": True,
                        "parameters": MCPHelper.filter_mcp_input_schema(tool.inputSchema),
                    },
                }
                for tool in tool_objects
            ]
        return []
