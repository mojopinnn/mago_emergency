"""
[회사 PC용] 메일 수신 → 첨부파일 자동 저장 스크립트

사용법:
    python receiver.py

최초 실행 시 설정 파일(receiver_config.json)이 생성됩니다.
설정 파일을 수정한 후 다시 실행하세요.

Gmail IMAP 활성화 필요:
    Gmail 설정 → 전달 및 POP/IMAP → IMAP 사용 체크
"""

import email
import imaplib
import json
import os
import sys
import time
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "receiver_config.json"

DEFAULT_CONFIG = {
    "gmail_address": "회사 메일 주소를 입력하세요",
    "gmail_app_password": "앱 비밀번호를 입력하세요",
    "save_directory": "C:/path/to/your/project",
    "subject_prefix": "[AUTO-DEPLOY]",
    "check_interval_seconds": 10,
    "delete_after_download": True,
}


def load_config():
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"설정 파일이 생성되었습니다: {CONFIG_FILE}")
        print("설정 파일을 수정한 후 다시 실행하세요.")
        print()
        print("Gmail 사용 시:")
        print("  1. Gmail 설정 → 전달 및 POP/IMAP → IMAP 사용 체크")
        print("  2. https://myaccount.google.com/apppasswords 에서 앱 비밀번호 생성")
        print()
        print("회사 메일(Outlook 등) 사용 시:")
        print("  receiver_config.json에서 IMAP 서버 설정을 추가해야 합니다.")
        sys.exit(0)

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    if config["gmail_app_password"] == "앱 비밀번호를 입력하세요":
        print("설정 파일을 먼저 수정해주세요:", CONFIG_FILE)
        sys.exit(1)

    save_dir = Path(config["save_directory"])
    if not save_dir.exists():
        save_dir.mkdir(parents=True)
        print(f"저장 폴더 생성: {save_dir}")

    return config


def check_and_download(config):
    prefix = config["subject_prefix"]
    save_dir = Path(config["save_directory"])
    downloaded = []

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        imap.login(config["gmail_address"], config["gmail_app_password"])
        imap.select("INBOX")

        query = f'(UNSEEN SUBJECT "{prefix}")'
        _, msg_ids = imap.search(None, query)

        if not msg_ids[0]:
            return downloaded

        for msg_id in msg_ids[0].split():
            _, msg_data = imap.fetch(msg_id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            for part in msg.walk():
                if part.get_content_disposition() != "attachment":
                    continue

                filename = part.get_filename()
                if not filename:
                    continue

                filepath = save_dir / filename
                content = part.get_payload(decode=True)

                with open(filepath, "wb") as f:
                    f.write(content)

                downloaded.append(filename)

            if config.get("delete_after_download"):
                imap.store(msg_id, "+FLAGS", "\\Deleted")

        if config.get("delete_after_download"):
            imap.expunge()

    finally:
        imap.logout()

    return downloaded


def main():
    config = load_config()

    print("=" * 50)
    print("  자동 배포 - 메일 수신 대기")
    print("=" * 50)
    print(f"  메일: {config['gmail_address']}")
    print(f"  저장 위치: {config['save_directory']}")
    print(f"  확인 간격: {config['check_interval_seconds']}초")
    print("=" * 50)
    print()
    print("메일이 오면 첨부파일을 자동으로 저장합니다.")
    print("종료하려면 Ctrl+C를 누르세요.")
    print()

    try:
        while True:
            try:
                files = check_and_download(config)
                if files:
                    ts = time.strftime("%H:%M:%S")
                    for f in files:
                        print(f"[{ts}] 다운로드 완료: {f}")
            except Exception as e:
                ts = time.strftime("%H:%M:%S")
                print(f"[{ts}] 오류: {e}")

            time.sleep(config["check_interval_seconds"])

    except KeyboardInterrupt:
        print("\n종료됨.")


if __name__ == "__main__":
    main()
