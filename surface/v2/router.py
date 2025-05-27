from fastapi import APIRouter

from app.routing import CustomRequestRoute
from surface.router import surface_router_v1
from surface.v2.views.chat_view import ChatView
from surface.v2.views.model_view import ModelViewV2

surface_router_v1.add_api_route("/ask", methods=["POST"],
                                endpoint=ChatView.handle_chat_request_v1)

surface_router_v2 = APIRouter(route_class=CustomRequestRoute)
surface_router_v2.add_api_route("/models", methods=["GET"],
                                endpoint=ModelViewV2.list_models_v2)
surface_router_v2.add_api_route("/ask", methods=["POST"], endpoint=ChatView.handle_chat_request_v2)
