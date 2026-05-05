"""
긴급 상황 및 푸시 구독 인메모리 저장소
"""
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EmergencyStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESPONDED = "responded"
    UNACKNOWLEDGED = "unacknowledged"


class ResponseType(str, Enum):
    REMOTE_WITHIN_10 = "remote_within_10"
    REMOTE_WITHIN_30 = "remote_within_30"
    REMOTE_UNAVAILABLE = "remote_unavailable"


RESPONSE_LABELS = {
    ResponseType.REMOTE_WITHIN_10: "10분 이내 원격 접속 가능",
    ResponseType.REMOTE_WITHIN_30: "30분 이내 원격 접속 가능",
    ResponseType.REMOTE_UNAVAILABLE: "30분 이내 원격 접속 불가",
}


@dataclass
class EmergencyRecord:
    id: str
    shot_id: int
    shot_code: str
    project_name: str
    assignee_ids: list[int]
    created_at: float
    status: EmergencyStatus = EmergencyStatus.PENDING
    acknowledged_at: Optional[float] = None
    responded_at: Optional[float] = None
    response_type: Optional[ResponseType] = None
    reminder_count: int = 0
    last_reminder_at: Optional[float] = None
    notified_unacknowledged: bool = False


@dataclass
class PushSubscription:
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}


# 저장소
_emergencies: dict[str, EmergencyRecord] = {}
_subscriptions: dict[int, PushSubscription] = {}  # userId → subscription


# ── Emergency CRUD ──────────────────────────────────────────────

def create_emergency(
    shot_id: int,
    shot_code: str,
    project_name: str,
    assignee_ids: list[int],
) -> EmergencyRecord:
    record = EmergencyRecord(
        id=f"emg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        shot_id=shot_id,
        shot_code=shot_code,
        project_name=project_name,
        assignee_ids=assignee_ids,
        created_at=time.time(),
    )
    _emergencies[record.id] = record
    logger.info(f"Emergency created: {record.id} / {shot_code}")
    return record


def get_emergency(emergency_id: str) -> Optional[EmergencyRecord]:
    return _emergencies.get(emergency_id)


def get_all_emergencies() -> list[EmergencyRecord]:
    return sorted(_emergencies.values(), key=lambda e: e.created_at, reverse=True)


def get_active_emergencies() -> list[EmergencyRecord]:
    return [
        e for e in _emergencies.values()
        if e.status in (EmergencyStatus.PENDING, EmergencyStatus.ACKNOWLEDGED)
    ]


def acknowledge_emergency(emergency_id: str) -> Optional[EmergencyRecord]:
    record = _emergencies.get(emergency_id)
    if not record or record.status != EmergencyStatus.PENDING:
        return record
    record.acknowledged_at = time.time()
    record.status = EmergencyStatus.ACKNOWLEDGED
    logger.info(f"Emergency acknowledged: {emergency_id}")
    return record


def respond_to_emergency(
    emergency_id: str,
    response_type: ResponseType,
) -> Optional[EmergencyRecord]:
    record = _emergencies.get(emergency_id)
    if not record:
        return None
    record.responded_at = time.time()
    record.response_type = response_type
    record.status = EmergencyStatus.RESPONDED
    logger.info(f"Emergency responded: {emergency_id} / {response_type}")
    return record


def mark_unacknowledged(emergency_id: str) -> Optional[EmergencyRecord]:
    record = _emergencies.get(emergency_id)
    if not record:
        return None
    record.status = EmergencyStatus.UNACKNOWLEDGED
    record.notified_unacknowledged = True
    logger.warning(f"Emergency unacknowledged: {emergency_id}")
    return record


def increment_reminder(emergency_id: str) -> Optional[EmergencyRecord]:
    record = _emergencies.get(emergency_id)
    if not record:
        return None
    record.reminder_count += 1
    record.last_reminder_at = time.time()
    return record


def needs_reminder(record: EmergencyRecord) -> bool:
    """2분마다 리마인더 발송"""
    if record.status != EmergencyStatus.PENDING:
        return False
    TWO_MINUTES = 2 * 60
    last = record.last_reminder_at or record.created_at
    return (time.time() - last) >= TWO_MINUTES


def needs_unacknowledged_alert(record: EmergencyRecord) -> bool:
    """5분 미확인 시 에스컬레이션"""
    if record.status != EmergencyStatus.PENDING:
        return False
    if record.notified_unacknowledged:
        return False
    FIVE_MINUTES = 5 * 60
    return (time.time() - record.created_at) >= FIVE_MINUTES


# ── Push Subscription ────────────────────────────────────────────

def save_subscription(user_id: int, subscription: PushSubscription) -> None:
    _subscriptions[user_id] = subscription
    logger.info(f"Subscription saved: userId={user_id}")


def get_subscription(user_id: int) -> Optional[PushSubscription]:
    return _subscriptions.get(user_id)


def remove_subscription(user_id: int) -> None:
    _subscriptions.pop(user_id, None)
    logger.info(f"Subscription removed: userId={user_id}")
