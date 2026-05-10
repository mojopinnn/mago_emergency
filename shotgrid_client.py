"""
ShotGrid API 클라이언트
shotgun-api3 라이브러리를 사용합니다.
"""
from __future__ import annotations

import logging
import os
import re
from typing import NamedTuple, Optional

import shotgun_api3

logger = logging.getLogger(__name__)

_sg: Optional[shotgun_api3.Shotgun] = None


class VersionEmergencyContext(NamedTuple):
    shot_id: int
    shot_code: str
    project_name: str
    project_id: Optional[int]
    assignee_ids: list[int]
    note_preview: Optional[str]
    version_label: Optional[str]


def get_sg() -> shotgun_api3.Shotgun:
    global _sg
    if _sg is None:
        _sg = shotgun_api3.Shotgun(
            os.environ["SHOTGRID_URL"],
            script_name=os.environ["SHOTGRID_SCRIPT_NAME"],
            api_key=os.environ["SHOTGRID_API_KEY"],
        )
        logger.info("ShotGrid connection initialized")
    return _sg


def cc_marker_field() -> str:
    return os.environ.get("SHOTGRID_CC_MARKER_FIELD", "sg_emer_cc")


def cc_group_code() -> str:
    return os.environ.get("MAGO_CC_GROUP_CODE", "emer_cc")


def mago_cc_pm_marker_value() -> str:
    return os.environ.get("MAGO_CC_PM_MARKER_VALUE", "pm")


def user_part_field() -> str:
    """
    최근 처리 내역에 표시할 "파트"(comp / fx 등) 출처 — HumanUser 의 필드 코드.
    스튜디오마다 다르므로 ``SHOTGRID_USER_PART_FIELD`` 로 지정(기본 ``sg_discipline``).
    """
    raw = os.environ.get("SHOTGRID_USER_PART_FIELD", "sg_discipline")
    return (raw or "sg_discipline").strip() or "sg_discipline"


def _human_sg_fields() -> list[str]:
    ordered = [
        "id",
        "name",
        "email",
        "login",
        "sg_role",
        "sg_push_token",
        cc_marker_field(),
        user_part_field(),
    ]
    seen: set[str] = set()
    out: list[str] = []
    for f in ordered:
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _strip_simple_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(t.split()).strip()


def get_latest_linked_note_body_for_version(
    version_id: int, project_id: Optional[int]
) -> Optional[str]:
    del project_id  # 예약: 프로젝트 스코프 필터가 필요해지면 사용
    try:
        sg = get_sg()
        notes = sg.find(
            "Note",
            [["note_links", "is", {"type": "Version", "id": version_id}]],
            ["subject", "content", "created_at"],
            order=[{"field": "created_at", "direction": "desc"}],
            limit=1,
        )
        if not notes:
            return None
        row = notes[0]
        raw = str(row.get("content") or row.get("subject") or "").strip()
        if not raw:
            return None
        return _strip_simple_html(raw)
    except Exception as e:
        logger.warning(
            "get_latest_linked_note_body_for_version(%s): %s", version_id, e
        )
        return None


def _version_task_field_list() -> list[str]:
    raw = os.environ.get("SHOTGRID_VERSION_TASK_FIELDS", "sg_task,task")
    return [p.strip() for p in raw.split(",") if p.strip()] or ["sg_task", "task"]


def _version_feedback_fallback_field() -> Optional[str]:
    key = os.environ.get("SHOTGRID_VERSION_FEEDBACK_FALLBACK_FIELD") or os.environ.get(
        "SHOTGRID_VERSION_NOTE_FIELD"
    )
    if not key or not str(key).strip():
        return None
    return str(key).strip()


