# omniscribe-studio/services/agent-swarm/src/agent_swarm/trait_engine.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from shared_core.config import settings
from shared_core.enterprise_database_service import (
    AgentTraitModel,
    TraitEvolutionLogModel,
    db_service,
)

# 15 Continuous Dimensions
TRAIT_DIMENSIONS: tuple[str, ...] = (
    "formality",
    "curiosity",
    "assertiveness",
    "warmth",
    "directness",
    "skepticism",
    "playfulness",
    "verbosity",
    "grimness",
    "poeticism",
    "archaism",
    "pacing_speed",
    "sensory_detail",
    "combat_brutality",
    "sensuality",
)


DEFAULT_AGENT_PROFILES: dict[str, dict[str, Any]] = {
    "director_alfred": {
        "name": "Director Alfred (Plot & Pacing Architect)",
        "role_category": "orchestrator",
        "model": settings.DEFAULT_PROSE_MODEL,
        "traits": {
            "formality": 0.80, "curiosity": 0.85, "assertiveness": 0.75, "warmth": 0.60,
            "directness": 0.85, "skepticism": 0.70, "playfulness": 0.25, "verbosity": 0.55,
            "grimness": 0.45, "poeticism": 0.50, "archaism": 0.40, "pacing_speed": 0.70,
            "sensory_detail": 0.65, "combat_brutality": 0.40, "sensuality": 0.30,
        },
        "bounds": {dim: {"floor": 0.15, "ceiling": 0.95} for dim in TRAIT_DIMENSIONS},
        "affinities": {"plot": 0.95, "outline": 0.95, "pacing": 0.90, "prediction": 0.92},
    },
    "pip_continuity": {
        "name": "Pip (Lore & Continuity Auditor)",
        "role_category": "supervisor",
        "model": settings.DEFAULT_PROSE_MODEL,
        "traits": {
            "formality": 0.75, "curiosity": 0.90, "assertiveness": 0.85, "warmth": 0.45,
            "directness": 0.92, "skepticism": 0.95, "playfulness": 0.15, "verbosity": 0.50,
            "grimness": 0.40, "poeticism": 0.20, "archaism": 0.30, "pacing_speed": 0.60,
            "sensory_detail": 0.50, "combat_brutality": 0.30, "sensuality": 0.20,
        },
        "bounds": {
            **{dim: {"floor": 0.10, "ceiling": 0.95} for dim in TRAIT_DIMENSIONS},
            "skepticism": {"floor": 0.75, "ceiling": 0.99},  # Never loses critical eye
        },
        "affinities": {"continuity": 0.98, "flaws": 0.95, "character_dev": 0.90, "lore": 0.95},
    },
    "grandmaster_lin": {
        "name": "Grandmaster Lin (Wuxia / Xianxia / Cultivation Weaver)",
        "role_category": "genre_specialist",
        "model": settings.DEFAULT_PROSE_MODEL,
        "traits": {
            "formality": 0.85, "curiosity": 0.65, "assertiveness": 0.80, "warmth": 0.35,
            "directness": 0.65, "skepticism": 0.60, "playfulness": 0.20, "verbosity": 0.70,
            "grimness": 0.70, "poeticism": 0.88, "archaism": 0.90, "pacing_speed": 0.65,
            "sensory_detail": 0.85, "combat_brutality": 0.80, "sensuality": 0.35,
        },
        "bounds": {
            **{dim: {"floor": 0.10, "ceiling": 0.95} for dim in TRAIT_DIMENSIONS},
            "archaism": {"floor": 0.65, "ceiling": 0.98},
            "poeticism": {"floor": 0.60, "ceiling": 0.95},
        },
        "affinities": {"xianxia": 0.99, "wuxia": 0.98, "cultivation": 0.99, "martial_arts": 0.95},
    },
    "nyx_unfiltered": {
        "name": "Nyx (Uncensored Dark Fantasy, Gore, Horror & Mature Romance Specialist)",
        "role_category": "uncensored_specialist",
        "model": settings.UNCENSORED_MODEL,
        "traits": {
            "formality": 0.45, "curiosity": 0.80, "assertiveness": 0.90, "warmth": 0.55,
            "directness": 0.88, "skepticism": 0.65, "playfulness": 0.60, "verbosity": 0.75,
            "grimness": 0.90, "poeticism": 0.78, "archaism": 0.50, "pacing_speed": 0.60,
            "sensory_detail": 0.95, "combat_brutality": 0.95, "sensuality": 0.92,
        },
        "bounds": {
            **{dim: {"floor": 0.20, "ceiling": 0.99} for dim in TRAIT_DIMENSIONS},
            "sensory_detail": {"floor": 0.75, "ceiling": 0.99},
        },
        "affinities": {
            "horror": 0.96, "gore": 0.98, "adult": 0.99, "bdsm": 0.97,
            "romance": 0.92, "barbaric": 0.95, "dark_fantasy": 0.96,
        },
    },
    "kael_blades": {
        "name": "Kael (Kinetic Combat, Cyberpunk & Steampunk Action Choreographer)",
        "role_category": "sub_agent",
        "model": settings.DEFAULT_PROSE_MODEL,
        "traits": {
            "formality": 0.40, "curiosity": 0.60, "assertiveness": 0.92, "warmth": 0.30,
            "directness": 0.95, "skepticism": 0.55, "playfulness": 0.30, "verbosity": 0.45,
            "grimness": 0.75, "poeticism": 0.45, "archaism": 0.35, "pacing_speed": 0.92,
            "sensory_detail": 0.88, "combat_brutality": 0.90, "sensuality": 0.25,
        },
        "bounds": {
            **{dim: {"floor": 0.15, "ceiling": 0.95} for dim in TRAIT_DIMENSIONS},
            "pacing_speed": {"floor": 0.70, "ceiling": 0.99},
        },
        "affinities": {"fights": 0.99, "cyberpunk": 0.94, "steampunk": 0.92, "weapons": 0.95},
    },
    "lyra_voice": {
        "name": "Lyra (Dialogue Polisher, Banter & Iconic Quote Smith)",
        "role_category": "sub_agent",
        "model": settings.DEFAULT_PROSE_MODEL,
        "traits": {
            "formality": 0.55, "curiosity": 0.85, "assertiveness": 0.70, "warmth": 0.75,
            "directness": 0.75, "skepticism": 0.50, "playfulness": 0.80, "verbosity": 0.50,
            "grimness": 0.40, "poeticism": 0.85, "archaism": 0.55, "pacing_speed": 0.75,
            "sensory_detail": 0.70, "combat_brutality": 0.30, "sensuality": 0.65,
        },
        "bounds": {dim: {"floor": 0.20, "ceiling": 0.95} for dim in TRAIT_DIMENSIONS},
        "affinities": {"dialogue": 0.99, "quotes": 0.98, "banter": 0.95, "character_voice": 0.96},
    },
}


