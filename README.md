# YouTube Data Extraction API

FastAPI 기반 YouTube 데이터 추출 API입니다. 영상 정보, 자막, 댓글을 손쉽게 추출할 수 있으며, n8n 워크플로우와의 통합을 지원합니다.

## 주요 기능

- **영상 정보 추출**: 제목, 설명, 조회수, 좋아요, 채널 정보 등
- **자막 추출**: VTT 포맷, 타임스탬프 포함, 다국어 지원
- **댓글 추출**: 인기순 정렬, 작성자 정보, 좋아요 수
- **클라우드 지원**: Railway, AWS, GCP 등 클라우드 환경에서 안정적으로 작동
- **n8n 통합**: 워크플로우 자동화 지원

## Quick Start

### 1. 설치

```bash
pip install -r requirements.txt
```

### 2. 실행

**API 서버로 실행:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 다음 주소에서 접근 가능합니다:
- **API 서버**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

**터미널에서 직접 실행 (CSV 배치 처리):**
```bash
# 기본 사용 (JSON 저장)
python extract_from_csv.py urls.csv

# 언어 지정
python extract_from_csv.py urls.csv ko,en

# CSV 형식으로 저장
python extract_from_csv.py urls.csv ko,en csv

# 출력 파일명 지정
python extract_from_csv.py urls.csv ko,en json output.json
```

**CSV 파일 형식:**
```csv
url
https://www.youtube.com/watch?v=VIDEO_ID_1
https://www.youtube.com/watch?v=VIDEO_ID_2
VIDEO_ID_3
```

## 엔드포인트

### 1. 간편 테스트 (브라우저 접근)

#### 영상 정보 테스트
**GET** `/test/{video_id}`

```
http://localhost:8000/test/dQw4w9WgXcQ
```

언어 지정:
```
http://localhost:8000/test/dQw4w9WgXcQ?languages=ko,en
```

#### 댓글 테스트
**GET** `/test-comments/{video_id}`

```
http://localhost:8000/test-comments/dQw4w9WgXcQ
```

개수 지정:
```
http://localhost:8000/test-comments/dQw4w9WgXcQ?max_comments=50
```

### 2. 단일 영상 추출

**POST** `/extract`

#### 요청 예시

```json
{
  "url": "https://www.youtube.com/watch?v={VIDEO_ID}",
  "include_transcript": true,
  "transcript_languages": ["ko", "en"]
}
```

#### 응답 예시

```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Video Title",
  "description": "Video description...",
  "duration": 199,
  "view_count": 1234567,
  "like_count": 12345,
  "channel": "Channel Name",
  "channel_id": "UCxxxxxxxxxx",
  "channel_url": "https://www.youtube.com/@ChannelName",
  "upload_date": "20231118",
  "thumbnail": "https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg",
  "tags": ["tag1", "tag2"],
  "categories": ["Music"],
  "transcript": "Full transcript text...",
  "transcript_language": "ko",
  "transcript_list": [
    {
      "text": "First subtitle",
      "start": 0.0,
      "duration": 2.5
    }
  ]
}
```

### 3. 여러 영상 일괄 추출

**POST** `/transcript`

#### 요청 예시

```json
{
  "urls": [
    "https://www.youtube.com/watch?v=video1",
    "https://www.youtube.com/watch?v=video2"
  ],
  "include_transcript": true,
  "transcript_languages": ["ko", "en"]
}
```

### 4. 댓글 추출

**POST** `/comments`

#### 요청 예시

```json
{
  "video_url": "https://www.youtube.com/watch?v={VIDEO_ID}",
  "max_comments": 100
}
```

#### 응답 예시

```json
{
  "video_id": "dQw4w9WgXcQ",
  "video_title": "Video Title",
  "comment_count": 150,
  "fetched_count": 100,
  "comments": [
    {
      "author": "User Name",
      "text": "Great video!",
      "like_count": 15,
      "time_text": "1 week ago",
      "author_id": "UCxxxxxxxxxx",
      "author_thumbnail": "https://yt3.ggpht.com/...",
      "is_favorited": false,
      "author_is_uploader": false,
      "reply_count": 2
    }
  ]
}
```

