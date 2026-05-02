# Cloudflare Tunnel 설정 가이드

한 번 설정하면 집 PC 재시작해도 **주소가 영구 고정**됩니다.

---

## 1단계: Cloudflare 계정 만들기

1. https://cloudflare.com 접속 → 무료 가입
2. 도메인이 있다면 Cloudflare에 등록 (선택사항)
   - 도메인 없어도 됩니다 → Cloudflare가 무료 주소 발급

---

## 2단계: cloudflared 설치 (집 PC 윈도우)

**방법 A: winget (권장)**
```powershell
winget install --id Cloudflare.cloudflared
```

**방법 B: 직접 다운로드**
1. https://github.com/cloudflare/cloudflared/releases/latest 접속
2. `cloudflared-windows-amd64.exe` 다운로드
3. `C:\cloudflared\cloudflared.exe` 로 이동

---

## 3단계: Cloudflare 로그인

```powershell
cloudflared tunnel login
```
→ 브라우저가 열리면 Cloudflare 계정으로 로그인
→ 도메인 선택 (없으면 skip)

---

## 4단계: 터널 생성

```powershell
cloudflared tunnel create mago-emergency
```

성공하면 이런 메시지가 나옵니다:
```
Created tunnel mago-emergency with id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```
이 **터널 ID**를 메모해두세요.

---

## 5단계: 설정 파일 생성

`C:\Users\[사용자명]\.cloudflared\config.yml` 파일 생성:

```yaml
tunnel: mago-emergency
credentials-file: C:\Users\[사용자명]\.cloudflared\[터널ID].json

ingress:
  - service: http://localhost:8000
```

> `[사용자명]`과 `[터널ID]`를 실제 값으로 교체하세요.

---

## 6단계: 무료 주소 발급 (도메인 없는 경우)

```powershell
cloudflared tunnel route dns mago-emergency mago-emergency.cfargotunnel.com
```

또는 임시 주소로 바로 실행:
```powershell
cloudflared tunnel --url http://localhost:8000
```
→ `https://xxxx-xxxx.trycloudflare.com` 형태의 주소 발급
→ 단, 이 방식은 재시작 시 주소 바뀜

---

## 7단계: 터널 실행

```powershell
cloudflared tunnel run mago-emergency
```

터미널에 이런 주소가 나옵니다:
```
https://mago-emergency.[계정].cfargotunnel.com
```
이게 **영구 고정 주소**입니다.

---

## 8단계: Windows 서비스 등록 (자동 시작)

PC 켤 때마다 자동으로 터널이 시작되도록:

```powershell
cloudflared service install
```

이후 PC 재시작해도 터널 자동 시작됩니다.

---

## 9단계: .env 파일 업데이트

`mago_emergency_server/.env` 파일에서:
```
PUBLIC_BASE_URL=https://mago-emergency.[계정].cfargotunnel.com
```

ShotGrid AMI URL도 동일하게 업데이트:
```
https://mago-emergency.[계정].cfargotunnel.com/sg_webhook
```

---

## 최종 구조

```
집 PC (항상 켜져 있음)
├── Python FastAPI 서버 (포트 8000)
└── cloudflared 서비스 (자동 실행)
        ↓ 고정 주소로 외부 연결
https://mago-emergency.[계정].cfargotunnel.com
        ↓
스튜디오 ShotGrid AMI → /sg_webhook
직원 폰 → /app?userId=42&userName=홍길동
```

---

## 문제 해결

| 증상 | 해결 |
|------|------|
| 터널 연결 안 됨 | `cloudflared tunnel run mago-emergency` 다시 실행 |
| 서비스 시작 안 됨 | 관리자 권한으로 PowerShell 실행 |
| 주소 확인 | `cloudflared tunnel info mago-emergency` |
