from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from app.routing import CustomRequestRoute
from mcp_configs.router import mcp_config_router_v1
from surface.router import surface_router_v1
from surface.v2.router import surface_router_v2
from threads.router import threads_router_v1, threads_router_v2
from wrapper.router import wrapper_router_v1


async def healthz():
    return JSONResponse(status_code=200, content={"success": True})


api_router = APIRouter()

""" all version v1.0 routes """
api_router_v1 = APIRouter(prefix='/v1.0', route_class=CustomRequestRoute)
api_router_v2 = APIRouter(prefix='/v2.0', route_class=CustomRequestRoute)

api_router_v1.include_router(wrapper_router_v1)
api_router_v1.include_router(threads_router_v1)
api_router_v1.include_router(mcp_config_router_v1)
api_router_v1.include_router(surface_router_v1)

api_router_v2.include_router(threads_router_v2)
api_router_v2.include_router(surface_router_v2)

""" health check routes """
api_router_healthz = APIRouter()
api_router_healthz.add_api_route("/_healthz", methods=['GET'], endpoint=healthz, include_in_schema=False)
api_router_healthz.add_api_route("/_readyz", methods=['GET'], endpoint=healthz, include_in_schema=False)

api_router.include_router(api_router_healthz)
api_router.include_router(api_router_v1)
api_router.include_router(api_router_v2)
