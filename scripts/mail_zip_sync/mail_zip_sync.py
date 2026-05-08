#!/usr/bin/env python3
"""Shared helpers for Daou mail based zip/manifest sync."""

from __future__ import annotations

import datetime as dt
import email
import hashlib
import imaplib
import json
import shutil
import smtplib
import subprocess
import time
import zipfile
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable


class ZipSyncError(RuntimeError):
    """Base error raised by zip sync helpers."""


class NoChangesError(ZipSyncError):
    """Raised when there are no changed files to package."""


class BaselineRequiredError(ZipSyncError):
    """Raised when sender state has not been initialized."""


@dataclass(frozen=True)
class PackageInfo:
    path: Path
    sha256: str
    package_id: str
    manifest: dict
    current_state: dict[str, str]


@dataclass(frozen=True)
class ReceivedPackage:
    zip_path: Path
    sha256: str
    subject: str
    sender: str


DEFAULT_EXCLUDE_GLOBS = (
    ".git/**",
    "__pycache__/**",
    "*.pyc",
    "sender_config.json",
    "receiver_config.json",
    ".mail_zip_*",
    ".mail_zip_*/**",
    "mail_zip_outbox/**",
    "mail_zip_inbox/**",
    "mail_zip_backups/**",
    "mail_zip_logs/**",
)


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_state(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in data.get("files", {}).items()}


def save_state(path: Path, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"updated_at": utc_stamp(), "files": files}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def is_safe_relative_path(path: str) -> bool:
    candidate = Path(path)
    return not candidate.is_absolute() and ".." not in candidate.parts and path not in ("", ".")


def _merge_patterns(patterns: Iterable[str], defaults: Iterable[str]) -> tuple[str, ...]:
    merged = list(defaults)
    for pattern in patterns:
        if pattern not in merged:
            merged.append(pattern)
    return tuple(merged)


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(
        pattern == "**/*" or fnmatch(path, pattern) or fnmatch(f"./{path}", pattern)
        for pattern in patterns
    )


def iter_sync_files(source_dir: Path, include_globs: Iterable[str], exclude_globs: Iterable[str]) -> list[Path]:
    source_dir = source_dir.resolve()
    includes = tuple(include_globs) or ("**/*",)
    excludes = _merge_patterns(exclude_globs, DEFAULT_EXCLUDE_GLOBS)
    files: list[Path] = []

    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir).as_posix()
        if not is_safe_relative_path(relative):
            continue
        if not _matches_any(relative, includes):
            continue
        if _matches_any(relative, excludes):
            continue
        files.append(path)

    return sorted(files)


def snapshot_files(source_dir: Path, include_globs: Iterable[str], exclude_globs: Iterable[str]) -> dict[str, str]:
    source_dir = source_dir.resolve()
    return {
        path.relative_to(source_dir).as_posix(): sha256_file(path)
        for path in iter_sync_files(source_dir, include_globs, exclude_globs)
    }


def create_package(
    source_dir: Path,
    outbox_dir: Path,
    state_path: Path,
    *,
    include_globs: Iterable[str] = ("**/*",),
    exclude_globs: Iterable[str] = (),
    include_deletes: bool = False,
) -> PackageInfo:
    previous = load_state(state_path)
    if previous is None:
        raise BaselineRequiredError("Sender baseline is missing. Run sender.py --snapshot once before watching.")

    source_dir = source_dir.resolve()
    outbox_dir = outbox_dir.resolve()
    current = snapshot_files(source_dir, include_globs, exclude_globs)
    changed_paths = [path for path, digest in current.items() if previous.get(path) != digest]
    deleted_paths = [path for path in previous if path not in current] if include_deletes else []

    if not changed_paths and not deleted_paths:
        raise NoChangesError("No changed files found.")

    package_id = f"sync_{utc_stamp()}_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
    manifest_files = []
    for relative in changed_paths:
        file_path = source_dir / relative
        manifest_files.append(
            {
                "path": relative,
                "action": "upsert",
                "sha256": current[relative],
                "previous_sha256": previous.get(relative),
                "size": file_path.stat().st_size,
            }
        )
    for relative in deleted_paths:
        manifest_files.append(
            {
                "path": relative,
                "action": "delete",
                "sha256": None,
                "previous_sha256": previous.get(relative),
                "size": 0,
            }
        )

    manifest = {
        "version": 1,
        "package_id": package_id,
        "created_at": utc_stamp(),
        "files": manifest_files,
    }

    outbox_dir.mkdir(parents=True, exist_ok=True)
    zip_path = outbox_dir / f"{package_id}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        for item in manifest_files:
            if item["action"] != "upsert":
                continue
            archive.write(source_dir / item["path"], f"payload/{item['path']}")

    return PackageInfo(zip_path, sha256_file(zip_path), package_id, manifest, current)


