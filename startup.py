"""
Database Setup and Initialization Script

This script provides utilities for setting up and initializing the catalyst AI Assistant database.
It handles database migrations using Alembic and seeds initial model configurations.

Usage:
    python startup.py --migrate  # Run database migrations
    python startup.py --seed     # Seed initial model configurations
    python startup.py --all      # Run both migrations and seeding
    python startup.py            # Show help message

The script uses the same database connection handling as the main application,
ensuring consistency across the codebase.
"""

import asyncio
import argparse
import os
import sys

# Add project root to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from wrapper.models import LLMModelConfig
from utils.connection_handler import gandalf_connection_handler
from utils.load_config import init_connections


async def run_alembic_upgrade():
    """
    Run Alembic migrations to upgrade the database schema.
    
    This function executes the 'alembic upgrade head' command to apply all
    pending migrations to the database, bringing it to the latest schema version.
    """
    print("Running Alembic migrations...")
    os.system("alembic upgrade head")
    print("Alembic migrations completed successfully")


async def add_model_configs():
    """
    Add initial model configurations to the database.
    
    This function seeds the database with predefined LLM model configurations.
    It checks for existing configurations by name to avoid duplicates and
    uses the application's connection handling mechanisms for database operations.
    
    The configurations include models from various providers like OpenAI, Anthropic,
    and their respective parameters such as token limits, capabilities, and API details.
    """
    print("Adding model configurations...")

    # Initialize connections if not already initialized
    await init_connections()

    # Define model configurations
    model_configs = [
        {
            "name": "Claude 3.5 Sonnet", "slug": "claude-3-5-sonnet-20240620",
            "engine": "claude-3-5-sonnet-20240620", "api_key_name": "claude_key",
            "icon": "openai_icon_svg", "enabled": True, "rank": 5, "accept_image": True,
            "max_tokens": 8192, "provider": "anthropic", "base_url": "", "is_premium": False
        },
        {
            "name": "o1", "slug": "gpt-o1", "engine": "o1",
            "api_key_name": "openai_key", "icon": "openai_icon_svg",
            "enabled": True, "rank": 2, "accept_image": False, "max_tokens": 16384,
            "provider": "openai-o1", "base_url": "", "is_premium": False
        },
        {
            "name": "Claude 3 Opus", "slug": "claude-3-opus-20240229",
            "engine": "claude-3-opus-20240229", "api_key_name": "claude_key",
            "icon": "openai_icon_svg", "enabled": True, "rank": 9, "accept_image": True,
            "max_tokens": 4096, "provider": "anthropic", "base_url": "", "is_premium": False
        },
        {
            "name": "Gpt-4o", "slug": "gpt-4o", "engine": "gpt-4o",
            "api_key_name": "openai_key", "icon": "openai_icon_svg",
            "enabled": True, "rank": 0, "accept_image": True, "max_tokens": 16384,
            "provider": "openai", "base_url": "", "is_premium": False
        },
        {
            "name": "Gpt-4o mini", "slug": "gpt-4o-mini", "engine": "gpt-4o-mini",
            "api_key_name": "openai_key", "icon": "openai_icon_svg",
            "enabled": True, "rank": 1, "accept_image": False, "max_tokens": 16384,
            "provider": "openai", "base_url": "", "is_premium": False
        },
        {
            "name": "o1-mini", "slug": "gpt-o1-mini", "engine": "o1-mini",
            "api_key_name": "openai_key", "icon": "openai_icon_svg",
            "enabled": True, "rank": 4, "accept_image": False, "max_tokens": 16384,
            "provider": "openai-o1", "base_url": "", "is_premium": False
        },
        {
            "name": "o1-preview", "slug": "gpt-o1-preview", "engine": "o1-preview",
            "api_key_name": "openai_key", "icon": "openai_icon_svg",
            "enabled": True, "rank": 3, "accept_image": False, "max_tokens": 16384,
            "provider": "openai-o1", "base_url": "", "is_premium": False
        }
    ]

    # Use the gandalf_connection_handler context manager
    async with gandalf_connection_handler() as connection_handler:
        try:
            # Add model configurations to the database
            for config in model_configs:
                # Check if model config already exists by name using ORM
                query = select(LLMModelConfig).where(LLMModelConfig.slug == config["slug"])
                result = await connection_handler.session.execute(query)
                existing = result.scalars().first()

                if existing:
                    print(f"Model config with name '{config['slug']}' already exists, skipping...")
                    continue

                model_config = LLMModelConfig(**config)
                connection_handler.session.add(model_config)

            # Commit changes
            await connection_handler.session_commit()
            print("Model configurations added successfully")

        except Exception as e:
            await connection_handler.session.rollback()
            print(f"Error adding model configurations: {e}")
            raise


async def main():
    """
    Main function to run startup tasks based on command line arguments.
    
    This function parses command line arguments and executes the requested
    database operations. It supports running migrations, seeding data, or both.
    If no arguments are provided, it displays the help message.
    
    Command line arguments:
        --migrate: Run database migrations
        --seed: Seed initial model configurations
        --all: Run both migrations and seeding
    """
    parser = argparse.ArgumentParser(description="Database setup and initialization script")
    parser.add_argument("--migrate", action="store_true", help="Run database migrations")
    parser.add_argument("--seed", action="store_true", help="Seed initial model configurations")
    parser.add_argument("--all", action="store_true", help="Run both migrations and seeding")

    args = parser.parse_args()

    # If no arguments provided, show help
    if not (args.migrate or args.seed or args.all):
        parser.print_help()
        return

    # Run migrations if --migrate or --all flag is provided
    if args.migrate or args.all:
        await run_alembic_upgrade()

    # Add model configs if --seed or --all flag is provided
    if args.seed or args.all:
        await add_model_configs()

    print("Requested startup tasks completed successfully")


if __name__ == "__main__":
    asyncio.run(main())