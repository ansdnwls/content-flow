# Google Sheets 연동 설정 가이드

> ContentFlow가 yt-factory의 Google Sheets 작업 시트를 읽기 위한 설정.

---

## 1단계: Google Cloud Console 설정

### 1-1. 프로젝트 선택
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 기존 ContentFlow 프로젝트 선택 (YouTube OAuth와 같은 프로젝트 권장)

### 1-2. Sheets API 활성화
1. 왼쪽 메뉴 → **API 및 서비스** → **라이브러리**
2. "Google Sheets API" 검색
3. **사용** 버튼 클릭

### 1-3. 서비스 계정 만들기
1. **API 및 서비스** → **사용자 인증 정보**
2. **+ 사용자 인증 정보 만들기** → **서비스 계정**
3. 이름: `contentflow-sheets` (원하는 이름)
4. 역할: 없음 (Sheets 권한은 시트 공유로 관리)
5. **완료**

### 1-4. JSON 키 다운로드
1. 생성된 서비스 계정 클릭
2. **키** 탭 → **키 추가** → **새 키 만들기**
3. **JSON** 선택 → 다운로드
4. 안전한 위치에 저장 (예: `C:/Users/y2k_w/contentflow-sa.json`)
5. **절대 git에 커밋하지 말 것!**

---

## 2단계: ContentFlow .env 설정

`.env` 파일에 아래 중 하나를 추가:

### 방법 A: 파일 경로 (로컬 개발용, 권장)
```
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=C:/Users/y2k_w/contentflow-sa.json
```

### 방법 B: JSON 문자열 (Railway/Docker 배포용)
```
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key":"..."}
```

> 두 값 모두 설정하면 파일 경로가 우선.

---

## 3단계: 시트 공유 권한 부여

1. 서비스 계정 이메일 확인 (JSON 파일의 `client_email` 필드)
   - 예: `contentflow-sheets@project-id.iam.gserviceaccount.com`
2. yt-factory 작업 시트 열기
3. **공유** 버튼 클릭
4. 서비스 계정 이메일 추가
5. 권한: **뷰어** (읽기 전용)
6. **보내기**

---

## 4단계: 연결 확인

```powershell
cd C:\Users\y2k_w\projects\content-flow
.\.venv\Scripts\Activate.ps1
python scripts/test_sheets_connection.py
```

성공 시 출력 예시:
```
✅ 인증 성공
✅ 시트 읽기 성공 (5행)
Row 1: ['video_id', 'title', 'status', ...]
Row 2: ['abc123', 'My Video', 'done', ...]
...
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `Permission denied` | 시트에 서비스 계정 공유 안 됨 | 3단계 다시 확인 |
| `not found` | Sheet ID가 잘못됨 | URL에서 `/d/` 뒤의 긴 문자열 확인 |
| `No Google service account` | .env 설정 안 됨 | 2단계 확인 |
| `not valid JSON` | JSON 문자열이 깨짐 | notepad로 .env 열어서 한 줄인지 확인 |

---

## Drive 파일 접근 설정

ContentFlow가 yt-factory가 Drive에 올린 영상/자막 파일을 다운로드하려면
Drive 폴더에도 서비스 계정 공유 권한이 필요합니다.

### 방법 1: 폴더 전체 공유 (권장)
1. yt-factory가 사용하는 Drive 루트 폴더 열기
   - 채널별 폴더: DRIVE_FOLDER_CH001, CH002, CH003 등
2. 각 폴더 우클릭 → "공유"
3. 서비스 계정 이메일 추가 (뷰어 권한)
4. 하위 폴더/파일에 자동 전파됨

### 방법 2: 개별 파일 공유
- 파일별로 공유하는 건 비효율적
- 방법 1 권장

### Drive 연결 확인
```powershell
$env:GOOGLE_DRIVE_TEST_FILE_ID = "여기에_Drive_파일_ID"
python scripts/test_drive_connection.py
```

---

## 참고: Sheet ID 찾는 법

Google Sheets URL:
```
https://docs.google.com/spreadsheets/d/THIS_IS_THE_SHEET_ID/edit
```

`/d/` 와 `/edit` 사이의 문자열이 Sheet ID.

---

## 권한 업데이트 (B11 이후)

B11부터 ContentFlow가 Sheets에 쓰기도 합니다 (업로드 완료 상태 기록).

### 변경 사항
- 기존: **뷰어** (읽기만)
- 신규: **편집자** (읽기 + 쓰기)

### 설정
1. yt-factory Google Sheets 열기
2. **공유** 설정에서 ContentFlow 서비스 계정 찾기
3. 권한을 "뷰어"에서 **"편집자"**로 변경

### .env 추가
```
YT_FACTORY_SHEET_ID=여기에_시트_ID
```
