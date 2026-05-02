"""
백그라운드 스케줄러
- 30초마다 활성 긴급 알림 상태 점검
- 2분마다 미확인 긴급 알림 재전송 (리마인더)
- 5분 미확인 시 실장/PM에게 에스컬레이션
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import store
import push
import shotgrid_client

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def _send_to_user(user_id: int, payload: push.PushPayload) -> bool:
    sub = store.get_subscription(user_id)
    if not sub:
        return False
    return push.send_push(sub.endpoint, sub.keys, payload)


async def _send_to_roles(roles: list[str], payload: push.PushPayload) -> None:
    for role in roles:
        for user in shotgrid_client.get_users_by_role(role):
            sub = store.get_subscription(user["id"])
            if sub:
                push.send_push(sub.endpoint, sub.keys, payload)


async def tick() -> None:
    """30초마다 실행 — 리마인더 및 에스컬레이션 점검"""
    actives = store.get_active_emergencies()
    if not actives:
        return

    for emergency in actives:
        # 5분 미확인 → 실장/PM 에스컬레이션 (1회만)
        if store.needs_unacknowledged_alert(emergency):
            logger.warning(f"[에스컬레이션] 미확인 5분 초과: {emergency.id}")
            store.mark_unacknowledged(emergency.id)

            payload = push.PushPayload(
                title="⚠️ 긴급 알림 미확인",
                body=(
                    f"[{emergency.project_name}] {emergency.shot_code}"
                    " - 작업자가 5분 내 확인하지 않았습니다. 후속 조치 필요!"
                ),
                emergency_id=emergency.id,
                shot_code=emergency.shot_code,
                project_name=emergency.project_name,
                type="unacknowledged",
                tag=f"unack-{emergency.id}",
            )
            await _send_to_roles(["supervisor", "pm"], payload)
            continue

        # 2분마다 리마인더
        if store.needs_reminder(emergency):
            store.increment_reminder(emergency.id)
            count = emergency.reminder_count + 1
            logger.info(f"[리마인더 #{count}] {emergency.id}")

            payload = push.PushPayload(
                title=f"🔔 긴급 알림 재전송 ({count}회)",
                body=(
                    f"[{emergency.project_name}] {emergency.shot_code}"
                    " - 아직 확인하지 않으셨습니다. 즉시 확인해주세요!"
                ),
                emergency_id=emergency.id,
                shot_code=emergency.shot_code,
                project_name=emergency.project_name,
                type="reminder",
                tag=f"reminder-{emergency.id}",
            )
            for user_id in emergency.assignee_ids:
                await _send_to_user(user_id, payload)


def start() -> None:
    scheduler.add_job(tick, "interval", seconds=30, id="emergency_tick")
    scheduler.start()
    logger.info("Emergency scheduler started (30s interval)")


def stop() -> None:
    scheduler.shutdown()
    logger.info("Emergency scheduler stopped")
