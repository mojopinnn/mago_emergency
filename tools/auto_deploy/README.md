# Auto Deploy (메일 기반 자동 배포)

폐쇄망 환경에서 집 PC → 회사 PC로 파일을 자동 전송하는 도구입니다.

## 구조

```
[집 PC]                          [회사 PC]
파일 저장 → sender.py 감지       receiver.py가 메일 확인
         → Gmail로 자동 전송  →  → 첨부파일 자동 저장
                                 → 지정 폴더에 덮어쓰기
```

## 사전 준비

### Gmail 앱 비밀번호 생성
1. https://myaccount.google.com/apppasswords 접속
2. 앱 이름 입력 (예: `auto-deploy`) → 만들기
3. 나온 **16자리 비밀번호**를 메모

### Gmail IMAP 활성화 (회사 PC가 Gmail인 경우)
1. Gmail 설정 → 전달 및 POP/IMAP
2. **IMAP 사용** 체크 → 저장

### Python 패키지
```bash
pip install watchdog  # sender.py에서만 필요 (없어도 동작함)
```

## 사용법

### 1단계: 집 PC (sender)
```bash
python sender.py
# 처음 실행 → sender_config.json 생성됨
# 설정 수정 후 다시 실행
```

`sender_config.json` 예시:
```json
{
  "gmail_address": "myemail@gmail.com",
  "gmail_app_password": "abcd efgh ijkl mnop",
  "receiver_email": "company@email.com",
  "watch_files": [
    "C:/projects/nuke_tool/main.py",
    "C:/projects/nuke_tool/render.py"
  ],
  "subject_prefix": "[AUTO-DEPLOY]",
  "min_interval_seconds": 5
}
```

### 2단계: 회사 PC (receiver)
```bash
python receiver.py
# 처음 실행 → receiver_config.json 생성됨
# 설정 수정 후 다시 실행
```

`receiver_config.json` 예시:
```json
{
  "gmail_address": "company@email.com",
  "gmail_app_password": "abcd efgh ijkl mnop",
  "save_directory": "C:/projects/nuke_tool",
  "subject_prefix": "[AUTO-DEPLOY]",
  "check_interval_seconds": 10,
  "delete_after_download": true
}

```

### 결과

집에서 `main.py` 저장 → 5~15초 후 회사 PC의 지정 폴더에 자동 반영