### 5. 헬스 체크

**GET** `/health`

## n8n에서 사용하기 (HTTP Request)

n8n의 **HTTP Request** 노드를 사용하여 이 API를 호출할 수 있습니다.

### URL 설정

**로컬 실행:**
- `http://localhost:8000` (로컬에서 FastAPI 실행 시)
- `http://host.docker.internal:8000` (n8n이 Docker에서 실행 중일 때)

**Docker Compose:**
- `http://youtube-extractor:8000` (같은 Docker 네트워크 사용 시)

**Railway 배포:**
- `https://your-app.railway.app` (Railway 배포 URL)

### 1. 단일 영상 추출

**n8n HTTP Request 노드 설정:**

- **Method**: `POST`
- **URL**: `http://localhost:8000/extract` (또는 Railway URL)
- **Authentication**: None
- **Body Content Type**: `JSON`
- **Body**:
  ```json
  {
    "video_url": "https://www.youtube.com/watch?v={{ $json.video_id }}",
    "languages": ["ko"]
  }
  ```

**응답 처리:**
- `{{ $json.title }}`: 영상 제목
- `{{ $json.transcript }}`: 자막 텍스트
- `{{ $json.view_count }}`: 조회수

### 2. 여러 영상 일괄 추출

**n8n HTTP Request 노드 설정:**

- **Method**: `POST`
- **URL**: `http://localhost:8000/transcript` (또는 Railway URL)
- **Body Content Type**: `JSON`
- **Body**:
  ```json
  {
    "video_urls": [
      "https://www.youtube.com/watch?v=VIDEO_ID_1",
      "https://www.youtube.com/watch?v=VIDEO_ID_2"
    ],
    "languages": ["ko"]
  }
  ```

**주의**: 최대 200개까지 처리 가능하며, 100개 이상일 때는 자동으로 3초 딜레이가 적용됩니다.

### 3. 댓글 추출

**n8n HTTP Request 노드 설정:**

- **Method**: `POST`
- **URL**: `http://localhost:8000/comments` (또는 Railway URL)
- **Body Content Type**: `JSON`
- **Body**:
  ```json
  {
    "video_url": "https://www.youtube.com/watch?v={{ $json.video_id }}",
    "max_comments": 100
  }
  ```

**응답 처리:**
- `{{ $json.comments }}`: 댓글 배열
- `{{ $json.comments[0].text }}`: 첫 번째 댓글 내용
- `{{ $json.comments[0].like_count }}`: 첫 번째 댓글 좋아요 수

### 4. CSV 파일 업로드 (배치 처리)

**n8n HTTP Request 노드 설정:**

- **Method**: `POST`
- **URL**: `http://localhost:8000/transcript/csv-save` (또는 Railway URL)
- **Body Content Type**: `Form-Data` 또는 `Multipart-Form-Data`
- **Body**:
  - `file`: CSV 파일 (File 타입)
  - `languages`: `ko` (Text 타입)
  - `format`: `json` 또는 `csv` (Text 타입)

**CSV 파일 형식:**
```csv
url
https://www.youtube.com/watch?v=VIDEO_ID_1
https://www.youtube.com/watch?v=VIDEO_ID_2
```

**응답**: JSON 또는 CSV 파일 다운로드

### 5. 에러 처리

n8n에서 에러가 발생하면:
- **429 오류**: Rate Limiting - 잠시 후 재시도
- **403 오류**: 봇 감지 - 쿠키 파일 사용 권장
- **500 오류**: 서버 오류 - 로그 확인

**재시도 설정:**
- n8n HTTP Request 노드에서 "Retry" 옵션 활성화
- 최대 재시도: 3회
- 재시도 간격: 5초

## 추출되는 정보

### 조회/반응 통계
- **view_count**: 조회수
- **like_count**: 좋아요 수
- **comment_count**: 댓글 수

