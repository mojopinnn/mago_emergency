# Cloudflare Worker 설정 가이드

집 PC가 꺼져 있어도 ShotGrid AMI를 안전하게 수신하고,
PC가 켜지면 자동으로 처리합니다.

---

## 1단계: Cloudflare 계정 및 wrangler 설치

```powershell
npm install -g wrangler
wrangler login
```

---

## 2단계: KV 네임스페이스 생성

```powershell
wrangler kv:namespace create MAGO_KV
```

출력된 id 값을 복사해서 `wrangler.toml`에 붙여넣기:
```toml
[[kv_namespaces]]
binding = "MAGO_KV"
id = "여기에_복사한_ID"
```

---

## 3단계: 환경변수 설정

```powershell
# 집 서버의 Cloudflare Tunnel 주소
wrangler secret put HOME_SERVER_URL
# 입력 예시: https://mago-emergency.계정.cfargotunnel.com

# 워커 ↔ 서버 인증용 비밀 토큰 (아무 문자열)
wrangler secret put RELAY_SECRET
# 입력 예시: mago2024secretkey
```

`.env` 파일에도 동일하게 입력:
```
CF_WORKER_URL=https://mago-emergency.계정.workers.dev
RELAY_SECRET=mago2024secretkey
```

---

## 4단계: 워커 배포

```powershell
wrangler deploy
```

성공하면 이런 주소가 나옵니다:
```
https://mago-emergency.계정.workers.dev
```

---

## 5단계: ShotGrid AMI URL 변경

ShotGrid 관리자 → AMI 설정에서 URL을 워커 주소로 변경:
```
기존: https://집서버주소/sg_webhook
변경: https://mago-emergency.계정.workers.dev/sg_webhook
```

이제 ShotGrid → 워커 → 집 서버 순으로 중계됩니다.

---

## 전체 동작 흐름

```
[정상 상태]
ShotGrid AMI
  → Cloudflare Worker (항상 켜져 있음)
  → 집 서버로 중계
  → 웹 푸시 발송

[집 PC 꺼진 상태]
ShotGrid AMI
  → Cloudflare Worker
  → 집 서버 응답 없음 (4초 타임아웃)
  → KV 대기열에 저장
  → ShotGrid에는 200 OK 반환 (에러 표시 없음)

[집 PC 다시 켜짐]
서버 시작
  → KV 대기열 확인
  → 미처리 긴급 요청 발견
  → 작업자 폰에 "지연 전달" 알림 🔔
  → 실장/PM 폰에 "오프라인 중 요청 발생" 알림 🔔
  → KV에서 삭제
```