def read_manifest(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as archive:
        try:
            data = archive.read("manifest.json")
        except KeyError as exc:
            raise ZipSyncError("Package is missing manifest.json") from exc
    return json.loads(data.decode("utf-8"))


def _backup_file(target_dir: Path, backup_dir: Path, relative: str) -> None:
    source = target_dir / relative
    if not source.exists() or not source.is_file():
        return
    destination = backup_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def validate_package(
    target_dir: Path,
    zip_path: Path,
    *,
    allow_overwrite_without_previous: bool = False,
    allow_missing_previous: bool = False,
) -> dict:
    target_dir = target_dir.resolve()
    manifest = read_manifest(zip_path)
    files = manifest.get("files", [])
    if manifest.get("version") != 1 or not isinstance(files, list):
        raise ZipSyncError("Unsupported manifest format.")

    with zipfile.ZipFile(zip_path) as archive:
        for item in files:
            relative = str(item.get("path", ""))
            action = item.get("action")
            previous_sha = item.get("previous_sha256")
            if not is_safe_relative_path(relative):
                raise ZipSyncError(f"Unsafe package path: {relative}")

            target = (target_dir / relative).resolve()
            if target_dir not in target.parents and target != target_dir:
                raise ZipSyncError(f"Package path escapes target: {relative}")

            current_sha = sha256_file(target) if target.exists() and target.is_file() else None
            if current_sha is not None and previous_sha is None and not allow_overwrite_without_previous:
                raise ZipSyncError(f"Refusing to overwrite existing file without baseline: {relative}")
            if current_sha is not None and previous_sha is not None and current_sha != previous_sha:
                raise ZipSyncError(f"Target file changed since sender baseline: {relative}")
            if current_sha is None and previous_sha is not None and not allow_missing_previous:
                raise ZipSyncError(f"Target file missing but sender expected previous content: {relative}")

            if action == "upsert":
                payload_name = f"payload/{relative}"
                try:
                    payload = archive.read(payload_name)
                except KeyError as exc:
                    raise ZipSyncError(f"Missing payload for {relative}") from exc
                if sha256_bytes(payload) != item.get("sha256"):
                    raise ZipSyncError(f"Payload SHA256 mismatch: {relative}")
            elif action == "delete":
                pass
            else:
                raise ZipSyncError(f"Unsupported action for {relative}: {action}")

    return manifest


def apply_package(
    target_dir: Path,
    zip_path: Path,
    backup_root: Path,
    *,
    allow_overwrite_without_previous: bool = False,
    allow_missing_previous: bool = False,
) -> Path:
    target_dir = target_dir.resolve()
    backup_dir = backup_root / utc_stamp()
    manifest = validate_package(
        target_dir,
        zip_path,
        allow_overwrite_without_previous=allow_overwrite_without_previous,
        allow_missing_previous=allow_missing_previous,
    )

    backup_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for item in manifest["files"]:
            relative = item["path"]
            _backup_file(target_dir, backup_dir, relative)
            target = target_dir / relative
            if item["action"] == "delete":
                if target.exists():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(f"payload/{relative}"))

    return backup_dir


def run_commands(target_dir: Path, commands: Iterable[str], timeout_seconds: int) -> list[tuple[str, int, str]]:
    results: list[tuple[str, int, str]] = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=target_dir,
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


def write_result_log(path: Path, package: ReceivedPackage | None, backup_dir: Path | None, results: list[tuple[str, int, str]]) -> None:
    lines = [f"created_at: {utc_stamp()}"]
    if package:
        lines.extend([f"subject: {package.subject}", f"package: {package.zip_path}", f"sha256: {package.sha256}"])
    if backup_dir:
        lines.append(f"backup_dir: {backup_dir}")
    for command, return_code, output in results:
        lines.extend(["", f"$ {command}", f"exit_code: {return_code}", output.rstrip()])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_package_email(config: dict, package: PackageInfo) -> EmailMessage:
    message = EmailMessage()
    message["From"] = config["from_addr"]
    message["To"] = config["to_addr"]
    message["Subject"] = f'{config["subject_prefix"]} {package.path.name}'
    message.set_content(
        "\n".join(
            [
                f'token: {config["secret_token"]}',
                f"sha256: {package.sha256}",
                f"package_id: {package.package_id}",
                "type: zip-manifest",
                "",
            ]
        )
    )
    message.add_attachment(
        package.path.read_bytes(),
        maintype="application",
        subtype="zip",
        filename=package.path.name,
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


def send_package(config: dict, package: PackageInfo) -> None:
    send_email(config, build_package_email(config, package))


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


def fetch_zip_messages(config: dict, inbox_dir: Path) -> list[ReceivedPackage]:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    received: list[ReceivedPackage] = []

    with _imap_client(config) as client:
        client.login(config["username"], config["password"])
        client.select(config.get("mailbox", "INBOX"))
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            raise ZipSyncError("IMAP search failed")

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
                if not filename or not filename.endswith(".zip"):
                    continue
                zip_path = inbox_dir / f"{utc_stamp()}_{Path(filename).name}"
                zip_path.write_bytes(part.get_payload(decode=True) or b"")
                actual_sha = sha256_file(zip_path)
                if actual_sha != expected_sha:
                    zip_path.unlink(missing_ok=True)
                    raise ZipSyncError(f"SHA256 mismatch for {filename}")
                received.append(ReceivedPackage(zip_path, expected_sha, subject, sender))
                client.store(message_id, "+FLAGS", "\\Seen")

    return received
