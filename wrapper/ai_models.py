import copy
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, List

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from pydantic import ConfigDict, BaseModel

from config.logging import logger
from config.settings import loaded_config
from mcp_client.chat import MCPChatProcessor
from utils.base_view import BaseView
from utils.connection_handler import gandalf_connection_handler
from utils.prompts import conversation_base_prompt
from wrapper.service import LLMModelConfigService


class ModelConfig(BaseModel):
    name: str
    slug: str
    engine: str
    api_key: Optional[str] = None
    icon: str = ""
    enabled: bool = False
    rank: int = 10000
    accept_image: bool = False
    max_tokens: int = 4096
    temperature: float = 0.1
    base_url: str = ""
    is_premium: bool = False


class LLMModelConfigValidator(BaseModel):
    name: str
    slug: str
    engine: str
    api_key_name: str = ""
    icon: str = ""
    enabled: bool = False
    rank: int = 10000
    accept_image: bool = False
    max_tokens: int = 4096
    temperature: float = 0.1
    base_url: str = ""
    is_premium: bool = False
    provider: str = ""
    id: int = 0

    model_config = ConfigDict(from_attributes=True)


@dataclass
class AzureConfig:
    api_key: str
    api_base: str
    deployment_name: str
    api_version: str
    api_type: str = 'azure'


class BaseMessageProcessor:
    @staticmethod
    def process_messages(messages: List[dict]) -> tuple[str, list]:
        system_message = ""
        filtered_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_message += msg['content'][0]['text'] if isinstance(msg['content'], list) else msg['content']
            else:
                content = msg['content'][0]['text'] if isinstance(msg['content'], list) else msg['content']
                if not content:
                    msg['content'] = "''"
                filtered_messages.append({'role': msg['role'], 'content': msg['content']})

        return system_message, filtered_messages


class ModelInterface(ABC):
    @abstractmethod
    async def predict(self, messages: list | str, **kwargs):
        raise NotImplementedError

    @abstractmethod
    async def predict_completion(self, prompt: str, **kwargs):
        raise NotImplementedError


