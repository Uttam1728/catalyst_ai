from fastapi import APIRouter

from app.routing import CustomRequestRoute
from surface.views import ModelView

surface_router_v1 = APIRouter(route_class=CustomRequestRoute)

surface_router_v1.add_api_route("/surface/{surface_id}/models", methods=["GET"],
                                endpoint=ModelView.list_models_v1)
