#!/usr/bin/env python3
"""Receive Daou Office zip/manifest packages and apply them without Git."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from mail_zip_sync import (
    ZipSyncError,
    apply_package,
    fetch_zip_messages,
    load_or_create_config,
    run_commands,
    utc_stamp,
    write_result_log,
)


DEFAULT_CONFIG = {
    "imap_host": "imap.daouoffice.com",
    "imap_port": 993,
    "imap_ssl": True,
    "username": "receiver@company.com",
    "password": "DAOU_MAIL_PASSWORD_OR_APP_PASSWORD",
    "mailbox": "INBOX",
    "allowed_sender": "home@example.com",
    "subject_prefix": "[MAGO-ZIP-SYNC]",
    "secret_token": "CHANGE_ME_TO_LONG_RANDOM_TEXT",
    "target_dir": "D:/mago_tool",
    "inbox_dir": "D:/mago_zip_sync/inbox",
    "backup_dir": "D:/mago_zip_sync/backups",
    "log_dir": "D:/mago_zip_sync/logs",
    "poll_interval_seconds": 5,
    "allow_overwrite_without_previous": False,
    "allow_missing_previous": False,
    "test_commands": [
        "python main.py --help"
    ],
    "command_timeout_seconds": 120,
}


def process_once(config: dict) -> int:
    target_dir = Path(config["target_dir"]).expanduser().resolve()
    inbox_dir = Path(config["inbox_dir"]).expanduser().resolve()
    backup_root = Path(config["backup_dir"]).expanduser().resolve()
    log_dir = Path(config["log_dir"]).expanduser().resolve()

    packages = fetch_zip_messages(config, inbox_dir)
    if not packages:
        print("No new zip sync mail.")
        return 0

    exit_code = 0
    for package in packages:
        print(f"Applying {package.zip_path.name} from {package.sender}")
        backup_dir = None
        results = []
        try:
            backup_dir = apply_package(
                target_dir,
                package.zip_path,
                backup_root,
                allow_overwrite_without_previous=bool(config.get("allow_overwrite_without_previous", False)),
                allow_missing_previous=bool(config.get("allow_missing_previous", False)),
            )
            results = run_commands(
                target_dir,
                config.get("test_commands", []),
                int(config.get("command_timeout_seconds", 120)),
            )
            if any(return_code != 0 for _, return_code, _ in results):
                exit_code = 1
        except (ZipSyncError, RuntimeError, OSError) as exc:
            exit_code = 1
            results = [("apply_package", 1, str(exc))]
        finally:
            log_path = log_dir / f"result_{utc_stamp()}.log"
            write_result_log(log_path, package, backup_dir, results)
            print(f"Result log: {log_path}")

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="receiver_config.json", help="Path to receiver config JSON.")
    parser.add_argument("--once", action="store_true", help="Check mail once and exit.")
    args = parser.parse_args()

    config_path = Path(args.config)
    config, created = load_or_create_config(config_path, DEFAULT_CONFIG)
    if created:
        print(f"Created {config_path}. Edit it, then run receiver.py again.")
        return 0

    while True:
        try:
            status = process_once(config)
        except KeyboardInterrupt:
            print("Stopped.")
            return 130
        if args.once:
            return status
        time.sleep(float(config.get("poll_interval_seconds", 5)))


if __name__ == "__main__":
    sys.exit(main())
