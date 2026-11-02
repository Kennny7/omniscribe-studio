# omniscribe-studio/tests/test_omniscribe_core.py
from __future__ import annotations

import pytest

from agent_swarm.dynamic_prompt_builder import DynamicPromptBuilder
from agent_swarm.feedback_engine import feedback_engine
from agent_swarm.trait_engine import TRAIT_DIMENSIONS, trait_engine
from ingestion_scraper.site_adapters import DomainSpecificExtractor
from manuscript_editor.editor_engine import AntiClicheScrubber
from shared_core.enterprise_database_service import db_service


@pytest.mark.asyncio
async def test_trait_dna_bounds_and_evolution() -> None:
    """Verifies 15 continuous dimensions stay strictly within [floor, ceiling] boundaries."""
    await db_service.initialize()
    await trait_engine.seed_default_agents()

    agent = await trait_engine.get_agent_dna("grandmaster_lin")
    assert len(agent.traits_json) == 15
    for dim in TRAIT_DIMENSIONS:
        assert dim in agent.traits_json

    # Attempt to push archaism above ceiling (0.98) and formality below floor (0.10)
    updated = await trait_engine.evolve_traits(
        agent_id="grandmaster_lin",
        deltas={"archaism": 5.0, "formality": -5.0},
        trigger_channel="explicit",
        reason="Boundary stress test",
    )
    assert updated["archaism"] <= 0.98
    assert updated["formality"] >= 0.10


@pytest.mark.asyncio
async def test_dynamic_prompt_builder_reflects_traits() -> None:
    """Verifies numerical trait vectors compile into behavioral system directives."""
    await db_service.initialize()
    await trait_engine.seed_default_agents()

    nyx = await trait_engine.get_agent_dna("nyx_unfiltered")
    prompt = DynamicPromptBuilder.build_system_prompt(
        agent=nyx,
        genre_tag="dark_fantasy",
        lore_context="Blood Moon Sect controls the Northern Abyss.",
    )
    assert "NEVER use em-dashes" in prompt
    assert "Blood Moon Sect" in prompt
    assert "Nyx" in prompt


@pytest.mark.asyncio
async def test_implicit_edit_distance_feedback() -> None:
    """Verifies heavy author trimming reduces agent verbosity automatically."""
    await db_service.initialize()
    await trait_engine.seed_default_agents()

    before = (await trait_engine.get_agent_dna("director_alfred")).traits_json["verbosity"]
    bloated_draft = " ".join(["The sky was very dark and ominous."] * 25)
    concise_author_edit = "The sky darkened."

    updated = await feedback_engine.process_implicit_edit_distance(
        agent_id="director_alfred",
        agent_draft=bloated_draft,
        author_final_text=concise_author_edit,
    )
    assert updated is not None
    assert updated["verbosity"] < before


def test_anti_cliche_and_punctuation_scrubber() -> None:
    """Ensures em-dashes, semicolons, and chatbot cliches are stripped."""
    raw = (
        "A shiver ran down his spine—he couldn't help but stare; "
        "it was a testament to the sect's power."
    )
    cleaned = AntiClicheScrubber.scrub(raw)
    assert "—" not in cleaned
    assert ";" not in cleaned
    assert "shiver ran down his spine" not in cleaned.lower()
    assert "a testament to" not in cleaned.lower()
    assert "couldn't help but" not in cleaned.lower()


def test_site_specific_extractors() -> None:
    """Verifies DOM extraction for 69shuba, Twkan, WTR-Lab, OpenNovel, and Gutenberg."""
    sample_69shuba_html = """
    <html><body>
      <div class="txtnav">
        <h1>第42章 剑斩星辰</h1>
        <div class="txtinfo">69书吧 www.69shuba.com</div>
        苍穹之上，剑气纵横三万里。<br/><br/>
        林玄一步踏出，天地变色。<br/>
        本章未完，请点击下一页继续阅读
      </div>
    </body></html>
    """
    title, paras = DomainSpecificExtractor.extract_title_and_paragraphs(
        "https://www.69shuba.com/txt/12345/67890", sample_69shuba_html
    )
    assert title == "第42章 剑斩星辰"
    assert len(paras) == 2
    assert "69书吧" not in paras[0]
    assert "本章未完" not in paras[-1]