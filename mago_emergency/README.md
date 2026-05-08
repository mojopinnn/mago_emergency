# MAGO Emergency Server

ShotGrid 연동 긴급 수정 알림 시스템 (Python FastAPI)

---

## 설치 방법 (집 PC 서버)

### 1단계: 파일 복사
이 `mago_emergency_server` 폴더 전체를 집 PC 서버로 복사합니다.

### 2단계: Python 패키지 설치
```bash
pip install -r requirements.txt
```

### 3단계: 환경변수 설정
```bash
cp .env.example .env
```
`.env` 파일을 열어서 아래 항목 입력:
```
SHOTGRID_URL=https://studiomago.shotgrid.autodesk.com
SHOTGRID_SCRIPT_NAME=comp_script
SHOTGRID_API_KEY=your_api_key
VAPID_PUBLIC_KEY=BGMO3B-T28iHhBelsbHkk31FLlwTOJvsiZ7EVPI4mca-jiHaoASgdYNmBiljfhOQLQSnlKeOgHDTfm_M7WOVUvU
VAPID_PRIVATE_KEY=RUk1JsBnVvTRwRAnmffGKN2GF1GzaV5YD1-kLRIt-Rw
VAPID_EMAIL=mailto:admin@studiomago.com
PORT=8080

# 선택 권장: 운영 보안/저장소
ADMIN_TOKEN=change_me_admin_token
WEBHOOK_SECRET=change_me_webhook_secret
MAGO_STORE_PATH=./data/store.json
```

> 위 VAPID 값은 형식 예시입니다. 운영에서는 반드시 새 키를 생성해서 사용하세요.

### 4단계: 서버 시작
```bash
bash start.sh
```
또는
```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

---

## ShotGrid 초기 설정 (최초 1회)

### 커스텀 필드 자동 생성
서버 실행 후 아래 API 호출:
```bash
curl -X POST http://localhost:8080/admin/setup-shotgrid-fields
```
이것으로 ShotGrid에 다음 필드가 자동 생성됩니다:
- `HumanUser.sg_role` — 역할 구분 (artist / supervisor / pm)
- `HumanUser.sg_push_token` — 웹 푸시 토큰 자동 저장
- `Shot.sg_emergency` — 긴급 체크박스

### 사용자 역할 설정
ShotGrid 웹에서 각 사용자의 `sg_role` 필드에 입력:
- 작업자 → `artist`
- 실장 → `supervisor`
- PM → `pm`

### AMI(Action Menu Item) 등록
ShotGrid 관리자 패널에서:
1. Admin → Action Menu Items → New AMI
2. 아래 값으로 설정:
   - Title: `mago_emergency`
   - Entity Type: `Shot`
   - URL: `http://[서버IP]:8080/sg_webhook`
   - Method: `POST`

---

## 사용 방법

### 작업자/실장/PM 앱 설치
1. 폰에서 `http://[서버IP]:8080/app` 접속
2. ShotGrid 사용자 ID + 이름 입력 후 "설정 저장"
3. 알림 권한 허용
4. 브라우저 메뉴 → "홈 화면에 추가" (PWA 설치)

### 긴급 알림 발동
1. PM이 ShotGrid에서 해당 샷의 `sg_emergency` 체크
2. 샷 우클릭 → `mago_emergency` 실행
3. 담당 작업자 폰에 즉시 알림 발송

### 알림 흐름
```
PM mago_emergency 실행
  → 작업자 폰에 강력 알림 + 진동
  → 실장/PM에게 발생 알림
  → [2분마다 재알림, 미확인 시]
  → [5분 후 미확인 → 실장/PM에게 에스컬레이션]
  → 작업자가 [확인] 버튼 클릭 → 실장/PM에게 전달
  → 작업자가 응답 선택 → 실장/PM에게 즉시 전달
      ⚡ 10분 이내 원격 접속 가능
      🕐 30분 이내 원격 접속 가능
      ❌ 30분 이내 원격 접속 불가
```

---

## API 엔드포인트

| 경로 | 설명 |
|------|------|
| `GET /app` | PWA 웹앱 |
| `GET /healthz` | 서버 상태 확인 |
| `POST /sg_webhook` | ShotGrid AMI 웹훅 |
| `GET /emergency` | 긴급 상황 목록 |
| `POST /emergency/{id}/acknowledge` | 확인 처리 |
| `POST /emergency/{id}/respond` | 응답 처리 |
| `POST /subscribe` | 푸시 구독 등록 |
| `GET /vapid-public-key` | VAPID 공개키 |
| `POST /admin/setup-shotgrid-fields` | ShotGrid 필드 자동 생성 |
| `GET /admin/users` | 사용자 목록 조회 |
| `GET /admin/links` | 직원별 PWA 등록 링크 |

---

## 운영 보완 사항

### 데이터 저장

긴급 기록과 푸시 구독은 기본적으로 `./data/store.json`에 저장됩니다.
경로를 바꾸려면 `MAGO_STORE_PATH`를 설정하세요. 서버를 재시작해도 브라우저 푸시 구독과 긴급 처리 이력이 유지됩니다.

### 관리자 API 보호

`ADMIN_TOKEN`을 설정하면 `/admin/*` API는 아래 중 하나로 토큰을 전달해야 접근할 수 있습니다.

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8080/admin/users
curl -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8080/admin/users
```

### 웹훅 보호

`WEBHOOK_SECRET`을 설정하면 `/sg_webhook` 호출에 아래 중 하나가 필요합니다.

```bash
X-MAGO-Webhook-Secret: <WEBHOOK_SECRET>
?secret=<WEBHOOK_SECRET>
form field: secret=<WEBHOOK_SECRET>
```

Cloudflare Worker를 경유하는 경우 Worker secret에도 같은 `WEBHOOK_SECRET`을 설정하세요.

---

## 외부 접근 설정

집 PC 서버에서 ShotGrid(외부)가 접근하려면:

**방법 A: 공유기 포트포워딩**
- 공유기 설정 → 포트포워딩 → 외부포트 8080 → 내부IP:8080

**방법 B: ngrok (테스트용, 간편)**
```bash
pip install pyngrok
ngrok http 8080
# 출력된 https://xxxx.ngrok.io 를 AMI URL로 사용
```
