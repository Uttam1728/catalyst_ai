from config.logging import logger
from request_logger.services import RequestLoggerService
from utils.connection_handler import catalyst_write_connection_handler_context


async def log_tokens(user, request_type, tokens_data, url, header="", body="", model=""):
    try:
        async with catalyst_write_connection_handler_context() as connection_handler:
            log_service = RequestLoggerService(connection_handler=connection_handler)
            await log_service.log_model_request(user, url, request_type, tokens_data, header=header, body=body,
                                                model=model)
    except Exception as e:
        logger.error(f"Error logging request - {e}")
