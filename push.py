"""
Web Push 알림 발송 모듈
pywebpush 라이브러리를 사용합니다.
"""
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)


@dataclass
class PushPayload:
    title: str
    body: str
    emergency_id: str
    shot_code: str
    project_name: str
    type: str  # "emergency" | "reminder" | "status_update" | "unacknowledged"
    tag: Optional[str] = None
    note: Optional[str] = None
    version_label: Optional[str] = None


def send_push(
    endpoint: str,
    keys: dict,
    payload: PushPayload,
) -> bool:
    """
    Web Push 알림을 단일 구독자에게 발송합니다.
    keys: {"p256dh": "...", "auth": "..."}
    """
    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_email = os.environ.get("VAPID_EMAIL", "mailto:admin@example.com")

    if not vapid_private:
        logger.error("VAPID_PRIVATE_KEY not configured")
        return False

    data = {
        "title": payload.title,
        "body": payload.body,
        "emergencyId": payload.emergency_id,
        "shotCode": payload.shot_code,
        "projectName": payload.project_name,
        "type": payload.type,
        "tag": payload.tag or f"emergency-{payload.emergency_id}",
    }
    if payload.note:
        data["note"] = payload.note
    if payload.version_label:
        data["versionLabel"] = payload.version_label

    try:
        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": keys,
            },
            data=json.dumps(data),
            vapid_private_key=vapid_private,
            vapid_claims={"sub": vapid_email},
            ttl=300,
            headers={"urgency": "high"},
        )
        logger.info(f"Push sent → {endpoint[:50]}...")
        return True

    except WebPushException as e:
        status = e.response.status_code if e.response else None
        if status in (404, 410):
            logger.warning(f"Push subscription expired (status={status}): {endpoint[:50]}")
        else:
            logger.error(f"Push failed (status={status}): {e}")
        return False

    except Exception as e:
        logger.error(f"Push unexpected error: {e}")
        return False


def get_vapid_public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "")
