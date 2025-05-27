from contextlib import asynccontextmanager
from typing import Optional, Callable, Any

from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import loaded_config
from utils.base_view import BaseView


class ConnectionHandler:

    def __init__(self, connection_manager=None, event_bridge=None):
        self._session: Optional[AsyncSession] = None
        self._connection_manager = connection_manager

    @property
    def session(self):
        if not self._session:
            session_factory = self._connection_manager.get_session_factory()
            self._session = session_factory()
        return self._session

    async def session_commit(self):
        await self.session.commit()

    async def close(self):
        if self._session:
            await self._session.close()
        # if self._redis_connection:
        #     await self._redis_connection.close()


async def get_connection_handler_for_app():
    connection_handler = ConnectionHandler(
        connection_manager=loaded_config.connection_manager
        # event_bridge=loaded_config.async_event_bridge
    )
    try:
        yield connection_handler
    finally:
        await connection_handler.close()


@asynccontextmanager
async def gandalf_connection_handler():
    connection_handler = ConnectionHandler(
        connection_manager=loaded_config.connection_manager
        # event_bridge=loaded_config.async_event_bridge
    )
    try:
        yield connection_handler
    finally:
        await connection_handler.close()


async def get_read_connection_handler_for_app():
    connection_handler = ConnectionHandler(
        connection_manager=loaded_config.read_connection_manager
    )
    try:
        yield connection_handler
    finally:
        await connection_handler.close()


@asynccontextmanager
async def gandalf_read_connection_handler():
    connection_handler = ConnectionHandler(
        connection_manager=loaded_config.read_connection_manager
    )
    try:
        yield connection_handler
    finally:
        await connection_handler.close()


# @db_query_latency()
async def execute_db_operation(operation: Callable, *args, **kwargs) -> Any:
    async with gandalf_connection_handler() as connection_handler:
        try:
            result = await operation(connection_handler, *args)
            await connection_handler.session.commit()  # Commit for write operations
            return result
        except Exception as e:
            await connection_handler.session.rollback()  # Rollback on error
            raise_exc = kwargs.get("raise_exc", True)
            return_value = kwargs.get("return_value", None)
            BaseView.construct_error_response(e)
            if raise_exc: raise
            return return_value


# @db_query_latency()
async def execute_read_db_operation(operation: Callable, *args, **kwargs) -> Any:
    async with gandalf_read_connection_handler() as connection_handler:
        try:
            result = await operation(connection_handler, *args)
            return result
        except Exception as e:
            raise_exc = kwargs.get("raise_exc", True)
            return_value = kwargs.get("return_value", None)
            BaseView.construct_error_response(e)
            if raise_exc: raise
            return return_value


@asynccontextmanager
async def catalyst_write_connection_handler_context():
    connection_handler = ConnectionHandler(
        connection_manager=loaded_config.connection_manager
    )
    try:
        yield connection_handler
    finally:
        await connection_handler.close()


@asynccontextmanager
async def catalyst_read_connection_handler_context():
    connection_handler = ConnectionHandler(
        connection_manager=loaded_config.read_connection_manager
    )
    try:
        yield connection_handler
    finally:
        await connection_handler.close()
