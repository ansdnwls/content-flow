"""Manual verification script for Google Sheets connection.

Usage:
    cd C:\\Users\\y2k_w\\projects\\content-flow
    .venv\\Scripts\\python.exe scripts/test_sheets_connection.py

Set GOOGLE_SHEETS_TEST_ID env var or edit SHEET_ID below.
This file is NOT committed to git.
"""
from __future__ import annotations

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SHEET_ID = os.environ.get("GOOGLE_SHEETS_TEST_ID", "")


def main() -> None:
    if not SHEET_ID:
        print("❌ GOOGLE_SHEETS_TEST_ID 환경변수를 설정하세요.")
        print("   예: set GOOGLE_SHEETS_TEST_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms")
        print("   (Google Sheets URL의 /d/ 뒤 문자열)")
        sys.exit(1)

    print(f"📋 Sheet ID: {SHEET_ID}")
    print()

    try:
        from app.services.google_sheets import GoogleSheetsClient
    except Exception as exc:
        print(f"❌ import 실패: {exc}")
        sys.exit(1)

    # 1. 인증
    print("🔑 인증 시도...")
    try:
        client = GoogleSheetsClient()
        print("✅ 인증 성공")
    except Exception as exc:
        print(f"❌ 인증 실패: {exc}")
        sys.exit(1)

    print()

    # 2. 시트 읽기
    print("📖 시트 읽기 시도...")
    try:
        rows = client.read_sheet(SHEET_ID, "Sheet1")
        print(f"✅ 시트 읽기 성공 ({len(rows)}행)")
        print()
        for i, row in enumerate(rows[:5], start=1):
            print(f"  Row {i}: {row}")
        if len(rows) > 5:
            print(f"  ... 외 {len(rows) - 5}행")
    except Exception as exc:
        print(f"❌ 시트 읽기 실패: {exc}")
        sys.exit(1)

    print()

    # 3. dict 변환
    print("📊 dict 변환 시도...")
    try:
        dicts = client.read_sheet_as_dicts(SHEET_ID, "Sheet1")
        print(f"✅ dict 변환 성공 ({len(dicts)}행)")
        if dicts:
            print(f"  헤더: {list(dicts[0].keys())}")
            print(f"  첫 행: {dicts[0]}")
    except Exception as exc:
        print(f"❌ dict 변환 실패: {exc}")
        sys.exit(1)

    print()
    print("🎉 모든 테스트 통과!")


if __name__ == "__main__":
    main()
