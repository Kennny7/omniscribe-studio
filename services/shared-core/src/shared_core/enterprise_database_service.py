# omniscribe-studio/services/shared-core/src/shared_core/enterprise_database_service.py
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis
import structlog
from neo4j import AsyncGraphDatabase, AsyncDriver
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from shared_core.config import settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Relational Models (PostgreSQL & SQLite Fallback Compatible)
# ---------------------------------------------------------------------------
class AgentTraitModel(Base):
    __tablename__ = "agent_traits"

    agent_id = Column(String(64), primary_key=True, index=True)
    agent_name = Column(String(128), nullable=False)
    role_category = Column(String(64), nullable=False)
    model_identifier = Column(String(128), nullable=False)
    traits_json = Column(JSON, nullable=False)       # Current 15 float values
    bounds_json = Column(JSON, nullable=False)       # {trait: {"floor": float, "ceiling": float}}
    topic_affinities = Column(JSON, nullable=False)  # {topic_tag: float}
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TraitEvolutionLogModel(Base):
    __tablename__ = "trait_evolution_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(64), index=True, nullable=False)
    trigger_channel = Column(String(32), nullable=False)  # explicit | implicit | inter_agent
    previous_traits = Column(JSON, nullable=False)
    new_traits = Column(JSON, nullable=False)
    delta_applied = Column(JSON, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ParagraphVersionModel(Base):
    """Git-like granular version control per paragraph for instant Undo/Redo."""
    __tablename__ = "paragraph_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(64), index=True, nullable=False)
    chapter_id = Column(String(64), index=True, nullable=False)
    paragraph_index = Column(Integer, index=True, nullable=False)
    version_number = Column(Integer, nullable=False)
    raw_content = Column(Text, nullable=False)
    styled_content = Column(Text, nullable=False)
    author_agent_id = Column(String(64), nullable=False)
    operation_type = Column(String(64), nullable=False)  # translate | polish | uncensored_rewrite
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Enterprise Multi-Engine Database Service
# ---------------------------------------------------------------------------
class EnterpriseDatabaseService:
    """
    Manages PostgreSQL (with automatic SQLite fallback), Neo4j Knowledge Graph,
    Qdrant Genre-Tagged Vector Store, and Redis Live Telemetry Streams.
    """

    def __init__(self) -> None:
        self.pg_engine: AsyncEngine | None = None
        self.sqlite_engine: AsyncEngine | None = None
        self.active_session_factory: async_sessionmaker[AsyncSession] | None = None
        self.using_sqlite_fallback: bool = False

        self.neo4j_driver: AsyncDriver | None = None
        self.qdrant_client: AsyncQdrantClient | None = None
        self.redis_client: aioredis.Redis | None = None

    async def initialize(self) -> None:
        """Initializes all database engines with automatic failover."""
        await self._init_relational_db()
        await self._init_redis()
        await self._init_neo4j()
        await self._init_qdrant()

    async def _init_relational_db(self) -> None:
        # Always prepare SQLite fallback in data/trait_engine/traits.db
        self.sqlite_engine = create_async_engine(settings.sqlite_dsn, echo=False)
        async with self.sqlite_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        try:
            self.pg_engine = create_async_engine(
                settings.postgres_dsn, pool_pre_ping=True, pool_size=10, max_overflow=20
            )
            async with self.pg_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                await conn.run_sync(Base.metadata.create_all)
            self.active_session_factory = async_sessionmaker(
                self.pg_engine, expire_on_commit=False
            )
            self.using_sqlite_fallback = False
            logger.info("relational_db.connected", engine="PostgreSQL")
        except Exception as exc:
            logger.warning(
                "relational_db.postgres_unavailable_using_sqlite_fallback",
                error=str(exc),
                fallback_path=str(settings.SQLITE_FALLBACK_PATH),
            )
            self.active_session_factory = async_sessionmaker(
                self.sqlite_engine, expire_on_commit=False
            )
            self.using_sqlite_fallback = True

    async def _init_redis(self) -> None:
        try:
            self.redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.redis_client.ping()
            logger.info("redis.connected", url=settings.REDIS_URL)
        except Exception as exc:
            logger.warning("redis.unavailable", error=str(exc))
            self.redis_client = None

    async def _init_neo4j(self) -> None:
        try:
            self.neo4j_driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            await self.neo4j_driver.verify_connectivity()
            await self._seed_agent_topology_graph()
            logger.info("neo4j.connected", uri=settings.NEO4J_URI)
        except Exception as exc:
            logger.warning("neo4j.unavailable", error=str(exc))
            self.neo4j_driver = None

    async def _init_qdrant(self) -> None:
        try:
            self.qdrant_client = AsyncQdrantClient(
                host=settings.QDRANT_HOST, port=settings.QDRANT_PORT
            )
            collections = await self.qdrant_client.get_collections()
            existing = {c.name for c in collections.collections}
            if settings.VECTOR_COLLECTION_NAME not in existing:
                await self.qdrant_client.create_collection(
                    collection_name=settings.VECTOR_COLLECTION_NAME,
                    vectors_config=qmodels.VectorParams(
                        size=settings.EMBEDDING_DIM, distance=qmodels.Distance.COSINE
                    ),
                )
            logger.info("qdrant.connected", collection=settings.VECTOR_COLLECTION_NAME)
        except Exception as exc:
            logger.warning("qdrant.unavailable", error=str(exc))
            self.qdrant_client = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provides a transactional relational session (Postgres or SQLite fallback)."""
        if not self.active_session_factory:
            await self._init_relational_db()
        assert self.active_session_factory is not None
        async with self.active_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def sync_to_sqlite_mirror(self, model_instance: Base) -> None:
        """Mirrors critical trait updates to local SQLite even when Postgres is primary."""
        if self.using_sqlite_fallback or not self.sqlite_engine:
            return
        sqlite_session_factory = async_sessionmaker(self.sqlite_engine, expire_on_commit=False)
        async with sqlite_session_factory() as s_session:
            await s_session.merge(model_instance)
            await s_session.commit()

    async def _seed_agent_topology_graph(self) -> None:
        """Seeds the core 4-tier Agent Supervisory & Specialist Network in Neo4j."""
        if not self.neo4j_driver:
            return
        cypher = """
        MERGE (director:Agent {id: 'director_alfred', name: 'Director Alfred', tier: 'Orchestrator'})
        MERGE (lead_editor:Agent {id: 'pip_continuity', name: 'Pip Continuity & Lore Reviewer', tier: 'Supervisor'})
        MERGE (wuxia_master:Agent {id: 'grandmaster_lin', name: 'Grandmaster Lin (Xianxia/Wuxia)', tier: 'Specialist'})
        MERGE (dark_weaver:Agent {id: 'nyx_unfiltered', name: 'Nyx (Dark/Mature/Uncensored)', tier: 'Specialist'})
        MERGE (combat_choreo:Agent {id: 'kael_blades', name: 'Kael (Combat & Action)', tier: 'SubAgent'})
        MERGE (dialogue_bard:Agent {id: 'lyra_voice', name: 'Lyra (Dialogue & Quotes)', tier: 'SubAgent'})

        MERGE (director)-[:MANAGES {weight: 1.0}]->(lead_editor)
        MERGE (lead_editor)-[:REVIEWS {weight: 0.95}]->(wuxia_master)
        MERGE (lead_editor)-[:REVIEWS {weight: 0.95}]->(dark_weaver)
        MERGE (wuxia_master)-[:COLLABORATES_WITH {weight: 0.9}]->(combat_choreo)
        MERGE (wuxia_master)-[:COLLABORATES_WITH {weight: 0.85}]->(dialogue_bard)
        MERGE (dark_weaver)-[:COLLABORATES_WITH {weight: 0.88}]->(dialogue_bard)
        """
        async with self.neo4j_driver.session() as session:
            await session.run(cypher)

    async def emit_live_telemetry(
        self, service: str, event_type: str, message: str, progress: float | None = None, metadata: dict[str, Any] | None = None
    ) -> None:
        """Publishes real-time progress logs to Redis for the Angular Live Tracker Drawer."""
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "event_type": event_type,
            "message": message,
            "progress": progress,
            "metadata": metadata or {},
        }
        logger.info("telemetry.emit", **payload)
        if self.redis_client:
            await self.redis_client.publish("omniscribe:telemetry_stream", json.dumps(payload))


db_service = EnterpriseDatabaseService()