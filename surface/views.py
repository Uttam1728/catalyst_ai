import asyncio

from clerk_integration.utils import UserData
from fastapi import BackgroundTasks
from fastapi_prometheus_middleware import track_streaming_generator
from fastapi_prometheus_middleware.context import token_usage_context
from starlette.responses import StreamingResponse

from config.settings import loaded_config
from request_logger.helpers import log_tokens
from surface.serializers import SurfaceRequest
from surface.services import SurfaceService
from utils.base_view import BaseView
from utils.exceptions import ModelFetchException
from wrapper.ai_models import ModelRegistry


class ChatView(BaseView):
    """Handles chat-related endpoints"""

    @classmethod
    async def handle_streaming_chat_request_v1(
            cls,
            surface_request: SurfaceRequest,
            background_tasks: BackgroundTasks,
            user_data: UserData,
            surface_id: int = 1
    ):
        try:
            surface_service = SurfaceService()
            # Log the surface request asynchronously (non-blocking)
            return StreamingResponse(
                track_streaming_generator(
                    surface_service.process_surface_request_stream_v1(
                        surface_request=surface_request,
                        background_tasks=background_tasks,
                        user_data=user_data
                    ),
                    endpoint="handle_streaming_chat_request_v1"
                ),
                media_type="text/event-stream"
            )
        except Exception as e:
            return cls.construct_error_response(
                f"Error: Oops!! {loaded_config.app_name} Agent Couldn't Complete Streaming Chat Request! Please retry.")

    @classmethod
    async def handle_non_streaming_chat_request(cls, surface_request: SurfaceRequest, surface_id: int = 1):
        try:
            surface_service = SurfaceService()

            response_data = await surface_service.process_surface_request_v2(surface_request=surface_request)

            return cls.construct_success_response(data=response_data)
        except Exception as e:
            return cls.construct_error_response(e)
        finally:
            tokens_data = token_usage_context.get()
            asyncio.create_task(
                log_tokens(user=surface_request.requested_by, request_type="chat", tokens_data=tokens_data,
                           url="/ask", header="", body=str(surface_request),
                           model=surface_request.model))


class ModelView(BaseView):
    """Handles model-related endpoints"""

    @classmethod
    async def list_models_v1(cls, surface_id: int = 1):
        """
        Fetch available models directly from ModelRegistry.
        :param surface_id: (Optional) ID for surface (not used in function).
        :return: ResponseData object containing model list.
        """
        try:
            models = ModelRegistry.list_models()
            return cls.construct_success_response(data={"models": models})
        except Exception as e:
            return cls.construct_error_response(ModelFetchException(str(e)))
