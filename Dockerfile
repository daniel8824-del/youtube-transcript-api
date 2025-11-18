FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 도구 설치
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY main.py .

# 포트 노출 (Railway는 PORT 환경 변수 사용)
EXPOSE 8000

# Railway의 PORT 환경 변수 사용 (없으면 기본값 8000)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

