from asyncio import current_task

from sqlalchemy.ext.asyncio import create_async_engine, async_scoped_session, AsyncSession
from sqlalchemy.orm import sessionmaker


class ConnectionManager:

    def __init__(self, db_url, db_echo, redis_url=None):
        self.db_url = db_url
        self.db_echo = db_echo

        self._db_engine, self._db_session_factory = self._setup_db()

    def get_session_factory(self):
        return self._db_session_factory

    def _setup_db(self):
        engine = create_async_engine(str(self.db_url),
                                     echo=self.db_echo,
                                     pool_size=10,  # Set the maximum number of connections in the pool
                                     max_overflow=10,  # Allow up to 10 additional connections beyond the pool size
                                     pool_timeout=10,  # Maximum number of seconds to wait for a connection
                                     )
        session_factory = async_scoped_session(
            sessionmaker(
                engine,
                expire_on_commit=False,
                class_=AsyncSession,
            ),
            scopefunc=current_task,
        )
        return engine, session_factory

    async def close_connections(self):
        await self._db_engine.dispose()
