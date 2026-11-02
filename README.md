# OmniScribe Studio (Codename: DaoForge)

Autonomous Multi-Agent Literary Engine, World-Building Knowledge Graph, and Reinforcement Learning Manuscript Suite for Professional Novelists.

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Microservices Breakdown](#microservices-breakdown)
  - [1. shared-core](#1-serviceshared-core)
  - [2. core-gateway](#2-servicescore-gateway)
  - [3. ingestion-scraper](#3-servicesingestion-scraper)
  - [4. translation-pipeline](#4-servicestranslation-pipeline)
  - [5. agent-swarm](#5-servicesagent-swarm)
  - [6. manuscript-editor](#6-servicesmanuscript-editor)
  - [7. rag-lore-engine](#7-servicesrag-lore-engine)
  - [8. model-trainer](#8-servicesmodel-trainer)
- [Supported Genres, Categories, and Uncensored Writing](#supported-genres-categories-and-uncensored-writing)
- [Multi-Format File Ingestion and Scalable Web Scraping](#multi-format-file-ingestion-and-scalable-web-scraping)
- [Reinforcement Learning and 15-Dimension Trait DNA Engine](#reinforcement-learning-and-15-dimension-trait-dna-engine)
- [Open Source Models for Novel Writing and Translation](#open-source-models-for-novel-writing-and-translation)
- [User Interfaces: Flutter UI and Angular Desktop UI](#user-interfaces-flutter-ui-and-angular-desktop-ui)
- [Prerequisites and uv Environment Setup](#prerequisites-and-uv-environment-setup)
- [Docker Services and Volume Management](#docker-services-and-volume-management)
- [Running the Test Suite](#running-the-test-suite)
- [API Reference](#api-reference)
- [License](#license)

---

## Overview

OmniScribe Studio is an enterprise-grade AI literary ecosystem and microservice workspace designed specifically for authors, web-novel writers, and translators. It solves the critical limitations of standard chatbots when writing long-form novels:

1. **Genre Mastery Across All Themes:** Full native support for Xianxia, Wuxia, Xuanhuan, Western Fantasy, LitRPG/Progression, Cyberpunk, Steampunk, Sci-Fi, Romance, Historical Fiction, Urban Supernatural, Horror, Mystery/Thriller, and Dark/Mature Fiction.
2. **Zero Chatbot Cliches:** Strips em-dashes (`—`), semicolons (`;`), and repetitive assistant phrasing (`a testament to`, `a shiver ran down his spine`, `couldn't help but`) via grammar and AST scrubbers.
3. **Reinforced Personality Evolution (Trait DNA):** Writing agents are not static system prompts. Each agent is governed by a 15-dimension numerical trait vector that dynamically generates prompting instructions and continuously self-tunes via author feedback and implicit edit distance.
4. **Universal Ingestion and Anti-Duplication:** Parses files from local systems (`.epub`, `.pdf`, `.docx`, `.md`, `.txt`, and raw chapter folders) and scrapes web novels from sources like Twkan, 69shuba, WTR-Lab, OpenNovel, and Project Gutenberg with automated DOM noise removal and deduplication.
5. **Continuous Model Training and Fine-Tuning:** Transforms accepted prose, polished chapters, and crawled web novels into continuation instruction datasets with automated scripts for 4-bit QLoRA fine-tuning with Unsloth.
6. **Granular Paragraph Versioning:** Every paragraph has individual version tracking, diff calculation, and one-click rollback to prevent deadlock during editing.
7. **No Content Restrictions:** Dedicated uncensored model routing (`Nyx 14B`, `Dolphin Mistral-Nemo 12B`) guarantees that gritty battles, dark horror, visceral descriptions, and mature themes remain unneutered.

---

## System Architecture

OmniScribe Studio is architected as an event-driven microservices workspace powered by Python 3.12, Astral `uv`, Redis 7.4 Streams, PostgreSQL 16 (with automatic zero-config SQLite failover), Neo4j 5 Graph Database, and Qdrant Vector Search.

```text
+-----------------------------------------------------------------------------------+
|                           Client Applications & UIs                               |
|   - Angular 19 + Tauri Desktop UI (Parchment, Dark Obsidian, Neutral Grey Modes)   |
|   - Flutter Cross-Platform UI (Desktop, Tablet, and Mobile Access)                |
+-----------------------------------------------------------------------------------+
                                         |
                                         v  WebSocket / REST API
+-----------------------------------------------------------------------------------+
|                        Core Gateway (services/core-gateway)                       |
|   - FastAPI High-Throughput HTTP REST Router                                      |
|   - Non-Blocking WebSocket Multiplexer (/ws/studio, /ws/telemetry)                |
+-----------------------------------------------------------------------------------+
                                         |
                                         v  Redis Streams & Pub/Sub
+-----------------------------------------------------------------------------------+
|                           Independent Microservices                               |
|                                                                                   |
|  +--------------------+  +--------------------+  +--------------------+           |
|  | ingestion-scraper  |  | translation-pipe   |  |   manuscript-editor|           |
|  | - EPUB/PDF/DOCX/MD |  | - Dao-9B raw MTL   |  | - Paragraph Diffs  |           |
|  | - Web Scrapers     |  | - Term glossary    |  | - Anti-Cliche      |           |
|  | - SHA256 Dedupe    |  | - Parallel batch   |  | - Deadlock check   |           |
|  +--------------------+  +--------------------+  +--------------------+           |
|                                                                                   |
|  +--------------------+  +--------------------+  +--------------------+           |
|  |    agent-swarm     |  |  rag-lore-engine   |  |    model-trainer   |           |
|  | - 15-Dim Trait DNA |  | - Neo4j GraphRAG   |  | - QLoRA Fine-Tune  |           |
|  | - Dynamic Prompts  |  | - Vector Memory    |  | - Unsloth 4-bit    |           |
|  | - RL Feedback Bus  |  | - Entity Tracker   |  | - Dataset builder  |           |
|  +--------------------+  +--------------------+  +--------------------+           |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                     Shared Storage & Engine Infrastructure                        |
|   - Relational: PostgreSQL 16 (Primary) + data/trait_engine/traits.db (SQLite)     |
|   - Knowledge Graph: Neo4j 5 (Character Profiles, Relationships, Sect Factions)   |
|   - Semantic Vector Store: Qdrant (Lore chunks, Scene embeddings, 1024-dim)       |
|   - Event & Message Bus: Redis 7.4 (Pub/Sub & Telemetry Streams)                  |
|   - FlareSolverr: Cloudflare / Anti-Bot Bypass for Protected Web Ingestion        |
+-----------------------------------------------------------------------------------+
```

---

## Microservices Breakdown

### 1. `services/shared-core`
The foundational layer shared across all microservices:
- **`enterprise_database_service.py`**: Manages unified connection pools for PostgreSQL, Neo4j, Qdrant, and Redis. Automatically detects database availability and falls back to local SQLite (`data/trait_engine/traits.db`) when external engines are offline.
- **`config.py`**: Centralized configuration management using Pydantic Settings reading from environment variables or `.env`.
- **Telemetry Bus**: Broadcasts real-time events, progress updates, and agent status messages to Redis pub/sub.

### 2. `services/core-gateway`
The unified entry point for client applications:
- **REST Endpoints**: Chapter ingestion, full-novel translation triggers, plotline planning, character profile generation, and model training invocation.
- **WebSocket Hub**: Supports non-blocking multiplexed bidirectional communication. Authors can continue prompting, editing, and dispatching tasks while agents compute in the background.

### 3. `services/ingestion-scraper`
Handles raw text ingestion and web crawling:
- **Local File Parsers**: Ingests `.epub`, `.pdf`, `.docx`, `.md`, and `.txt` files with metadata preservation.
- **Deduplication Engine**: Uses SHA-256 fingerprinting and semantic similarity to prevent duplicate paragraphs or chapters from contaminating the corpus.
- **Scalable Web Scrapers**: Dedicated site adapters for platforms such as Twkan, 69shuba, WTR-Lab, OpenNovel, and Project Gutenberg. Integrated with FlareSolverr for Cloudflare-protected sites.

### 4. `services/translation-pipeline`
Specialized translation and raw MTL polishing:
- Powered by `Dao-9B` and local LLM backends.
- Retains authentic genre terminology (Daoist concepts, cultivation realms, martial stances, cyberpunk slang).
- Processes large manuscripts in parallel paragraph batches with glossaries to ensure name consistency across chapters.

### 5. `services/agent-swarm`
The multi-agent writer's room and RL orchestration engine:
- **`trait_engine.py`**: Manages 15-dimension personality vectors for each agent.
- **`dynamic_prompt_builder.py`**: Compiles numerical trait vectors into real-time behavioral directives.
- **`topic_router.py`**: Directs requests to specialized agents based on genre and narrative context.
- **`feedback_engine.py`**: Adjusts trait vectors using explicit ratings (`/rate good`, `/rate bad`) and implicit author edits (Levenshtein edit distance).

### 6. `services/manuscript-editor`
Granular manuscript operations:
- Paragraph-by-paragraph version history with instant rollback.
- Anti-cliche filtering that strips em-dashes, semicolons, and formulaic chatbot phrases.
- Deadlock-free writing and editing pipelines.

### 7. `services/rag-lore-engine`
World-building and narrative continuity:
- **Neo4j Knowledge Graph**: Stores character profiles, faction hierarchies, realm progressions, and relationship graphs.
- **Qdrant Vector Store**: Semantic indexing of previous chapters for context retrieval.
- **Lore Auditor**: Detects continuity flaws, contradictory character actions, and broken plotlines before text is finalized.

### 8. `services/model-trainer`
Continuous reinforcement and model customization:
- Converts ingested chapters and accepted author edits into instruction-following JSONL datasets.
- Generates reproducible Unsloth 4-bit QLoRA training scripts.
- Supports incremental fine-tuning on local GPUs.

---

## Supported Genres, Categories, and Uncensored Writing

OmniScribe Studio includes built-in knowledge bases, prompt templates, and agent personalities for:

| Category | Primary Focus & Archetypes |
|---|---|
| **Xianxia & Cultivation** | Qi condensation, golden cores, tribulation lightning, daoist philosophy, sect politics. |
| **Wuxia & Martial Arts** | Jianghu honor codes, meridian pathways, weapon styles, martial arts tournaments. |
| **Western & Epic Fantasy** | High magic systems, medieval geopolitics, dungeon mechanics, mythical beasts. |
| **Cyberpunk & Sci-Fi** | Megacorporations, cyberware, netrunning, dystopian urban landscapes, orbital colonies. |
| **Steampunk & Victorian** | Clockwork automation, steam-powered locomotives, Victorian etiquette, alchemical societies. |
| **Romance & Drama** | Slow-burn character arcs, emotional tension, dialogue subtext, relationship dynamics. |
| **Horror & Supernatural** | Psychological dread, eldritch deities, visceral atmosphere, investigative pacing. |
| **Dark & Mature Fiction** | Unfiltered gritty combat, high-stakes moral dilemmas, uncensored narrative freedom. |

---

## Multi-Format File Ingestion and Scalable Web Scraping

OmniScribe Studio processes local documents and online novels with high throughput:

### Local File Formats
- **EPUB (`.epub`)**: Parses spine items, removes CSS and boilerplate tags, extracts clean chapter headings and body paragraphs.
- **PDF (`.pdf`)**: Extracts continuous multi-page prose while repairing broken line wraps and stripping headers and footers.
- **Word (`.docx`)**: Preserves heading hierarchies and extracts styled paragraphs.
- **Markdown (`.md`) and Text (`.txt`)**: Splits chapters using regex heuristics (`Chapter \d+`, `第.+章`).

### Scalable Web Novel Scraping
The `ingestion-scraper` service includes dedicated adapters for major web-novel sites:
- **Twkan (`twkan.com`)**: Optimized CSS selector extraction with automatic advertisement scrubbing.
- **69shuba (`69shuba.com`)**: GBK encoding decoding, removal of pagination watermarks and reading reminders.
- **WTR-Lab (`wtr-lab.com`)**: Ingests raw machine translations and translated web-novel chapters.
- **OpenNovel (`opennovel.co`)**: Modern HTML container extraction with ad-slot filtering.
- **Project Gutenberg (`gutenberg.org`)**: Strips Gutenberg legal license headers and footers for public domain training text.

### Scraping Architecture
```text
URL Input ---> Domain Resolver ---> FlareSolverr (if Cloudflare active)
                     |
                     v
             BeautifulSoup HTML Parser
                     |
       +-------------+-------------+
       v                           v
Title Extractor             Noise Decomposer
(h1, h2, custom)        (ads, scripts, nav, footers)
       |                           |
       +-------------+-------------+
                     v
          Paragraph Text Extractor
                     |
                     v
          Watermark & Ad Scrubber
                     |
                     v
       SHA-256 Deduplication Check
                     |
                     v
   Stored to SQLite / Postgres & Datasets
```

---

## Reinforcement Learning and 15-Dimension Trait DNA Engine

Every writing agent in OmniScribe Studio is governed by a **15-dimension numerical personality vector** normalized between `0.0` and `1.0`. These vectors evolve dynamically based on how the author interacts with the generated prose.

### The 15 Trait Dimensions
1. **`pacing`**: Fast kinetic progression vs. slow atmospheric world-building.
2. **`dialogue_ratio`**: Heavy character interaction vs. dense narrative exposition.
3. **`sensory_detail`**: Vivid visual/auditory/olfactory immersion level.
4. **`combat_grit`**: Visceral, bone-crunching choreography vs. abstract power scaling.
5. **`poeticism`**: Flowing metaphorical prose vs. sharp minimalist economy.
6. **`archaism`**: Classical phrasing and archaic vocabulary vs. contemporary style.
7. **`darkness`**: Bleak themes, psychological weight, and mature stakes.
8. **`verbosity`**: Descriptive paragraph length and elaboration.
9. **`emotional_resonance`**: Deep internal character monologue and psychological stakes.
10. **`comedic_undertone`**: Satirical wit and comedic relief vs. strict solemnity.
11. **`mystery_suspense`**: Cryptic foreshadowing and delayed exposition.
12. **`philosophical_depth`**: Exploration of Daoist, existential, or ideological themes.
13. **`formality`**: Polished courtly etiquette vs. colloquial speech.
14. **`metaphor_frequency`**: Density of symbolic imagery and analogical descriptions.
15. **`ruthlessness`**: Decisive, proactive protagonist actions vs. merciful hesitation.

### Evolution Mechanisms
- **Explicit Feedback**: When an author clicks `+1 /rate good` or `-1 /rate bad`, the associated agent's traits shift by calibrated deltas (+0.03 / -0.03).
- **Implicit Feedback (Edit Distance)**: If an author significantly shortens an agent's output, `verbosity` decreases automatically. If the author inserts archaic vocabulary, `archaism` increments.
- **Boundary Enforcement**: Every agent has defined `[floor, ceiling]` constraints preventing extreme drift.
- **Audit Logging**: Every trait evolution is recorded in `data/trait_engine/trait_evolution_log.jsonl` with timestamps and causal reasons.

---

## Open Source Models for Novel Writing and Translation

OmniScribe Studio is built to run entirely on local GPUs via **vLLM**, **Ollama**, or **LiteLLM**. Recommended open-source weights:

| Model ID | Optimal Role | Recommended Precision | Context Length |
|---|---|---|---|
| **Dao-9B** | Chinese Xianxia/Wuxia to English Raw Translation | 4-bit / 8-bit GGUF, BF16 | 8K - 16K |
| **Qwen-2.5-14B-Instruct** | General Prose, Chapter Planning, World-Building | Q4_K_M / Q8_0 GGUF, AWQ | 32K - 128K |
| **Qwen-2.5-7B-Instruct** | Fast Scene Drafting and Dialogue Generation | 4-bit GGUF, EXL2 | 32K |
| **Dolphin-2.9.2-Mistral-Nemo-12B** | Uncensored Dark Fantasy, Horror, Mature Themes | Q5_K_M GGUF, AWQ | 16K - 32K |
| **Command-R / Command-R+ (35B-104B)** | Extended Context Continuity Auditing and Plot RAG | Q4_K_M GGUF | 128K |
| **BGE-Large-EN-v1.5 / BGE-M3** | Dense Vector Embeddings for Qdrant Lore Retrieval | FP16, INT8 | 8K |

To use any local model, specify its endpoint in `.env`:
```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
DEFAULT_PROSE_MODEL=openai/qwen2.5:14b
TRANSLATION_MODEL=openai/dao-9b
UNCENSORED_MODEL=openai/dolphin-mistral-nemo:12b
```

---

## User Interfaces: Flutter UI and Angular Desktop UI

OmniScribe Studio provides two frontend implementations:

### 1. Angular 19 Desktop Interface (`frontend-angular`)
- Built with Angular 19 and Tauri for lightweight desktop deployment.
- Three custom themes: **Light Parchment**, **Dark Obsidian**, and **Neutral Grey Studio**.
- Split-screen workspace: Left pane for versioned paragraph editing with instant undo; right pane for multi-agent parallel chat.
- Collapsible bottom drawer for live telemetry and WebSocket progress logs.
- Zero emojis across all UI components for a distraction-free writing environment.

### 2. Flutter Cross-Platform UI
- Designed for tablet, mobile, and lightweight desktop environments.
- Direct WebSocket and REST connection to the `core-gateway` at port 8000.
- Touch-friendly paragraph cards and quick trait feedback buttons.

---

## Prerequisites and uv Environment Setup

### System Requirements
- **Operating System**: Windows 10/11, Ubuntu 22.04+, or macOS Sonoma+
- **Python**: Version 3.12 or higher
- **Package Manager**: [Astral `uv`](https://docs.astral.sh/uv/) (v0.5.0 or newer)
- **Docker & Docker Compose**: For PostgreSQL, Neo4j, Qdrant, Redis, and FlareSolverr
- **Node.js**: Version 20+ (for Angular frontend)

### Installation Steps

1. **Install Astral `uv`**:
   - On Windows (PowerShell):
     ```powershell
     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
     ```
   - On Linux / macOS:
     ```bash
     curl -LsSf https://astral.sh/uv/install.sh | sh
     ```

2. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/omniscribe-studio.git
   cd omniscribe-studio
   ```

3. **Install Python 3.12 and Sync the Workspace**:
   ```bash
   uv python pin 3.12
   uv sync
   ```
   This command installs all required libraries across all eight microservices within a single coordinated virtual environment (`.venv`).

4. **Verify Installation**:
   ```bash
   uv run pytest -k "test_anti_cliche_and_punctuation_scrubber or test_site_specific_extractors"
   ```

---

## Docker Services and Volume Management

OmniScribe Studio includes a production `docker-compose.yml` defining the supporting infrastructure services.

### Start All Services
```bash
docker compose up -d
```

### Services Included
| Service | Image | Internal Port | Host Port | Purpose |
|---|---|---|---|---|
| **postgres** | `postgres:16-alpine` | 5432 | 5432 | Primary relational store for Agent Trait DNA, chapters, and edit history. |
| **neo4j** | `neo4j:5.24-community` | 7474, 7687 | 7474, 7687 | Graph database for character profiles, sect relationships, and lore trees. |
| **qdrant** | `qdrant/qdrant:v1.12.0` | 6333, 6334 | 6333, 6334 | Vector database for scene retrieval and semantic memory. |
| **redis** | `redis:7.4-alpine` | 6379 | 6379 | Pub/sub message bus and live progress telemetry streaming. |
| **flaresolverr** | `ghcr.io/flaresolverr/flaresolverr:latest` | 8191 | 8191 | Cloudflare bypass proxy for web scraping. |

### Volume Isolation
All persistent state is stored in the local `./data` directory:
- `./data/postgres`: PostgreSQL database files.
- `./data/neo4j`: Graph database nodes, relationships, and logs.
- `./data/qdrant`: Vector index files.
- `./data/redis`: Redis append-only files (AOF).
- `./data/trait_engine`: Local SQLite database (`traits.db`) and evolution logs (`trait_evolution_log.jsonl`).
- `./data/training_datasets`: Fine-tuning datasets generated by `model-trainer`.
- `./data/lora_adapters`: Output directory for trained LoRA weights.

All database files and training artifacts inside `./data` are strictly excluded from version control via `.gitignore`.

---

## Running the Test Suite

The test suite validates database failover, trait evolution bounds, dynamic prompt compilation, anti-cliche scrubbing, and site-specific web novel scrapers.

```bash
# Run all tests
uv run pytest -v

# Run only scraper and anti-cliche tests
uv run pytest -k "test_anti_cliche_and_punctuation_scrubber or test_site_specific_extractors"

# Run with verbose output and no warnings suppression
uv run pytest -v -W ignore::DeprecationWarning
```

---

## API Reference

### Health and Status
- `GET /health`
  Returns the health status of all database engines, message queues, and registered agents.

### Ingestion and Scraping
- `POST /api/v1/ingest/file`
  Upload an `.epub`, `.pdf`, `.docx`, `.md`, or `.txt` file for parsing and deduplicated chapter extraction.
- `POST /api/v1/ingest/web`
  Scrape a chapter or full novel from a URL (Twkan, 69shuba, WTR, OpenNovel, Gutenberg).

### Translation Pipeline
- `POST /api/v1/translate/chapter`
  Translates or polishes a raw chapter using `Dao-9B` with term glossaries and parallel paragraph processing.

### Multi-Agent Council
- `POST /api/v1/agent/chat`
  Send a message to the agent council or target a specific specialist (`@kael_blades`, `@nyx_unfiltered`).
- `POST /api/v1/agent/rate`
  Submit feedback on an agent's response to evolve its 15-dimension Trait DNA vector.
- `WebSocket /ws/studio`
  Multiplexed real-time bidirectional agent chat and editing channel.
- `WebSocket /ws/telemetry`
  Live telemetry stream reporting progress for scrapers, translators, and training jobs.

### Model Training
- `POST /api/v1/trainer/export-dataset`
  Build an instruction fine-tuning dataset from a collection of chapters.
- `POST /api/v1/trainer/trigger-qlora`
  Generate and trigger an Unsloth 4-bit QLoRA fine-tuning job for local 7B-15B models.

---

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for complete details.