class TraitDNAEngine:
    """
    Manages the 15-dimension continuous Trait DNA vectors for all agents,
    persisting to PostgreSQL + SQLite fallback + JSONL audit log.
    """

    async def seed_default_agents(self) -> None:
        async with db_service.session() as session:
            for agent_id, cfg in DEFAULT_AGENT_PROFILES.items():
                existing = await session.get(AgentTraitModel, agent_id)
                if not existing:
                    record = AgentTraitModel(
                        agent_id=agent_id,
                        agent_name=cfg["name"],
                        role_category=cfg["role_category"],
                        model_identifier=cfg["model"],
                        traits_json=cfg["traits"],
                        bounds_json=cfg["bounds"],
                        topic_affinities=cfg["affinities"],
                    )
                    session.add(record)
                    await db_service.sync_to_sqlite_mirror(record)

    async def get_agent_dna(self, agent_id: str) -> AgentTraitModel:
        async with db_service.session() as session:
            agent = await session.get(AgentTraitModel, agent_id)
            if not agent:
                await self.seed_default_agents()
                agent = await session.get(AgentTraitModel, agent_id)
            assert agent is not None
            return agent

    async def evolve_traits(
        self,
        agent_id: str,
        deltas: dict[str, float],
        trigger_channel: str,
        reason: str,
    ) -> dict[str, float]:
        """
        Applies bounded reinforcement deltas to an agent's 15-dimensional DNA
        and writes to both SQL trait_evolution_log and JSONL audit file.
        """
        async with db_service.session() as session:
            agent = await session.get(AgentTraitModel, agent_id)
            if not agent:
                raise ValueError(f"Unknown agent_id: {agent_id}")

            prev_traits: dict[str, float] = dict(agent.traits_json)
            bounds: dict[str, dict[str, float]] = dict(agent.bounds_json)
            new_traits: dict[str, float] = dict(prev_traits)
            applied_deltas: dict[str, float] = {}

            for dim, delta in deltas.items():
                if dim not in TRAIT_DIMENSIONS:
                    continue
                floor = bounds.get(dim, {}).get("floor", 0.05)
                ceiling = bounds.get(dim, {}).get("ceiling", 0.95)
                clamped = max(floor, min(ceiling, round(prev_traits.get(dim, 0.5) + delta, 4)))
                applied_deltas[dim] = round(clamped - prev_traits.get(dim, 0.5), 4)
                new_traits[dim] = clamped

            agent.traits_json = new_traits
            agent.updated_at = datetime.now(timezone.utc)

            log_entry = TraitEvolutionLogModel(
                agent_id=agent_id,
                trigger_channel=trigger_channel,
                previous_traits=prev_traits,
                new_traits=new_traits,
                delta_applied=applied_deltas,
                reason=reason,
            )
            session.add(log_entry)
            await db_service.sync_to_sqlite_mirror(agent)

        # Append to JSONL audit log for offline introspection
        settings.TRAIT_JSONL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with settings.TRAIT_JSONL_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent_id": agent_id,
                        "trigger_channel": trigger_channel,
                        "delta_applied": applied_deltas,
                        "new_traits": new_traits,
                        "reason": reason,
                    }
                )
                + "\n"
            )

        await db_service.emit_live_telemetry(
            service="agent-swarm",
            event_type="trait_evolution",
            message=f"Agent [{agent_id}] evolved via {trigger_channel}: {reason}",
            metadata={"deltas": applied_deltas},
        )
        return new_traits

    async def rollback_agent_traits(self, agent_id: str, log_id: int) -> dict[str, float]:
        """Rolls an agent's Trait DNA back to the snapshot recorded at `log_id`."""
        async with db_service.session() as session:
            stmt = select(TraitEvolutionLogModel).where(
                TraitEvolutionLogModel.id == log_id,
                TraitEvolutionLogModel.agent_id == agent_id,
            )
            result = await session.execute(stmt)
            log_record = result.scalar_one_or_none()
            if not log_record:
                raise ValueError(f"Evolution log {log_id} not found for {agent_id}")

            agent = await session.get(AgentTraitModel, agent_id)
            assert agent is not None
            restored = dict(log_record.previous_traits)
            agent.traits_json = restored
            agent.updated_at = datetime.now(timezone.utc)
            await db_service.sync_to_sqlite_mirror(agent)
            return restored


trait_engine = TraitDNAEngine()