from clerk_integration.utils import UserData
from fastapi import Depends, Path, Body

from utils.base_view import BaseView
from utils.common import UserDataHandler
from utils.connection_handler import ConnectionHandler, get_connection_handler_for_app, \
    get_read_connection_handler_for_app
from wrapper.ai_models import LLMModelConfigValidator
from wrapper.serializers import UpdateModelConfigRequest, CreateModelConfigRequest
from wrapper.service import LLMModelConfigService


class LLMModelConfigView(BaseView):
    SUCCESS_MESSAGE = "Model configuration processed successfully!"

    @classmethod
    async def post(
            cls,
            config_request: CreateModelConfigRequest,
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request)
    ):
        try:
            model_config_service = cls._get_model_config_service(connection_handler)
            data = await model_config_service.create_model_config(config_request=config_request)
            await connection_handler.session.commit()
            LLMModelConfigValidator.model_validate(data)
            return cls.construct_success_response(data=data, message=cls.SUCCESS_MESSAGE)
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @classmethod
    async def put(
            cls,
            config_id: int = Path(description="Model Config ID to be updated"),
            config_request: UpdateModelConfigRequest = Body(...),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request)
    ):
        try:
            model_config_service = cls._get_model_config_service(connection_handler)
            update_values = config_request.dict(exclude_unset=True)
            data = await model_config_service.update_model_config(config_id, update_values)
            await connection_handler.session.commit()
            return cls.construct_success_response(data=data.rowcount)
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @classmethod
    async def get(
            cls,
            connection_handler: ConnectionHandler = Depends(get_read_connection_handler_for_app),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request)
    ):
        try:
            model_config_service = cls._get_model_config_service(connection_handler)
            configs = await model_config_service.get_all_model_configs()
            configs = [LLMModelConfigValidator.model_validate(config) for config in configs]
            return cls.construct_success_response(data={'configs': configs})
        except Exception as exp:
            return cls.construct_error_response(exp)

    @classmethod
    async def delete(
            cls,
            config_id: int = Path(description="CONFIG ID TO BE DELETED"),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request)):
        try:
            model_config_service = cls._get_model_config_service(connection_handler)
            await model_config_service.delete_model_config(config_id=config_id)
            await connection_handler.session.commit()
            return cls.construct_success_response(message=f"Configuration with ID {config_id} deleted successfully.")
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @staticmethod
    def _get_model_config_service(connection_handler):
        return LLMModelConfigService(connection_handler=connection_handler)
