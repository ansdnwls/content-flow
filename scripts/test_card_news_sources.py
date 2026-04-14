"""CLI script to test multi-source card news generation.

Usage:
    python scripts/test_card_news_sources.py --source youtube --query "xQR5-Nk9N6o"
    python scripts/test_card_news_sources.py --source news --query "AI 최신 소식"
    python scripts/test_card_news_sources.py --source github --query "anthropics/anthropic-sdk-python"
    python scripts/test_card_news_sources.py --source rss --query "https://feeds.bbci.co.uk/korean/rss.xml"
    python scripts/test_card_news_sources.py --source text --query "직접 입력한 내용..." --title "제목"
    python scripts/test_card_news_sources.py --source url --query "https://example.com/article"
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
from pathlib import Path

# Fix Windows cp949 encoding for emoji output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.content_fetcher import ContentFetcher
from app.services.card_news_generator import CardNewsGenerator


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test multi-source card news")
    parser.add_argument(
        "--source", required=True,
        choices=["youtube", "news", "rss", "github", "url", "text"],
        help="Content source type",
    )
    parser.add_argument("--query", required=True, help="URL, keyword, repo, or text")
    parser.add_argument("--title", default="", help="Title override (for text source)")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch, skip card generation")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"Multi-Source Card News Generator")
    print(f"Source: {args.source}")
    print(f"Query:  {args.query[:80]}")
    print(f"{'=' * 60}\n")

    # Step 1: Fetch content
    print("[1/2] Fetching content...")
    fetcher = ContentFetcher()
    kwargs = {}
    if args.source == "text" and args.title:
        kwargs["title"] = args.title

    try:
        content = await fetcher.fetch(args.source, args.query, **kwargs)
    except Exception as exc:
        print(f"FETCH FAILED: {type(exc).__name__}: {exc}")
        return

    print(f"  Title:  {content.title}")
    print(f"  Type:   {content.source_type}")
    print(f"  URL:    {content.source_url or 'N/A'}")
    print(f"  ID:     {content.source_id}")
    print(f"  Text:   {content.text[:200]}...")
    print(f"  Length: {len(content.text)} chars")
    if content.metadata:
        print(f"  Meta:   {content.metadata}")

    if args.fetch_only:
        print(f"\n{'=' * 60}")
        print("Fetch-only mode. Skipping card generation.")
        print(f"{'=' * 60}\n")
        return

    # Step 2: Generate card news
    print(f"\n[2/2] Generating card news...")
    gen = CardNewsGenerator()
    result = await gen.generate_from_text(
        title=content.title,
        text=content.text,
        source_id=content.source_id,
    )

    print(f"\n{'=' * 60}")
    print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Source ID: {result.video_id}")
    print(f"Cards: {result.card_count}")
    print(f"Theme: {result.color_theme}")
    print(f"Output: {result.output_dir}")

    if result.error:
        print(f"Error: {result.error}")

    if result.image_paths:
        print(f"\nGenerated PNGs:")
        for p in result.image_paths:
            print(f"  {p}")

    if result.cards:
        print(f"\nCard Plan:")
        for c in result.cards:
            print(f"  [{c.index}] {c.layout:10s} {c.card_type:8s} | {c.title}")

    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
