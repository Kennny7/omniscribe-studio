# omniscribe-studio/services/translation-pipeline/pyproject.toml
[project]
name = "translation-pipeline"
version = "1.0.0"
description = "Targeted Dao-9B / SLM parallel batch translator for Chinese Raws and MTL refinement"
requires-python = ">=3.12"
dependencies = [
    "shared-core",
    "litellm>=1.50.0",
    "tenacity>=9.0.0",
    "structlog>=24.4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"