# YouTube Data Extraction API

FastAPI 기반 YouTube 데이터 추출 API입니다. 영상 정보, 자막, 댓글을 손쉽게 추출할 수 있으며, n8n 워크플로우와의 통합을 지원합니다.

## 주요 기능

- 📹 **영상 정보 추출**: 제목, 설명, 조회수, 좋아요, 채널 정보 등
- 📝 **자막 추출**: VTT 포맷, 타임스탬프 포함, 다국어 지원
- 💬 **댓글 추출**: 인기순 정렬, 작성자 정보, 좋아요 수
- ☁️ **클라우드 지원**: Railway, AWS, GCP 등 클라우드 환경에서 안정적으로 작동
- 🔗 **n8n 통합**: 워크플로우 자동화 지원

## Quick Start

### 1. 설치

```bash
pip install -r requirements.txt
```

### 2. 실행

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 다음 주소에서 접근 가능합니다:
- **API 서버**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

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

## n8n에서 사용하기

### 단일 영상 추출

1. n8n에서 **HTTP Request** 노드 추가
2. 설정:
   - **Method**: POST
   - **URL**: `http://localhost:8000/extract`
   - **Body Content Type**: JSON
   - **Body**:
   ```json
   {
     "video_url": "{{ $json.link }}",
     "languages": ["ko", "en"]
   }
   ```

### 여러 영상 일괄 추출

1. n8n에서 **HTTP Request** 노드 추가
2. 설정:
   - **Method**: POST
   - **URL**: `http://localhost:8000/transcript`
   - **Body Content Type**: JSON
   - **Body**:
   ```json
   {
     "video_urls": ["{{ $json.link }}", "..."],
     "languages": ["ko", "en"]
   }
   ```

### 댓글 추출

1. n8n에서 **HTTP Request** 노드 추가
2. 설정:
   - **Method**: POST
   - **URL**: `http://localhost:8000/comments`
   - **Body Content Type**: JSON
   - **Body**:
   ```json
   {
     "video_url": "{{ $json.link }}",
     "max_comments": 100
   }
   ```

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

## Railway 배포 (Docker)

Railway에서 Dockerfile을 사용하여 배포하면 mise 패키지 관리자 문제를 우회할 수 있습니다.

### 배포 방법

1. **GitHub 저장소 연결**
   - Railway 대시보드에서 "New Project" 선택
   - "Deploy from GitHub repo" 선택
   - 저장소 연결

2. **자동 배포**
   - Railway가 Dockerfile을 자동으로 감지
   - Docker 이미지 빌드 및 배포 자동 실행
   - PORT 환경 변수 자동 설정

3. **배포 확인**
   - Railway 대시보드에서 생성된 URL 확인
   - `https://your-app.railway.app/health` 접속하여 상태 확인

### Dockerfile 특징

- Python 3.11 기반
- ffmpeg 포함 (yt-dlp 필수)
- Railway PORT 환경 변수 자동 사용
- 최적화된 레이어 캐싱

### 로컬 Docker 테스트

```bash
# 이미지 빌드
docker build -t youtube-extractor .

# 컨테이너 실행
docker run -p 8000:8000 youtube-extractor

# 또는 docker-compose 사용
docker-compose up
```

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

