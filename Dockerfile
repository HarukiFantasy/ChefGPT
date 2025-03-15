# Python 3.10 slim 이미지 사용 (경량화된 공식 이미지)
FROM python:3.10-slim

# 작업 디렉토리 생성
WORKDIR /app

# 필요한 시스템 패키지 설치 (예: 빌드용, HTTPS 인증)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 로컬 소스 코드 복사
COPY . .

# 파이썬 패키지 설치 (requirements.txt 기준)
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 8080 포트 사용 (Fly.io 기본)
EXPOSE 8080

# FastAPI 앱 실행 (uvicorn으로 서버 시작)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
