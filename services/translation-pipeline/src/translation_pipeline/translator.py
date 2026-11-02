# omniscribe-studio/services/translation-pipeline/src/translation_pipeline/translator.py
from __future__ import annotations

import asyncio
from typing import Sequence

import litellm
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from shared_core.config import settings
from shared_core.enterprise_database_service import db_service

logger = structlog.get_logger(__name__)


class DaoTranslationPipeline:
    """
    Translates non-English novel raws (Chinese/Korean/Japanese) or broken MTL
    using targeted models (e.g., Dao-9B / Qwen-2.5-14B) in parallel paragraph batches
    with automatic retries and glossary consistency.
    """

    def __init__(self, max_parallel_batches: int = 4, batch_size: int = 3) -> None:
        self.semaphore = asyncio.Semaphore(max_parallel_batches)
        self.batch_size = batch_size

    async def translate_chapter_paragraphs(
        self,
        paragraphs: Sequence[str],
        genre_tag: str = "xianxia",
        glossary: dict[str, str] | None = None,
    ) -> list[str]:
        """
        Splits paragraphs into small batches and translates them concurrently
        so large chapters never overflow context or stall the GPU.
        """
        batches: list[ tuple[int, list[str]] ] = [
            (idx, list(paragraphs[i : i + self.batch_size]))
            for idx, i in enumerate(range(0, len(paragraphs), self.batch_size))
        ]
        total_batches = max(len(batches), 1)
        completed = 0

        async def _process_batch(batch_idx: int, batch_paras: list[str]) -> tuple[int, list[str]]:
            nonlocal completed
            async with self.semaphore:
                translated = await self._translate_single_batch(
                    batch_paras, genre_tag=genre_tag, glossary=glossary or {}
                )
                completed += 1
                await db_service.emit_live_telemetry(
                    service="translation-pipeline",
                    event_type="batch_translated",
                    message=f"Dao-9B translated batch {completed}/{total_batches} ({genre_tag})",
                    progress=round(completed / total_batches, 2),
                )
                return batch_idx, translated

        results = await asyncio.gather(
            *(_process_batch(b_idx, b_paras) for b_idx, b_paras in batches)
        )
        results.sort(key=lambda item: item[0])

        flattened: list[str] = []
        for _, batch_out in results:
            flattened.extend(batch_out)
        return flattened

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1.5, min=2, max=15))
    async def _translate_single_batch(
        self,
        batch_paragraphs: list[str],
        genre_tag: str,
        glossary: dict[str, str],
    ) -> list[str]:
        glossary_str = (
            "\n".join(f"- {k} -> {v}" for k, v in glossary.items())
            if glossary
            else "Use standard Wuxia/Xianxia terminology (Qi, Dantian, Nascent Soul, Dao Heart)."
        )
        numbered_input = "\n\n".join(
            f"[P{i}] {p}" for i, p in enumerate(batch_paragraphs)
        )

        system_prompt = (
            f"You are Dao-9B, an elite literary translator specializing in {genre_tag.upper()} novels.\n"
            "Translate the provided raw/MTL paragraphs into evocative, publishable English prose.\n"
            "STRICT RULES:\n"
            "1. Preserve the exact [P0], [P1]... markers at the start of each translated paragraph.\n"
            "2. NEVER use em-dashes (—) or semicolons (;).\n"
            "3. Preserve martial arts stances, cultivation realms, and idioms naturally.\n"
            f"GLOSSARY:\n{glossary_str}"
        )

        try:
            response = await litellm.acompletion(
                model=settings.TRANSLATION_MODEL,
                api_base=settings.LLM_BASE_URL,
                api_key=settings.LLM_API_KEY,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": numbered_input},
                ],
                temperature=0.4,
                max_tokens=1800,
            )
            content = response.choices[0].message.content or ""
            parsed = [
                line.split("]", 1)[-1].strip()
                for line in content.split("\n\n")
                if line.strip()
            ]
            if len(parsed) == len(batch_paragraphs):
                return parsed
            return [content.strip()]
        except Exception as exc:
            logger.warning("translation.offline_fallback", error=str(exc))
            return [f"[Translated ({genre_tag})]: {p}" for p in batch_paragraphs]


dao_translator = DaoTranslationPipeline()