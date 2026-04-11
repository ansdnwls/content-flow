"""Test script: Naver Blog Playwright automation.

Usage:
    # Step 1: Setup session (manual login)
    python scripts/test_naver_blog_playwright.py login

    # Step 2: Test post
    python scripts/test_naver_blog_playwright.py post

    # Step 3: Test via adapter interface
    python scripts/test_naver_blog_playwright.py adapter
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def cmd_login() -> None:
    """Open browser for manual Naver login and save session."""
    from app.services.naver_blog_playwright import NaverBlogPlaywright

    client = NaverBlogPlaywright()
    print(f"Session path: {client.session_path}")
    print("Opening browser for manual login...")
    print("Log in to Naver, then the session will be saved automatically.\n")
    await client.setup_session()
    print(f"\nSession saved: {client.has_session()}")


async def cmd_post() -> None:
    """Test posting a blog entry via NaverBlogPlaywright.post()."""
    from app.services.naver_blog_playwright import NaverBlogPlaywright

    client = NaverBlogPlaywright()

    if not client.has_session():
        print("No session file. Run: python scripts/test_naver_blog_playwright.py login")
        return

    print(f"Blog ID: {client.blog_id}")
    print(f"Session: {client.session_path}")
    print("Posting test blog entry...\n")

    result = await client.post(
        title="ContentFlow 테스트 포스팅",
        content=(
            "안녕하세요! ContentFlow 자동화 테스트입니다.\n"
            "이 글은 Playwright를 통해 자동으로 작성되었습니다.\n"
            "정상 동작을 확인하면 삭제해주세요.\n"
            "\n"
            "ContentFlow는 유튜브 콘텐츠를 다채널로 자동 배포하는 서비스입니다.\n"
            "블로그, 인스타그램, 틱톡 등 여러 플랫폼에 한 번에 배포할 수 있습니다.\n"
            "자세한 내용은 추후 업데이트 예정입니다."
        ),
        tags=["ContentFlow", "테스트", "자동화", "블로그"],
    )

    print(f"\nResult: {result}")


async def cmd_adapter() -> None:
    """Test posting via the NaverBlogAdapter interface."""
    from app.adapters.base import MediaSpec
    from app.adapters.naver_blog import NaverBlogAdapter

    adapter = NaverBlogAdapter()

    result = await adapter.publish(
        text=(
            "어댑터 인터페이스 테스트입니다.\n"
            "NaverBlogAdapter.publish()를 통해 작성되었습니다.\n"
            "확인 후 삭제해주세요."
        ),
        media=[],
        options={
            "title": "ContentFlow 어댑터 테스트",
            "tags": ["ContentFlow", "어댑터테스트"],
        },
        credentials={},
    )

    print(f"\nPublishResult: success={result.success}, url={result.url}")
    if result.error:
        print(f"Error: {result.error}")


async def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()
    if cmd == "login":
        await cmd_login()
    elif cmd == "post":
        await cmd_post()
    elif cmd == "adapter":
        await cmd_adapter()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
