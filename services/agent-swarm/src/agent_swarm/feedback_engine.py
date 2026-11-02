# omniscribe-studio/services/agent-swarm/src/agent_swarm/feedback_engine.py
from __future__ import annotations

from difflib import SequenceMatcher
from agent_swarm.trait_engine import trait_engine


class MultiChannelFeedbackEngine:
    """
    Calibrates Agent Trait DNA across Explicit, Implicit, and Inter-Agent channels.
    """

    async def process_explicit_feedback(
        self, agent_id: str, rating: str, user_comment: str = ""
    ) -> dict[str, float]:
        """Handles '/rate good', '/rate bad', thumbs_up, or thumbs_down."""
        is_positive = rating.lower() in {"good", "thumbs_up", "up", "+1"}
        comment_lower = user_comment.lower()
        deltas: dict[str, float] = {}

        if is_positive:
            deltas["assertiveness"] = 0.02
            deltas["sensory_detail"] = 0.02
        else:
            deltas["skepticism"] = 0.02
            if "wordy" in comment_lower or "long" in comment_lower:
                deltas["verbosity"] = -0.05
                deltas["pacing_speed"] = 0.04
            elif "bland" in comment_lower or "boring" in comment_lower:
                deltas["poeticism"] = 0.04
                deltas["sensory_detail"] = 0.05
            elif "tame" in comment_lower or "soft" in comment_lower:
                deltas["combat_brutality"] = 0.05
                deltas["grimness"] = 0.04
                deltas["sensuality"] = 0.04

        return await trait_engine.evolve_traits(
            agent_id=agent_id,
            deltas=deltas,
            trigger_channel="explicit",
            reason=f"User explicit rating={rating} ({user_comment or 'no comment'})",
        )

    async def process_implicit_edit_distance(
        self, agent_id: str, agent_draft: str, author_final_text: str
    ) -> dict[str, float] | None:
        """
        Implicit RL signal: Measures how heavily the human author rewrote the agent's paragraph.
        High similarity reinforces current DNA; heavy pruning calibrates verbosity & directness.
        """
        similarity = SequenceMatcher(None, agent_draft, author_final_text).ratio()
        if similarity > 0.92:
            return await trait_engine.evolve_traits(
                agent_id=agent_id,
                deltas={"assertiveness": 0.01},
                trigger_channel="implicit",
                reason=f"High author acceptance ratio ({similarity:.2f})",
            )

        len_ratio = len(author_final_text) / max(len(agent_draft), 1)
        deltas: dict[str, float] = {}
        if len_ratio < 0.75:
            # Author trimmed bloated prose
            deltas["verbosity"] = -0.03
            deltas["directness"] = 0.03
        elif len_ratio > 1.25:
            # Author expanded thin descriptions
            deltas["verbosity"] = 0.03
            deltas["sensory_detail"] = 0.03

        if deltas:
            return await trait_engine.evolve_traits(
                agent_id=agent_id,
                deltas=deltas,
                trigger_channel="implicit",
                reason=f"Author edit calibration (similarity={similarity:.2f}, len_ratio={len_ratio:.2f})",
            )
        return None

    async def process_inter_agent_review(
        self,
        reviewer_agent_id: str,
        target_agent_id: str,
        continuity_score: float,
        style_score: float,
        review_notes: str,
    ) -> dict[str, float]:
        """
        Allows Supervisor agents (e.g. Pip or Director Alfred) to adjust sub-agent traits.
        """
        deltas: dict[str, float] = {}
        if continuity_score < 0.6:
            deltas["skepticism"] = 0.03
            deltas["directness"] = 0.02
        if style_score < 0.6:
            deltas["poeticism"] = 0.03
            deltas["sensory_detail"] = 0.03
        elif style_score > 0.85:
            deltas["assertiveness"] = 0.02

        return await trait_engine.evolve_traits(
            agent_id=target_agent_id,
            deltas=deltas,
            trigger_channel=f"inter_agent:{reviewer_agent_id}",
            reason=f"Peer review by {reviewer_agent_id}: {review_notes}",
        )


feedback_engine = MultiChannelFeedbackEngine()