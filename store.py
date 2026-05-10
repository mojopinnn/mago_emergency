"""
긴급 상황 및 푸시 구독 저장소
구독 정보는 subscriptions.json 파일에 영구 저장 (서버 재시작 후에도 유지)
"""
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

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
    project_id: Optional[int]
    assignee_ids: list[int]
    created_at: float
    status: EmergencyStatus = EmergencyStatus.PENDING
    acknowledged_at: Optional[float] = None
    responded_at: Optional[float] = None
    response_type: Optional[ResponseType] = None
    reminder_count: int = 0
    last_reminder_at: Optional[float] = None
    notified_unacknowledged: bool = False
    context_note: Optional[str] = None
    version_id: Optional[int] = None
    version_label: Optional[str] = None
    ami_entity_type: Optional[str] = None
    ami_initiator_user_id: Optional[int] = None
    ami_initiator_name: Optional[str] = None
    # 응답 완료 시 작업자 표시(ShotGrid 에서 응답 시점에 스냅샷)
    responded_by_user_id: Optional[int] = None
    responded_by_name: Optional[str] = None
    responded_by_part: Optional[str] = None


@dataclass
class PushSubscription:
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}


_emergencies: dict[str, EmergencyRecord] = {}
_subscriptions: dict[int, PushSubscription] = {}

_SUBS_FILE = Path(os.environ.get("SUBS_FILE", Path(__file__).parent / "subscriptions.json"))


def _load_subscriptions_from_file() -> None:
    if not _SUBS_FILE.exists():
        return
    try:
        raw = json.loads(_SUBS_FILE.read_text(encoding="utf-8"))
        for uid_str, sub in raw.items():
            _subscriptions[int(uid_str)] = PushSubscription(
                endpoint=sub["endpoint"],
                keys=sub["keys"],
            )
        logger.info("구독 %s건 파일에서 복원: %s", len(_subscriptions), _SUBS_FILE)
    except Exception as e:
        logger.error("구독 파일 로드 실패 (무시하고 계속): %s", e)


def _save_subscriptions_to_file() -> None:
    try:
        data = {
            str(uid): {"endpoint": sub.endpoint, "keys": sub.keys}
            for uid, sub in _subscriptions.items()
        }
        _SUBS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("구독 파일 저장 실패: %s", e)


_load_subscriptions_from_file()


def create_emergency(
    shot_id: int,
    shot_code: str,
    project_name: str,
    assignee_ids: list[int],
    project_id: Optional[int] = None,
    *,
    context_note: Optional[str] = None,
    version_id: Optional[int] = None,
    version_label: Optional[str] = None,
    ami_entity_type: Optional[str] = None,
    ami_initiator_user_id: Optional[int] = None,
    ami_initiator_name: Optional[str] = None,
) -> EmergencyRecord:
    record = EmergencyRecord(
        id=f"emg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        shot_id=shot_id,
        shot_code=shot_code,
        project_name=project_name,
        project_id=project_id,
        assignee_ids=assignee_ids,
        created_at=time.time(),
        context_note=context_note,
        version_id=version_id,
        version_label=version_label,
        ami_entity_type=ami_entity_type,
        ami_initiator_user_id=ami_initiator_user_id,
        ami_initiator_name=ami_initiator_name,
    )
    _emergencies[record.id] = record
    logger.info("Emergency created: %s / %s", record.id, shot_code)
    return record


def get_emergency(emergency_id: str) -> Optional[EmergencyRecord]:
    return _emergencies.get(emergency_id)


def get_all_emergencies() -> list[EmergencyRecord]:
    return sorted(_emergencies.values(), key=lambda e: e.created_at, reverse=True)


def get_active_emergencies() -> list[EmergencyRecord]:
    return [
        e
        for e in _emergencies.values()
        if e.status in (EmergencyStatus.PENDING, EmergencyStatus.ACKNOWLEDGED)
    ]


def acknowledge_emergency(emergency_id: str) -> Optional[EmergencyRecord]:
    record = _emergencies.get(emergency_id)
    if not record or record.status != EmergencyStatus.PENDING:
        return record
    record.acknowledged_at = time.time()
    record.status = EmergencyStatus.ACKNOWLEDGED
    logger.info("Emergency acknowledged: %s", emergency_id)
    return record


def respond_to_emergency(
    emergency_id: str,
    response_type: ResponseType,
    *,
    responded_by_user_id: Optional[int] = None,
    responded_by_name: Optional[str] = None,
    responded_by_part: Optional[str] = None,
) -> Optional[EmergencyRecord]:
    record = _emergencies.get(emergency_id)
    if not record:
        return None
    record.responded_at = time.time()
    record.response_type = response_type
    record.status = EmergencyStatus.RESPONDED
    record.responded_by_user_id = responded_by_user_id
    record.responded_by_name = responded_by_name
    record.responded_by_part = responded_by_part
    logger.info("Emergency responded: %s / %s", emergency_id, response_type)
    return record


def mark_unacknowledged(emergency_id: str) -> Optional[EmergencyRecord]:
    record = _emergencies.get(emergency_id)
    if not record:
        return None
    record.status = EmergencyStatus.UNACKNOWLEDGED
    record.notified_unacknowledged = True
    logger.warning("Emergency unacknowledged: %s", emergency_id)
    return record


def increment_reminder(emergency_id: str) -> Optional[EmergencyRecord]:
    record = _emergencies.get(emergency_id)
    if not record:
        return None
    record.reminder_count += 1
    record.last_reminder_at = time.time()
    return record


def needs_reminder(record: EmergencyRecord) -> bool:
    if record.status != EmergencyStatus.PENDING:
        return False
    TWO_MINUTES = 2 * 60
    last = record.last_reminder_at or record.created_at
    return (time.time() - last) >= TWO_MINUTES


def needs_unacknowledged_alert(record: EmergencyRecord) -> bool:
    if record.status != EmergencyStatus.PENDING:
        return False
    if record.notified_unacknowledged:
        return False
    FIVE_MINUTES = 5 * 60
    return (time.time() - record.created_at) >= FIVE_MINUTES


def save_subscription(user_id: int, subscription: PushSubscription) -> None:
    _subscriptions[user_id] = subscription
    _save_subscriptions_to_file()
    logger.info("Subscription saved: userId=%s", user_id)


def get_subscription(user_id: int) -> Optional[PushSubscription]:
    return _subscriptions.get(user_id)


def remove_subscription(user_id: int) -> None:
    _subscriptions.pop(user_id, None)
    _save_subscriptions_to_file()
    logger.info("Subscription removed: userId=%s", user_id)


def reset_for_testing() -> None:
    _emergencies.clear()
