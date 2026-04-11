"""Google Drive 연결 테스트."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.google_drive import GoogleDriveClient

FILE_ID = os.environ.get("GOOGLE_DRIVE_TEST_FILE_ID", "")


def main():
    if not FILE_ID:
        print("환경변수 GOOGLE_DRIVE_TEST_FILE_ID 설정 필요")
        print("예: $env:GOOGLE_DRIVE_TEST_FILE_ID = '1AbCdEf...'")
        sys.exit(1)

    client = GoogleDriveClient()

    # 1. 메타데이터 조회
    print(f"Fetching metadata for: {FILE_ID}")
    meta = client.get_file_metadata(FILE_ID)
    print(f"  Name: {meta.get('name')}")
    print(f"  Type: {meta.get('mimeType')}")
    size_mb = int(meta.get("size", 0)) / 1024 / 1024
    print(f"  Size: {size_mb:.2f} MB")

    # 2. SRT면 텍스트로, mp4면 디스크로
    mime = meta.get("mimeType", "")
    name = meta.get("name", "unknown")

    if "text" in mime or name.endswith(".srt") or name.endswith(".json"):
        print("Downloading as text...")
        content = client.download_text(FILE_ID)
        print(f"  First 200 chars: {content[:200]}")
    else:
        dest = f"/tmp/drive_test_{name}"
        print(f"Downloading to: {dest}")
        path = client.download_file(FILE_ID, dest)
        print(f"  Downloaded: {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
