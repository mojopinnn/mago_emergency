# 폐쇄망 Daou 메일 기반 Git Patch 자동 반입 솔루션

## 목적

집 PC에서 Cursor/AI로 빠르게 개발한 코드를 회사 폐쇄망 PC에 거의 실시간으로 반입해 ShotGrid/Nuke 테스트를 돌리는 운영 방식이다. 회사 PC가 GitHub에 접속하지 못해도, Daou Office 메일과 RustDesk만 가능하면 사용할 수 있다.

핵심은 다음 조합이다.

```text
메일 자동화 + git patch + 적용 전 검사 + 백업 + 자동 테스트
```

메일은 운송 수단이고, git patch는 운송할 변경 내역 포맷이다.

## 전체 그림

```text
집 PC
  1. main.py, shotgrid_client.py, nuke_render.py 등을 수정
  2. sender.py가 변경 감지
  3. git diff --binary HEAD -- 로 change_*.patch 생성
  4. Daou SMTP로 회사 메일에 patch 전송

회사 폐쇄망 PC
  5. receiver.py가 Daou IMAP으로 unread 메일 확인
  6. 발신자, 제목 prefix, secret token, SHA256 검증
  7. git apply --check 로 적용 가능 여부 검사
  8. 바뀔 파일을 backup_dir에 백업
  9. git apply 로 patch 적용
 10. ShotGrid/Nuke smoke test 실행
 11. 결과 로그 저장
```

체감 흐름은 다음과 같다.

```text
집에서 저장
-> 2~3초 후 sender가 patch 메일 전송
-> 회사 receiver가 5초 주기로 메일 확인
-> 5~15초 후 회사 repo에 변경 반영
-> 테스트 명령 자동 실행
```

## 왜 git pull이 아닌가

`git pull`은 회사 PC가 GitHub 같은 외부 Git 서버에 직접 접속해야 한다.

```text
회사 PC -> GitHub/GitLab -> 최신 코드 다운로드
```

폐쇄망에서는 이 경로가 막혀 있다.

git patch 방식은 회사 PC가 외부 Git 서버에 접속하지 않는다.

```text
집 PC -> patch 파일 생성 -> Daou 메일 -> 회사 PC에서 로컬 적용
```

즉, GitHub가 아니라 메일 첨부파일을 통해 변경 지시서를 전달한다.

## 왜 파일 덮어쓰기보다 좋은가

파일 직접 첨부 방식:

```text
main.py 첨부
-> 회사 PC에서 main.py 덮어쓰기
```

이 방식은 단일 파일 MVP에는 빠르지만, 여러 파일이 생기면 위험하다.

- 파일 누락 가능
- 경로 실수 가능
- 회사 쪽 수정사항 덮어쓰기 가능
- 충돌 감지 어려움
- 삭제/추가 파일 추적 어려움

git patch 방식:

```text
change.patch 첨부
-> git apply --check
-> git apply
```

장점:

- 여러 파일 변경을 한 번에 적용
- 새 파일 추가와 파일 삭제도 포함
- 적용 전 충돌 검사 가능
- 실패하면 적용하지 않고 멈춤
- 바뀐 줄 단위로 추적 가능
- 회사 사내 Git에 commit/push하기 쉬움

## 전제 조건

### 집 PC

- Python 3
- Git
- 작업 repo
- Daou SMTP로 메일 발송 가능 계정

### 회사 PC

- Python 3
- Git
- 회사 내부 테스트 repo
- Daou IMAP으로 메일 수신 가능 계정
- ShotGrid 접근 가능
- Nuke CLI 실행 가능
- 필요 시 RustDesk로 화면 확인 가능

### Daou Office 확인 사항

- SMTP 사용 허용
- IMAP 사용 허용
- 외부 메일 클라이언트 사용 허용
- 앱 비밀번호 또는 메일 비밀번호 로그인 허용

기본 서버 값:

```text
SMTP: smtp.daouoffice.com
SMTP SSL port: 465
IMAP: imap.daouoffice.com
IMAP SSL port: 993
```

회사 정책에 따라 `587 STARTTLS`를 써야 할 수도 있다.

## 파일 구성

```text
scripts/mail_patch_sync/
  sender.py
  receiver.py
  mail_patch_sync.py
  README.md
  CLOSED_NETWORK_AUTOMATION_KO.md
```

- `sender.py`: 집 PC에서 repo 변경을 감지하고 patch 메일을 보낸다.
- `receiver.py`: 회사 PC에서 patch 메일을 받고 검증/적용/테스트한다.
- `mail_patch_sync.py`: 공통 로직이다.
- `README.md`: 짧은 영문 사용 설명이다.
- `CLOSED_NETWORK_AUTOMATION_KO.md`: 이 운영 문서다.

