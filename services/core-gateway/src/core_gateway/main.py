# omniscribe-studio/services/core-gateway/src/core_gateway/main.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select

from agent_swarm.feedback_engine import feedback_engine
from agent_swarm.orchestrator import swarm_orchestrator
from agent_swarm.trait_engine import trait_engine
from ingestion_scraper.parser_and_scraper import ingestion_service
from manuscript_editor.editor_engine import manuscript_editor
from model_trainer.unsloth_trainer import incremental_trainer
from rag_lore_engine.lore_auditor import lore_engine
from shared_core.enterprise_database_service import AgentTraitModel, db_service
from translation_pipeline.translator import dao_translator


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    await db_service.initialize()
    await trait_engine.seed_default_agents()
    yield


app = FastAPI(
    title="OmniScribe Studio API Gateway (DaoForge)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------
class ChatSubmissionRequest(BaseModel):
    session_id: str = "default-session"
    message: str
    genre: str = "xianxia"
    lore_context: str = ""


class DirectoryIngestRequest(BaseModel):
    project_id: str
    directory_path: str
    explicit_genre: str | None = None
    auto_translate_raws: bool = True


class WebScrapeRequest(BaseModel):
    project_id: str
    url: str
    use_flaresolverr: bool = True
    translate_if_raw: bool = True


class ChapterEditRequest(BaseModel):
    project_id: str
    chapter_id: str
    paragraphs: list[str]
    instruction: str = "Polish grammar and elevate into authentic Wuxia/Xianxia prose."
    genre_tag: str = "xianxia"
    use_uncensored_model: bool = False
    author_agent_id: str = "grandmaster_lin"


class UndoParagraphRequest(BaseModel):
    project_id: str
    chapter_id: str
    paragraph_index: int
    target_version: int | None = None


class ImplicitEditFeedbackRequest(BaseModel):
    agent_id: str
    agent_draft: str
    author_final_text: str


class CharacterProfileRequest(BaseModel):
    project_id: str
    name: str
    realm_or_rank: str
    traits: list[str] = Field(default_factory=list)
    faction: str = "Independent"
    relationships: list[dict[str, str]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "online",
        "codename": "DaoForge",
        "sqlite_fallback_active": db_service.using_sqlite_fallback,
        "neo4j_connected": db_service.neo4j_driver is not None,
        "qdrant_connected": db_service.qdrant_client is not None,
        "redis_connected": db_service.redis_client is not None,
    }


@app.get("/api/agents")
async def list_agents_and_traits() -> list[dict[str, Any]]:
    async with db_service.session() as session:
        res = await session.execute(select(AgentTraitModel))
        agents = res.scalars().all()
        return [
            {
                "agent_id": a.agent_id,
                "name": a.agent_name,
                "role_category": a.role_category,
                "model": a.model_identifier,
                "traits": a.traits_json,
                "affinities": a.topic_affinities,
            }
            for a in agents
        ]


@app.post("/api/chat/send")
async def send_non_blocking_chat(req: ChatSubmissionRequest) -> dict[str, Any]:
    """Dispatches non-blocking parallel agent execution while keeping chat input open."""
    return await swarm_orchestrator.submit_user_message(
        session_id=req.session_id,
        user_message=req.message,
        explicit_genre=req.genre,
        lore_context=req.lore_context,
    )


@app.post("/api/ingest/directory")
async def ingest_local_directory(req: DirectoryIngestRequest) -> dict[str, Any]:
    chapters = await ingestion_service.ingest_directory(
        directory_path=req.directory_path,
        project_id=req.project_id,
        explicit_genre=req.explicit_genre,
    )
    output_chapters = []
    for ch in chapters:
        paras = ch.paragraphs
        if ch.is_non_english_raw and req.auto_translate_raws:
            paras = await dao_translator.translate_chapter_paragraphs(
                paras, genre_tag=ch.detected_genres[0]
            )
        output_chapters.append(
            {
                "chapter_index": ch.chapter_index,
                "title": ch.title,
                "genres": ch.detected_genres,
                "was_translated": ch.is_non_english_raw and req.auto_translate_raws,
                "paragraphs": paras,
            }
        )
    return {"project_id": req.project_id, "chapters": output_chapters}


@app.post("/api/ingest/web")
async def scrape_web_novel_chapter(req: WebScrapeRequest) -> dict[str, Any]:
    chapter = await ingestion_service.fetch_web_chapter(
        url=req.url, use_flaresolverr=req.use_flaresolverr
    )
    paras = chapter.paragraphs
    if chapter.is_non_english_raw and req.translate_if_raw:
        paras = await dao_translator.translate_chapter_paragraphs(
            paras, genre_tag=chapter.detected_genres[0]
        )
    await incremental_trainer.export_genre_dataset(
        genre_tag=chapter.detected_genres[0], paragraphs=paras
    )
    return {
        "title": chapter.title,
        "url": req.url,
        "genres": chapter.detected_genres,
        "is_raw": chapter.is_non_english_raw,
        "paragraphs": paras,
    }


@app.post("/api/editor/process-chapter")
async def process_chapter_paragraphs(req: ChapterEditRequest) -> dict[str, Any]:
    results = await manuscript_editor.process_chapter_in_parallel(
        project_id=req.project_id,
        chapter_id=req.chapter_id,
        paragraphs=req.paragraphs,
        instruction=req.instruction,
        genre_tag=req.genre_tag,
        use_uncensored_model=req.use_uncensored_model,
        author_agent_id=req.author_agent_id,
    )
    return {"project_id": req.project_id, "chapter_id": req.chapter_id, "paragraphs": results}


@app.post("/api/editor/undo-paragraph")
async def undo_paragraph(req: UndoParagraphRequest) -> dict[str, Any]:
    return await manuscript_editor.undo_paragraph_to_version(
        project_id=req.project_id,
        chapter_id=req.chapter_id,
        paragraph_index=req.paragraph_index,
        target_version=req.target_version,
    )


@app.post("/api/rl/implicit-feedback")
async def submit_implicit_edit_feedback(req: ImplicitEditFeedbackRequest) -> dict[str, Any]:
    updated = await feedback_engine.process_implicit_edit_distance(
        agent_id=req.agent_id,
        agent_draft=req.agent_draft,
        author_final_text=req.author_final_text,
    )
    return {"agent_id": req.agent_id, "updated_traits": updated}


@app.post("/api/lore/character")
async def save_character_profile(req: CharacterProfileRequest) -> dict[str, Any]:
    return await lore_engine.upsert_character_profile(
        project_id=req.project_id,
        name=req.name,
        realm_or_rank=req.realm_or_rank,
        traits=req.traits,
        faction=req.faction,
        relationships=req.relationships,
    )


@app.post("/api/lore/audit-and-predict")
async def audit_and_predict_plot(
    project_id: str, draft_text: str, genre_tag: str = "xianxia"
) -> dict[str, Any]:
    audit, predictions = await asyncio.gather(
        lore_engine.audit_chapter_continuity_and_development(project_id, draft_text, genre_tag),
        lore_engine.predict_next_chapters_and_plotline(project_id, draft_text[:1500], genre_tag),
    )
    return {"continuity_audit": audit, "plot_predictions": predictions}


# ---------------------------------------------------------------------------
# WebSocket Multiplexer (Parallel Chat Stream + Live Telemetry Log Box)
# ---------------------------------------------------------------------------
@app.websocket("/ws/stream")
async def websocket_multiplexer(websocket: WebSocket) -> None:
    await websocket.accept()
    if not db_service.redis_client:
        try:
            while True:
                await asyncio.sleep(5)
        except WebSocketDisconnect:
            return

    pubsub = db_service.redis_client.pubsub()
    await pubsub.subscribe("omniscribe:chat_stream", "omniscribe:telemetry_stream")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_json(
                    {
                        "channel": message["channel"],
                        "payload": message["data"],
                    }
                )
    except WebSocketDisconnect:
        await pubsub.unsubscribe("omniscribe:chat_stream", "omniscribe:telemetry_stream")