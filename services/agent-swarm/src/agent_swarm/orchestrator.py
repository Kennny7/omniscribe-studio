# omniscribe-studio/services/agent-swarm/src/agent_swarm/orchestrator.py
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import litellm
import structlog

from agent_swarm.dynamic_prompt_builder import DynamicPromptBuilder
from agent_swarm.feedback_engine import feedback_engine
from agent_swarm.topic_router import topic_router
from agent_swarm.trait_engine import trait_engine
from shared_core.config import settings
from shared_core.enterprise_database_service import AgentTraitModel, db_service

logger = structlog.get_logger(__name__)

MENTION_REGEX = re.compile(r"@([a-zA-Z0-9_]+)")


class SwarmOrchestrator:
    """
    Non-blocking parallel multi-agent message bus.
    Allows the author to send multiple overlapping tasks while agents collaborate,
    tag each other (@agent_id), and evolve their Trait DNA in the background.
    """

    def __init__(self) -> None:
        self._background_tasks: set[asyncio.Task[Any]] = set()

    async def submit_user_message(
        self,
        session_id: str,
        user_message: str,
        explicit_genre: str = "xianxia",
        lore_context: str = "",
    ) -> dict[str, Any]:
        """
        Immediately returns a task receipt so the UI chat never blocks,
        while spawning parallel agent execution in the background.
        """
        # Handle explicit RL rating commands (/rate good, /rate bad)
        if user_message.strip().startswith("/rate"):
            return await self._handle_explicit_rating_command(session_id, user_message)

        task_id = str(uuid.uuid4())
        primary_agent, cc_agents = await topic_router.route_query(user_message, explicit_genre)

        task = asyncio.create_task(
            self._execute_parallel_agent_turn(
                task_id=task_id,
                session_id=session_id,
                user_message=user_message,
                primary_agent=primary_agent,
                cc_agents=cc_agents,
                genre_tag=explicit_genre,
                lore_context=lore_context,
            )
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return {
            "task_id": task_id,
            "status": "dispatched_non_blocking",
            "primary_agent": primary_agent.agent_id,
            "cc_agents": [a.agent_id for a in cc_agents],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _handle_explicit_rating_command(
        self, session_id: str, command_text: str
    ) -> dict[str, Any]:
        parts = command_text.strip().split(maxsplit=3)
        # Format: /rate <good|bad> [agent_id] [comment]
        rating = parts[1] if len(parts) > 1 else "good"
        target_agent = parts[2] if len(parts) > 2 else "grandmaster_lin"
        comment = parts[3] if len(parts) > 3 else ""

        updated_traits = await feedback_engine.process_explicit_feedback(
            agent_id=target_agent, rating=rating, user_comment=comment
        )
        await self._broadcast_chat_event(
            session_id=session_id,
            sender_id="system_rl_engine",
            sender_name="Trait DNA Engine",
            content=f"Calibrated `{target_agent}` DNA via explicit `{rating}` feedback.",
            metadata={"updated_traits": updated_traits},
        )
        return {"status": "rating_applied", "agent_id": target_agent, "traits": updated_traits}

    async def _execute_parallel_agent_turn(
        self,
        task_id: str,
        session_id: str,
        user_message: str,
        primary_agent: AgentTraitModel,
        cc_agents: list[AgentTraitModel],
        genre_tag: str,
        lore_context: str,
    ) -> None:
        await db_service.emit_live_telemetry(
            service="agent-swarm",
            event_type="agent_turn_start",
            message=f"{primary_agent.agent_name} is drafting response (CC: {[a.agent_id for a in cc_agents]})",
            progress=0.15,
            metadata={"task_id": task_id},
        )

        # 1. Run Primary Specialist Agent
        primary_reply = await self._call_agent_llm(
            agent=primary_agent,
            user_prompt=(
                f"{user_message}\n\n"
                "If you need combat choreography, dialogue polish, or continuity checks, "
                "tag a peer at the end of your response using @kael_blades, @lyra_voice, "
                "@nyx_unfiltered, or @pip_continuity."
            ),
            genre_tag=genre_tag,
            lore_context=lore_context,
        )

        await self._broadcast_chat_event(
            session_id=session_id,
            sender_id=primary_agent.agent_id,
            sender_name=primary_agent.agent_name,
            content=primary_reply,
            metadata={"task_id": task_id, "role": "primary"},
        )

        # 2. Detect explicit @mentions in Primary Reply + combine with Topic Router CC list
        mentioned_ids = set(MENTION_REGEX.findall(primary_reply))
        collaborator_map: dict[str, AgentTraitModel] = {a.agent_id: a for a in cc_agents}

        for m_id in mentioned_ids:
            if m_id not in collaborator_map and m_id != primary_agent.agent_id:
                try:
                    collaborator_map[m_id] = await trait_engine.get_agent_dna(m_id)
                except Exception:
                    continue

        # 3. Fire Collaborator / Sub-Agent replies in parallel without blocking
        if collaborator_map:
            await asyncio.gather(
                *(
                    self._run_collaborator_followup(
                        task_id=task_id,
                        session_id=session_id,
                        collaborator=collab_agent,
                        primary_agent=primary_agent,
                        original_user_message=user_message,
                        primary_draft=primary_reply,
                        genre_tag=genre_tag,
                        lore_context=lore_context,
                    )
                    for collab_agent in collaborator_map.values()
                ),
                return_exceptions=True,
            )

        await db_service.emit_live_telemetry(
            service="agent-swarm",
            event_type="agent_turn_complete",
            message=f"Task {task_id[:8]} completed by council.",
            progress=1.0,
        )

    async def _run_collaborator_followup(
        self,
        task_id: str,
        session_id: str,
        collaborator: AgentTraitModel,
        primary_agent: AgentTraitModel,
        original_user_message: str,
        primary_draft: str,
        genre_tag: str,
        lore_context: str,
    ) -> None:
        collab_prompt = (
            f"Original Author Request: {original_user_message}\n\n"
            f"Draft/Response from @{primary_agent.agent_id}:\n{primary_draft}\n\n"
            f"As {collaborator.agent_name}, contribute your specialized enhancement, critique, "
            f"or scene expansion. Tag @{primary_agent.agent_id} directly in your response."
        )
        reply = await self._call_agent_llm(
            agent=collaborator,
            user_prompt=collab_prompt,
            genre_tag=genre_tag,
            lore_context=lore_context,
        )

        await self._broadcast_chat_event(
            session_id=session_id,
            sender_id=collaborator.agent_id,
            sender_name=collaborator.agent_name,
            content=reply,
            metadata={
                "task_id": task_id,
                "role": "collaborator",
                "replying_to": primary_agent.agent_id,
            },
        )

        # If Supervisor (Pip or Director Alfred) reviewed a specialist, trigger Inter-Agent RL
        if collaborator.role_category in {"supervisor", "orchestrator"}:
            await feedback_engine.process_inter_agent_review(
                reviewer_agent_id=collaborator.agent_id,
                target_agent_id=primary_agent.agent_id,
                continuity_score=0.88,
                style_score=0.85,
                review_notes=f"Automated peer check on task {task_id[:8]}",
            )

    async def _call_agent_llm(
        self,
        agent: AgentTraitModel,
        user_prompt: str,
        genre_tag: str,
        lore_context: str,
    ) -> str:
        system_prompt = DynamicPromptBuilder.build_system_prompt(
            agent=agent, genre_tag=genre_tag, lore_context=lore_context
        )
        try:
            response = await litellm.acompletion(
                model=agent.model_identifier,
                api_base=settings.LLM_BASE_URL,
                api_key=settings.LLM_API_KEY,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.75,
                max_tokens=1600,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("llm.fallback_simulated_response", agent=agent.agent_id, error=str(exc))
            return (
                f"[{agent.agent_name} - Offline/Simulated Mode ({agent.model_identifier})]: "
                f"Processed request in {genre_tag} style. Ready for local Ollama/vLLM connection."
            )

    async def _broadcast_chat_event(
        self,
        session_id: str,
        sender_id: str,
        sender_name: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "session_id": session_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        if db_service.redis_client:
            await db_service.redis_client.publish("omniscribe:chat_stream", json.dumps(event))


swarm_orchestrator = SwarmOrchestrator()