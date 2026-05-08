#!/usr/bin/env python3
"""Watch a folder and send changed files as a zip/manifest package email."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from mail_zip_sync import (
    BaselineRequiredError,
    NoChangesError,
    create_package,
    iter_sync_files,
    load_or_create_config,
    save_state,
    send_package,
    snapshot_files,
)


DEFAULT_CONFIG = {
    "source_dir": ".",
    "outbox_dir": "./.mail_zip_outbox",
    "state_path": "./.mail_zip_sender_state.json",
    "include_globs": ["**/*"],
    "exclude_globs": [
        "sender_config.json",
        "receiver_config.json",
        ".mail_zip_*",
        ".mail_zip_*/**",
        "__pycache__/**",
        "*.pyc",
    ],
    "include_deletes": False,
    "poll_seconds": 2,
    "debounce_seconds": 2,
    "send_on_start": False,
    "subject_prefix": "[MAGO-ZIP-SYNC]",
    "smtp_host": "smtp.daouoffice.com",
    "smtp_port": 465,
    "smtp_security": "ssl",
    "username": "your_id@company.com",
    "password": "CHANGE_ME",
    "from_addr": "your_id@company.com",
    "to_addr": "receiver@company.com",
    "secret_token": "CHANGE_ME_LONG_RANDOM_STRING",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="sender_config.json", help="Path to sender config JSON.")
    parser.add_argument("--once", action="store_true", help="Generate and send one package, then exit.")
    parser.add_argument("--snapshot", action="store_true", help="Record current file hashes without sending mail.")
    return parser.parse_args()


def latest_source_mtime(config: dict) -> float:
    source_dir = Path(config["source_dir"]).resolve()
    latest = 0.0
    for path in iter_sync_files(source_dir, config.get("include_globs", ["**/*"]), config.get("exclude_globs", [])):
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    return latest


def write_snapshot(config: dict) -> None:
    source_dir = Path(config["source_dir"]).resolve()
    state_path = Path(config["state_path"]).resolve()
    files = snapshot_files(source_dir, config.get("include_globs", ["**/*"]), config.get("exclude_globs", []))
    save_state(state_path, files)
    print(f"[sender] snapshot saved: {state_path} ({len(files)} files)")


def send_current_package(config: dict) -> bool:
    source_dir = Path(config["source_dir"]).resolve()
    outbox_dir = Path(config["outbox_dir"]).resolve()
    state_path = Path(config["state_path"]).resolve()
    try:
        package = create_package(
            source_dir,
            outbox_dir,
            state_path,
            include_globs=config.get("include_globs", ["**/*"]),
            exclude_globs=config.get("exclude_globs", []),
            include_deletes=bool(config.get("include_deletes", False)),
        )
    except BaselineRequiredError as exc:
        print(f"[sender] {exc}")
        print("[sender] Run with --snapshot after the company folder has the same baseline.")
        return False
    except NoChangesError as exc:
        print(f"[sender] {exc}")
        return False

    send_package(config, package)
    save_state(state_path, package.current_state)
    print(f"[sender] sent {package.path} sha256={package.sha256}")
    return True


def watch_and_send(config: dict) -> None:
    poll_seconds = float(config["poll_seconds"])
    debounce_seconds = float(config["debounce_seconds"])
    last_mtime = latest_source_mtime(config)

    if config.get("send_on_start", False):
        send_current_package(config)

    print(f"[sender] watching {Path(config['source_dir']).resolve()}")
    while True:
        current_mtime = latest_source_mtime(config)
        if current_mtime > last_mtime:
            last_mtime = current_mtime
            time.sleep(debounce_seconds)
            send_current_package(config)
            last_mtime = latest_source_mtime(config)
        time.sleep(poll_seconds)


def main() -> int:
    args = parse_args()
    config, created = load_or_create_config(Path(args.config), DEFAULT_CONFIG)
    if created:
        print(f"[sender] created {args.config}. Edit it, then run sender.py --snapshot once.")
        return 0

    if args.snapshot:
        write_snapshot(config)
        return 0
    if args.once:
        return 0 if send_current_package(config) else 1

    watch_and_send(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
