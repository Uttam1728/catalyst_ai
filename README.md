# Cerebrum AI Assistant

A FastAPI-based AI assistant application with integrations for multiple LLM providers and services.

## Overview

This application provides an AI assistant interface with support for:
- Multiple LLM providers (OpenAI, Claude, Groq)
- Database integration with PostgreSQL
- Authentication via Clerk
- Monitoring and logging capabilities
- Kubernetes deployment support

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis (optional)
- Docker (for containerized deployment)

### Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements/requirements.txt
   ```
3. Create a local configuration file:
   ```
   cp config/default.local.tmp.yaml config/default.local.yaml
   ```
4. Update the configuration with your API keys and database settings

### Database Setup

The application requires a PostgreSQL database. You can set up and initialize the database using the provided `startup.py` script:

```bash
# Run database migrations
python startup.py --migrate

# Seed initial model configurations
python startup.py --seed

# Run both migrations and seeding
python startup.py --all
```

This script will:
1. Apply all Alembic migrations to create or update the database schema
2. Seed the database with initial LLM model configurations for various providers (OpenAI, Anthropic, etc.)

### Running Locally

```bash
python entrypoint.py
```

## Configuration

Configuration is managed through YAML files in the `config/` directory. Environment-specific configurations are available:
- `default.local.yaml` - Local development
- `default.sit.yaml` - System Integration Testing
- `default.prod.yaml` - Production

## Database Migrations

Database migrations are managed with Alembic:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head
```

## Docker Deployment

Build and run the Docker container:

```bash
docker build -t cerebrum .
docker run -p 8081:80 cerebrum
```

## Testing

Run tests with:

```bash
./ci-test.sh
```

## License
