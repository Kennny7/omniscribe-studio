# Contributing to OmniScribe Studio (DaoForge)

Thank you for contributing to **OmniScribe Studio**! Because this project uses an **Astral `uv` multi-package workspace**, adding new agents, scrapers, or LLM adapters is modular and straightforward.

---

## ðŸ› ï¸ Development Environment Setup

1. **Install `uv`:**
   ```bash
   curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

   docker compose up -d

   uv sync --all-packages


# Add agent

Adding a New Specialist Agent
Open services/agent-swarm/src/agent_swarm/registry.py.

Register your agent's default 15-dimension Trait DNA profile along with its [floor, ceiling] constraints.

Add its preferred local LLM tag (e.g., ollama/qwen2.5:14b or ollama/dao-9b) and initial topic affinity weights.

# Code quality testing
uv run ruff check .
uv run mypy services/
uv run pytest


---

### 4. Submodule 0: `services/shared-core` (Enterprise Database & Telemetry Layer)
To avoid duplicating database drivers and config logic across microservices, `shared-core` holds the **Multi-Engine Shared & Private Topology (`enterprise_database_service.py`)** and global settings.

#### `services/shared-core/pyproject.toml`
```toml
# omniscribe-studio/services/shared-core/pyproject.toml
[project]
name = "shared-core"
version = "1.0.0"
description = "Shared Enterprise Multi-Engine Database Service, Schemas, and Telemetry Bus"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.2",
    "sqlalchemy[asyncio]>=2.0.35",
    "asyncpg>=0.29.0",
    "aiosqlite>=0.20.0",
    "neo4j>=5.25.0",
    "qdrant-client>=1.12.0",
    "redis>=5.1.1",
    "structlog>=24.4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
