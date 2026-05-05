@echo off
chcp 65001 >nul
title MAGO Emergency Server

echo ==============================
echo   MAGO Emergency Server 시작
echo ==============================
echo.

REM .env 파일 확인
if not exist ".env" (
    echo [오류] .env 파일이 없습니다.
    echo   .env.example 을 복사해서 .env 로 만들고 값을 입력해주세요.
    echo   명령어: copy .env.example .env
    pause
    exit /b 1
)

REM venv 경로 설정
set VENV_PYTHON=venv\Scripts\python.exe
set VENV_PIP=venv\Scripts\pip.exe
set VENV_UVICORN=venv\Scripts\uvicorn.exe

REM venv 확인 및 생성
if not exist "%VENV_PYTHON%" (
    echo [설치] 가상환경 생성 중...
    python -m venv venv
    if errorlevel 1 (
        echo [오류] Python venv 생성 실패. Python이 설치되어 있는지 확인하세요.
        pause
        exit /b 1
    )
    echo       가상환경 생성 완료
)

REM cloudflared 터널 백그라운드 실행 (설치된 경우)
echo [1/2] Cloudflare Tunnel 확인 중...
where cloudflared >nul 2>&1
if %errorlevel% == 0 (
    start "Cloudflare Tunnel" cloudflared tunnel run mago-emergency
    echo       Cloudflare Tunnel 실행됨
) else (
    echo       cloudflared 미설치 - ngrok 또는 직접 접근으로 실행합니다
)

echo.
echo [2/2] Python FastAPI 서버 시작 중...
echo       로컬 접속:  http://localhost:8000/app
echo       관리자:     http://localhost:8000/admin/links
echo       헬스체크:   http://localhost:8000/healthz
echo.
echo       서버를 종료하려면 Ctrl+C 또는 이 창을 닫으세요.
echo.

REM 패키지 설치 (이미 설치된 건 자동으로 건너뜀)
echo [설치] 패키지 확인 및 설치 중...
%VENV_PIP% install -r requirements.txt
echo.

REM 서버 실행
%VENV_UVICORN% main:app --host 0.0.0.0 --port 8000 --reload

pause