### 채널 정보
- **channel**: 채널명
- **channel_id**: 채널 ID
- **channel_url**: 채널 URL
- **channel_follower_count**: 구독자 수

### 영상 메타데이터
- **video_id**: 유튜브 영상 ID
- **title**: 영상 제목
- **description**: 영상 설명
- **upload_date**: 업로드 날짜
- **duration**: 영상 길이(초)
- **duration_string**: 길이 ("3:20" 형식)
- **language**: 영상 언어

### 미디어
- **thumbnail**: 대표 썸네일 URL

### 분류
- **tags**: 태그 목록
- **categories**: 카테고리

### 자막 텍스트
- **transcript**: 전체 자막 텍스트
- **transcript_language**: 자막 언어 코드
- **transcript_language_name**: 자막 언어 이름
- **is_generated**: 자동 생성 자막 여부
- **snippet_count**: 자막 구간 수
- **transcript_list**: 타임스탬프가 포함된 자막 리스트

### 자막 URL (원본 파일)
- **subtitle_urls**: 모든 언어의 자막 원본 URL (VTT 우선)
  ```json
  {
    "language": "ko",
    "ext": "vtt",
    "url": "https://www.youtube.com/api/timedtext?v=..."
  }
  ```
  - **language**: 언어 코드 (ko, en, ja 등)
  - **ext**: 파일 형식 (vtt 우선, json3, srv3 대체)
  - **url**: 직접 다운로드 링크
  
  **VTT(WebVTT) 포맷 선호 이유:**
  - W3C 웹 표준, HTML5 네이티브 지원
  - 스타일링 및 위치 제어 가능
  - 밀리초 단위 정확한 타임스탬프
  - 단어별 타이밍 정보 포함 가능

### 댓글 정보 (POST /comments)
- **video_id**: 영상 ID
- **video_title**: 영상 제목
- **comment_count**: 전체 댓글 수
- **fetched_count**: 실제 가져온 댓글 수
- **comments**: 댓글 리스트 (인기순 정렬)
  - **author**: 작성자 이름
  - **text**: 댓글 내용
  - **like_count**: 좋아요 수 (정렬 기준)
  - **time_text**: 작성 시간 ("1주 전")
  - **author_id**: 작성자 채널 ID
  - **author_thumbnail**: 작성자 프로필 이미지
  - **is_favorited**: 고정 댓글 여부
  - **author_is_uploader**: 채널 주인 댓글 여부
  - **reply_count**: 답글 수

**인기순 정렬**: 좋아요가 많은 댓글부터 수집하여 의미있는 반응을 우선 분석

## 기술 스택

- **FastAPI**: 고성능 비동기 웹 프레임워크
- **yt-dlp**: YouTube 데이터 추출 (영상 정보, 자막, 댓글)
- **VTT 포맷**: WebVTT 표준 자막 포맷 (타임스탬프 포함)
- **Railway/AWS/GCP 지원**: 클라우드 환경에서 안정적으로 작동

### 클라우드 환경 지원

이 API는 **yt-dlp**를 사용하여 Railway, AWS, GCP, Azure 등 클라우드 플랫폼에서도 안정적으로 작동합니다.

기존 `youtube-transcript-api`는 클라우드 IP를 차단하는 문제가 있었으나, `yt-dlp`로 전환하여 해결했습니다.

### Rate Limiting 및 봇 감지 처리

YouTube의 429 (Too Many Requests) 및 봇 감지 오류를 자동으로 처리합니다:
- **자동 재시도**: 최대 3회 재시도 (exponential backoff: 2초 → 4초 → 최대 10초)
- **요청 딜레이**: 자막 다운로드 전 0.5초, 배치 처리 시 1초 대기
- **HTTP 헤더 최적화**: 최신 브라우저와 유사한 헤더 사용 (Chrome 131, Sec-Fetch-* 헤더 포함)
- **쿠키 지원**: 환경 변수 `YOUTUBE_COOKIES_FILE`로 쿠키 파일 경로 지정 가능

#### 차단 해제 시간

