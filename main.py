"""
MAGO Emergency Server
긴급 수정 알림 시스템 - FastAPI 서버

실행 방법:
  pip install -r requirements.txt
  cp .env.example .env   # 후 .env 파일 수정
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import store
import push
import shotgrid_client
import scheduler as sched
import cloudflare_kv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


# ── 서버 생애주기 ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MAGO Emergency Server 시작 중...")
    sched.start()
    await _process_pending_queue()
    yield
    sched.stop()
    logger.info("서버 종료됨.")


async def _process_pending_queue():
    """서버 오프라인 중 Cloudflare Worker KV에 쌓인 긴급 요청 처리"""
    items = await cloudflare_kv.fetch_pending_queue()
    if not items:
        return

    logger.warning(f"오프라인 중 미처리 긴급 요청 {len(items)}건 발견!")

    for item in items:
        key = item["key"]
        form = item["data"].get("formData", {})
        queued_at = item["data"].get("timestamp", 0)
        queued_min_ago = int((time.time() * 1000 - queued_at) / 1000 / 60)

        entity_id_str = form.get("selected_ids", "")
        if not entity_id_str:
            await cloudflare_kv.delete_pending_key(key)
            continue

        entity_id = int(entity_id_str.split(",")[0].strip())
        task_info = shotgrid_client.get_task(entity_id)

        if task_info:
            task_name = task_info.get("content", f"Task_{entity_id}")
            linked = task_info.get("entity") or {}
            shot_code = linked.get("name", task_name)
            project_name = (task_info.get("project") or {}).get("name", "Unknown")
            assignee_ids = [a["id"] for a in (task_info.get("task_assignees") or [])]
        else:
            shot_code = f"Task_{entity_id}"
            project_name = "Unknown"
            assignee_ids = []

        emergency = store.create_emergency(
            shot_id=entity_id,
            shot_code=shot_code,
            project_name=project_name,
            assignee_ids=assignee_ids,
        )

        # 작업자에게 지연 전달 알림
        artist_payload = push.PushPayload(
            title="🚨 긴급 수정 요청 (지연 전달)",
            body=f"[{project_name}] {shot_code} - {queued_min_ago}분 전 발생한 긴급 요청입니다!",
            emergency_id=emergency.id,
            shot_code=shot_code,
            project_name=project_name,
            type="emergency",
            tag=f"emergency-{emergency.id}",
        )
        for uid in assignee_ids:
            sub = store.get_subscription(uid)
            if sub:
                push.send_push(sub.endpoint, sub.keys, artist_payload)

        # 실장/PM에게 서버 오프라인 경고
        offline_payload = push.PushPayload(
            title="⚠️ 서버 오프라인 중 긴급 요청 발생",
            body=(
                f"[{project_name}] {shot_code}"
                f" - 서버 꺼짐 ({queued_min_ago}분 전) 중 긴급 요청이 발생했습니다. 지금 전달됩니다."
            ),
            emergency_id=emergency.id,
            shot_code=shot_code,
            project_name=project_name,
            type="unacknowledged",
            tag=f"offline-{emergency.id}",
        )
        for role in ["supervisor", "pm"]:
            for user in shotgrid_client.get_users_by_role(role):
                sub = store.get_subscription(user["id"])
                if sub:
                    push.send_push(sub.endpoint, sub.keys, offline_payload)

        logger.info(f"대기열 처리 완료: {shot_code} (key={key})")
        await cloudflare_kv.delete_pending_key(key)


# ── 앱 초기화 ────────────────────────────────────────────────────

app = FastAPI(title="MAGO Emergency", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 헬스체크 ─────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    return {"status": "ok"}


# ── PWA 서빙 ────────────────────────────────────────────────────

@app.get("/app", response_class=HTMLResponse)
def serve_app():
    html_file = STATIC_DIR / "app.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/sw.js")
def serve_sw():
    """Service Worker는 루트에서 서빙해야 올바른 scope 적용"""
    return FileResponse(str(STATIC_DIR / "sw.js"), media_type="application/javascript")


# ── VAPID 공개키 ─────────────────────────────────────────────────

@app.get("/vapid-public-key")
def get_vapid_key():
    return {"key": push.get_vapid_public_key()}


# ── Web Push 구독 관리 ───────────────────────────────────────────

class SubscribeRequest(BaseModel):
    userId: int
    subscription: dict  # {endpoint, keys: {p256dh, auth}}


@app.post("/subscribe")
def subscribe(req: SubscribeRequest):
    sub_data = req.subscription
    if not sub_data.get("endpoint") or not sub_data.get("keys"):
        raise HTTPException(400, "endpoint and keys required")

    subscription = store.PushSubscription(
        endpoint=sub_data["endpoint"],
        keys=sub_data["keys"],
    )
    store.save_subscription(req.userId, subscription)

    try:
        shotgrid_client.update_user_push_token(req.userId, sub_data["endpoint"])
    except Exception:
        logger.warning(f"ShotGrid push token 업데이트 실패: userId={req.userId}")

    return {"ok": True}


@app.post("/unsubscribe")
def unsubscribe(body: dict):
    user_id = body.get("userId")
    if not user_id:
        raise HTTPException(400, "userId required")
    store.remove_subscription(int(user_id))
    return {"ok": True}


# ── ShotGrid AMI 웹훅 ─────────────────────────────────────────────
# AMI는 multipart/form-data로 전송합니다:
#   selected_ids : 선택된 엔티티 ID (쉼표 구분)
#   user_name    : AMI를 실행한 PM 이름
#   entity_type  : Task 또는 Shot

@app.post("/sg_webhook")
async def sg_webhook(request: Request):
    """ShotGrid Action Menu Item 웹훅"""
    form_data = await request.form()

    selected_ids_str = form_data.get("selected_ids", "")
    pm_name = form_data.get("user_name", "PM")
    entity_type = form_data.get("entity_type", "Task")

    logger.info(
        f"AMI 수신: entity_type={entity_type}, ids={selected_ids_str}, pm={pm_name}"
    )

    if not selected_ids_str:
        return {"status": "error", "message": "선택된 엔티티가 없습니다"}

    entity_id = int(selected_ids_str.split(",")[0].strip())

    if entity_type == "Task":
        task_info = shotgrid_client.get_task(entity_id)
        if not task_info:
            raise HTTPException(404, f"Task {entity_id}를 찾을 수 없습니다")

        task_name = task_info.get("content", f"Task_{entity_id}")
        assignees = task_info.get("task_assignees") or []
        assignee_ids = [a["id"] for a in assignees]
        linked_entity = task_info.get("entity") or {}
        shot_code = linked_entity.get("name", task_name)
        project_name = (task_info.get("project") or {}).get("name", "Unknown Project")

    else:
        # Shot 엔티티
        shot = shotgrid_client.get_shot(entity_id)
        if not shot:
            raise HTTPException(404, f"Shot {entity_id}를 찾을 수 없습니다")

        shot_code = shot.get("code", f"Shot_{entity_id}")
        project_name = (shot.get("project") or {}).get("name", "Unknown Project")

        tasks = shotgrid_client.get_tasks_for_shot(entity_id)
        assignee_ids: list[int] = []
        for task in tasks:
            for a in task.get("task_assignees") or []:
                if a["id"] not in assignee_ids:
                    assignee_ids.append(a["id"])

    logger.info(f"긴급 발동: {shot_code} / 담당자={assignee_ids} / PM={pm_name}")

    emergency = store.create_emergency(
        shot_id=entity_id,
        shot_code=shot_code,
        project_name=project_name,
        assignee_ids=assignee_ids,
    )

    # 작업자 알림
    artist_payload = push.PushPayload(
        title="🚨 긴급 수정 요청",
        body=f"[{project_name}] {shot_code} 긴급 수정 발생! 즉시 확인해주세요.",
        emergency_id=emergency.id,
        shot_code=shot_code,
        project_name=project_name,
        type="emergency",
        tag=f"emergency-{emergency.id}",
    )

    sent_count = 0
    for user_id in assignee_ids:
        sub = store.get_subscription(user_id)
        if sub:
            push.send_push(sub.endpoint, sub.keys, artist_payload)
            sent_count += 1
        else:
            logger.warning(f"작업자 {user_id} 푸시 구독 없음 (앱 미등록)")

    # 실장/PM 알림
    for role, role_label in [("supervisor", "실장"), ("pm", "PM")]:
        role_users = shotgrid_client.get_users_by_role(role)
        role_payload = push.PushPayload(
            title=f"🚨 [{role_label}] 긴급 수정 발생",
            body=f"[{project_name}] {shot_code} - 작업자 {len(assignee_ids)}명에게 알림 발송됨.",
            emergency_id=emergency.id,
            shot_code=shot_code,
            project_name=project_name,
            type="emergency",
            tag=f"emergency-{role}-{emergency.id}",
        )
        for user in role_users:
            sub = store.get_subscription(user["id"])
            if sub:
                push.send_push(sub.endpoint, sub.keys, role_payload)

    store.increment_reminder(emergency.id)

    return {
        "ok": True,
        "emergencyId": emergency.id,
        "shotCode": shot_code,
        "projectName": project_name,
        "assigneeCount": len(assignee_ids),
        "sentCount": sent_count,
    }


# ── 긴급 상황 관리 API ───────────────────────────────────────────

def _record_to_dict(r: store.EmergencyRecord) -> dict:
    return {
        "id": r.id,
        "shotId": r.shot_id,
        "shotCode": r.shot_code,
        "projectName": r.project_name,
        "assigneeIds": r.assignee_ids,
        "createdAt": int(r.created_at * 1000),
        "status": r.status.value,
        "acknowledgedAt": int(r.acknowledged_at * 1000) if r.acknowledged_at else None,
        "respondedAt": int(r.responded_at * 1000) if r.responded_at else None,
        "responseType": r.response_type.value if r.response_type else None,
        "reminderCount": r.reminder_count,
        "lastReminderAt": int(r.last_reminder_at * 1000) if r.last_reminder_at else None,
        "notifiedUnacknowledged": r.notified_unacknowledged,
    }


@app.get("/emergency")
def list_emergencies():
    return {"data": [_record_to_dict(e) for e in store.get_all_emergencies()[:50]]}


@app.get("/emergency/{emergency_id}")
def get_emergency(emergency_id: str):
    record = store.get_emergency(emergency_id)
    if not record:
        raise HTTPException(404, "Emergency not found")
    return {"data": _record_to_dict(record)}


class AcknowledgeRequest(BaseModel):
    userId: Optional[int] = None


@app.post("/emergency/{emergency_id}/acknowledge")
async def acknowledge(emergency_id: str, req: AcknowledgeRequest):
    record = store.acknowledge_emergency(emergency_id)
    if not record:
        raise HTTPException(404, "Emergency not found or already processed")

    acknowledger_name = "작업자"
    if req.userId:
        user = shotgrid_client.get_user_by_id(req.userId)
        if user:
            acknowledger_name = user.get("name", "작업자")

    notify_payload = push.PushPayload(
        title="✅ 긴급 알림 확인됨",
        body=f"[{record.project_name}] {record.shot_code} - {acknowledger_name}님이 확인했습니다.",
        emergency_id=record.id,
        shot_code=record.shot_code,
        project_name=record.project_name,
        type="status_update",
        tag=f"ack-{record.id}",
    )
    for role in ["supervisor", "pm"]:
        for user in shotgrid_client.get_users_by_role(role):
            sub = store.get_subscription(user["id"])
            if sub:
                push.send_push(sub.endpoint, sub.keys, notify_payload)

    return {"ok": True, "data": _record_to_dict(record)}


class RespondRequest(BaseModel):
    userId: Optional[int] = None
    responseType: str


@app.post("/emergency/{emergency_id}/respond")
async def respond(emergency_id: str, req: RespondRequest):
    try:
        response_type = store.ResponseType(req.responseType)
    except ValueError:
        raise HTTPException(400, f"Invalid responseType: {req.responseType}")

    record = store.respond_to_emergency(emergency_id, response_type)
    if not record:
        raise HTTPException(404, "Emergency not found")

    responder_name = "작업자"
    if req.userId:
        user = shotgrid_client.get_user_by_id(req.userId)
        if user:
            responder_name = user.get("name", "작업자")

    label = store.RESPONSE_LABELS[response_type]

    notify_payload = push.PushPayload(
        title="📋 작업자 응답 도착",
        body=f"[{record.project_name}] {record.shot_code} - {responder_name}: {label}",
        emergency_id=record.id,
        shot_code=record.shot_code,
        project_name=record.project_name,
        type="status_update",
        tag=f"respond-{record.id}",
    )
    for role in ["supervisor", "pm"]:
        for user in shotgrid_client.get_users_by_role(role):
            sub = store.get_subscription(user["id"])
            if sub:
                push.send_push(sub.endpoint, sub.keys, notify_payload)

    return {"ok": True, "data": _record_to_dict(record), "label": label}


# ── 관리자 API ───────────────────────────────────────────────────

@app.post("/admin/setup-shotgrid-fields")
def setup_shotgrid_fields():
    """ShotGrid 커스텀 필드 자동 생성 (최초 1회)"""
    try:
        results = shotgrid_client.setup_custom_fields()
        return {"ok": True, "results": results}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/admin/users")
def list_users():
    """ShotGrid 활성 사용자 목록 (역할 설정 확인용)"""
    try:
        sg = shotgrid_client.get_sg()
        users = sg.find(
            "HumanUser",
            [["sg_status_list", "is", "act"]],
            ["id", "name", "email", "login", "sg_role"],
        )
        return {"data": users}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/admin/links", response_class=HTMLResponse)
def generate_links(request: Request):
    """
    전체 직원 개인별 앱 링크 생성 페이지.
    관리자가 각 직원 링크를 복사해 카카오톡으로 전송.
    직원은 링크 접속 후 '알림 활성화' 버튼 한 번만 누르면 완료.
    """
    base_url = os.environ.get("PUBLIC_BASE_URL", str(request.base_url).rstrip("/"))

    try:
        sg = shotgrid_client.get_sg()
        users = sg.find(
            "HumanUser",
            [["sg_status_list", "is", "act"]],
            ["id", "name", "email", "login", "sg_role"],
        )
    except Exception as e:
        raise HTTPException(500, str(e))

    rows = ""
    for u in users:
        uid = u["id"]
        name = u.get("name", "Unknown")
        role = u.get("sg_role") or "미설정"
        link = f"{base_url}/app?userId={uid}&userName={quote(name)}"
        rows += f"""
        <tr>
          <td>{name}</td>
          <td><span class="role">{role}</span></td>
          <td>
            <input readonly value="{link}" onclick="this.select()"
              style="width:100%;background:#1a1a2e;border:1px solid #2a2a4a;
                     color:#e8e8f0;padding:6px 10px;border-radius:6px;font-size:12px;" />
          </td>
          <td>
            <button onclick="navigator.clipboard.writeText('{link}')
                      .then(()=>this.textContent='✅ 복사됨')
                      .catch(()=>this.textContent='❌')"
              style="background:#ff4444;color:#fff;border:none;padding:6px 14px;
                     border-radius:6px;cursor:pointer;font-size:12px;">
              복사
            </button>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>MAGO 직원 링크 관리</title>
  <style>
    body {{ background:#0f0f1a; color:#e8e8f0; font-family:sans-serif; padding:24px; }}
    h1 {{ color:#ff4444; margin-bottom:8px; font-size:20px; }}
    p {{ color:#9999bb; font-size:13px; margin-bottom:20px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th {{ background:#1a1a2e; padding:10px 12px; text-align:left; font-size:13px; color:#9999bb; border-bottom:1px solid #2a2a4a; }}
    td {{ padding:10px 12px; border-bottom:1px solid #2a2a4a; font-size:13px; vertical-align:middle; }}
    tr:hover td {{ background:#1a1a2e; }}
    .role {{ background:#2a2a4a; padding:2px 8px; border-radius:10px; font-size:12px; }}
  </style>
</head>
<body>
  <h1>🔗 직원 개인 링크</h1>
  <p>각 직원에게 아래 링크를 카카오톡으로 보내주세요.<br>
     링크 접속 후 <strong>알림 활성화</strong> 버튼 한 번만 누르면 이후 자동으로 긴급 알림이 수신됩니다.</p>
  <table>
    <thead>
      <tr><th>이름</th><th>역할</th><th>개인 링크</th><th></th></tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