def resolve_version_emergency_context(
    version_id: int,
) -> Optional[VersionEmergencyContext]:
    try:
        sg = get_sg()

        vf_base = ["code", "project", "entity"]
        vb = list(
            dict.fromkeys(
                _version_task_field_list()
                + ([_version_feedback_fallback_field()] if _version_feedback_fallback_field() else [])
            )
        )

        ver = sg.find_one("Version", [["id", "is", version_id]], vf_base + vb)
        if not ver:
            return None

        proj = ver.get("project") or {}
        pid = (
            int(proj["id"]) if isinstance(proj, dict) and proj.get("id") else None
        )
        pname = (
            proj.get("name", "Unknown Project")
            if isinstance(proj, dict)
            else "Unknown Project"
        )

        vlabel_raw = ver.get("code")

        shot_id = version_id
        shot_code = str(vlabel_raw) if vlabel_raw is not None else f"v{version_id}"
        ent = ver.get("entity") or {}
        if ent.get("type") == "Shot" and ent.get("id"):
            shot_id = int(ent["id"])
            shot_rec = sg.find_one("Shot", [["id", "is", shot_id]], ["code"])
            if shot_rec and shot_rec.get("code"):
                shot_code = str(shot_rec["code"])

        assignee_ids: list[int] = []
        tid: Optional[int] = None
        for fld in _version_task_field_list():
            link = ver.get(fld)
            if isinstance(link, dict) and link.get("id"):
                tid = int(link["id"])
                break
        if tid is not None:
            task = sg.find_one("Task", [["id", "is", tid]], ["task_assignees"])
            if task:
                for a in task.get("task_assignees") or []:
                    if a.get("id"):
                        uid = int(a["id"])
                        if uid not in assignee_ids:
                            assignee_ids.append(uid)

        fb_field = _version_feedback_fallback_field()
        fb_note: Optional[str] = None
        if fb_field and ver.get(fb_field):
            fb_note = _strip_simple_html(str(ver.get(fb_field)))

        note = (
            get_latest_linked_note_body_for_version(version_id, pid) or fb_note
        )

        return VersionEmergencyContext(
            shot_id=shot_id,
            shot_code=shot_code,
            project_name=pname,
            project_id=pid,
            assignee_ids=assignee_ids,
            note_preview=note,
            version_label=vlabel_raw if isinstance(vlabel_raw, str) else (
                str(vlabel_raw) if vlabel_raw is not None else None
            ),
        )
    except Exception as e:
        logger.warning("resolve_version_emergency_context(%s): %s", version_id, e)
        return None


def find_human_user_id_by_login(login: str) -> Optional[int]:
    login_clean = (login or "").strip()
    if not login_clean:
        return None
    try:
        sg = get_sg()
        row = sg.find_one(
            "HumanUser",
            [["sg_status_list", "is", "act"], ["login", "is", login_clean]],
            ["id"],
        )
        if row and row.get("id"):
            return int(row["id"])
    except Exception as e:
        logger.warning("find_human_user_id_by_login(%r): %s", login_clean[:64], e)
    return None


def get_task(task_id: int) -> Optional[dict]:
    try:
        sg = get_sg()
        return sg.find_one(
            "Task",
            [["id", "is", task_id]],
            ["content", "task_assignees", "entity", "project"],
        )
    except Exception as e:
        logger.error("get_task(%s) failed: %s", task_id, e)
        return None


def get_shot(shot_id: int) -> Optional[dict]:
    try:
        sg = get_sg()
        return sg.find_one(
            "Shot",
            [["id", "is", shot_id]],
            ["code", "project", "sg_status_list"],
        )
    except Exception as e:
        logger.error("get_shot(%s) failed: %s", shot_id, e)
        return None


def get_tasks_for_shot(shot_id: int) -> list[dict]:
    try:
        sg = get_sg()
        tasks = sg.find(
            "Task",
            [["entity", "is", {"type": "Shot", "id": shot_id}]],
            ["content", "task_assignees", "entity"],
        )
        return tasks or []
    except Exception as e:
        logger.error("get_tasks_for_shot(%s) failed: %s", shot_id, e)
        return []


