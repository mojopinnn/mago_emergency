"""
auto_git_puller.py
위치: E:\my_venv\auto_git_puller.py

E:\my_venv\ 하위 폴더 중 git 저장소(.git 폴더가 있는 것)를 자동 감지하여
주기적으로 git pull을 실행합니다.
새 툴 폴더를 추가해도 이 파일을 수정할 필요 없이 자동으로 인식됩니다.
"""

import subprocess
import time
import os
import logging
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent  # E:\my_venv\
INTERVAL = 30  # 초

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "git_puller.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def find_git_repos(base: Path) -> list[Path]:
    """base 하위 디렉토리 중 .git 폴더가 있는 것을 반환"""
    repos = []
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and (entry / ".git").exists():
            repos.append(entry)
    return repos


def pull_repo(repo: Path) -> None:
    """git pull 실행 후 결과 로깅"""
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip() or result.stderr.strip()
        if result.returncode == 0:
            log.info(f"[{repo.name}] {output}")
        else:
            log.warning(f"[{repo.name}] 오류: {output}")
    except subprocess.TimeoutExpired:
        log.error(f"[{repo.name}] git pull 타임아웃")
    except Exception as e:
        log.error(f"[{repo.name}] 예외 발생: {e}")


def main():
    log.info(f"Auto Git Puller 시작 — 감시 폴더: {BASE_DIR}, 주기: {INTERVAL}초")
    while True:
        repos = find_git_repos(BASE_DIR)
        if repos:
            log.info(f"감지된 저장소 {len(repos)}개: {[r.name for r in repos]}")
            for repo in repos:
                pull_repo(repo)
        else:
            log.warning("git 저장소를 찾을 수 없습니다.")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
