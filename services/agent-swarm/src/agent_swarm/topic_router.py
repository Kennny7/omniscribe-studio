# omniscribe-studio/services/agent-swarm/src/agent_swarm/topic_router.py
from __future__ import annotations

from sqlalchemy import select
from shared_core.enterprise_database_service import AgentTraitModel, db_service


class IntelligentTopicRouter:
    """
    Dynamically routes incoming author tasks based on evolving topic affinities,
    selecting a Primary Agent and auto-CCing Collaborator Agents on the message bus.
    """

    SEMANTIC_ANCHORS: dict[str, tuple[str, ...]] = {
        "xianxia": ("cultivation", "qi", "dao", "immortal", "tribulation", "sect", "dantian", "realm"),
        "wuxia": ("martial", "jianghu", "sword", "inner strength", "meridian", "stance", "sect"),
        "fights": ("fight", "battle", "strike", "blade", "combat", "kill", "duel", "ambush"),
        "adult": ("nsfw", "erotic", "bdsm", "sensual", "intimate", "lust", "barbaric", "wild", "passion"),
        "gore": ("blood", "dismember", "viscera", "horror", "corpse", "torture", "brutal"),
        "dialogue": ("dialogue", "conversation", "quote", "banter", "speech", "monologue"),
        "continuity": ("flaw", "check", "reasonable", "character development", "inconsistency", "plot hole"),
        "plot": ("predict", "next chapter", "outline", "arc", "future", "plan"),
        "cyberpunk": ("cyber", "neon", "implant", "hacker", "megacorp", "chrome"),
        "steampunk": ("steam", "brass", "clockwork", "airship", "gear", "victorian"),
    }

    async def route_query(
        self, prompt: str, explicit_genre: str | None = None
    ) -> tuple[AgentTraitModel, list[AgentTraitModel]]:
        """
        Returns (primary_agent, cc_secondary_agents) for parallel non-blocking execution.
        """
        lowered = prompt.lower()
        detected_topics: dict[str, float] = {}

        if explicit_genre:
            detected_topics[explicit_genre.lower()] = 1.0

        for topic, anchors in self.SEMANTIC_ANCHORS.items():
            hits = sum(1 for token in anchors if token in lowered)
            if hits > 0:
                detected_topics[topic] = min(1.0, hits * 0.35)

        if not detected_topics:
            detected_topics["plot"] = 0.6

        async with db_service.session() as session:
            result = await session.execute(select(AgentTraitModel))
            agents = list(result.scalars().all())

        scored: list[tuple[float, AgentTraitModel]] = []
        for agent in agents:
            affinities: dict[str, float] = agent.topic_affinities or {}
            score = sum(
                weight * affinities.get(topic, 0.1) for topic, weight in detected_topics.items()
            )
            scored.append((score, agent))

        scored.sort(key=lambda item: item[0], reverse=True)
        primary = scored[0][1]
        # Auto-CC top 2 secondary specialists if their affinity is meaningful
        cc_agents = [ag for sc, ag in scored[1:3] if sc >= 0.25]
        return primary, cc_agents


topic_router = IntelligentTopicRouter()