#!/usr/bin/env python3
"""Watch a git repo and send changed files as a patch email."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from mail_patch_sync import NoChangesError, generate_patch, load_or_create_config, send_patch


DEFAULT_CONFIG = {
    "repo_path": ".",
    "outbox_dir": "./mail_patch_outbox",
    "poll_seconds": 2,
    "debounce_seconds": 2,
    "send_on_start": False,
    "exclude_globs": [
        "sender_config.json",
        "receiver_config.json",
        "mail_patch_outbox/**",
        ".mail_patch_outbox/**",
        ".mail_patch_inbox/**",
        ".mail_patch_backups/**",
        ".mail_patch_logs/**"
    ],
    "subject_prefix": "[MAGO-PATCH]",
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
    parser.add_argument("--once", action="store_true", help="Generate and send one patch, then exit.")
    return parser.parse_args()


def latest_repo_mtime(repo_path: Path) -> float:
    latest = 0.0
    for path in repo_path.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    return latest


def send_current_patch(config: dict) -> bool:
    repo_path = Path(config["repo_path"]).resolve()
    outbox_dir = Path(config["outbox_dir"]).resolve()
    try:
        patch = generate_patch(repo_path, outbox_dir, exclude_globs=config.get("exclude_globs", []))
    except NoChangesError as exc:
        print(f"[sender] {exc}")
        return False

    send_patch(config, patch)
    print(f"[sender] sent {patch.path} sha256={patch.sha256}")
    return True


def watch_and_send(config: dict) -> None:
    repo_path = Path(config["repo_path"]).resolve()
    poll_seconds = float(config["poll_seconds"])
    debounce_seconds = float(config["debounce_seconds"])
    last_mtime = latest_repo_mtime(repo_path)

    if config.get("send_on_start", False):
        send_current_patch(config)

    print(f"[sender] watching {repo_path}")
    while True:
        current_mtime = latest_repo_mtime(repo_path)
        if current_mtime > last_mtime:
            last_mtime = current_mtime
            time.sleep(debounce_seconds)
            send_current_patch(config)
            last_mtime = latest_repo_mtime(repo_path)
        time.sleep(poll_seconds)


def main() -> int:
    args = parse_args()
    config, created = load_or_create_config(Path(args.config), DEFAULT_CONFIG)
    if created:
        print(f"[sender] created {args.config}. Edit it, then run sender.py again.")
        return 0

    if args.once:
        return 0 if send_current_patch(config) else 1

    watch_and_send(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
