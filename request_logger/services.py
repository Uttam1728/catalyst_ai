from config.logging import logger
from request_logger.dao import RequestLoggerDao
from utils.connection_handler import ConnectionHandler


class RequestLoggerService():

    def __init__(self, connection_handler: ConnectionHandler = None):
        self.connection_handler = connection_handler
        self.request_logger_dao = RequestLoggerDao(session=self.connection_handler.session)

    async def log_model_request(self, user, url, request_type, tokens_data, header, body, model):
        try:
            total_tokens = tokens_data['total_tokens']
            await self.request_logger_dao.create_log(user, url, request_type, total_tokens,
                                                     meta={"tokens": tokens_data}, header=header, body=body,
                                                     model=model)
        except Exception as e:
            logger.error(f"Error logging request - {e}")
