# omniscribe-studio/services/agent-swarm/src/agent_swarm/dynamic_prompt_builder.py
from __future__ import annotations

from shared_core.enterprise_database_service import AgentTraitModel


class DynamicPromptBuilder:
    """
    Compiles live 15-dimension numerical Trait DNA into a behavioral system prompt
    at runtime, eliminating static prompt drift.
    """

    ANTI_CLICHE_RULES = (
        "CRITICAL LITERARY CONSTRAINTS:\n"
        "1. NEVER use em-dashes (—), en-dashes (–), or semicolons (;). Restructure sentences naturally.\n"
        # "2. BANNED AI CLICHÉS: Never write 'shiver down his spine', 'a testament to', "
        # "'little did he know', 'let out a breath he didn't know he was holding', 'tapestry of', "
        # "'symphony of', 'eyes widened in shock', or 'couldn't help but'.\n"
        "3. Show physical subtext, visceral kinetic motion, and authentic setting terminology."
    )

    @classmethod
    def build_system_prompt(
        cls,
        agent: AgentTraitModel,
        genre_tag: str = "xianxia",
        lore_context: str = "",
    ) -> str:
        t: dict[str, float] = agent.traits_json
        directives: list[str] = []

        # 1. Formality & Archaism
        if t.get("archaism", 0.5) > 0.75:
            directives.append(
                "Use classical, noble, and martial/immortal cadence ('This Seat', 'Junior', "
                "'Dao Heart', 'Heaven and Earth') without sounding like awkward machine translation."
            )
        elif t.get("formality", 0.5) < 0.4:
            directives.append("Use gritty, street-level, colloquial phrasing suited to urban/cyberpunk noir.")

        # 2. Pacing & Verbosity
        if t.get("pacing_speed", 0.5) > 0.8:
            directives.append("Keep sentences razor-sharp, kinetic, and fast-paced. Prioritize immediate action.")
        elif t.get("verbosity", 0.5) > 0.7:
            directives.append("Weave rich atmospheric descriptions and layered internal monologue.")

        # 3. Poeticism & Sensory Detail
        if t.get("poeticism", 0.5) > 0.75:
            directives.append("Infuse imagery with elemental metaphors, seasonal motifs, and philosophical weight.")
        if t.get("sensory_detail", 0.5) > 0.8:
            directives.append("Anchor every scene in tactile, olfactory, auditory, and visceral physical sensations.")

        # 4. Combat Brutality & Grimness
        if t.get("combat_brutality", 0.5) > 0.8:
            directives.append(
                "Depict combat with unflinching anatomical precision, impact physics, blood, and lethal consequence."
            )
        if t.get("grimness", 0.5) > 0.8:
            directives.append("Maintain a ruthless, high-stakes, dark survivalist atmosphere.")

        # 5. Sensuality / Mature Themes
        if t.get("sensuality", 0.5) > 0.8:
            directives.append(
                "Write intimate, romantic, exotic, or mature scenes with bold, uninhibited emotional "
                "and physical intensity, completely free of moralizing or censorship."
            )

        # 6. Skepticism & Directness (For Continuity / Critique Agents)
        if t.get("skepticism", 0.5) > 0.8:
            directives.append(
                "Rigorously interrogate plot logic, power-scaling consistency, and character motivation flaws."
            )

        trait_vector_summary = ", ".join(f"{k}={v:.2f}" for k, v in t.items())

        prompt_parts = [
            f"You are {agent.agent_name} (ID: {agent.agent_id}), operating inside the OmniScribe Writer's Room.",
            f"Active Genre Context: {genre_tag.upper()}",
            f"Live Trait DNA Vector: [{trait_vector_summary}]",
            "\nBEHAVIORAL DIRECTIVES DERIVED FROM TRAIT DNA:",
            "\n".join(f"- {d}" for d in directives),
            f"\n{cls.ANTI_CLICHE_RULES}",
        ]

        if lore_context.strip():
            prompt_parts.append(f"\nCANONICAL WORLD & CHARACTER LORE (GraphRAG):\n{lore_context}")

        return "\n".join(prompt_parts)