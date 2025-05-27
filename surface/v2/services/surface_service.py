import asyncio
import copy
import inspect
import json
from typing import Optional

from chat_threads.threads.serializers import CreateMessageRequest
from clerk_integration.utils import UserData
from fastapi import BackgroundTasks
from fastapi_prometheus_middleware.context import token_usage_context

from config.logging import logger
from config.settings import loaded_config
from request_logger.helpers import log_tokens
from surface.constants import MessageType
from surface.helper import SurfaceHelper
from surface.serializers import SurfaceRequest
from surface.services import SurfaceService
from surface.v2.utils import transform_messages_v2
from utils.LRU_cache import LRUCache
from utils.base_view import BaseView
from utils.connection_handler import execute_db_operation, ConnectionHandler
from utils.stream_handler import StreamConfig, StreamHandlerFactory
from utils.stream_strategy import StreamStrategyType


class SurfaceServiceV2:
    def __init__(self, connection_handler: ConnectionHandler = None):
        self.connection_handler = connection_handler
        self.cache = LRUCache()
        self.max_retry = 3
        self.thread_id = ""
        self.last_thread_message_id = 0
        self.surface_service_v2 = SurfaceService()

    async def process_surface_request_stream_v2(self, surface_request: SurfaceRequest,
                                                background_tasks: BackgroundTasks, user_data: UserData):
        response_text = ""
        thresholds = await SurfaceHelper._determine_thresholds(surface_request)
        stream_config = StreamConfig(
            rand_min=thresholds["rand_min"],
            rand_max=thresholds["rand_max"]
        )
        references = surface_request.data["messages"][-1].get('prompt_details', {}).get("references", dict())
        handler = StreamHandlerFactory.create_handler('combined', stream_config,
                                                      strategy_type=StreamStrategyType.OBJECT)
        last_message = dict()
        try:
            last_message = surface_request.data["messages"][-1]
            if not last_message.get('regenerate', False):
                await self._create_and_update_thread_message(surface_request, last_message, user_data.orgId)
                yield handler.format_output(str(self.thread_id), msg_type=MessageType.THREAD_UUID)

            else:
                self.thread_id = last_message.get("conversationId", 0)
                self.last_thread_message_id = last_message.get("id")
                self.surface_service_v2.thread_id = self.thread_id
                self.surface_service_v2.last_thread_message_id = last_message.get("id")

            yield handler.format_output(str(self.last_thread_message_id), msg_type=MessageType.LAST_USER_MESSAGE_ID)
            # summary processing here before thread message id is stripped from the input
            messages = surface_request.data['messages']
            thread_and_summaries = await self.surface_service_v2._get_thread_message_and_summaries(messages,
                                                                                                   model=surface_request.model)
            surface_request.data["summary_and_messages"] = thread_and_summaries

            # Get and prepare agent
            agent = await self.surface_service_v2._get_agent(surface_request)
            first_message = surface_request.data["messages"][-1].get("firstMessage", False)
            thread_id = self.thread_id

            surface_request.data["messages"] = await transform_messages_v2(
                surface_request.data["messages"],
                agent.llm.config.slug
            )

            last_message = copy.deepcopy(surface_request.data["messages"][-1])

            user_tags = await SurfaceService._get_user_tags(surface_request)
            self.cache.update_tags(user_tags)

            process_result = agent.process_input(
                surface_request.data,
                api_key=surface_request.metadata.get("api_key", ""),
                model=surface_request.model,
                additional_rules=surface_request.metadata.get("additional_rules", ""),
                references=references,
                user_tags=self.cache.get_cache_order()
            )

            if inspect.isasyncgen(process_result):
                async for process_output in process_result:
                    yield handler.format_output(process_output, msg_type=MessageType.PROGRESS)
            else:
                await process_result

            yield handler.format_output('', msg_type=MessageType.STREAM_START)

            execution_count = 1

            # Case: Empty response from OpenAI (Retry mechanism to make sure)
            while execution_count <= self.max_retry:
                response = await agent.execute(api_key=surface_request.metadata.get("api_key", ""))
                if isinstance(response, str):
                    yield handler.format_output(response, msg_type=MessageType.DATA)
                    break
                else:
                    async for output in self.surface_service_v2._stream_response(surface_request, response, thresholds,
                                                                                 stream_type=StreamStrategyType.OBJECT):
                        try:
                            parsed_output = json.loads(output.split(f"{loaded_config.stream_token}: ")[1])
                            if parsed_output.get('type') == 'data':
                                response_text += parsed_output.get('payload', {}).get('content', '')
                            yield output
                        except Exception as e:
                            logger.error(f"Error processing stream output: {str(e)}")
                            yield handler.format_output('Error processing response', msg_type=MessageType.ERROR)
                    if response_text.strip():
                        break
                # Increment the retry counter with labels for email ID and last message
                # Metrics collection removed
                execution_count += 1

            if first_message:
                message = await SurfaceHelper._handle_first_message(last_message, response_text,
                                                                    api_key=surface_request.metadata.get("api_key", ""),
                                                                    thread_id=thread_id)
                yield handler.format_output(message, msg_type=MessageType.CONVERSATION_TITLE)
            last_assistant_message = await self.surface_service_v2.save_assistant_message(response_text,
                                                                                          surface_request)
            yield handler.format_output(str(last_assistant_message.id), msg_type=MessageType.LAST_AI_MESSAGE_ID)
            yield handler.format_output('', msg_type=MessageType.STREAM_END)

        except Exception as e:
            error_response = BaseView.construct_error_response(e)
            yield handler.format_output(error_response.message, msg_type=MessageType.ERROR)

        except asyncio.CancelledError:
            if response_text.strip():
                background_tasks.add_task(
                    SurfaceHelper._handle_first_message,
                    last_message,
                    response_text,
                    api_key=surface_request.metadata.get("api_key", ""),
                    thread_id=self.thread_id
                )
                background_tasks.add_task(
                    self.surface_service_v2.save_assistant_message,
                    response_text,
                    surface_request
                )
        finally:
            tokens_data = token_usage_context.get()
            asyncio.create_task(
                log_tokens(
                    user=surface_request.requested_by,
                    request_type="chat",
                    tokens_data=tokens_data,
                    url="/ask",
                    header="",
                    body=str(surface_request),
                    model=surface_request.model,
                )
            )

    async def process_surface_request_v2(self, surface_request: SurfaceRequest, background_tasks: BackgroundTasks,
                                         user_data: UserData):
        agent = await self.surface_service_v2._get_agent(surface_request)
        references = surface_request.data["messages"][-1].get('prompt_details', {}).get("references", dict())
        last_message = dict()
        data = dict()
        try:
            last_message = surface_request.data["messages"][-1]
            if not last_message.get('regenerate', False) and last_message.get('is_json'):
                await self._create_and_update_thread_message(surface_request, last_message, user_data.orgId)
            else:
                if last_message.get('is_json'):
                    self.thread_id = last_message.get("conversationId", 0)
                    self.last_thread_message_id = surface_request.data["messages"][-1]['id']
                    self.surface_service_v2.thread_id = last_message.get("conversationId", 0)
                    self.surface_service_v2.last_thread_message_id = surface_request.data["messages"][-1]['id']

            first_message = surface_request.data["messages"][-1].get("firstMessage", False)
            surface_request.data["messages"] = await transform_messages_v2(surface_request.data["messages"],
                                                                           agent.llm.config.slug)
            last_message = copy.deepcopy(surface_request.data["messages"][-1])

            response = await agent.handle(
                surface_request.data,
                api_key=surface_request.metadata.get("api_key", ""),
                model=surface_request.model,
                additional_rules=surface_request.metadata.get("additional_rules", ""),
                references=references
            )

            data = SurfaceHelper._construct_response_data(response, surface_request)
            data["threadId"] = self.thread_id
            if first_message and last_message.get('is_json'):
                message = await SurfaceHelper._handle_first_message(message=last_message, response_text=data["content"],
                                                                    api_key=surface_request.metadata.get("api_key", ""),
                                                                    thread_id=self.thread_id)
                data["title"] = message

            return data
        except Exception as e:
            error_response = BaseView.construct_error_response(e)
            return error_response

        except asyncio.CancelledError:
            if data["content"].strip() and last_message.get('is_json'):
                background_tasks.add_task(
                    SurfaceHelper._handle_first_message,
                    last_message,
                    data["content"],
                    api_key=surface_request.metadata.get("api_key", ""),
                    thread_id=self.thread_id
                )
                background_tasks.add_task(
                    self.surface_service_v2.save_assistant_message,
                    data['content'],
                    surface_request
                )

        finally:
            tokens_data = token_usage_context.get()
            asyncio.create_task(
                log_tokens(
                    user=surface_request.requested_by,
                    request_type="chat",
                    tokens_data=tokens_data,
                    url="/ask",
                    header="",
                    body=str(surface_request),
                    model=surface_request.model,
                )
            )

    async def _create_and_update_thread_message(self, surface_request: SurfaceRequest, last_message: dict,
                                                org_id: Optional[str] = None) -> CreateMessageRequest:

        request_params = {
            'content': last_message.get("content", ""),
            'requested_by': surface_request.requested_by,
            'role': last_message.get('role', 'user'),
            'parent_message_id': last_message.get('parentId'),
            'product': surface_request.product,
            'is_json': last_message.get('isJson', False),
            'question_config': last_message.get('question_config', {}),
            'prompt_details': last_message.get('prompt_details', {})
        }

        if conversation_id := last_message.get('conversationId'):
            request_params['thread_id'] = conversation_id

        create_message_request = CreateMessageRequest(**request_params)
        last_user_thread_message = await execute_db_operation(
            SurfaceService._create_thread_message,
            create_message_request,
            org_id,
            raise_exc=True
        )

        self.last_thread_message_id = last_user_thread_message.id
        self.thread_id = last_user_thread_message.thread_uuid
        self.surface_service_v2.thread_id = last_user_thread_message.thread_uuid
        self.surface_service_v2.last_thread_message_id = last_user_thread_message.id

        await execute_db_operation(
            SurfaceService.update_thread_operation,
            self.thread_id,
            {"last_message_id": self.last_thread_message_id},
            raise_exc=True
        )

        return last_user_thread_message
