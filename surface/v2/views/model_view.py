from clerk_integration.utils import UserData
from fastapi import Depends

from utils.base_view import BaseView
from utils.common import UserDataHandler
from utils.exceptions import ModelFetchException
from wrapper.ai_models import ModelRegistry


class ModelViewV2(BaseView):
    @classmethod
    async def list_models_v2(cls, user_data: UserData = Depends(UserDataHandler.get_user_data_from_request)):
        """
        Fetch available models directly from ModelRegistry.
        :return: ResponseData object containing model list.
        """
        try:
            models = ModelRegistry.list_models()
            return cls.construct_success_response(data={"models": models})
        except Exception as e:
            return cls.construct_error_response(ModelFetchException(str(e)))