def get_users_by_role(role: str) -> list[dict]:
    """
    sg_role 필드 문자열 매칭 (supervisor / pm / artist 등).
    CC(실장/PM 참조 그룹)은 ``iter_cc_users_deduped`` 로 별도 운영.
    """
    try:
        sg = get_sg()
        users = sg.find(
            "HumanUser",
            [
                ["sg_status_list", "is", "act"],
                ["sg_role", "is", role],
            ],
            _human_sg_fields(),
        )
        return users or []
    except Exception as e:
        logger.error("get_users_by_role(%s) failed: %s", role, e)
        return []


def get_cc_group_lead_users() -> list[dict]:
    try:
        sg = get_sg()
        code = cc_group_code()
        g = sg.find_one("Group", [["code", "is", code]], ["users"])
        if not g:
            return []
        users_field = g.get("users") or []
        ids: list[int] = []
        for u in users_field:
            if isinstance(u, dict) and u.get("id"):
                ids.append(int(u["id"]))
        ids = sorted(set(ids))
        if not ids:
            return []
        return sg.find("HumanUser", [["id", "in", ids]], _human_sg_fields()) or []
    except Exception as e:
        logger.warning("get_cc_group_lead_users: %s", e)
        return []


def get_cc_pm_users() -> list[dict]:
    try:
        sg = get_sg()
        mf = cc_marker_field()
        val = mago_cc_pm_marker_value()
        return sg.find(
            "HumanUser",
            [["sg_status_list", "is", "act"], [mf, "is", val]],
            _human_sg_fields(),
        ) or []
    except Exception as e:
        logger.warning("get_cc_pm_users: %s", e)
        return []


def iter_cc_users_deduped() -> list[dict]:
    """
    CC(참조) 수신자 목록.
    현재 운영 정책: ``emer_cc`` 그룹 멤버만 CC로 취급 (PM 자동 포함 없음).
    """
    seen: set[int] = set()
    out: list[dict] = []
    for user in get_cc_group_lead_users():
        uid = user.get("id")
        if uid is None:
            continue
        i = int(uid)
        if i in seen:
            continue
        seen.add(i)
        out.append(user)
    return out


def get_user_by_id(user_id: int) -> Optional[dict]:
    try:
        sg = get_sg()
        return sg.find_one(
            "HumanUser",
            [["id", "is", user_id]],
            _human_sg_fields(),
        )
    except Exception as e:
        logger.error("get_user_by_id(%s) failed: %s", user_id, e)
        return None


def update_user_push_token(user_id: int, token: str) -> bool:
    try:
        sg = get_sg()
        sg.update("HumanUser", user_id, {"sg_push_token": token})
        logger.info("Push token updated: userId=%s", user_id)
        return True
    except Exception as e:
        logger.error("update_user_push_token(%s) failed: %s", user_id, e)
        return False


def setup_custom_fields() -> dict:
    """
    시스템에 필요한 ShotGrid 커스텀 필드를 생성합니다.
    최초 1회 실행 필요: POST /admin/setup-shotgrid-fields
    """
    sg = get_sg()
    results: dict[str, str] = {}

    fields_to_create = [
        ("HumanUser", "sg_role", "text", "MAGO Role"),
        ("HumanUser", "sg_push_token", "text", "MAGO Push Token"),
        ("HumanUser", cc_marker_field(), "text", "MAGO Emergency CC Marker"),
        ("Shot", "sg_emergency", "checkbox", "Emergency"),
    ]

    for entity_type, field_name, field_type, display_name in fields_to_create:
        try:
            schema = sg.schema_field_read(entity_type)
            if field_name in schema:
                results[f"{entity_type}.{field_name}"] = "already_exists"
                logger.info("Field %s.%s already exists", entity_type, field_name)
            else:
                sg.schema_field_create(entity_type, field_type, display_name)
                results[f"{entity_type}.{field_name}"] = "created"
                logger.info("Field %s.%s created", entity_type, field_name)
        except Exception as e:
            results[f"{entity_type}.{field_name}"] = f"error: {e}"
            logger.error("Failed to create field %s.%s: %s", entity_type, field_name, e)

    return results
