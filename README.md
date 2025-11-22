# YouTube 정보 추출 API

유튜브 영상의 메타데이터, 자막, 댓글을 추출하는 FastAPI 서버입니다.

**GitHub**: [https://github.com/daniel8824-del/youtube-transcript-api](https://github.com/daniel8824-del/youtube-transcript-api)

## 📁 파일 구성

### `main.py` - 메인 파일
- ✅ 영상 메타데이터 추출
- ✅ 자막 텍스트 추출 (타임스탬프 포함)
- ✅ 자막 URL 제공 (모든 언어)
- ✅ 댓글 추출 (언어 감지 및 6개 그룹 분류)
- ✅ 배치 처리 지원 (최대 50개)
- ✅ 자막 URL 전용 엔드포인트 (`/subtitle-url`)

## ⚡ 빠른 시작

```bash
# 1. 저장소 클론
git clone https://github.com/daniel8824-del/youtube-transcript-api.git
cd youtube-transcript-api

# 2. Docker로 실행 (Docker 설치 필요)
docker-compose up -d

# 3. 브라우저에서 확인
# http://localhost:8000/docs
```

## 📥 설치 방법

### 1. GitHub에서 클론

```bash
git clone https://github.com/daniel8824-del/youtube-transcript-api.git
cd youtube-transcript-api
```

### 2. Docker 설치

**Windows/Mac:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 다운로드 및 설치

**Linux:**
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

## 🚀 실행 방법

### Docker로 실행 (권장)

```bash
# 실행
docker-compose up -d

# 중지
docker-compose down

# 로그 확인
docker-compose logs -f
```

**서버 확인**: `http://localhost:8000/docs`

### 로컬 실행

```bash
# 패키지 설치
pip install -r requirements.txt

# 실행
python main.py
```

## 📚 API 엔드포인트

### 1. 자막 URL만 추출 ⭐

**POST** `/subtitle-url` 또는 **GET** `/subtitle-url/{video_id}`

가장 가벼운 엔드포인트로, 한국어 VTT 자막 URL만 추출합니다.

```json
// POST 요청
{
  "video_url": "https://www.youtube.com/watch?v=H5TAW-0X7eQ"
}

// 응답
{
  "video_id": "H5TAW-0X7eQ",
  "subtitle_urls": [
    {
      "language": "ko",
      "ext": "vtt",
      "url": "https://www.youtube.com/api/timedtext?v=..."
    }
  ],
  "error": null
}
```

**브라우저 테스트**: `GET /test-subtitle-url/{video_id}`

### 2. 영상 정보 + 자막 추출

**POST** `/extract`

```json
// 요청
{
  "video_url": "https://www.youtube.com/watch?v=H5TAW-0X7eQ",
  "languages": ["ko", "en"]
}

// 응답
{
  "video_id": "H5TAW-0X7eQ",
  "title": "영상 제목",
  "description": "영상 설명",
  "view_count": 12345,
  "like_count": 678,
  "comment_count": 90,
  "channel": "채널명",
  "channel_id": "UCxxxxx",
  "channel_url": "https://www.youtube.com/@...",
  "channel_follower_count": 1000000,
  "upload_date": "20240101",
  "duration": 300,
  "duration_string": "5:00",
  "thumbnail": "https://i.ytimg.com/...",
  "tags": ["tag1", "tag2"],
  "categories": ["Music"],
  "transcript": "전체 자막 텍스트...",
  "transcript_language": "ko",
  "transcript_language_name": "Korean",
  "is_generated": false,
  "snippet_count": 150,
  "transcript_list": [
    {
      "text": "자막 텍스트",
      "start": 0.0,
      "duration": 2.5
    }
  ],
  "subtitle_urls": [
    {
      "language": "ko",
      "ext": "vtt",
      "url": "https://www.youtube.com/api/timedtext?..."
    }
  ]
}
```

**브라우저 테스트**: `GET /test/{video_id}`

### 3. 여러 영상 일괄 추출

**POST** `/transcript`

```json
// 요청
{
  "video_urls": [
    "https://www.youtube.com/watch?v=video1",
    "https://www.youtube.com/watch?v=video2"
  ],
  "languages": ["ko", "en"]
}
```

**주의**: 최대 50개까지 처리 가능, 요청 간 0.5초 대기

### 4. 댓글 추출 (언어 감지 및 분류)

**POST** `/comments`

```json
// 요청
{
  "video_url": "https://www.youtube.com/watch?v=H5TAW-0X7eQ",
  "max_comments": 100
}

// 응답
{
  "videoId": "H5TAW-0X7eQ",
  "title": "영상 제목",
  "description": "영상 설명",
  "link": "https://www.youtube.com/watch?v=H5TAW-0X7eQ",
  "channelName": "채널명",
  "channelLink": "https://www.youtube.com/@...",
  "views": 12345,
  "likes": 678,
  "comments": 500,
  "length": "5:00",
  "thumbnail": "https://i.ytimg.com/...",
  "upload_date": "2025-11-13",
  "tags": ["tag1", "tag2"],
  "categories": ["Music"],
  "fetched_count": 100,
  "language_stats": {
    "korean": 25,
    "japanese": 5,
    "chinese": 3,
    "southeast_asian": 2,
    "western": 60,
    "latin": 2,
    "others": 3
  },
  "all_comments": [
    {
      "author": "작성자명",
      "text": "댓글 내용",
      "like_count": 15,
      "time_text": "1주 전",
      "author_id": "UCxxxxx",
      "author_thumbnail": "https://...",
      "is_favorited": false,
      "author_is_uploader": false,
      "reply_count": 3,
      "language": "ko",
      "language_group": "korean"
    }
  ],
  "korean_comments": [...],
  "japanese_comments": [...],
  "chinese_comments": [...],
  "southeast_asian_comments": [...],
  "western_comments": [...],
  "latin_comments": [...],
  "other_comments": [...]
}
```

**브라우저 테스트**: `GET /test-comments/{video_id}?max_comments=50`

### 5. 헬스 체크

**GET** `/health`

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "version": "2.1"
}
```

## 📖 API 문서

서버 실행 후 자동 생성된 API 문서를 확인할 수 있습니다:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **루트 엔드포인트**: `http://localhost:8000/` (API 정보 요약)