## 1단계: 회사 PC repo 기준 맞추기

집 PC와 회사 PC의 repo는 가능한 같은 기준 커밋에서 시작해야 한다.

처음 한 번은 다음 중 하나로 맞춘다.

- 회사 사내 Git에서 clone
- 승인된 방식으로 repo zip 반입
- 기존 회사 repo를 기준으로 집 repo를 맞춤

기준이 많이 다르면 `git apply --check`가 실패한다. 실패 자체는 정상 안전장치다.

## 2단계: 집 PC sender 설정

집 PC repo 루트에서 실행한다.

```bash
python3 scripts/mail_patch_sync/sender.py
```

처음 실행하면 `sender_config.json`을 만들고 종료한다.

예시:

```json
{
  "repo_path": "C:/home_dev/nuke-tool",
  "outbox_dir": "C:/home_dev/nuke-tool/.mail_patch_outbox",
  "poll_seconds": 2,
  "debounce_seconds": 2,
  "send_on_start": false,
  "exclude_globs": [
    "sender_config.json",
    "receiver_config.json",
    ".mail_patch_*",
    ".mail_patch_*/**"
  ],
  "subject_prefix": "[MAGO-PATCH]",
  "smtp_host": "smtp.daouoffice.com",
  "smtp_port": 465,
  "smtp_security": "ssl",
  "username": "home-or-company-account@example.com",
  "password": "mail-or-app-password",
  "from_addr": "home-or-company-account@example.com",
  "to_addr": "company-receiver@example.com",
  "secret_token": "replace-with-a-long-random-token"
}
```

수정 후 다시 실행한다.

```bash
python3 scripts/mail_patch_sync/sender.py
```

이제 집 PC에서 파일을 저장하면 patch가 생성되어 메일로 전송된다.

## 3단계: 회사 PC receiver 설정

회사 PC repo 루트에서 실행한다.

```bash
python3 scripts/mail_patch_sync/receiver.py
```

처음 실행하면 `receiver_config.json`을 만들고 종료한다.

예시:

```json
{
  "imap_host": "imap.daouoffice.com",
  "imap_port": 993,
  "imap_ssl": true,
  "smtp_host": "smtp.daouoffice.com",
  "smtp_port": 465,
  "smtp_security": "ssl",
  "username": "company-receiver@example.com",
  "password": "mail-or-app-password",
  "mailbox": "INBOX",
  "allowed_sender": "home-or-company-account@example.com",
  "subject_prefix": "[MAGO-PATCH]",
  "secret_token": "replace-with-the-same-long-random-token",
  "repo_path": "D:/company/nuke-tool",
  "inbox_dir": "D:/mago_patch_sync/inbox",
  "backup_dir": "D:/mago_patch_sync/backups",
  "log_dir": "D:/mago_patch_sync/logs",
  "poll_interval_seconds": 5,
  "test_commands": ["python main.py --help"],
  "command_timeout_seconds": 120
}
```

수정 후 다시 실행한다.

```bash
python3 scripts/mail_patch_sync/receiver.py
```

이제 회사 PC는 5초마다 Daou 메일을 확인하고, 유효한 patch 메일만 처리한다.

## 4단계: Nuke/ShotGrid 테스트 명령 연결

`receiver_config.json`의 `test_commands`를 실제 내부 테스트 명령으로 바꾼다.

단순 Python smoke test:

```json
{
  "test_commands": ["python main.py --shotgrid-test --shot SH010"]
}
```

Nuke background render 예시:

```json
{
  "test_commands": [
    "\"C:/Program Files/Nuke15.0v2/Nuke15.0.exe\" -x D:/mago_tests/test_render.nk -F 1001-1005"
  ],
  "command_timeout_seconds": 600
}
```

여러 단계도 가능하다.

```json
{
  "test_commands": [
    "python main.py --shotgrid-test --shot SH010",
    "\"C:/Program Files/Nuke15.0v2/Nuke15.0.exe\" -x D:/mago_tests/test_render.nk -F 1001-1005"
  ]
}
```

앞 명령이 실패하면 뒤 명령은 실행하지 않는다.

## 5단계: 실제 사용 루프

평소에는 두 프로세스를 계속 켜둔다.

집 PC:

```bash
python3 scripts/mail_patch_sync/sender.py
```

회사 PC:

```bash
python3 scripts/mail_patch_sync/receiver.py
```

개발 루프:

```text
1. 집에서 코드 수정
2. 저장
3. sender가 patch 생성 후 메일 발송
4. receiver가 메일 수신
5. git apply --check
6. 기존 파일 백업
7. patch 적용
8. ShotGrid/Nuke 테스트
9. log_dir에서 결과 확인
10. 필요하면 RustDesk로 회사 PC 화면 확인
```

