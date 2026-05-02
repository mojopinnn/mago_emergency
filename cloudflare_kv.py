"""
Cloudflare KV 클라이언트
워커가 오프라인 중 저장한 대기열 긴급 요청을 서버 시작 시 가져옵니다.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def get_worker_url() -> Optional[str]:
    return os.environ.get("CF_WORKER_URL") or None


async def fetch_pending_queue() -> list[dict]:
    """
    Cloudflare Worker KV에서 오프라인 중 쌓인 대기열 조회.
    서버 시작 시 호출됩니다. CF_WORKER_URL 미설정 시 빈 리스트 반환.
    """
    worker_url = get_worker_url()
    if not worker_url:
        return []

    relay_secret = os.environ.get("RELAY_SECRET", "")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{worker_url}/worker/pending",
                headers={"X-Relay-Secret": relay_secret},
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                logger.info(f"KV 대기열 조회 완료: {len(items)}건")
                return items
            else:
                logger.warning(f"KV 대기열 조회 실패: HTTP {resp.status_code}")
                return []
    except Exception as e:
        logger.warning(f"Cloudflare Worker 연결 실패: {e}")
        return []


async def delete_pending_key(key: str) -> None:
    """처리 완료된 대기열 항목 삭제"""
    worker_url = get_worker_url()
    if not worker_url:
        return

    relay_secret = os.environ.get("RELAY_SECRET", "")

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.delete(
                f"{worker_url}/worker/pending/{key}",
                headers={"X-Relay-Secret": relay_secret},
            )
            logger.info(f"KV 키 삭제 완료: {key}")
    except Exception as e:
        logger.warning(f"KV 키 삭제 실패 ({key}): {e}")