## 📋 추출 가능한 정보

### 영상 메타데이터
- **video_id**: 유튜브 영상 ID
- **title**: 영상 제목
- **description**: 영상 설명
- **view_count**: 조회수
- **like_count**: 좋아요 수
- **comment_count**: 댓글 수
- **upload_date**: 업로드 날짜 (YYYYMMDD)
- **duration**: 영상 길이(초)
- **duration_string**: 길이 ("5:00" 형식)
- **thumbnail**: 대표 썸네일 URL
- **tags**: 태그 목록
- **categories**: 카테고리

### 채널 정보
- **channel**: 채널명
- **channel_id**: 채널 ID
- **channel_url**: 채널 URL
- **channel_follower_count**: 구독자 수

### 자막 정보

#### 자막 텍스트
- **transcript**: 전체 자막 텍스트
- **transcript_language**: 자막 언어 코드 (예: "ko")
- **transcript_language_name**: 자막 언어 이름 (예: "Korean")
- **is_generated**: 자동 생성 자막 여부
- **snippet_count**: 자막 구간 수
- **transcript_list**: 타임스탬프가 포함된 자막 리스트
  ```json
  {
    "text": "자막 텍스트",
    "start": 0.0,
    "duration": 2.5
  }
  ```

#### 자막 URL (모든 버전)
- **subtitle_urls**: 자막 URL 리스트
  - `/extract`: 모든 사용 가능한 언어의 자막 URL 반환
  - `/subtitle-url`: 한국어 VTT 자막 URL만 반환
  ```json
  {
    "language": "ko",
    "ext": "vtt",
    "url": "https://www.youtube.com/api/timedtext?v=..."
  }
  ```

### 댓글 정보

- **language_stats**: 언어별 통계 (6개 그룹)
  - **korean**: 한국어 댓글 수
  - **japanese**: 일본어 댓글 수
  - **chinese**: 중국어 댓글 수
  - **southeast_asian**: 동남아시아 (태국어, 인도네시아어, 베트남어) 댓글 수
  - **western**: 서구권 (영어, 프랑스어, 독일어) 댓글 수
  - **latin**: 라틴권 (스페인어, 포르투갈어) 댓글 수
  - **others**: 기타 언어 댓글 수
- **all_comments**: 모든 댓글 (언어 정보 포함)
- **korean_comments**: 한국어 댓글만
- **japanese_comments**: 일본어 댓글만
- **chinese_comments**: 중국어 댓글만
- **southeast_asian_comments**: 동남아시아 댓글만
- **western_comments**: 서구권 댓글만
- **latin_comments**: 라틴권 댓글만
- **other_comments**: 기타 언어 댓글

각 댓글 필드:
- **author**: 작성자 이름
- **text**: 댓글 내용
- **like_count**: 좋아요 수 (인기순 정렬 기준)
- **time_text**: 작성 시간 ("1주 전")
- **author_id**: 작성자 채널 ID
- **author_thumbnail**: 작성자 프로필 이미지
- **is_favorited**: 고정 댓글 여부
- **author_is_uploader**: 채널 주인 댓글 여부
- **reply_count**: 답글 수
- **language**: 감지된 언어 코드 (ko, en, ja, es 등) ⭐
- **language_group**: 언어 그룹 (korean, japanese, chinese, southeast_asian, western, latin, others) ⭐

## 💡 사용 가이드

### 자막 URL만 필요
→ **`/subtitle-url`** 엔드포인트 사용
- 자막 텍스트는 필요 없고 URL만 필요할 때
- 가장 가벼운 요청으로 차단 위험 최소화
- 한국어 VTT 자막만 필요할 때

## ⚠️ 주의사항

- 자막이 없는 영상의 경우 `subtitle_urls`는 빈 배열 또는 `null`로 반환됩니다.
- 댓글 추출은 시간이 걸릴 수 있습니다 (100개 기준 약 30초~1분).
- 대량 요청 시 차단 방지를 위해 요청 간 딜레이가 있습니다 (0.5초).
- YouTube의 이용 약관을 준수해야 합니다.
- 자막 URL은 만료 시간이 있어서, 필요시 새로 요청해야 합니다.

## 📝 파일 구조

```
.
├── main.py              # 메인 파일 (모든 기능 포함)
├── requirements.txt     # Python 패키지 의존성
├── Dockerfile          # Docker 이미지 빌드 파일
├── docker-compose.yml  # Docker Compose 설정
├── README_N8N          # n8n 연동 가이드
└── README.md           # 이 파일
```

## 🔗 관련 문서

- **GitHub 저장소**: [https://github.com/daniel8824-del/youtube-transcript-api](https://github.com/daniel8824-del/youtube-transcript-api)
- **API 문서**: 서버 실행 후 `http://localhost:8000/docs` 접속
- **n8n 연동**: `README_N8N` 참조

## 📦 의존성

주요 패키지:
- `fastapi==0.104.1`: 웹 프레임워크
- `uvicorn[standard]==0.24.0`: ASGI 서버
- `yt-dlp>=2024.8.6`: YouTube 데이터 추출
- `youtube-transcript-api>=0.6.2`: 자막 추출
- `langdetect>=1.0.9`: 언어 감지

전체 의존성은 `requirements.txt`를 참조하세요.
