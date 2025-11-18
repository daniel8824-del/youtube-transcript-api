# Railway 배포 가이드

## 배포 전 체크리스트

- [x] Dockerfile 존재
- [x] requirements.txt 존재
- [x] main.py 존재
- [x] .dockerignore 설정 (불필요한 파일 제외)
- [x] .gitignore 설정 (쿠키 파일 제외)
- [x] health 엔드포인트 (`/health`) 존재

## 배포 단계

### 1. GitHub에 푸시

```bash
# 변경사항 커밋
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### 2. Railway에서 배포

1. **Railway 대시보드 접속**
   - https://railway.app 접속
   - 로그인 (GitHub 계정으로)

2. **새 프로젝트 생성**
   - "New Project" 클릭
   - "Deploy from GitHub repo" 선택
   - 저장소 선택 및 연결

3. **자동 배포**
   - Railway가 `Dockerfile`을 자동 감지
   - Docker 이미지 빌드 시작
   - 배포 완료까지 대기 (약 2-5분)

4. **배포 확인**
   - Railway 대시보드에서 생성된 URL 확인
   - `https://your-app.railway.app/health` 접속하여 상태 확인
   - `https://your-app.railway.app/docs` 접속하여 Swagger UI 확인

### 3. 환경 변수 설정 (선택사항)

**쿠키 파일 사용 시:**

1. Railway 대시보드 → 프로젝트 선택
2. **Variables** 탭 클릭
3. **New Variable** 클릭
4. 변수 추가:
   - **Name**: `YOUTUBE_COOKIES_FILE`
   - **Value**: `/app/cookies.txt`
5. **Add** 클릭

**참고**: 쿠키 파일은 Railway에 직접 업로드할 수 없으므로, Dockerfile에서 복사하거나 다른 방법을 사용해야 합니다.

## 배포 후 테스트

```bash
# Health check
curl https://your-app.railway.app/health

# API 테스트
curl -X POST https://your-app.railway.app/extract \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "languages": ["ko"]}'
```

## 문제 해결

### 빌드 실패
- Dockerfile 문법 확인
- requirements.txt 의존성 확인
- Railway 로그 확인

### 429 오류 발생
- 쿠키 파일 사용 권장
- 요청 간격 늘리기
- 잠시 대기 후 재시도

### 배포는 되지만 API가 작동하지 않음
- `/health` 엔드포인트 확인
- Railway 로그 확인
- 포트 설정 확인 (Railway가 자동 설정)

## 주의사항

- 쿠키 파일은 `.gitignore`에 추가되어 있어 Git에 커밋되지 않습니다
- Railway는 무료 플랜에서도 사용 가능하지만, 사용량 제한이 있을 수 있습니다
- 클라우드 IP 차단 시 자동으로 `yt-dlp`로 폴백됩니다

