# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.

---

## MAGO Emergency System

긴급 수정 알림 시스템 - ShotGrid 연동

### 아키텍처

```
ShotGrid (PM이 mago_emergency 실행)
  → POST /api/webhook/shotgrid
  → FastAPI 서버 (긴급 상황 생성)
  → Web Push → 작업자 폰 PWA 앱
  → 작업자 확인/응답 → 실장/PM에게 전달
```

### 엔드포인트

| 경로 | 설명 |
|------|------|
| `GET /api/app` | PWA 웹앱 (작업자/실장/PM이 폰에 설치) |
| `POST /api/webhook/shotgrid` | ShotGrid AMI 웹훅 수신 |
| `GET /api/emergency` | 긴급 상황 목록 |
| `POST /api/emergency/:id/acknowledge` | 확인 처리 |
| `POST /api/emergency/:id/respond` | 응답 처리 (원격접속 가능 여부) |
| `POST /api/subscribe` | Web Push 구독 등록 |
| `GET /api/vapid-public-key` | VAPID 공개키 |

### 응답 타입

- `remote_within_10` — 10분 이내 원격 접속 가능
- `remote_within_30` — 30분 이내 원격 접속 가능
- `remote_unavailable` — 30분 이내 원격 접속 불가

### ShotGrid 설정

1. HumanUser에 커스텀 필드 추가: `sg_role` (text), `sg_push_token` (text)
2. Shot에 커스텀 필드 추가: `sg_emergency` (checkbox)
3. 각 사용자의 `sg_role` 설정: `artist` / `supervisor` / `pm`
4. ShotGrid 관리자 패널 → AMI 등록: `mago_emergency` → `POST /api/webhook/shotgrid`
5. `shotgrid_setup/setup_shotgrid.py` 실행하여 자동 설정

### 환경변수

- `SHOTGRID_URL` — ShotGrid 서버 URL
- `SHOTGRID_SCRIPT_NAME` — Script 이름
- `SHOTGRID_API_KEY` — Script API Key
- `VAPID_PUBLIC_KEY` — Web Push 공개키
- `VAPID_PRIVATE_KEY` — Web Push 비밀키
- `VAPID_EMAIL` — VAPID 이메일

### 알림 로직

- 긴급 발생 시 즉시 작업자에게 Web Push 발송
- 2분마다 미확인 알림 재전송
- 5분 내 미확인 시 실장/PM에게 미확인 알림 발송
- 작업자 확인/응답 시 실장/PM에게 즉시 전달
