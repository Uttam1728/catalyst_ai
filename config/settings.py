import enum
import os
from typing import Optional

from clerk_integration.utils import ClerkAuthHelper
from pydantic_settings import BaseSettings, SettingsConfigDict
from sentence_transformers import SentenceTransformer

from config.config_parser import docker_args
from utils.connection_manager import ConnectionManager
from utils.sqlalchemy import async_db_url

args = docker_args


class LogLevel(enum.Enum):  # noqa: WPS600
    """Possible log levels."""
    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


class Settings(BaseSettings):
    # pydantic v2: use model_config with SettingsConfigDict to define settings configuration
    model_config = SettingsConfigDict()

    app_name : str = os.getenv("APP_NAME", args.app_name)
    # Server configuration
    env: str = args.env
    port: int = args.port
    host: str = args.host
    debug: bool = args.debug
    workers_count: int = 1
    log_level: str = LogLevel.INFO.value
    use_dummy_user: bool = os.getenv("USE_DUMMY_USER", "False").lower() == "true" or args.use_dummy_user

    # Database connections
    db_url: str = async_db_url(args.db_url)
    read_db_url: str = async_db_url(args.read_db_url)
    db_echo: bool = args.debug
    redis_payments_url: str = os.getenv("REDIS_PAYMENTS_URL", args.redis_payments_url)

    # External services
    ingestion_url: str = args.ingestion_url

    # API keys and credentials
    openai_key: str = os.getenv("OPENAI_KEY", args.openai_key)
    claude_key: str = os.getenv("CLAUDE_KEY", args.claude_key)
    groq_key: str = os.getenv("GROQ_KEY", args.groq_key)
    deepseek_api_key: Optional[str] = args.deepseek_api_key
    stream_token: str = args.stream_token
    clerk_secret_key: str = args.clerk_secret_key

    # Global class instances
    connection_manager: Optional[ConnectionManager] = None
    read_connection_manager: Optional[ConnectionManager] = None
    clerk_auth_helper: ClerkAuthHelper = ClerkAuthHelper(service_name="catalyst", clerk_secret_key=clerk_secret_key)

    # Kubernetes configuration
    POD_NAME: str = args.K8S_POD_NAME

    # Monitoring and logging
    sentry_dsn: Optional[str] = args.sentry_dsn
    sentry_sample_rate: float = 1.0
    sentry_environment: str = args.sentry_environment

    # Application settings

    max_tokens: int = 128000
    thread_summary_count: int = int(args.thread_summary_count)
    full_message_count: int = int(args.full_message_count)
    thread_summary_context_limit: int = int(args.thread_summary_context_limit)
    use_thread_summaries: bool = args.use_thread_summaries
    skip_paths_for_restriction: str = args.skip_paths_for_restriction
    kb_agent_enabled: bool = args.kb_agent_enabled

    # File paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


loaded_config = Settings()
