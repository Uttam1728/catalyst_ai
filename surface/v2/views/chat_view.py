import asyncio

from clerk_integration.utils import UserData
from fastapi import Depends, BackgroundTasks
from fastapi_prometheus_middleware import track_streaming_generator
from fastapi_prometheus_middleware.context import token_usage_context
from starlette.responses import StreamingResponse

from config.settings import loaded_config
from request_logger.helpers import log_tokens
from surface.helper import SurfaceHelper
from surface.serializers import SurfaceRequest
from surface.v2.services.surface_service import SurfaceServiceV2
from surface.views import ChatView as SurfaceChatView
from utils.base_view import BaseView
from utils.common import UserDataHandler


class ChatView(BaseView):
    """ Views for Chat"""

    @classmethod
    async def handle_chat_request_v1(cls, surface_request: SurfaceRequest,
                                     background_tasks: BackgroundTasks,
                                     user_data: UserData = Depends(UserDataHandler.get_user_data_from_request)):
        UserDataHandler.validate_email_match(user_email=user_data.email, requested_by=surface_request.requested_by)
        if surface_request.stream:
            return await SurfaceChatView.handle_streaming_chat_request_v1(surface_request, background_tasks=background_tasks,
                                                                          user_data=user_data)
        else:
            return await SurfaceChatView.handle_non_streaming_chat_request(surface_request)

    @classmethod
    async def handle_chat_request_v2(
            cls,
            surface_request: SurfaceRequest,
            background_tasks: BackgroundTasks,
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
    ):
        UserDataHandler.validate_email_match(user_email=user_data.email, requested_by=surface_request.requested_by)
        last_question_id = surface_request.data["messages"][-1].get("last_question_id", None)
        surface_request.data["messages"] = await SurfaceHelper.process_messages(surface_request.thread_id,
                                                                                surface_request.data["messages"],
                                                                                last_question_id)
        if surface_request.stream:
            return await cls.handle_streaming_chat_request_v2(surface_request, background_tasks, user_data)
        else:
            return await cls.handle_non_streaming_chat_request_v2(surface_request, background_tasks, user_data)

    @classmethod
    async def handle_streaming_chat_request_v2(
            cls,
            surface_request: SurfaceRequest,
            background_tasks: BackgroundTasks,
            user_data: UserData,
            surface_id: int = 1
    ):
        try:
            if surface_request.data["messages"][-1].get("resend", False):
                surface_request.data["messages"][-1]["parentId"] = surface_request.data["messages"][-2]["parentId"]
                del surface_request.data["messages"][-2]
            surface_service = SurfaceServiceV2()
            return StreamingResponse(
                track_streaming_generator(
                    surface_service.process_surface_request_stream_v2(
                        surface_request=surface_request,
                        background_tasks=background_tasks,
                        user_data=user_data
                    ),
                    endpoint="handle_streaming_chat_request_v2"
                ),
                media_type="text/event-stream"
            )
        except Exception as e:
            return cls.construct_error_response(
                f"Error: Oops!! {loaded_config.app_name} Agent Couldn't Complete Streaming Chat Request! Please retry.")

    @classmethod
    async def handle_non_streaming_chat_request_v2(
            cls,
            surface_request: SurfaceRequest,
            background_tasks: BackgroundTasks,
            user_data: UserData,
            surface_id: int = 1
    ):
        try:
            surface_service = SurfaceServiceV2()

            response_data = await surface_service.process_surface_request_v2(surface_request, background_tasks,
                                                                             user_data)

            return cls.construct_success_response(data=response_data)
        except Exception as e:
            return cls.construct_error_response(e)
        finally:
            tokens_data = token_usage_context.get()
            asyncio.create_task(
                log_tokens(user=surface_request.requested_by, request_type="chat", tokens_data=tokens_data,
                           url="/ask", header="", body=str(surface_request),
                           model=surface_request.model))
