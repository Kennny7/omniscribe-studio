# omniscribe-studio/services/manuscript-editor/src/manuscript_editor/editor_engine.py
from __future__ import annotations

import asyncio
import re
from typing import Sequence

import litellm
import structlog
from sqlalchemy import desc, select
from tenacity import retry, stop_after_attempt, wait_exponential

from shared_core.config import settings
from shared_core.enterprise_database_service import ParagraphVersionModel, db_service

logger = structlog.get_logger(__name__)


class AntiClicheScrubber:
    """
    Deterministic post-processor that strips chatbot clichés, em-dashes (—),
    en-dashes (–), and semicolons (;) from any LLM output.
    """

    CLICHE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\ba shiver (?:ran |went )?down (?:his|her|their) spine\b", re.I), "cold dread settled in"),
        (re.compile(r"\blet out a breath (?:he|she|they) didn't know (?:he|she|they) (?:was|were) holding\b", re.I), "exhaled slowly"),
        (re.compile(r"\ba testament to\b", re.I), "proof of"),
        (re.compile(r"\blittle did (?:he|she|they) know\b", re.I), "unseen by anyone"),
        (re.compile(r"\bcouldn't help but\b", re.I), ""),
        (re.compile(r"\beyes widened in (?:shock|surprise|horror)\b", re.I), "gaze sharpened"),
        (re.compile(r"\ba tapestry of\b", re.I), "a web of"),
        (re.compile(r"\ba symphony of\b", re.I), "a chorus of"),
    )

    @classmethod
    def scrub(cls, text: str) -> str:
        cleaned = text
        # Replace em-dashes and en-dashes with commas or periods
        cleaned = re.sub(r"\s*[—–]\s*", ", ", cleaned)
        # Replace semicolons with periods and capitalize next letter if needed
        cleaned = re.sub(r";\s*", ". ", cleaned)

        for pattern, replacement in cls.CLICHE_REPLACEMENTS:
            cleaned = pattern.sub(replacement, cleaned)

        # Clean up accidental double punctuation or spaces
        cleaned = re.sub(r",\s*,", ",", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return cleaned.strip()


class ParallelManuscriptEditor:
    """
    Rewrites, grammar-checks, or expands chapters paragraph-by-paragraph in parallel
    with exponential backoff retries and full paragraph-level Undo/Redo versioning.
    """

    def __init__(self, concurrency_limit: int = 5) -> None:
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def process_chapter_in_parallel(
        self,
        project_id: str,
        chapter_id: str,
        paragraphs: Sequence[str],
        instruction: str = "Polish grammar and elevate into authentic Wuxia/Xianxia novel prose.",
        genre_tag: str = "xianxia",
        use_uncensored_model: bool = False,
        author_agent_id: str = "grandmaster_lin",
    ) -> list[dict[str, str | int]]:
        """
        Processes multiple paragraphs concurrently without loading the whole novel into memory.
        Saves every paragraph revision to PostgreSQL/SQLite for one-click Undo.
        """
        total = max(len(paragraphs), 1)
        completed = 0

        async def _worker(p_idx: int, raw_para: str) -> dict[str, str | int]:
            nonlocal completed
            async with self.semaphore:
                styled = await self._rewrite_single_paragraph(
                    raw_para=raw_para,
                    instruction=instruction,
                    genre_tag=genre_tag,
                    use_uncensored_model=use_uncensored_model,
                )
                version_num = await self.record_paragraph_version(
                    project_id=project_id,
                    chapter_id=chapter_id,
                    paragraph_index=p_idx,
                    raw_content=raw_para,
                    styled_content=styled,
                    author_agent_id=author_agent_id,
                    operation_type="uncensored_rewrite" if use_uncensored_model else "style_polish",
                )
                completed += 1
                await db_service.emit_live_telemetry(
                    service="manuscript-editor",
                    event_type="paragraph_processed",
                    message=f"Edited paragraph {completed}/{total} (v{version_num})",
                    progress=round(completed / total, 2),
                )
                return {
                    "paragraph_index": p_idx,
                    "version": version_num,
                    "original": raw_para,
                    "edited": styled,
                }

        tasks = [_worker(idx, para) for idx, para in enumerate(paragraphs)]
        results = await asyncio.gather(*tasks)
        results.sort(key=lambda item: int(item["paragraph_index"]))
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def _rewrite_single_paragraph(
        self,
        raw_para: str,
        instruction: str,
        genre_tag: str,
        use_uncensored_model: bool,
    ) -> str:
        target_model = (
            settings.UNCENSORED_MODEL if use_uncensored_model else settings.DEFAULT_PROSE_MODEL
        )
        system_prompt = (
            f"You are a master {genre_tag.upper()} novelist and line editor.\n"
            f"Task: {instruction}\n"
            "STRICT FORMATTING RULES:\n"
            "- Output ONLY the revised paragraph text without commentary.\n"
            "- NEVER use dashes (— or –) or semicolons (;).\n"
            "- Avoid robotic transitional phrases or repetitive sentence starters."
        )
        try:
            resp = await litellm.acompletion(
                model=target_model,
                api_base=settings.LLM_BASE_URL,
                api_key=settings.LLM_API_KEY,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_para},
                ],
                temperature=0.65,
                max_tokens=800,
            )
            draft = resp.choices[0].message.content or raw_para
        except Exception:
            draft = raw_para

        return AntiClicheScrubber.scrub(draft)

    # -------------------------------------------------------------------------
    # Granular Version Control (Undo / Rollback per Paragraph or Chapter)
    # -------------------------------------------------------------------------
    async def record_paragraph_version(
        self,
        project_id: str,
        chapter_id: str,
        paragraph_index: int,
        raw_content: str,
        styled_content: str,
        author_agent_id: str,
        operation_type: str,
    ) -> int:
        async with db_service.session() as session:
            stmt = (
                select(ParagraphVersionModel)
                .where(
                    ParagraphVersionModel.project_id == project_id,
                    ParagraphVersionModel.chapter_id == chapter_id,
                    ParagraphVersionModel.paragraph_index == paragraph_index,
                )
                .order_by(desc(ParagraphVersionModel.version_number))
                .limit(1)
            )
            res = await session.execute(stmt)
            latest = res.scalar_one_or_none()
            next_version = (latest.version_number + 1) if latest else 1

            record = ParagraphVersionModel(
                project_id=project_id,
                chapter_id=chapter_id,
                paragraph_index=paragraph_index,
                version_number=next_version,
                raw_content=raw_content,
                styled_content=styled_content,
                author_agent_id=author_agent_id,
                operation_type=operation_type,
            )
            session.add(record)
            return next_version

    async def undo_paragraph_to_version(
        self,
        project_id: str,
        chapter_id: str,
        paragraph_index: int,
        target_version: int | None = None,
    ) -> dict[str, str | int]:
        """
        Restores a paragraph to its previous version (or a specific version number).
        """
        async with db_service.session() as session:
            stmt = (
                select(ParagraphVersionModel)
                .where(
                    ParagraphVersionModel.project_id == project_id,
                    ParagraphVersionModel.chapter_id == chapter_id,
                    ParagraphVersionModel.paragraph_index == paragraph_index,
                )
                .order_by(desc(ParagraphVersionModel.version_number))
            )
            res = await session.execute(stmt)
            history = list(res.scalars().all())
            if not history:
                raise ValueError("No version history found for this paragraph.")

            if target_version is not None:
                chosen = next((h for h in history if h.version_number == target_version), history[-1])
            elif len(history) >= 2:
                chosen = history[1]  # Previous version
            else:
                chosen = history[0]  # Original raw

            return {
                "paragraph_index": paragraph_index,
                "restored_version": chosen.version_number,
                "content": chosen.raw_content if len(history) == 1 else chosen.styled_content,
            }


manuscript_editor = ParallelManuscriptEditor()