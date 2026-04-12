"""CLI script to test the YouTube → Naver Blog pipeline.

Usage:
    python scripts/test_youtube_to_blog.py <youtube_url>
    python scripts/test_youtube_to_blog.py <youtube_url> --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.youtube_to_blog import PipelineOptions, YouTubeToBlogPipeline


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test YouTube → Naver Blog pipeline",
    )
    parser.add_argument("youtube_url", help="YouTube video URL or ID")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run transcript + Claude conversion only (skip Naver publish)",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip AI image generation",
    )
    parser.add_argument(
        "--blog-id",
        default=None,
        help="Override Naver blog ID",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=[],
        help="Extra tags to add",
    )

    args = parser.parse_args()

    opts = PipelineOptions(
        blog_id=args.blog_id,
        extra_tags=args.tags,
        generate_images=not args.no_images,
    )

    pipeline = YouTubeToBlogPipeline(options=opts)

    print(f"\n{'=' * 60}")
    print(f"YouTube → Blog Pipeline {'(DRY RUN)' if args.dry_run else '(FULL)'}")
    print(f"URL: {args.youtube_url}")
    print(f"Images: {'OFF' if args.no_images else 'ON'}")
    print(f"{'=' * 60}\n")

    if args.dry_run:
        result = await pipeline.run_dry(args.youtube_url)
    else:
        result = await pipeline.run(args.youtube_url)

    print(f"\n{'=' * 60}")
    print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Video ID: {result.video_id}")
    print(f"Title: {result.title}")
    print(f"Tags: {result.tags}")
    print(f"Blocks: {len(result.blocks)}")

    if result.blog_url:
        print(f"Blog URL: {result.blog_url}")
    if result.error:
        print(f"Error: {result.error}")

    print(f"{'=' * 60}\n")

    if result.blocks:
        print("--- Generated Blocks ---")
        for i, block in enumerate(result.blocks):
            btype = block.get("type", "?")
            text = block.get("text", block.get("prompt", ""))[:80]
            print(f"  [{i}] {btype}: {text}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