테스트 성공 후 회사 PC에서 사내 Git에 기록한다.

```bash
git status
git add .
git commit -m "Update Nuke render tool"
git push origin main
```

여기서 `origin`은 개인 GitHub가 아니라 회사 내부 Git 서버다.

## 수동 테스트 방법

자동화를 켜기 전에 이 수동 절차를 한 번 해보면 구조가 바로 이해된다.

집 PC:

```bash
git diff --binary HEAD -- > change.patch
```

`change.patch`를 Daou 메일로 회사에 보낸다.

회사 PC:

```bash
git apply --check change.patch
git apply change.patch
python main.py --help
```

이 수동 흐름이 성공하면 `sender.py`/`receiver.py` 자동화로 넘어간다.

## 보안 규칙

반드시 지킬 것:

- `secret_token`은 길고 랜덤하게 만든다.
- `sender_config.json`과 `receiver_config.json`은 Git에 commit하지 않는다.
- 메일 비밀번호 또는 앱 비밀번호를 patch에 포함하지 않는다.
- `allowed_sender`를 반드시 지정한다.
- `subject_prefix`를 일반 메일과 겹치지 않게 한다.
- receiver 전용 메일 계정을 쓰는 것이 좋다.
- `git apply --check` 실패 시 강제 적용하지 않는다.
- 회사 PC의 `backup_dir`와 `log_dir`는 repo 밖에 두는 것이 좋다.
- 테스트 성공한 변경만 사내 Git에 commit한다.

이미 도구는 기본적으로 다음 경로를 patch에서 제외한다.

```text
sender_config.json
receiver_config.json
mail_patch_outbox/**
.mail_patch_outbox/**
.mail_patch_inbox/**
.mail_patch_backups/**
.mail_patch_logs/**
```

그래도 운영 환경에서는 config 파일을 repo 밖에 두는 편이 안전하다.

## 장애 대응

### 메일 로그인이 실패한다

확인할 것:

- Daou 계정/비밀번호가 맞는지
- 앱 비밀번호가 필요한지
- SMTP/IMAP이 회사 정책상 허용되는지
- 포트가 `465 SSL`인지 `587 STARTTLS`인지

### patch 적용이 실패한다

보통 집 PC repo와 회사 PC repo의 기준 버전이 달라서 그렇다.

확인할 것:

```bash
git status
git log --oneline -5
git apply --check change.patch
```

해결:

- 회사 PC 변경을 먼저 commit/stash
- 집/회사 repo 기준 커밋 맞추기
- 너무 오래된 patch는 새로 생성

### 메일은 왔는데 receiver가 처리하지 않는다

확인할 것:

- 제목이 `subject_prefix`로 시작하는지
- 발신자가 `allowed_sender`와 정확히 같은지
- sender/receiver의 `secret_token`이 같은지
- patch 첨부파일 확장자가 `.patch`인지
- 메일이 이미 읽음 처리되었는지

### 테스트가 실패한다

확인할 것:

- `log_dir`의 `result_*.log`
- Nuke 실행 경로
- ShotGrid credentials
- 테스트 샷 이름
- 렌더 출력 폴더 권한

## 추천 운영 단계

### 1단계: 수동 patch

```text
git diff > change.patch
메일 전송
git apply --check
git apply
```

목적: 폐쇄망 반입 흐름 이해.

### 2단계: sender만 자동화

```text
저장하면 patch 메일 자동 발송
회사에서는 수동 git apply
```

목적: 집 개발 속도 개선.

### 3단계: receiver 자동 적용

```text
회사 PC가 patch 수신/검증/적용 자동 처리
```

목적: 5~15초 반영 루프 구축.

### 4단계: 자동 테스트

```text
patch 적용 후 ShotGrid/Nuke smoke test 자동 실행
```

목적: RustDesk로 매번 클릭하지 않고 결과만 확인.

### 5단계: 사내 Git 기록

```text
성공한 변경만 회사 PC에서 사내 Git commit/push
```

목적: 회사 내부 배포/협업 기록 유지.

## 최종 결론

가장 빠르고 효율적인 방식은 다음이다.

```text
집 PC sender.py
  -> git patch 생성
  -> Daou 메일 발송

회사 PC receiver.py
  -> Daou 메일 수신
  -> 발신자/token/SHA256 검증
  -> git apply --check
  -> 백업
  -> git apply
  -> ShotGrid/Nuke 테스트
  -> 결과 로그 확인
```

이 방식은 GitHub 접속이 막힌 폐쇄망에서도 쓸 수 있고, 단일 파일 덮어쓰기보다 안전하며, 여러 파일 변경을 한 번에 반영할 수 있다.
