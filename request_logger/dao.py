from sqlalchemy.ext.asyncio import AsyncSession

from config.logging import logger
from request_logger.models import RequestLogger
from utils.dao import BaseDao


class RequestLoggerDao(BaseDao):

    def __init__(self, session: AsyncSession):
        super().__init__(session=session, db_model=RequestLogger)

    # @db_query_latency()
    async def create_log(self, user, url, request_type="", tokens=0, meta={}, header="", body="", response="",
                         model=""):
        try:
            new_request_logger = RequestLogger(
                user=user, request_type=request_type, tokens=tokens, url=url, meta=meta, header=header,
                body=body, response=response, model=model
            )
            self.session.add(new_request_logger)
            await self.session.commit()
            return new_request_logger
        except Exception as e:
            logger.error(f"Error Logging request for URL- {url} - {e}")
            await self.session.rollback()
