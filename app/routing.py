from typing import Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute


class CustomRequestRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            return await original_route_handler(request)

        return custom_route_handler
