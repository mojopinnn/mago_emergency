"""
ShotGrid API 클라이언트
shotgun-api3 라이브러리를 사용합니다.
"""
import logging
import os
from typing import Optional

import shotgun_api3

logger = logging.getLogger(__name__)

_sg: Optional[shotgun_api3.Shotgun] = None


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


def get_task(task_id: int) -> Optional[dict]:
    """태스크 정보 조회 (담당자, 연결된 샷/에셋, 프로젝트 포함)"""
    try:
        sg = get_sg()
        task = sg.find_one(
            "Task",
            [["id", "is", task_id]],
            ["content", "task_assignees", "entity", "project"],
        )
        return task
    except Exception as e:
        logger.error(f"get_task({task_id}) failed: {e}")
        return None


def get_shot(shot_id: int) -> Optional[dict]:
    """샷 정보 조회"""
    try:
        sg = get_sg()
        shot = sg.find_one(
            "Shot",
            [["id", "is", shot_id]],
            ["code", "project", "sg_status_list"],
        )
        return shot
    except Exception as e:
        logger.error(f"get_shot({shot_id}) failed: {e}")
        return None


def get_tasks_for_shot(shot_id: int) -> list[dict]:
    """샷에 연결된 태스크 및 담당자 조회"""
    try:
        sg = get_sg()
        tasks = sg.find(
            "Task",
            [["entity", "is", {"type": "Shot", "id": shot_id}]],
            ["content", "task_assignees", "entity"],
        )
        return tasks or []
    except Exception as e:
        logger.error(f"get_tasks_for_shot({shot_id}) failed: {e}")
        return []


def get_users_by_role(role: str) -> list[dict]:
    """sg_role로 사용자 조회 (supervisor / pm / artist)"""
    try:
        sg = get_sg()
        users = sg.find(
            "HumanUser",
            [
                ["sg_status_list", "is", "act"],
                ["sg_role", "is", role],
            ],
            ["id", "name", "email", "login", "sg_role", "sg_push_token"],
        )
        return users or []
    except Exception as e:
        logger.error(f"get_users_by_role({role}) failed: {e}")
        return []


def get_user_by_id(user_id: int) -> Optional[dict]:
    """사용자 ID로 조회"""
    try:
        sg = get_sg()
        return sg.find_one(
            "HumanUser",
            [["id", "is", user_id]],
            ["id", "name", "email", "login", "sg_role", "sg_push_token"],
        )
    except Exception as e:
        logger.error(f"get_user_by_id({user_id}) failed: {e}")
        return None


def update_user_push_token(user_id: int, token: str) -> bool:
    """사용자의 sg_push_token 업데이트"""
    try:
        sg = get_sg()
        sg.update("HumanUser", user_id, {"sg_push_token": token})
        logger.info(f"Push token updated: userId={user_id}")
        return True
    except Exception as e:
        logger.error(f"update_user_push_token({user_id}) failed: {e}")
        return False


def setup_custom_fields() -> dict:
    """
    시스템에 필요한 ShotGrid 커스텀 필드를 생성합니다.
    최초 1회 실행 필요: POST /admin/setup-shotgrid-fields
    """
    sg = get_sg()
    results = {}

    fields_to_create = [
        ("HumanUser", "sg_role", "text", "MAGO Role"),
        ("HumanUser", "sg_push_token", "text", "MAGO Push Token"),
        ("Shot", "sg_emergency", "checkbox", "Emergency"),
    ]

    for entity_type, field_name, field_type, display_name in fields_to_create:
        try:
            schema = sg.schema_field_read(entity_type)
            if field_name in schema:
                results[field_name] = "already_exists"
                logger.info(f"Field {entity_type}.{field_name} already exists")
            else:
                sg.schema_field_create(entity_type, field_type, display_name)
                results[field_name] = "created"
                logger.info(f"Field {entity_type}.{field_name} created")
        except Exception as e:
            results[field_name] = f"error: {e}"
            logger.error(f"Failed to create field {field_name}: {e}")

    return results
