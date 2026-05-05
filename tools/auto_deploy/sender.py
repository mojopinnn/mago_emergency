"""
[집 PC용] 파일 변경 감지 → 자동 메일 발송 스크립트

사용법:
    python sender.py

최초 실행 시 설정 파일(sender_config.json)이 생성됩니다.
설정 파일을 수정한 후 다시 실행하세요.

필요 패키지:
    pip install watchdog
"""

import json
import os
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "sender_config.json"

DEFAULT_CONFIG = {
    "gmail_address": "your@gmail.com",
    "gmail_app_password": "앱 비밀번호를 입력하세요",
    "receiver_email": "회사 메일 주소를 입력하세요",
    "watch_files": [
        "/path/to/your/project/main.py"
    ],
    "subject_prefix": "[AUTO-DEPLOY]",
    "min_interval_seconds": 5,
}


def load_config():
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"설정 파일이 생성되었습니다: {CONFIG_FILE}")
        print("설정 파일을 수정한 후 다시 실행하세요.")
        print()
        print("Gmail 앱 비밀번호 생성 방법:")
        print("  1. https://myaccount.google.com/apppasswords 접속")
        print("  2. 앱 이름 입력 (예: auto-deploy) → 생성")
        print("  3. 나온 16자리 비밀번호를 설정 파일에 입력")
        sys.exit(0)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    if config["gmail_app_password"] == "앱 비밀번호를 입력하세요":
        print("설정 파일을 먼저 수정해주세요:", CONFIG_FILE)
        sys.exit(1)

    return config


def send_file(config, filepath):
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"  파일 없음: {filepath}")
        return False

    msg = EmailMessage()
    msg["Subject"] = f"{config['subject_prefix']} {filepath.name}"
    msg["From"] = config["gmail_address"]
    msg["To"] = config["receiver_email"]
    msg.set_content(f"Auto-deploy: {filepath.name}\nTime: {time.strftime('%H:%M:%S')}")

    with open(filepath, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="octet-stream",
            filename=filepath.name,
        )

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(config["gmail_address"], config["gmail_app_password"])
        smtp.send_message(msg)

    return True


def main():
    config = load_config()
    watch_files = [Path(f) for f in config["watch_files"]]
    interval = config["min_interval_seconds"]

    print("=" * 50)
    print("  자동 배포 - 파일 감시 시작")
    print("=" * 50)
    print(f"  발신: {config['gmail_address']}")
    print(f"  수신: {config['receiver_email']}")
    print(f"  감시 대상:")
    for f in watch_files:
        print(f"    - {f}")
    print(f"  최소 전송 간격: {interval}초")
    print("=" * 50)
    print()
    print("파일을 수정하면 자동으로 메일이 전송됩니다.")
    print("종료하려면 Ctrl+C를 누르세요.")
    print()

    last_mtimes = {}
    last_sent = {}

    for f in watch_files:
        if f.exists():
            last_mtimes[str(f)] = f.stat().st_mtime

    try:
        while True:
            for filepath in watch_files:
                key = str(filepath)

                if not filepath.exists():
                    continue

                current_mtime = filepath.stat().st_mtime
                prev_mtime = last_mtimes.get(key, 0)

                if current_mtime > prev_mtime:
                    now = time.time()
                    if now - last_sent.get(key, 0) < interval:
                        continue

                    last_mtimes[key] = current_mtime
                    ts = time.strftime("%H:%M:%S")
                    print(f"[{ts}] 변경 감지: {filepath.name} → 전송 중...", end=" ")

                    try:
                        send_file(config, filepath)
                        last_sent[key] = now
                        print("완료!")
                    except Exception as e:
                        print(f"실패: {e}")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n종료됨.")


if __name__ == "__main__":
    main()
