"""CLI script to test the card news generator.

Usage:
    python scripts/test_card_news.py <youtube_url>
    python scripts/test_card_news.py xQR5-Nk9N6o
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

from app.services.card_news_generator import CardNewsGenerator


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test card news generator")
    parser.add_argument("youtube_url", help="YouTube video URL or ID")
    args = parser.parse_args()

    gen = CardNewsGenerator()

    print(f"\n{'=' * 60}")
    print(f"Card News Generator")
    print(f"URL: {args.youtube_url}")
    print(f"{'=' * 60}\n")

    result = await gen.generate(args.youtube_url)

    print(f"\n{'=' * 60}")
    print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Video ID: {result.video_id}")
    print(f"Cards: {result.card_count}")
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
