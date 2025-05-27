from utils.connection_handler import ConnectionHandler
from wrapper.dao import LLMModelConfigDAO
from wrapper.serializers import CreateModelConfigRequest


class LLMModelConfigService:

    def __init__(self, connection_handler: ConnectionHandler):
        self.connection_handler = connection_handler
        self.model_config_dao = LLMModelConfigDAO(session=connection_handler.session)

    async def create_model_config(self, config_request: CreateModelConfigRequest):
        config = self.model_config_dao.add_object(config_request.dict())
        return config

    async def update_model_config(self, config_id: int, update_values_dict: dict = {}):
        return await self.model_config_dao.update_by_pk(config_id, update_values_dict)

    async def get_all_model_configs(self):
        configs = await self.model_config_dao.get_all_configs()
        # print("DAO configs", configs)
        return configs

    async def delete_model_config(self, config_id: int):
        return await self.model_config_dao.delete_config(config_id)
