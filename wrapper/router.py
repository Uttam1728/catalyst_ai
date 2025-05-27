from fastapi import APIRouter

from app.routing import CustomRequestRoute
from wrapper.views import LLMModelConfigView

wrapper_router_v1 = APIRouter(route_class=CustomRequestRoute)

# Define routes for model configurations
wrapper_router_v1.add_api_route('/model-configs/', methods=['POST'], endpoint=LLMModelConfigView.post)
wrapper_router_v1.add_api_route('/model-configs/{config_id}/', methods=['PUT'], endpoint=LLMModelConfigView.put)
wrapper_router_v1.add_api_route('/model-configs/', methods=['GET'], endpoint=LLMModelConfigView.get)
wrapper_router_v1.add_api_route('/model-configs/{config_id}/', methods=['DELETE'], endpoint=LLMModelConfigView.delete)