YouTube 차단은 대부분 **일시적**입니다:
- **429 오류 (Rate Limiting)**: 보통 **10분~1시간** 후 자동 해제
- **봇 감지 차단**: 보통 **1~24시간** 후 자동 해제
- **IP 차단**: 보통 **24시간~몇 일** 후 자동 해제

**로컬에서도 차단될 수 있습니다:**
- 너무 많은 요청을 빠르게 보낼 때
- YouTube가 IP를 일시적으로 차단할 때
- **자동 폴백**: `youtube-transcript-api` 실패 시 자동으로 `yt-dlp`로 전환됨 (로그에 "yt-dlp로 폴백..." 표시)

**대응 방법 (우선순위):**
1. **쿠키 파일 사용 (가장 효과적)**: 로그인 상태로 인식되어 429 오류 우회 가능
   ```bash
   # 환경 변수 설정
   $env:YOUTUBE_COOKIES_FILE=".\cookies.txt"
   python extract_from_csv.py sample_url.csv
   ```
2. **요청 간격 늘리기**: 현재 5초 딜레이로 설정됨 (100개 이상일 때)
3. **잠시 대기**: 429 오류 발생 시 1-2시간 후 다시 시도
4. **작은 배치로 나누기**: 100개를 20개씩 5번 나눠서 처리
5. **실패한 항목 재시도**: 결과 파일에서 실패한 항목만 나중에 다시 처리

**429 오류가 계속 발생할 때:**
- 쿠키 파일을 반드시 사용하세요 (가장 효과적)
- 요청 간격을 더 늘리세요 (5초 → 10초)
- 하루에 처리할 양을 줄이세요

#### 쿠키 파일 사용 (선택사항)

봇 감지가 심한 경우 쿠키 파일을 사용할 수 있습니다:

1. **쿠키 파일 생성** (3가지 방법):
   
   **방법 A: 브라우저 확장 프로그램 (가장 쉬움)**
   - Chrome/Edge: "Get cookies.txt LOCALLY" 확장 프로그램 설치
   - YouTube.com 접속 후 로그인
   - 확장 프로그램 클릭 → "Export" → `cookies.txt` 다운로드
   
   **방법 B: yt-dlp 명령어 (자동)**
   ```bash
   # Chrome 쿠키 내보내기
   yt-dlp --cookies-from-browser chrome --cookies cookies.txt https://www.youtube.com
   
   # 또는 Firefox
   yt-dlp --cookies-from-browser firefox --cookies cookies.txt https://www.youtube.com
   ```
   
   **방법 C: 수동 추출 (고급)**
   - 브라우저 개발자 도구 (F12) → Application → Cookies → youtube.com
   - Netscape 형식으로 저장

2. **환경 변수 설정**:
   ```bash
   export YOUTUBE_COOKIES_FILE=/path/to/cookies.txt
   ```

3. **Railway 환경 변수 설정**:
   
   **방법 1: Railway 대시보드에서 설정**
   1. Railway 대시보드에서 프로젝트 선택
   2. 프로젝트 → **Variables** 탭 클릭
   3. **New Variable** 버튼 클릭
   4. 변수 이름: `YOUTUBE_COOKIES_FILE`
   5. 변수 값: `/app/cookies.txt` (또는 쿠키 파일의 실제 경로)
   6. **Add** 클릭
   
   **방법 2: 쿠키 파일 업로드**
   
   쿠키 파일을 프로젝트에 포함하려면:
   1. 쿠키 파일을 프로젝트 루트에 `cookies.txt`로 저장
   2. Dockerfile에서 쿠키 파일 복사:
   ```dockerfile
   COPY cookies.txt /app/cookies.txt
   ```
   3. Railway 환경 변수: `YOUTUBE_COOKIES_FILE=/app/cookies.txt`
   
   **방법 3: 쿠키 파일을 프로젝트에 포함 (권장)**
   
   쿠키 파일을 Docker 이미지에 포함:
   1. 쿠키 파일을 프로젝트 루트에 `cookies.txt`로 저장
   2. `.gitignore`에 `cookies.txt` 추가 (보안)
   3. Dockerfile 수정:
   ```dockerfile
   # 쿠키 파일 복사 (선택적)
   COPY cookies.txt /app/cookies.txt
   ```
   4. Railway 환경 변수 설정:
      - 변수 이름: `YOUTUBE_COOKIES_FILE`
      - 변수 값: `/app/cookies.txt`
   
   **주의**: 쿠키 파일은 민감한 정보이므로 `.gitignore`에 추가하여 Git에 커밋하지 마세요!

