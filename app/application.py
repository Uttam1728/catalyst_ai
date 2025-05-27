import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_prometheus_middleware import generate_prometheus_data, PrometheusMiddleware, metrics_endpoint
from opentelemetry.instrumentation import asgi
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.middleware.sessions import SessionMiddleware

from app.router import api_router
from config.sentry import configure_sentry
from config.settings import loaded_config
from utils.load_config import run_on_startup, run_on_exit
from utils.middlewares.custom_middleware import SecurityHeadersMiddleware
from utils.middlewares.restriction_middleware import RestrictionMiddleware

PROMETHEUS_LOG_TIME = 10


async def repeated_task_for_prometheus():
    while True:
        # Get the log file path from config
        from config.settings import loaded_config
        log_file = f"{loaded_config.BASE_DIR}/logs.prom"
        if loaded_config.POD_NAME != 'temp' and os.getenv("METRICS_DIR"):
            log_file = f'{os.getenv("METRICS_DIR")}/{loaded_config.POD_NAME}.prom'

        await generate_prometheus_data(log_file)
        await asyncio.sleep(PROMETHEUS_LOG_TIME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_on_startup()
    asyncio.create_task(repeated_task_for_prometheus())
    yield
    await run_on_exit()


def get_app() -> FastAPI:
    class PatchedASGIGetter(asgi.ASGIGetter):
        def keys(self, carrier):
            print("keys")
            headers = carrier.get("headers") or []
            return [_key.decode("utf8") for (_key, _value) in headers]

    asgi.asgi_getter = PatchedASGIGetter()
    """
    Get FastAPI application.

    This is the main constructor of an application.

    :return: application.
    """
    # if loaded_config.sentry_dsn:
    # Enables sentry integration.
    configure_sentry()

    catalyst_app = FastAPI(
        debug=True,
        title="catalyst",
        docs_url="/api-reference",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        root_path="/"
    )
    # Configure CORS to allow only 'wmsz0.de'
    catalyst_app.add_middleware(
        CORSMiddleware,
        # allow_origins=["*"],  # Only allow this origins
        allow_origins=[],  # Only allow this origins
        # allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    catalyst_app.include_router(api_router)
    catalyst_app.add_middleware(SessionMiddleware, secret_key="** Session Middleware **")
    catalyst_app.add_middleware(SecurityHeadersMiddleware)
    print(loaded_config.skip_paths_for_restriction.split(","))
    # Check if restriction middleware should be enabled from environment variable
    use_restriction_middleware = os.getenv("USE_RESTRICTION_MIDDLEWARE", "False").lower() == "true"

    if use_restriction_middleware:
        catalyst_app.add_middleware(RestrictionMiddleware, redis_url=loaded_config.redis_payments_url,
                                    skip_paths=loaded_config.skip_paths_for_restriction.split(","))
    # Add the Prometheus middleware with the catalyst prefix
    from config.logging import logger
    catalyst_app.add_middleware(
        PrometheusMiddleware,
        prefix="catalyst",
        logger=logger
    )

    FastAPIInstrumentor.instrument_app(catalyst_app)
    catalyst_app.add_route('/metrics', metrics_endpoint)
    return catalyst_app
