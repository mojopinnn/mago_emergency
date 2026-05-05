#!/usr/bin/env python3
"""Shared helpers for Daou mail based git patch sync."""

from __future__ import annotations

import datetime as dt
import email
import hashlib
import imaplib
import json
import os
import shutil
import smtplib
import subprocess
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Sequence


class PatchSyncError(RuntimeError):
    """Base error raised by the patch sync helpers."""


class NoChangesError(PatchSyncError):
    """Raised when there is no git diff to send."""


@dataclass(frozen=True)
class PatchInfo:
    path: Path
    sha256: str
    created_at: str


@dataclass(frozen=True)
class ReceivedPatch:
    patch_path: Path
    sha256: str
    subject: str
    sender: str


def utc_stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")


def load_or_create_config(path: Path, defaults: dict) -> tuple[dict, bool]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")), False

    path.write_text(json.dumps(defaults, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return defaults, True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repo_path: Path, args: Sequence[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    command = ["git", "-C", str(repo_path), *args]
    try:
        return subprocess.run(
            command,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise PatchSyncError(
            "\n".join(
                [
                    f"Command failed: {' '.join(command)}",
                    stdout.rstrip(),
                    stderr.rstrip(),
                ]
            ).strip()
        ) from exc


def _git_output(repo_path: Path, args: Sequence[str]) -> str:
    return run_git(repo_path, args).stdout.decode("utf-8", errors="replace")


def _repo_relative(repo_path: Path, path: Path) -> str | None:
    try:
        return path.resolve().relative_to(repo_path.resolve()).as_posix()
    except ValueError:
        return None


def _excluded_relative_paths(repo_path: Path, exclude_paths: Iterable[Path]) -> set[str]:
    relatives = set()
    for path in exclude_paths:
        relative = _repo_relative(repo_path, path)
        if relative:
            relatives.add(relative.rstrip("/"))
    return relatives


def _is_excluded(path: str, excluded: set[str], exclude_globs: Iterable[str]) -> bool:
    return any(path == item or path.startswith(f"{item}/") for item in excluded) or any(
        fnmatch(path, pattern) for pattern in exclude_globs
    )


def _intent_to_add_untracked(repo_path: Path, exclude_paths: Iterable[Path], exclude_globs: Iterable[str]) -> list[str]:
    excluded = _excluded_relative_paths(repo_path, exclude_paths)
    output = _git_output(repo_path, ["ls-files", "--others", "--exclude-standard"])
    untracked = [
        line for line in output.splitlines() if line.strip() and not _is_excluded(line, excluded, exclude_globs)
    ]
    if untracked:
        run_git(repo_path, ["add", "--intent-to-add", "--", *untracked])
    return untracked


def _exclude_pathspecs(repo_path: Path, exclude_paths: Iterable[Path]) -> list[str]:
    pathspecs = []
    for relative in sorted(_excluded_relative_paths(repo_path, exclude_paths)):
        pathspecs.append(f":(exclude){relative}")
        pathspecs.append(f":(exclude){relative}/**")
    return pathspecs


def _exclude_glob_pathspecs(exclude_globs: Iterable[str]) -> list[str]:
    return [f":(exclude){pattern}" for pattern in exclude_globs]


def generate_patch(
    repo_path: Path,
    output_dir: Path,
    *,
    include_untracked: bool = True,
    exclude_paths: Iterable[Path] = (),
    exclude_globs: Iterable[str] = (),
) -> PatchInfo:
    repo_path = repo_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    effective_excludes = [output_dir, *exclude_paths]

    intent_paths: list[str] = []
    try:
        if include_untracked:
            intent_paths = _intent_to_add_untracked(repo_path, effective_excludes, exclude_globs)

        diff_args = [
            "diff",
            "--binary",
            "HEAD",
            "--",
            ".",
            *_exclude_pathspecs(repo_path, effective_excludes),
            *_exclude_glob_pathspecs(exclude_globs),
        ]
        diff = run_git(repo_path, diff_args).stdout
        if not diff.strip():
            raise NoChangesError("No git changes found. Edit tracked files or enable intent-to-add for new files.")
    finally:
        if intent_paths:
            run_git(repo_path, ["reset", "--", *intent_paths])

    digest = hashlib.sha256(diff).hexdigest()
    created_at = utc_stamp()
    patch_path = output_dir / f"change_{created_at}_{digest[:12]}.patch"
    patch_path.write_bytes(diff)
    return PatchInfo(path=patch_path, sha256=digest, created_at=created_at)


def patch_changed_paths(patch_path: Path) -> list[str]:
    paths: list[str] = []
    for raw_line in patch_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line.startswith("diff --git "):
            continue
        parts = raw_line.split()
        if len(parts) < 4 or not parts[3].startswith("b/"):
            continue
        path = parts[3][2:]
        if path != "/dev/null" and path not in paths:
            paths.append(path)
    return paths


def backup_changed_files(repo_path: Path, patch_path: Path, backup_root: Path) -> Path:
    backup_dir = backup_root / utc_stamp()
    copied = False
    for relative in patch_changed_paths(patch_path):
        source = (repo_path / relative).resolve()
        if not source.exists() or not source.is_file():
            continue
        if repo_path.resolve() not in source.parents:
            raise PatchSyncError(f"Patch path escapes repo: {relative}")
        destination = backup_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied = True

    backup_dir.mkdir(parents=True, exist_ok=True)
    if not copied:
        (backup_dir / "NO_EXISTING_FILES.txt").write_text(
            "Patch only adds files or modifies files that did not exist before apply.\n",
            encoding="utf-8",
        )
    return backup_dir


def check_patch(repo_path: Path, patch_path: Path) -> None:
    run_git(repo_path, ["apply", "--check", str(patch_path)])


def apply_patch(repo_path: Path, patch_path: Path, backup_root: Path) -> Path:
    check_patch(repo_path, patch_path)
    backup_dir = backup_changed_files(repo_path, patch_path, backup_root)
    run_git(repo_path, ["apply", str(patch_path)])
    return backup_dir


def run_commands(repo_path: Path, commands: Iterable[str], timeout_seconds: int) -> list[tuple[str, int, str]]:
    results: list[tuple[str, int, str]] = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=repo_path,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
        )
        results.append((command, completed.returncode, completed.stdout))
        if completed.returncode != 0:
            break
    return results


def build_patch_email(config: dict, patch: PatchInfo) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config["from_addr"]
    message["To"] = config["to_addr"]
    message["Subject"] = f'{config["subject_prefix"]} {patch.path.name}'
    message.set_content(
        "\n".join(
            [
                f'token: {config["secret_token"]}',
                f"sha256: {patch.sha256}",
                f"created_at: {patch.created_at}",
                "type: git-patch",
                "",
            ]
        )
    )
    message.add_attachment(
        patch.path.read_bytes(),
        maintype="text",
        subtype="x-patch",
        filename=patch.path.name,
    )
    return message


def _smtp_client(config: dict):
    security = config.get("smtp_security", "ssl")
    if security == "ssl":
        return smtplib.SMTP_SSL(config["smtp_host"], int(config["smtp_port"]), timeout=30)
    client = smtplib.SMTP(config["smtp_host"], int(config["smtp_port"]), timeout=30)
    if security == "starttls":
        client.starttls()
    return client


def send_email(config: dict, message: EmailMessage) -> None:
    with _smtp_client(config) as client:
        client.login(config["username"], config["password"])
        client.send_message(message)


def send_patch(config: dict, patch: PatchInfo) -> None:
    send_email(config, build_patch_email(config, patch))


def extract_body(message: email.message.Message) -> str:
    if message.is_multipart():
        parts = []
        for part in message.walk():
            if part.get_content_maintype() == "text" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        return "\n".join(parts)

    payload = message.get_payload(decode=True)
    if not payload:
        return ""
    return payload.decode(message.get_content_charset() or "utf-8", errors="replace")


def body_field(body: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in body.splitlines():
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def sender_matches(actual_sender: str, allowed_sender: str) -> bool:
    _, actual_addr = parseaddr(actual_sender)
    return actual_addr.lower() == allowed_sender.lower()


def _imap_client(config: dict):
    if config.get("imap_ssl", True):
        return imaplib.IMAP4_SSL(config["imap_host"], int(config["imap_port"]))
    return imaplib.IMAP4(config["imap_host"], int(config["imap_port"]))


def fetch_patch_messages(config: dict, inbox_dir: Path) -> list[ReceivedPatch]:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    received: list[ReceivedPatch] = []

    with _imap_client(config) as client:
        client.login(config["username"], config["password"])
        client.select(config.get("mailbox", "INBOX"))
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            raise PatchSyncError("IMAP search failed")

        for message_id in data[0].split():
            status, payload = client.fetch(message_id, "(BODY.PEEK[])")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue

            message = email.message_from_bytes(payload[0][1])
            subject = str(message.get("Subject", ""))
            sender = str(message.get("From", ""))
            if not subject.startswith(config["subject_prefix"]):
                continue
            if not sender_matches(sender, config["allowed_sender"]):
                continue

            body = extract_body(message)
            if body_field(body, "token") != config["secret_token"]:
                continue
            expected_sha = body_field(body, "sha256")
            if not expected_sha:
                continue

            for part in message.walk():
                filename = part.get_filename()
                if not filename or not filename.endswith(".patch"):
                    continue
                patch_path = inbox_dir / f"{utc_stamp()}_{Path(filename).name}"
                patch_path.write_bytes(part.get_payload(decode=True) or b"")
                actual_sha = sha256_file(patch_path)
                if actual_sha != expected_sha:
                    patch_path.unlink(missing_ok=True)
                    raise PatchSyncError(f"SHA256 mismatch for {filename}")
                received.append(ReceivedPatch(patch_path, expected_sha, subject, sender))
                client.store(message_id, "+FLAGS", "\\Seen")

    return received


def build_result_email(config: dict, subject: str, log_path: Path) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config.get("result_from_addr", config["username"])
    message["To"] = config["result_to_addr"]
    message["Subject"] = f'{config.get("result_subject_prefix", "[MAGO-PATCH-RESULT]")} {subject}'
    message.set_content(log_path.read_text(encoding="utf-8", errors="replace"))
    message.add_attachment(
        log_path.read_bytes(),
        maintype="text",
        subtype="plain",
        filename=log_path.name,
    )
    return message


def send_result_email(config: dict, subject: str, log_path: Path) -> None:
    send_email(config, build_result_email(config, subject, log_path))


def write_result_log(path: Path, subject: str, backup_dir: Path | None, results: list[tuple[str, int, str]]) -> None:
    lines = [f"subject: {subject}", f"created_at: {utc_stamp()}"]
    if backup_dir:
        lines.append(f"backup_dir: {backup_dir}")
    for command, return_code, output in results:
        lines.extend(["", f"$ {command}", f"exit_code: {return_code}", output.rstrip()])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sleep_forever(interval_seconds: float) -> None:
    while True:
        time.sleep(interval_seconds)
