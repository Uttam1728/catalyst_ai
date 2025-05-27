from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from surface.models import UserPreference
from utils.dao import BaseDao


class UserPreferenceDao(BaseDao):

    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=UserPreference)

    # @db_query_latency()
    async def get_user_tags(self, user_email: str):
        query = select(UserPreference).where(UserPreference.user_email == user_email)
        result = await self._execute_query(query)
        return result.unique().scalar()

    # @db_query_latency()
    async def update_tags(self, user_email: str, tags: list):
        insert_query = insert(UserPreference).values(
            user_email=user_email,
            tags=tags
        )
        update_query = insert_query.on_conflict_do_update(
            index_elements=['user_email'],
            set_=dict(tags=insert_query.excluded.tags)
        )
        await self._execute_query(update_query)
        await self.session.commit()
