import json
import logging

import redis.asyncio as redis
from alfred.validator_factory import ValidatorFactory
from fastapi import FastAPI, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config.settings import loaded_config
from utils.common import UserDataHandler
from utils.constants import RestrictionMessageCodeMapping


class RestrictionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, redis_url: str, skip_paths=None):
        super().__init__(app)
        self.redis_url = redis_url or loaded_config.redis_payments_url
        self.redis = None
        self.skip_paths = set(skip_paths or [])
        self.validator_factory = ValidatorFactory(loaded_config.redis_payments_url)

    async def initialize_redis(self):
        """Initializes Redis connection if not already initialized."""
        if not self.redis:
            self.redis = await redis.from_url(self.redis_url, decode_responses=True)

    async def dispatch(self, request: Request, call_next):
        """Middleware logic to enforce user plan restrictions."""
        await self.initialize_redis()

        if request.url.path in self.skip_paths:
            return await call_next(request)

        try:
            request_body = await request.body()
            user_data = await UserDataHandler.get_user_data_from_request(request=request)

            plan_id = user_data.publicMetadata.get("subscription", {}).get(
                "active_plan_id", "") or loaded_config.fallback_plan_id
            request_data = json.loads(request_body or "{}")
            model = request_data.get("model")

            if not plan_id:
                return JSONResponse(
                    content={"error": "Missing plan ID in user data", "error_code": "MISSING_PLAN_ID"},
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

            rules_key = f"plan_rules:catalyst:{plan_id}"
            applied_rules = await self.redis.get(rules_key)

            try:
                applied_rules = json.loads(applied_rules or "[]")
            except json.JSONDecodeError:
                return JSONResponse(
                    content={"error": "Corrupt plan rules data", "error_code": "INVALID_PLAN_RULES"},
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

            restriction_data = []

            for rule in applied_rules:
                validator = self.validator_factory.load_validator(
                    rule, model_used=model, user_id=user_data.userId, org_id=user_data.orgId,
                    endpoint=request.url.path
                )

                success, data, message_code = await validator.validate()

                if not success:
                    return JSONResponse(
                        content={
                            "message": RestrictionMessageCodeMapping.get(message_code,
                                                                         RestrictionMessageCodeMapping["DEFAULT"]),
                            "error": "User restrictions applied",
                            "error_code": message_code,
                            "status_code": 4029
                        },
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                restriction_data.append(data)

            request.state.restriction_data = restriction_data

        except Exception as e:
            logging.error(f"RestrictionMiddleware Error: {str(e)}", exc_info=True)
            return JSONResponse(
                content={"error": "Internal server error", "error_code": "INTERNAL_SERVER_ERROR"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return await call_next(request)
