import uuid

from chat_threads.threads.services import ThreadService
from clerk_integration.utils import UserData
from fastapi import HTTPException

from utils.connection_handler import ConnectionHandler


class ThreadOwnershipService:
    def __init__(self, connection_handler: ConnectionHandler):
        self.thread_service = ThreadService(connection_handler=connection_handler)

    async def check_ownership(self, thread_id: uuid.UUID, user_data: UserData):
        if not user_data:
            raise HTTPException(status_code=403, detail="Unauthorized access to this thread.")

        thread = await self.thread_service.thread_dao.get_thread_by_id(thread_id)

        if not thread or not self._is_user_authorized(thread, user_data):
            raise HTTPException(status_code=404, detail="Unauthorized access to this thread.")

        return thread

    @staticmethod
    def _is_user_authorized(thread, user_data):
        return thread.user_email == user_data.email
