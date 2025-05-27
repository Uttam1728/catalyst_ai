import asyncio
import copy
import inspect
import json
from typing import List, Optional
from uuid import UUID

from chat_threads.threads.dao import ThreadDao, ThreadMessageSummaryDao
from chat_threads.threads.serializers import CreateMessageRequest
from chat_threads.threads.services import ThreadService
from chat_threads.utils.constants import Role
from clerk_integration.utils import UserData
from fastapi import BackgroundTasks
from fastapi_prometheus_middleware.context import token_usage_context

from config.logging import logger
from config.settings import loaded_config
from request_logger.helpers import log_tokens
from surface.constants import MessageType
from surface.dao import UserPreferenceDao
from surface.helper import SurfaceHelper
from surface.serializers import SurfaceRequest
from utils.LRU_cache import LRUCache
from utils.base_view import BaseView
from utils.common import MessageTransformer, TokenCalculator, SQLAlchemySerializer
from utils.connection_handler import ConnectionHandler, execute_db_operation, execute_read_db_operation
from utils.exceptions import SurfaceRequestException
from utils.stream_handler import StreamConfig, StreamHandlerFactory
from utils.stream_strategy import StreamStrategyType


class SurfaceService:

    def __init__(self, connection_handler: ConnectionHandler = None):
        self.connection_handler = connection_handler
        self.cache = LRUCache()
        self.max_retry = 3
        self.thread_id = ""
        self.last_thread_message_id = 0

    async def process_surface_request_v2(self, surface_request: SurfaceRequest):
        agent = await self._get_agent(surface_request)

        # Extract necessary values
        first_message = surface_request.data["messages"][-1].get("firstMessage", False)
        thread_id = surface_request.data["messages"][-1].get("conversationId", 0)
        surface_request.data["messages"] = await MessageTransformer.transform_messages(surface_request.data["messages"],
                                                                                       agent.llm.config.slug)
        last_message = copy.deepcopy(surface_request.data["messages"][-1])

        # Handle the request
        response = await agent.handle(
            surface_request.data,
            api_key=surface_request.metadata.get("api_key", ""),
            model=surface_request.model,
            additional_rules=surface_request.metadata.get("additional_rules", ""),
            references=surface_request.metadata.get("references", dict())
        )

        # Construct response data
        data = SurfaceHelper._construct_response_data(response, surface_request)

        # Handle first message if applicable
        if first_message:
            message = await SurfaceHelper._handle_first_message(message=last_message, response_text=data["content"],
                                                                api_key=surface_request.metadata.get("api_key", ""),
                                                                thread_id=thread_id)
            data["title"] = message

        return data

    async def process_surface_request_stream_v1(self, surface_request: SurfaceRequest,
                                                background_tasks: BackgroundTasks, user_data: UserData):
        try:
            # Initialize configuration
            response_text = ""
            thresholds = await SurfaceHelper._determine_thresholds(surface_request)
            stream_config = StreamConfig(
                rand_min=thresholds["rand_min"],
                rand_max=thresholds["rand_max"]
            )
            handler = StreamHandlerFactory.create_handler('combined', stream_config,
                                                          strategy_type=StreamStrategyType.OBJECT)
            last_message = surface_request.data["messages"][-1]
            if not surface_request.regenerate:
                request_params = {
                    'content': last_message['content'],
                    'requested_by': surface_request.requested_by,
                    'role': last_message.get('role', 'user'),
                    'parent_message_id': last_message.get('parentId'),
                    'product': surface_request.product,
                    'is_json': last_message.get('isJson', False),
                    'question_config': last_message.get('question_config', {})
                }

                # Add thread_id only if conversationId exists
                if conversation_id := last_message.get('conversationId'):
                    request_params['thread_id'] = conversation_id

                create_message_request = CreateMessageRequest(**request_params)
                last_user_thread_message = await execute_db_operation(
                    SurfaceService._create_thread_message,
                    create_message_request,
                    user_data.orgId,
                    raise_exc=True
                )
                self.last_thread_message_id = last_user_thread_message.id
                self.thread_id = last_user_thread_message.thread_uuid
                await execute_db_operation(
                    SurfaceService.update_thread_operation,
                    self.thread_id,
                    {"last_message_id": self.last_thread_message_id},
                    raise_exc=True
                )
                yield handler.format_output(str(self.thread_id), msg_type=MessageType.THREAD_UUID)
                yield handler.format_output(str(self.last_thread_message_id), msg_type=MessageType.LAST_USER_MESSAGE_ID)
                yield handler.format_output(
                    SQLAlchemySerializer.to_serializable_dict(last_user_thread_message),
                    msg_type=MessageType.LAST_USER_MESSAGE
                )
            else:
                self.thread_id = last_message.get('conversationId')
                self.last_thread_message_id = surface_request.data["messages"][-1]['id']
            # summary processing here before thread message id is stripped from the input
            messages = surface_request.data['messages']
            thread_and_summaries = await self._get_thread_message_and_summaries(messages, model=surface_request.model)
            surface_request.data["summary_and_messages"] = thread_and_summaries

            # Get and prepare agent
            agent = await self._get_agent(surface_request)
            first_message = surface_request.data["messages"][-1].get("firstMessage", False)
            surface_request.data["messages"] = await MessageTransformer.transform_messages(
                surface_request.data["messages"],
                agent.llm.config.slug)
            last_message = copy.deepcopy(surface_request.data["messages"][-1])

            user_tags = await self._get_user_tags(surface_request)
            self.cache.update_tags(user_tags)

            process_result = agent.process_input(
                surface_request.data,
                api_key=surface_request.metadata.get("api_key", ""),
                model=surface_request.model,
                additional_rules=surface_request.metadata.get("additional_rules", ""),
                references=surface_request.metadata.get("references", ""),
                user_tags=self.cache.get_cache_order(),
                user_id=user_data.userId,
                org_id=user_data.orgId
            )

            if inspect.isasyncgen(process_result):
                async for process_output in process_result:
                    yield handler.format_output(process_output, msg_type=MessageType.PROGRESS)
            else:
                await process_result

            yield handler.format_output("", msg_type=MessageType.STREAM_START)

            execution_count = 1
            # Sometimes OpenAI returns an empty response,
            # so we retry the request up to 3 maximum number of retries
            while execution_count <= self.max_retry:
                response = await agent.execute(
                    api_key=surface_request.metadata.get("api_key", ""),
                    user_data=user_data,
                    product=surface_request.product  # Pass product to execute
                )
                if isinstance(response, str):
                    yield handler.format_output(response, msg_type=MessageType.DATA)
                    break
                else:
                    async for output in self._stream_response(surface_request, response, thresholds,
                                                              stream_type=StreamStrategyType.OBJECT):
                        try:
                            parsed_output = json.loads(output.split(f"{loaded_config.stream_token}: ")[1])
                            if parsed_output.get('type') == 'data':
                                response_text += parsed_output.get('payload', {}).get('content', '')
                            yield output
                        except Exception as e:
                            logger.error(f"Error processing stream output: {str(e)}")
                            yield handler.format_output(f"Error processing response", msg_type=MessageType.ERROR)
                    if response_text.strip():
                        break
                # Increment the retry counter with labels for email ID and last message
                # Metrics collection removed
                execution_count += 1

            if first_message:
                message = await SurfaceHelper._handle_first_message(last_message, response_text,
                                                                    api_key=surface_request.metadata.get("api_key",
                                                                                                         ""),
                                                                    thread_id=self.thread_id)
                yield handler.format_output(message, msg_type=MessageType.CONVERSATION_TITLE)
                
            last_assistant_message = await self.save_assistant_message(response_text, surface_request)
            if last_assistant_message:
                yield handler.format_output(
                    SQLAlchemySerializer.to_serializable_dict(last_assistant_message),
                    msg_type=MessageType.LAST_AI_MESSAGE
                )
            else:
                # Handle the case where message saving failed
                yield handler.format_output(
                    {"error": "Failed to save assistant message"},
                    msg_type=MessageType.ERROR
                )
                
            yield handler.format_output("", msg_type=MessageType.STREAM_END)
        except Exception as e:
            error_response = BaseView.construct_error_response(e)
            yield handler.format_output(error_response.message, msg_type=MessageType.ERROR)

        except asyncio.CancelledError as cancelled_error:
            if response_text.strip():
                background_tasks.add_task(
                    SurfaceHelper._handle_first_message,
                    last_message,
                    response_text,
                    api_key=surface_request.metadata.get("api_key", ""),
                    thread_id=self.thread_id
                )
                background_tasks.add_task(
                    self.save_assistant_message,
                    response_text,
                    surface_request
                )
        finally:
            tokens_data = token_usage_context.get()
            asyncio.create_task(
                log_tokens(user=surface_request.requested_by, request_type="chat", tokens_data=tokens_data,
                           url="/ask", header="", body=str(surface_request),
                           model=surface_request.model))

    async def _get_agent(self, surface_request: SurfaceRequest):
        agent = await SurfaceHelper.get_agent(surface_request)
        if not agent:
            raise SurfaceRequestException("Invalid action or surface")
        return agent

    @classmethod
    async def _get_user_tags(cls, surface_request: SurfaceRequest):
        return await execute_read_db_operation(TagsService.get_user_tags, surface_request.requested_by, raise_exc=False,
                                               return_value=None)

    async def _stream_response(self, surface_request, response, thresholds,
                               stream_type: StreamStrategyType = StreamStrategyType.STRING):
        try:
            # Initialize configuration
            stream_config = StreamConfig(
                rand_min=thresholds["rand_min"],
                rand_max=thresholds["rand_max"]
            )
            handler = StreamHandlerFactory.create_handler('combined', stream_config, strategy_type=stream_type,
                                                          cache=self.cache)
            # Process the stream
            async for chunk in handler.handle_stream(response=response, model=surface_request.model):
                yield chunk

            # Get the results after streaming is complete
            result = handler.get_result()

            if result['tags']:
                await self._update_tags(
                    result['tags'],
                    surface_request.requested_by
                )

            # Handle summary if present
            if result['summary']:
                await self._store_conversation_summary(
                    self.thread_id,
                    self.last_thread_message_id,
                    result['summary']
                )

        except Exception as e:
            error_response = BaseView.construct_error_response(e)
            yield handler.format_output(error_response, msg_type=MessageType.ERROR)

    async def _get_agent(self, surface_request: SurfaceRequest):
        agent = await SurfaceHelper.get_agent(surface_request)
        if not agent:
            raise SurfaceRequestException("Invalid action or surface")
        return agent

    @classmethod
    async def _get_user_tags(cls, surface_request: SurfaceRequest):
        return await execute_read_db_operation(TagsService.get_user_tags, surface_request.requested_by, raise_exc=False,
                                               return_value=None)

    async def _update_tags(self, tags, requested_by):
        self.cache.update_tags(tags)
        updated_tags = self.cache.get_cache_order()
        await execute_db_operation(TagsService.update_user_tags, requested_by, updated_tags,
                                   raise_exc=False)

    @staticmethod
    async def update_thread_operation(connection_handler: ConnectionHandler, thread_uuid: UUID,
                                      update_values_dict: dict) -> None:
        """
        Operation to update a thread in the database.

        Args:
            connection_handler: The connection handler for database access.
            thread_uuid (int): The ID of the thread to update.
            update_values_dict (dict): A dictionary of values to update in the thread.
        """
        thread_dao = ThreadDao(session=connection_handler.session)
        await thread_dao.update_thread(thread_uuid=thread_uuid, update_values_dict=update_values_dict)

    async def _store_conversation_summary(self, thread_id: str, thread_message_id: int, summary: str):
        # Add validation to prevent empty thread_id
        if not thread_id:
            logger.error("Cannot store conversation summary: thread_id is empty")
            return
        
        # Implement summary storage logic here
        await execute_db_operation(
            self.add_conversation_summary,
            thread_id,
            thread_message_id,
            summary,
            raise_exc=False
        )

    async def add_conversation_summary(self, connection_handler: ConnectionHandler, thread_id, thread_message_id,
                                       summary: str):
        """
        Operation to add summary to conversation
        """
        summary_dao = ThreadMessageSummaryDao(session=connection_handler.session)
        await summary_dao.create_summary(thread_uuid=thread_id, thread_message_id=thread_message_id,
                                         summary_text=summary)

    async def _get_thread_message_and_summaries(self, messages, full_message_count=loaded_config.full_message_count,
                                                summary_message_count=loaded_config.thread_summary_count,
                                                model="gpt-4o"):
        """
        Get summary of all messages except the last message.
        """
        last_x_messages = messages[-full_message_count:]
        last_y_summary_index = summary_message_count + full_message_count
        last_y_messages = messages[-last_y_summary_index:-full_message_count]
        summary_msg_ids = [msg['id'] for msg in last_y_messages]

        # fetch summary of all messages except the last message
        ids_for_fetching_summary = [msg['id'] for msg in messages[-last_y_summary_index:-1]]
        summaries = await execute_read_db_operation(self.get_thread_message_and_summaries,
                                                    ids_for_fetching_summary, raise_exc=False, return_value=None)
        summaries_dict = {s.thread_message_id: s.summary for s in summaries}

        summaries_present = set(summary_msg_ids).intersection(set(summaries_dict.keys()))
        if not summaries_present:
            # if there are no summaries for previous y messages, just give those messages as is for holding context
            last_x_messages = last_y_messages + last_x_messages

        last_y_summaries = []
        for msg_id, summary in summaries_dict.items():
            if msg_id in summary_msg_ids:
                last_y_summaries.append(summary)

        for m in last_x_messages:
            if TokenCalculator.calculate_tokens(m, model) > loaded_config.thread_summary_context_limit:
                # if summary present, use it. Else use original message
                m['content'] = summaries_dict.get(m.get('id', 0), m['content'])

        summaries_and_messages = {"summaries": summaries_dict, "messages": last_x_messages}
        return summaries_and_messages

    async def get_thread_message_and_summaries(self, connection_handler: ConnectionHandler, message_ids: []):
        """

        """
        try:
            if not message_ids:
                return []
            thread_summary_dao = ThreadMessageSummaryDao(session=connection_handler.session)
            last_y_summaries = await thread_summary_dao.get_summaries(message_ids)
            return last_y_summaries
        except Exception as e:
            # logger.error("Error fetching summaries and messages : %s", str(e), call_stack=get_call_stack())
            # capture_exception(e)
            return []

    @staticmethod
    async def _create_thread_message(connection_handler: ConnectionHandler,
                                     create_message_request: CreateMessageRequest,
                                     org_id: Optional[str] = None) -> None:
        thread_service = ThreadService(connection_handler=connection_handler)
        return await thread_service.create_thread_message(
            create_message_request=create_message_request,
            user_email=create_message_request.requested_by,
            org_id=org_id
        )

    async def save_assistant_message(self, response_text: str, surface_request: SurfaceRequest):
        try:
            # Validate thread_id before proceeding
            if not self.thread_id:
                logger.error("Cannot save assistant message: thread_id is empty")
                return None
            
            create_message_request = CreateMessageRequest(
                content=response_text,
                thread_id=self.thread_id,
                requested_by=surface_request.requested_by,
                role=Role.ASSISTANT,
                parent_message_id=self.last_thread_message_id,
                product=surface_request.product,
                is_json=False,
                question_config={}
            )
            last_ai_message = await execute_db_operation(
                SurfaceService._create_thread_message,
                create_message_request,
                raise_exc=True
            )
            await execute_db_operation(
                SurfaceService.update_thread_operation,
                self.thread_id,
                {"last_message_id": last_ai_message.id},
                raise_exc=True
            )
            return last_ai_message
        except Exception as e:
            logger.error(f"Error storing AI message: {str(e)}")
            return None


class TagsService:

    @staticmethod
    async def get_user_tags(connection_handler: ConnectionHandler, user_email: str) -> List[str]:
        """
        Operation to get user tags.

        Args:
            connection_handler: The connection handler for database access.
            user_email (str): The email of the user whose tags need to be fetched.

        Returns:
            List[str]: A list of user tags.
        """
        user_preference_dao = UserPreferenceDao(session=connection_handler.session)
        result = await user_preference_dao.get_user_tags(user_email=user_email)
        return result.tags if result else []

    @staticmethod
    async def update_user_tags(connection_handler: ConnectionHandler, user_email: str,
                               tags: List[str]) -> None:
        """
        Operation to update user tags.

        Args:
            connection_handler: The connection handler for database access.
            user_email (str): The email of the user whose tags need to be updated.
            tags (List[str]): The new tags to update.
        """
        user_preference_dao = UserPreferenceDao(session=connection_handler.session)
        await user_preference_dao.update_tags(user_email=user_email, tags=tags)