## Railway 배포 (Docker)

Railway에서 Dockerfile을 사용하여 배포하면 mise 패키지 관리자 문제를 우회할 수 있습니다.

**Railway 배포 안전성:**

현재 코드는 Railway 등 클라우드 환경에서 안전하게 작동하도록 설계되었습니다:

1. **자동 폴백 시스템**:
   - `youtube-transcript-api` 우선 시도 (로컬에서 빠름)
   - 클라우드 IP 차단 시 자동으로 `yt-dlp`로 폴백
   - 사용자 개입 없이 자동 처리

2. **봇 감지 대응**:
   - 자동 재시도 (최대 3회)
   - Exponential backoff (2초 → 4초 → 10초)
   - 쿠키 파일 지원 (환경 변수로 설정)

3. **Rate Limiting 대응**:
   - 배치 처리 시 자동 딜레이 (100개 이상: 3초)
   - 429 오류 자동 재시도
   - 차단 시 일시적 대기 후 자동 해제

**결론**: Railway에 배포해도 안전합니다. 클라우드 IP 차단 문제는 자동으로 해결됩니다.

### 배포 방법

**Railway는 Dockerfile을 자동으로 감지하여 배포합니다.**

#### 1. GitHub에 푸시

```bash
# 변경사항 커밋 및 푸시
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

#### 2. Railway에서 배포

1. **Railway 대시보드 접속**
   - https://railway.app 접속
   - 로그인 (GitHub 계정으로)

2. **새 프로젝트 생성**
   - "New Project" 클릭
   - "Deploy from GitHub repo" 선택
   - 저장소 선택 및 연결

3. **자동 배포**
   - Railway가 프로젝트 루트의 `Dockerfile`을 자동으로 감지
   - Docker 이미지 빌드 및 배포 자동 실행 (약 2-5분)
   - `PORT` 환경 변수 자동 설정 (Railway가 제공)

4. **배포 확인**
   - Railway 대시보드에서 생성된 URL 확인 (예: `https://your-app.railway.app`)
   - `https://your-app.railway.app/health` 접속하여 상태 확인
   - `https://your-app.railway.app/docs` 접속하여 Swagger UI 확인

**중요**: Railway는 `Dockerfile`만 있으면 자동으로 배포합니다. 추가 설정 불필요!

#### 3. 환경 변수 설정 (선택사항)

**ScraperAPI 프록시 사용 (권장 - 429 오류 및 봇 감지 우회):**
- Railway 대시보드 → 프로젝트 → **Variables** 탭
- **New Variable** 클릭
- **Name**: `SCRAPERAPI_KEY`
- **Value**: `your_scraperapi_key_here` (예: `4383f1de116db25e8ae597e447a72752`)
- **Add** 클릭

**참고**: Railway의 TCP Proxy 기능은 외부 프록시 서버를 연결하는 것이며, ScraperAPI는 환경 변수로 설정하면 코드에서 자동으로 프록시가 적용됩니다.

**쿠키 파일 사용 시:**
- Railway 대시보드 → 프로젝트 → **Variables** 탭
- **New Variable** 클릭
- **Name**: `YOUTUBE_COOKIES_FILE`
- **Value**: `/app/cookies.txt`
- **Add** 클릭

**참고**: 쿠키 파일은 Railway에 직접 업로드할 수 없으므로, Dockerfile에서 복사하거나 다른 방법을 사용해야 합니다.

### Dockerfile 특징

