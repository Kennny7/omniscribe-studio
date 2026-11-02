# omniscribe-studio/services/manuscript-editor/pyproject.toml
[project]
name = "manuscript-editor"
version = "1.0.0"
description = "Parallel paragraph processor, Wuxia/Xianxia style enhancer, anti-cliche scrubber, and granular version control"
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