# Git 없이 쓰는 Daou 메일 Zip/Manifest 자동화 솔루션

## 지금 상황의 전제

- 회사 PC에서 GitHub는 쓸 수 없다.
- 사내 GitLab은 있지만 계정 승인 대기라 당장 쓸 수 없다.
- 회사 개인 PC에 Git 프로그램 설치도 어려울 수 있다.
- 그래도 Daou Office 메일과 RustDesk는 가능하다.

그래서 `git patch` 대신 다음 방식으로 간다.

```text
Daou 메일 + zip 패키지 + manifest 검증 + 백업 + 선택적 테스트
```

이 방식은 회사 PC에 Git이 없어도 동작한다.

## 전체 흐름

```text
집 PC
  1. sender.py가 작업 폴더를 감시
  2. 바뀐 파일만 zip으로 묶음
  3. manifest.json에 파일 경로, 새 SHA256, 이전 SHA256 기록
  4. Daou SMTP로 회사 메일에 전송

회사 PC
  5. receiver.py가 Daou IMAP으로 메일 확인
  6. 발신자, 제목 prefix, secret token, zip SHA256 검증
  7. manifest 기준으로 기존 파일이 예상 상태인지 확인
  8. 기존 파일 백업
  9. zip 안의 파일을 지정 폴더에 적용
 10. 선택적으로 Python/ShotGrid/Nuke 테스트 실행
 11. 결과 로그 저장
```

## 왜 manifest가 필요한가

그냥 zip을 덮어쓰면 위험하다.

```text
집에서 보낸 main.py
-> 회사 PC main.py 덮어쓰기
```

이러면 회사 PC에서 누군가 수정한 파일을 모르고 덮을 수 있다.

manifest는 적용 전 상태를 확인한다.

```json
{
  "path": "main.py",
  "action": "upsert",
  "sha256": "새 파일 해시",
  "previous_sha256": "집에서 알고 있던 이전 파일 해시"
}
```

receiver는 회사 PC의 현재 `main.py` 해시가 `previous_sha256`과 같은지 확인한다. 다르면 충돌로 보고 적용하지 않는다.

## 처음 세팅 순서

### 1. 회사 폴더 기준 맞추기

처음 한 번은 집 PC와 회사 PC의 폴더가 같은 내용이어야 한다.

예:

```text
집 PC: C:/home_dev/nuke-tool
회사 PC: D:/mago_tool
```

Git이 없으면 승인된 방식으로 zip 복사, USB 반입, 사내 공유폴더 등 회사 정책에 맞는 방식으로 최초 폴더를 맞춘다.

### 2. 집 PC sender 설정 파일 생성

집 PC에서 실행:

```bash
python3 scripts/mail_zip_sync/sender.py
```

처음 실행하면 `sender_config.json`이 생기고 종료된다.

예시:

```json
{
  "source_dir": "C:/home_dev/nuke-tool",
  "outbox_dir": "C:/home_dev/nuke-tool/.mail_zip_outbox",
  "state_path": "C:/home_dev/nuke-tool/.mail_zip_sender_state.json",
  "include_globs": ["**/*"],
  "exclude_globs": [
    "sender_config.json",
    "receiver_config.json",
    ".mail_zip_*",
    ".mail_zip_*/**",
    "__pycache__/**",
    "*.pyc"
  ],
  "include_deletes": false,
  "poll_seconds": 2,
  "debounce_seconds": 2,
  "send_on_start": false,
  "subject_prefix": "[MAGO-ZIP-SYNC]",
  "smtp_host": "smtp.daouoffice.com",
  "smtp_port": 465,
  "smtp_security": "ssl",
  "username": "your_id@company.com",
  "password": "mail-or-app-password",
  "from_addr": "your_id@company.com",
  "to_addr": "receiver@company.com",
  "secret_token": "긴_랜덤_문자열"
}
```

### 3. 집 PC baseline snapshot 생성

회사 폴더와 집 폴더가 같은 상태일 때 실행한다.

```bash
python3 scripts/mail_zip_sync/sender.py --snapshot
```

이 명령은 현재 파일 해시를 기록만 하고 메일은 보내지 않는다.

중요:

```text
snapshot 이후의 변경분부터 자동 전송된다.
```

### 4. 회사 PC receiver 설정 파일 생성

회사 PC에서 실행:

```bash
python3 scripts/mail_zip_sync/receiver.py
```

처음 실행하면 `receiver_config.json`이 생기고 종료된다.

예시:

```json
{
  "imap_host": "imap.daouoffice.com",
  "imap_port": 993,
  "imap_ssl": true,
  "username": "receiver@company.com",
  "password": "mail-or-app-password",
  "mailbox": "INBOX",
  "allowed_sender": "your_id@company.com",
  "subject_prefix": "[MAGO-ZIP-SYNC]",
  "secret_token": "sender와_같은_긴_랜덤_문자열",
  "target_dir": "D:/mago_tool",
  "inbox_dir": "D:/mago_zip_sync/inbox",
  "backup_dir": "D:/mago_zip_sync/backups",
  "log_dir": "D:/mago_zip_sync/logs",
  "poll_interval_seconds": 5,
  "allow_overwrite_without_previous": false,
  "allow_missing_previous": false,
  "test_commands": ["python main.py --help"],
  "command_timeout_seconds": 120
}
```

## 평소 실행

집 PC:

```bash
python3 scripts/mail_zip_sync/sender.py
```

회사 PC:

```bash
python3 scripts/mail_zip_sync/receiver.py
```

그 뒤의 체감은 다음과 같다.

```text
집에서 main.py 저장
-> sender가 변경 감지
-> zip + manifest 생성
-> Daou 메일 전송
-> 회사 receiver가 메일 수신
-> token/SHA256/manifest 검증
-> 기존 파일 백업
-> 지정 폴더에 적용
-> test_commands 실행
-> log_dir에 결과 저장
```

## Nuke render는 언제 붙이나

처음부터 Nuke render까지 자동화하지 않는다.

추천 단계:

```text
1. 파일 반입만 자동화
2. python main.py --help 같은 smoke test
3. ShotGrid 연결 테스트
4. Nuke command dry run
5. 짧은 Nuke background render
```

`receiver_config.json`의 `test_commands`를 단계별로 바꾼다.

단순 smoke test:

```json
{
  "test_commands": ["python main.py --help"]
}
```

ShotGrid 연결 테스트:

```json
{
  "test_commands": ["python main.py --shotgrid-test --shot SH010"]
}
```

Nuke dry run:

```json
{
  "test_commands": ["python main.py --build-nuke-command --shot SH010"]
}
```

짧은 Nuke render:

```json
{
  "test_commands": [
    "\"C:/Program Files/Nuke15.0v2/Nuke15.0.exe\" -x D:/mago_tests/test_render.nk -F 1001-1003"
  ],
  "command_timeout_seconds": 600
}
```

## 보안 규칙

- `secret_token`은 길고 랜덤하게 만든다.
- `sender_config.json`, `receiver_config.json`은 메일/zip에 포함하지 않는다.
- receiver는 `allowed_sender`와 `subject_prefix`가 맞는 메일만 처리한다.
- zip 전체 SHA256과 payload 파일 SHA256을 모두 확인한다.
- manifest의 `previous_sha256`이 회사 파일과 다르면 적용하지 않는다.
- 적용 전 기존 파일을 `backup_dir`에 복사한다.
- `allow_overwrite_without_previous`는 기본값 `false`로 둔다.
- 테스트가 안정화되기 전에는 Nuke render를 자동으로 돌리지 않는다.

## 장애 대응

### sender가 baseline이 없다고 한다

```bash
python3 scripts/mail_zip_sync/sender.py --snapshot
```

단, 집 폴더와 회사 폴더가 같은 상태일 때 실행해야 한다.

### receiver가 overwrite without baseline 에러를 낸다

회사 파일은 존재하는데 manifest에 이전 해시가 없다는 뜻이다.

해결:

```text
1. 집/회사 폴더를 같은 상태로 맞춘다.
2. 집에서 sender.py --snapshot 실행
3. 그 이후 수정부터 전송한다.
```

### receiver가 Target file changed 에러를 낸다

회사 PC 파일이 sender가 알고 있던 이전 상태와 다르다는 뜻이다.

해결:

```text
회사 파일 변경 내용을 확인
필요하면 백업
집/회사 폴더 기준을 다시 맞춤
다시 snapshot
```

### 메일 로그인이 안 된다

확인:

```text
Daou SMTP/IMAP 허용 여부
앱 비밀번호 필요 여부
465 SSL 또는 587 STARTTLS 여부
계정 잠김 여부
```

## 최종 결론

현재 조건에서는 GitLab이나 Git 설치를 기다리지 않고 다음 방식으로 시작하는 것이 가장 빠르다.

```text
집 PC sender.py
-> 변경 파일 zip 생성
-> manifest.json 생성
-> Daou 메일 발송

회사 PC receiver.py
-> Daou 메일 수신
-> 발신자/token/SHA256/manifest 검증
-> 기존 파일 백업
-> 지정 폴더에 적용
-> 가벼운 테스트부터 실행
```

사내 GitLab 승인이 나고 회사 PC에서 Git 사용이 가능해지면, 이후에 git patch 방식으로 업그레이드하면 된다.