- Python 3.11 기반
- ffmpeg 포함 (yt-dlp 필수)
- Railway PORT 환경 변수 자동 사용
- 최적화된 레이어 캐싱

### 로컬 Docker 테스트

**Railway 배포 전 로컬에서 테스트:**

```bash
# 1. Docker 이미지 빌드
docker build -t youtube-extractor .

# 2. 컨테이너 실행 (쿠키 파일 없이)
docker run -p 8000:8000 youtube-extractor

# 3. 브라우저에서 확인
# http://localhost:8000/docs
```

**쿠키 파일 사용 (선택사항):**

```bash
# Windows PowerShell:
docker run -p 8000:8000 `
  -e YOUTUBE_COOKIES_FILE=/app/cookies.txt `
  -v ${PWD}/cookies.txt:/app/cookies.txt:ro `
  youtube-extractor

# Linux/Mac:
docker run -p 8000:8000 \
  -e YOUTUBE_COOKIES_FILE=/app/cookies.txt \
  -v $(pwd)/cookies.txt:/app/cookies.txt:ro \
  youtube-extractor
```

**docker-compose 사용 (권장):**

```bash
# 쿠키 파일 없이 실행
docker-compose up

# 백그라운드 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 중지
docker-compose down
```

**쿠키 파일 사용 (선택사항):**

docker-compose.yml에서 쿠키 파일을 사용하려면:
1. `cookies.txt` 파일을 프로젝트 루트에 저장
2. `docker-compose.yml`의 주석을 해제:
   ```yaml
   environment:
     - YOUTUBE_COOKIES_FILE=/app/cookies.txt
   volumes:
     - ./cookies.txt:/app/cookies.txt:ro
   ```
3. `docker-compose up` 실행

**주의**: 쿠키 파일은 `.gitignore`에 추가되어 있어 Git에 커밋되지 않습니다.

### n8n과 연결

**같은 Docker 네트워크 사용 (권장):**

1. **docker-compose로 실행**:
   ```bash
   docker-compose up -d
   ```

2. **n8n HTTP Request에서 접근**:
   - URL: `http://youtube-extractor:8000/extract`
   - 컨테이너 이름으로 직접 접근 가능

**또는 로컬에서 실행:**

1. **로컬에서 FastAPI 실행**:
   ```bash
   # 쿠키 파일 사용 (선택사항)
   # Windows PowerShell:
   $env:YOUTUBE_COOKIES_FILE=".\cookies.txt"
   
   # 또는 Linux/Mac:
   export YOUTUBE_COOKIES_FILE=./cookies.txt
   
   # FastAPI 실행
   python main.py
   ```

2. **n8n HTTP Request에서 접근**:
   - URL: `http://host.docker.internal:8000/extract` (Windows/Mac)
   - 또는 `http://172.17.0.1:8000/extract` (Docker 네트워크 IP)

**쿠키 파일 사용 시 주의사항:**

- **10-20개 정도는 문제없음**: 쿠키 파일 사용 시 일반적으로 안전
- **Rate Limiting**: YouTube는 여전히 요청 제한을 적용 (초당 1-2개 권장)
- **배치 처리**: `/transcript` 엔드포인트는 자동으로 영상 간 1초 대기
- **쿠키 만료**: 쿠키는 주기적으로 갱신 필요 (보통 몇 주)
- **계정 보안**: 쿠키 파일은 개인 계정 정보이므로 안전하게 보관

## 주의사항

- 일부 영상은 자막이 없거나 추출이 제한될 수 있습니다.
- 자막이 없는 경우 `transcript`, `transcript_language`, `transcript_list` 필드는 `null`로 반환됩니다.
- 댓글은 인기순(좋아요 많은 순)으로 정렬되어 수집됩니다.
- 댓글 추출은 시간이 걸릴 수 있습니다 (100개 기준 약 30초~1분).
- 비디오당 100개 권장 (의미있는 인기 댓글 수집).
- 배치 처리로 여러 영상 동시 수집 가능.
- API 사용 시 유튜브의 이용 약관을 준수해야 합니다.

## 라이선스

MIT License