class UnifiedModel(ModelInterface, BaseMessageProcessor):
    def __init__(self, config: ModelConfig, provider: str,
                 base_url: Optional[str] = None):
        self.config = config
        self.provider = provider
        self.base_url = base_url

        if provider == 'anthropic':
            self.client = AsyncAnthropic(api_key=config.api_key)

    def process_o1_messages(self, messages):
        """Special message processing for o1 models"""
        system_message = ""
        filtered_messages = []

        for msg in messages:
            if msg['role'] == 'system':
                system_message += msg['content'][0]['text'] if isinstance(msg['content'], list) else msg['content']
            else:
                filtered_messages.append({'role': msg['role'], 'content': msg['content']})

        if self.config.slug == "gpt-o1":
            # Special handling for gpt-o1
            filtered_messages = [{
                "role": "developer",
                "content": [{
                    "type": "text",
                    "text": "Formatting re-enabled " + system_message
                }]
            }] + filtered_messages
        else:
            # Handling for o1-mini and o1-preview
            last_message = copy.deepcopy(filtered_messages[-1])
            last_content = last_message['content'][0]['text'] if isinstance(last_message['content'], list) else \
                last_message['content']
            last_content = f" System Message: {system_message} {last_content}"
            if isinstance(last_message['content'], list):
                last_message['content'][0]['text'] = last_content
            else:
                last_message['content'] = last_content
            filtered_messages = filtered_messages[:-1] + [last_message]

        return filtered_messages

    async def predict(self, messages: list | str, stream: bool = False, **kwargs):

        # Process O1 messages if needed
        if self.provider == 'openai-o1':
            messages = self.process_o1_messages(messages)

        # Define provider handlers
        provider_handlers = {
            'openai': self._handle_openai,
            'openai-o1': self._handle_openai,
            'anthropic': self._handle_anthropic,
            'groq': self._handle_groq,
            'deepseek': self._handle_deepseek
        }

        # Get the appropriate handler or raise error for unsupported provider
        handler = provider_handlers.get(self.provider)
        if not handler:
            raise ValueError(f"Unsupported provider: {self.provider}")

        # Call the handler with all necessary parameters
        return await handler(messages, stream, **kwargs)

    async def _handle_openai(self, messages, stream, **kwargs):
        """Handle OpenAI and OpenAI-O1 providers"""
        # Check for Azure load balancing
        api_key = kwargs.get('api_key', '').strip() or self.config.api_key
        user_data = kwargs.get('user_data', {})
        use_mcp = os.getenv('USE_MCP', "False").lower() == "true" and kwargs.get('use_mcp', False) and stream

        logger.info(f"use_mcp {use_mcp}")

        if use_mcp:
            return await self._predict_openai_with_mcp(messages, stream, api_key, self.provider, user_data)
        else:
            return await self._predict_openai(messages, stream, api_key, self.provider)

    async def _handle_anthropic(self, messages, stream, **kwargs):
        """Handle Anthropic provider"""
        system_message, consolidated_messages = self.process_messages(messages)
        if stream:
            use_mcp = os.getenv('USE_MCP', "False").lower() == "true" and kwargs.get('use_mcp', False)

            logger.info(f"use_mcp {use_mcp}")

            if use_mcp:
                return await  self._predict_anthropic_stream_with_mcp(system_message, consolidated_messages, **kwargs)
            else:
                return await self._predict_anthropic_stream(system_message, consolidated_messages, **kwargs)
        else:
            return await self._predict_anthropic_nonstream(system_message, consolidated_messages, **kwargs)

    async def _handle_groq(self, messages, stream, **kwargs):
        """Handle Groq provider"""
        # Process messages to ensure system message is a simple string
        api_key = kwargs.get('api_key', '') or self.config.api_key
        processed_messages = []
        for msg in messages:
            if msg['role'] in ['system', 'assistant']:
                content = msg['content'][0]['text'] if isinstance(msg['content'], list) else msg['content']
                processed_messages.append({'role': msg['role'], 'content': content})
            else:
                processed_messages.append(msg)

        aclient = AsyncOpenAI(api_key=api_key, base_url=self.config.base_url)

        if stream:
            return await aclient.chat.completions.create(
                model=self.config.engine,
                messages=processed_messages,
                stream=True,
                stream_options={"include_usage": True}
            )
        else:
            return await aclient.chat.completions.create(
                model=self.config.engine,
                messages=processed_messages,
                stream=False
            )

    async def _handle_deepseek(self, messages, stream, **kwargs):
        """Handle Deepseek provider"""
        # TODO: Add deepseek prediction code here
        # client = AsyncOpenAI(api_key="EMPTY", base_url="https://6c0a-34-93-164-248.ngrok-free.app/v1")
        #
        # if stream:
        #     return await client.chat.completions.create(
        #         model="DeepSeek-R1-Distill-Llama-8B",
        #         messages=messages,
        #         stream=True,
        #         # stream_options={"include_usage": True}
        #     )
        # else:
        #     return await client.chat.completions.create(
        #         model="DeepSeek-R1-Distill-Llama-8B",
        #         messages=messages,
        #         stream=False
        #     )
        pass

    async def _predict_openai(self, messages: list, stream: bool, api_key: str, provider: str):
        aclient = AsyncOpenAI(api_key=api_key)
        if "o1" in provider:
            response = await aclient.chat.completions.create(
                model=self.config.engine,
                messages=messages,
                stream=stream,
                stream_options={"include_usage": True} if stream else None)
        else:
            response = await aclient.chat.completions.create(
                model=self.config.engine,
                messages=messages,
                temperature=self.config.temperature,
                stream=stream,
                stream_options={"include_usage": True} if stream else None)
        return response

    async def _predict_openai_with_mcp(self, messages: list, stream: bool, api_key: str, provider: str,
                                       user_data: dict = {}):

        aclient = AsyncOpenAI(api_key=api_key)

        # Determine if we need to include temperature based on provider
        params = {
            "client": aclient,
            "model": self.config.engine,
            "messages": messages,
            "stream": stream,
            "stream_options": {"include_usage": True} if stream else None,
            "user_data": user_data
        }

        # Only add temperature for non-O1 models
        if "o1" not in provider:
            params["temperature"] = self.config.temperature

        return MCPChatProcessor.create_openai_stream(**params)

    async def _predict_anthropic_stream(self, system_message: str, consolidated_messages: list, **kwargs):
        return await self.client.messages.stream(
            max_tokens=self.config.max_tokens,
            messages=consolidated_messages,
            model=self.config.engine,
            system=system_message or conversation_base_prompt,
        ).__aenter__()

    async def _predict_anthropic_stream_with_mcp(self, system_message: str, consolidated_messages: list, **kwargs):
        user_data = kwargs.get('user_data', {})
        params = {
            "model": self.config.engine,
            "messages": consolidated_messages,
            "system_message": system_message or conversation_base_prompt,
            "client": self.client,
            "stream": True,
            "max_tokens": self.config.max_tokens,
            "user_data": user_data
        }
        return MCPChatProcessor.create_anthropic_stream(**params)

    async def _predict_anthropic_nonstream(self, system_message: str, consolidated_messages: list, **kwargs):
        return await self.client.messages.create(
            max_tokens=self.config.max_tokens,
            messages=consolidated_messages,
            model=self.config.engine,
            system=system_message or conversation_base_prompt,
        )

    async def predict_completion(self, prompt: str, **kwargs):
        raise NotImplementedError


class ModelRegistry:
    _models: Dict[str, UnifiedModel] = {}

    @classmethod
    def register_model(cls, config: ModelConfig, provider: str,
                       base_url: Optional[str] = None):
        model = UnifiedModel(config=config, provider=provider, base_url=base_url)
        cls._models[config.slug] = model

    @classmethod
    def get_model(cls, slug: str) -> Optional[UnifiedModel]:
        return cls._models.get(slug)

    @classmethod
    def list_models(cls) -> list:
        models = []
        for model in cls._models.values():
            if model.config.enabled:
                models.append({
                    "name": model.config.name,
                    "slug": model.config.slug,
                    "enabled": model.config.enabled,
                    "rank": model.config.rank,
                    "accept_image": model.config.accept_image
                })
        return sorted(models, key=lambda x: x["rank"])


async def initialize_models():
    async with gandalf_connection_handler() as connection_handler:
        model_config_service = LLMModelConfigService(connection_handler)
        all_configs = await model_config_service.get_all_model_configs()

        for config in all_configs:
            try:
                config = LLMModelConfigValidator.model_validate(config)
                ModelRegistry.register_model(
                    config=ModelConfig(
                        name=config.name,
                        slug=config.slug,
                        engine=config.engine,
                        api_key=getattr(loaded_config, config.api_key_name, ""),
                        icon=config.icon,
                        enabled=config.enabled,
                        rank=config.rank,
                        accept_image=config.accept_image,
                        max_tokens=config.max_tokens,
                        base_url=config.base_url,
                        is_premium=config.is_premium
                    ),
                    provider=config.provider
                )
            except Exception as e:
                BaseView.construct_error_response(e)
                print("Exception occurred in initialize models: ", e)
                continue
