#!/bin/bash
# mago_emergency 서버 코드만 GitHub에 배포하는 스크립트
# Replit Shell에서 실행: bash deploy_mago.sh

set -e

PAT="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"
REPO="https://${PAT}@github.com/mojopinnn/mago_emergency.git"
PREFIX="mago_emergency"

echo "🚀 mago_emergency 배포 시작..."

# 임시 브랜치 정리 (혹시 남아있을 경우)
git branch -D _deploy_temp 2>/dev/null || true

# 서버 폴더만 분리해서 임시 브랜치 생성
git subtree split --prefix=$PREFIX -b _deploy_temp

# GitHub에 force push
git push $REPO _deploy_temp:main --force

# 임시 브랜치 삭제
git branch -D _deploy_temp

echo "✅ 배포 완료! github.com/mojopinnn/mago_emergency 에서 확인하세요."
