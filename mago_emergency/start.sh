#!/bin/bash
# MAGO Emergency Server 시작 스크립트
# 실행: bash start.sh

set -e

echo "=============================="
echo "  MAGO Emergency Server 시작"
echo "=============================="

# .env 파일 확인
if [ ! -f ".env" ]; then
  echo "[오류] .env 파일이 없습니다."
  echo "  cp .env.example .env 후 값을 입력해주세요."
  exit 1
fi

# 패키지 설치 확인
if ! python -c "import fastapi" 2>/dev/null; then
  echo "[설치] 패키지 설치 중..."
  pip install -r requirements.txt
fi

echo "[시작] 서버를 시작합니다 (포트: ${PORT:-8080})"
echo "  웹앱:  http://localhost:${PORT:-8080}/app"
echo "  API:   http://localhost:${PORT:-8080}/healthz"
echo ""

uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}" --reload
