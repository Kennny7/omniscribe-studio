# omniscribe-studio/services/ingestion-scraper/src/ingestion_scraper/site_adapters.py
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True)
class SiteSelectorConfig:
    domain_key: str
    title_selectors: tuple[str, ...]
    content_selectors: tuple[str, ...]
    noise_selectors: tuple[str, ...]
    encoding_hint: str = "utf-8"
    requires_flaresolverr: bool = True


SITE_ADAPTER_REGISTRY: dict[str, SiteSelectorConfig] = {
    "twkan": SiteSelectorConfig(
        domain_key="twkan",
        title_selectors=("h1.txtnav", "div.txtnav h1", "h1"),
        content_selectors=("div#txtcontent", "div.txtnav"),
        noise_selectors=("script", "style", "div.txtinfo", "div.bottom-ad", "a"),
        encoding_hint="utf-8",
        requires_flaresolverr=True,
    ),
    "69shuba": SiteSelectorConfig(
        domain_key="69shuba",
        title_selectors=("div.txtnav h1", "h1.hide720", "h1"),
        content_selectors=("div.txtnav", "div#txtnav"),
        noise_selectors=("script", "style", "div.txtinfo", "div.yueduad", "span.txtcenter"),
        encoding_hint="gbk",
        requires_flaresolverr=True,
    ),
    "wtr": SiteSelectorConfig(
        domain_key="wtr",
        title_selectors=("h1.chapter-title", "h3.chapter-title", "h1"),
        content_selectors=("div.chapter-body", "div#chapter-content", "article.chapter-content"),
        noise_selectors=("script", "style", "div.ads-holder", "button", "nav"),
        encoding_hint="utf-8",
        requires_flaresolverr=True,
    ),
    "opennovel": SiteSelectorConfig(
        domain_key="opennovel",
        title_selectors=("h1.chapter-title", "header h1", "h1"),
        content_selectors=("div.chapter-content", "div#chapter-container", "article"),
        noise_selectors=("script", "style", "ins", ".ad-slot", "footer"),
        encoding_hint="utf-8",
        requires_flaresolverr=True,
    ),
    "gutenberg": SiteSelectorConfig(
        domain_key="gutenberg",
        title_selectors=("h1", "h2", "title"),
        content_selectors=("body", "div.chapter"),
        noise_selectors=("script", "style", "pre", "#pg-header", "#pg-footer"),
        encoding_hint="utf-8",
        requires_flaresolverr=False,  # Public domain archive, direct HTTP allowed
    ),
}

WATERMARK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"69书吧|www\.69shuba\.\w+|twkan\.com|台湾小说网", re.I),
    re.compile(r"本章未完，请点击下一页继续阅读.*", re.I),
    re.compile(r"\*\*\*+\s*START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*+", re.I),
    re.compile(r"\*\*\*+\s*END OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*+", re.I),
)


class DomainSpecificExtractor:
    """
    Detects the target novel site from the URL and extracts clean title + paragraph arrays
    using site-specific CSS selectors and watermark scrubbers.
    """

    @classmethod
    def resolve_adapter(cls, url: str) -> SiteSelectorConfig | None:
        hostname = urlparse(url).netloc.lower()
        for key, config in SITE_ADAPTER_REGISTRY.items():
            if key in hostname:
                return config
        return None

    @classmethod
    def extract_title_and_paragraphs(cls, url: str, html: str) -> tuple[str, list[str]]:
        adapter = cls.resolve_adapter(url)
        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Chapter Title FIRST
        title = url
        title_selectors = adapter.title_selectors if adapter else ("h1", "h2", "title")
        for sel in title_selectors:
            node = soup.select_one(sel)
            if node and node.get_text(strip=True):
                title = node.get_text(strip=True)
                break

        # 2. Remove known ad/script/navigation noise tags
        noise_list = adapter.noise_selectors if adapter else ("script", "style", "nav", "footer")
        for selector in noise_list:
            for junk in soup.select(selector):
                junk.decompose()

        # 3. Extract Chapter Container
        container: Tag | BeautifulSoup = soup
        if adapter:
            for sel in adapter.content_selectors:
                found = soup.select_one(sel)
                if found:
                    container = found
                    break

        # 4. Handle both <p>-based sites (WTR, OpenNovel, Gutenberg) and <br>-based raws (69shuba, Twkan)
        p_tags = container.find_all("p")
        if len(p_tags) >= 3:
            raw_lines = [p.get_text(" ", strip=True) for p in p_tags]
        else:
            for br in container.find_all("br"):
                br.replace_with("\n")
            raw_lines = container.get_text().splitlines()

        cleaned_paragraphs: list[str] = []
        for line in raw_lines:
            text = line.strip()
            for wm in WATERMARK_PATTERNS:
                text = wm.sub("", text).strip()
            if len(text) > 1 and text != title:
                cleaned_paragraphs.append(text)

        return title, cleaned_paragraphs
