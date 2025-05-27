from config.settings import loaded_config
from utils.connection_manager import ConnectionManager
from wrapper.ai_models import initialize_models


async def run_on_startup():
    try:
        await init_connections()
    except Exception as e:
        print(e)


async def run_on_exit():
    await loaded_config.connection_manager.close_connections()
    await loaded_config.read_connection_manager.close_connections()


async def init_connections():
    connection_manager = ConnectionManager(
        db_url=loaded_config.db_url,
        db_echo=loaded_config.db_echo
    )
    read_connection_manager = ConnectionManager(
        db_url=loaded_config.read_db_url,
        db_echo=loaded_config.db_echo
    )
    loaded_config.connection_manager = connection_manager
    loaded_config.read_connection_manager = read_connection_manager
    await initialize_models()
