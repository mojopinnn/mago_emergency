#!/bin/bash
# ============================================================================
# MAGO Emergency System - Google Cloud Run Deploy Script
# ============================================================================
# 이 스크립트는 MAGO Emergency 컨테이너 이미지를 빌드하고 Google Cloud Run에 배포합니다.
# 로컬에 Docker가 설치되어 있지 않더라도 Google Cloud Build를 사용해 클라우드에서 직접 빌드할 수 있습니다.

set -e

# Default configurations (원하는 값으로 변경 가능)
DEFAULT_REGION="asia-northeast3"  # 서울 리전
DEFAULT_SERVICE_NAME="mago-emergency"

echo "======================================================"
echo "🚀 MAGO Emergency - 구글 클라우드(Cloud Run) 배포 시작"
echo "======================================================"

# gcloud CLI 설치 여부 확인
if ! command -v gcloud &> /dev/null; then
    echo "❌ 에러: gcloud CLI가 설치되어 있지 않습니다."
    echo "구글 클라우드 SDK를 먼저 설치해주세요: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# GCP Project ID 입력 받기
if [ -z "$PROJECT_ID" ]; then
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ "$NON_INTERACTIVE" = "true" ]; then
        PROJECT_ID="$CURRENT_PROJECT"
    else
        read -p "GCP Project ID를 입력하세요 [기존 설정: $CURRENT_PROJECT]: " PROJECT_ID
        PROJECT_ID=${PROJECT_ID:-$CURRENT_PROJECT}
    fi
fi

if [ -z "$PROJECT_ID" ]; then
    echo "❌ 에러: GCP Project ID가 지정되지 않았습니다. 배포를 중단합니다."
    exit 1
fi

# GCP 프로젝트 설정 업데이트
gcloud config set project "$PROJECT_ID"

# 배포 리전 설정
if [ -z "$REGION" ]; then
    if [ "$NON_INTERACTIVE" = "true" ]; then
        REGION="$DEFAULT_REGION"
    else
        read -p "배포할 구글 클라우드 리전을 입력하세요 [기본값: $DEFAULT_REGION]: " REGION
        REGION=${REGION:-$DEFAULT_REGION}
    fi
fi

# Cloud Run 서비스 이름 설정
if [ -z "$SERVICE_NAME" ]; then
    if [ "$NON_INTERACTIVE" = "true" ]; then
        SERVICE_NAME="$DEFAULT_SERVICE_NAME"
    else
        read -p "Cloud Run 서비스 이름을 입력하세요 [기본값: $DEFAULT_SERVICE_NAME]: " SERVICE_NAME
        SERVICE_NAME=${SERVICE_NAME:-$DEFAULT_SERVICE_NAME}
    fi
fi

# VAPID Keys 및 ShotGrid 설정
if [ "$NON_INTERACTIVE" = "true" ]; then
    VAPID_EMAIL=${VAPID_EMAIL:-"mailto:dev@test.com"}
else
    echo ""
    echo "💬 웹 푸시(Web Push) 알림을 위해 VAPID 키 설정이 필요합니다."
    echo "키가 없으시다면 'npx web-push generate-vapid-keys --json'을 통해 발급받으실 수 있습니다."
    read -p "VAPID_PUBLIC_KEY 입력 (엔터 입력 시 무시): " VAPID_PUBLIC_KEY
    read -p "VAPID_PRIVATE_KEY 입력 (엔터 입력 시 무시): " VAPID_PRIVATE_KEY
    read -p "VAPID_EMAIL 입력 (엔터 입력 시 기본 dev@test.com): " VAPID_EMAIL
    VAPID_EMAIL=${VAPID_EMAIL:-"mailto:dev@test.com"}

    # ShotGrid 자격증명 설정 (필요시)
    read -p "SHOTGRID_URL 입력 (엔터 입력 시 무시): " SHOTGRID_URL
    read -p "SHOTGRID_SCRIPT_NAME 입력 (엔터 입력 시 무시): " SHOTGRID_SCRIPT_NAME
    read -p "SHOTGRID_API_KEY 입력 (엔터 입력 시 무시): " SHOTGRID_API_KEY
fi

echo ""
echo "------------------------------------------------------"
echo "⚙️ 배포 설정 요약:"
echo "Project ID:   $PROJECT_ID"
echo "Region:       $REGION"
echo "Service Name: $SERVICE_NAME"
echo "------------------------------------------------------"
echo ""

# 필요한 GCP 서비스 활성화
echo "📦 1. 필요한 Google Cloud API를 활성화하는 중..."
gcloud services enable run.googleapis.com \
                       artifactregistry.googleapis.com \
                       cloudbuild.googleapis.com

# Artifact Registry 저장소 생성 (mago-repo)
REPO_NAME="mago-repo"
echo "🐳 2. Artifact Registry 저장소($REPO_NAME) 확인 및 생성 중..."
if ! gcloud artifacts repositories describe "$REPO_NAME" --project="$PROJECT_ID" --location="$REGION" &>/dev/null; then
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="MAGO Emergency Docker Repository" \
        --project="$PROJECT_ID"
    echo "✅ 저장소가 생성되었습니다."
else
    echo "✅ 이미 존재하는 저장소입니다."
fi

# Cloud Build를 사용해 원격에서 안전하게 빌드 진행
IMAGE_TAG="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME:latest"
echo "⚡ 3. Google Cloud Build를 사용해 컨테이너 이미지를 빌드 및 푸시하는 중..."
echo "이미지 경로: $IMAGE_TAG"
gcloud builds submit --tag "$IMAGE_TAG" .

# Cloud Run으로 배포 진행
echo "🚀 4. Google Cloud Run에 서비스를 배포하는 중..."

# 환경변수 배열 빌드 (PORT는 Cloud Run 예약 변수이므로 제외)
ENV_VARS=""
append_env() {
    local key="$1"
    local val="$2"
    if [ -n "$val" ]; then
        if [ -n "$ENV_VARS" ]; then
            ENV_VARS="$ENV_VARS,$key=$val"
        else
            ENV_VARS="$key=$val"
        fi
    fi
}

append_env "VAPID_PUBLIC_KEY" "$VAPID_PUBLIC_KEY"
append_env "VAPID_PRIVATE_KEY" "$VAPID_PRIVATE_KEY"
append_env "VAPID_EMAIL" "$VAPID_EMAIL"
append_env "SHOTGRID_URL" "$SHOTGRID_URL"
append_env "SHOTGRID_SCRIPT_NAME" "$SHOTGRID_SCRIPT_NAME"
append_env "SHOTGRID_API_KEY" "$SHOTGRID_API_KEY"

if [ -n "$ENV_VARS" ]; then
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --platform managed \
        --allow-unauthenticated \
        --set-env-vars "$ENV_VARS" \
        --port 8080
else
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_TAG" \
        --region "$REGION" \
        --platform managed \
        --allow-unauthenticated \
        --port 8080
fi

echo ""
echo "======================================================"
echo "🎉 배포가 성공적으로 완료되었습니다!"
echo "웹 브라우저를 통해 위 표시된 Cloud Run URL로 접속하세요."
echo "======================================================"
