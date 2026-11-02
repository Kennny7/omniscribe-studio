# OmniScribe Studio Architecture Deep Dive (Codename: DaoForge)

Comprehensive technical specification for OmniScribe Studio: polyglot persistence, non-blocking asynchronous multiplexing, 15-dimension Reinforcement Learning Trait DNA, and scalable web novel ingestion.

---

## 1. High-Level Architectural Flow

```mermaid
flowchart TD
    subgraph Clients["Presentation & Desktop Clients"]
        Angular["Angular 19 Desktop / Tauri UI"]
        Flutter["Flutter Cross-Platform Client"]
    end

    subgraph Gateway["Core Gateway Service (Port 8000)"]
        FastAPI["FastAPI REST API"]
        WSMux["WebSocket Stream Multiplexer (/ws/stream)"]
    end

    subgraph Bus["Message Bus & Streaming Queue"]
        RedisPub["Redis 7.4 Pub/Sub (chat_stream, telemetry_stream)"]
    end

    subgraph Services["Microservice Engine Ecosystem"]
        Ingest["ingestion-scraper (EPUB/PDF/DOCX/Web)"]
        Trans["translation-pipeline (Dao-9B Raw Polish)"]
        Editor["manuscript-editor (Paragraph Diff & Versioning)"]
        Swarm["agent-swarm (15-Dim Trait DNA & Council)"]
        Lore["rag-lore-engine (GraphRAG & Plot Audit)"]
        Trainer["model-trainer (Unsloth QLoRA 4-bit)"]
    end

    subgraph Storage["Storage & Persistence Target Switcher"]
        PG[("PostgreSQL 16 (Primary)")]
        SQLite[("Local SQLite Lite (traits.db Fallback)")]
        Neo[("Neo4j 5 Knowledge Graph")]
        Qdrant[("Qdrant Vector Database")]
    end

    Angular <-->|HTTP / WS| Gateway
    Flutter <-->|HTTP / WS| Gateway
    Gateway <--> RedisPub
    RedisPub <--> Services
    Services <--> Storage
```

---

## 2. Storage Mode Switching Architecture

OmniScribe Studio implements a dynamic persistence layer managed by `shared-core/enterprise_database_service.py`:

```mermaid
stateDiagram-v2
    [*] --> StartupDetection
    StartupDetection --> CheckDocker: Probing Docker Ports (5432, 7687, 6333, 6379)
    CheckDocker --> DockerMode: PostgreSQL & Services Reachable
    CheckDocker --> SQLiteFallback: Services Offline / Refused

    DockerMode --> ManualSwitchToLocal: Author clicks "Local Lite Mode" in UI
    ManualSwitchToLocal --> SQLiteFallback: Switches to data/trait_engine/traits.db

    SQLiteFallback --> ManualSwitchToDocker: Author clicks "Docker Services" in UI
    ManualSwitchToDocker --> DockerMode: Reconnects PG, Neo4j, Qdrant, Redis
```

---

## 3. Microservice Specifications

### `shared-core`
- **Location**: `services/shared-core`
- **Role**: Shared models, configuration, connection pool failover, and telemetry emission.
- **Failover Contract**: If PostgreSQL connection fails, seamlessly switches active session factory to `aiosqlite` at `data/trait_engine/traits.db` without crashing endpoints.

### `core-gateway`
- **Location**: `services/core-gateway`
- **Role**: High-throughput FastAPI hub. Exposes `/api/health`, `/api/settings/storage-mode`, chapter ingestion, parallel editing, and WebSocket multiplexing.

### `ingestion-scraper`
- **Location**: `services/ingestion-scraper`
- **Role**: Local file parsing (`.epub`, `.pdf`, `.docx`, `.md`, `.txt`) and web-scraping (Twkan, 69shuba, WTR-Lab, OpenNovel, Project Gutenberg) with Cloudflare bypass (FlareSolverr).

### `agent-swarm`
- **Location**: `services/agent-swarm`
- **Role**: 15-dimension Reinforcement Learning Trait DNA engine, topic routing, and multi-agent asynchronous writer's room.

### `manuscript-editor`
- **Location**: `services/manuscript-editor`
- **Role**: Paragraph-by-paragraph versioning, atomic rollbacks, anti-cliche scrubbing, and punctuation standardization.

### `rag-lore-engine`
- **Location**: `services/rag-lore-engine`
- **Role**: Character profiles, faction hierarchies, realm progressions, and plot continuity auditing via Neo4j and Qdrant.

### `model-trainer`
- **Location**: `services/model-trainer`
- **Role**: Incremental QLoRA instruction dataset export and automated training script generation for Unsloth.
