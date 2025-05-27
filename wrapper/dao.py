from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.dao import BaseDao
from wrapper.models import LLMModelConfig


class LLMModelConfigDAO(BaseDao):
    def __init__(self, session: AsyncSession):
        """
        Initialize the ModelConfigDAO with an AsyncSession.
        """
        super().__init__(session=session, db_model=LLMModelConfig)

    async def get_all_configs(self):
        """
        Retrieve all rows from the model_configs table.
        """
        query = select(LLMModelConfig)
        result = await self._execute_query(query)
        return result.scalars().all()

    async def get_config_from_model_name(self, model_name: str) -> LLMModelConfig:
        """
        Retrieve a specific configuration by its model name.

        :param model_name: The name of the model to retrieve.
        :return: The configuration object if found, else None.
        """
        query = select(LLMModelConfig).where(LLMModelConfig.slug == model_name)
        result = await self._execute_query(query)
        return result.scalars().first()

    async def delete_config(self, config_id: int):
        """
        Delete a specific configuration by its ID.
        
        :param config_id: The ID of the configuration to delete.
        :return: None
        """
        query = delete(LLMModelConfig).where(LLMModelConfig.id == config_id)
        return await self._execute_query(query)
