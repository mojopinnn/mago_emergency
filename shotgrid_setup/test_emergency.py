"""
MAGO Emergency System - 긴급 알림 테스트 스크립트
ShotGrid 없이 서버 기능을 직접 테스트합니다.

실행: python test_emergency.py
필요: pip install requests
"""

import requests
import json
import time

SERVER_URL = "http://localhost:8080"  # 또는 http://YOUR_SERVER_IP:PORT

def test_health():
    print("[테스트 1] 서버 상태 확인...")
    try:
        res = requests.get(f"{SERVER_URL}/api/healthz")
        data = res.json()
        print(f"  ✅ 서버 정상: {data}")
    except Exception as e:
        print(f"  ❌ 서버 연결 실패: {e}")
        return False
    return True


def test_vapid_key():
    print("\n[테스트 2] VAPID 공개키 확인...")
    try:
        res = requests.get(f"{SERVER_URL}/api/vapid-public-key")
        data = res.json()
        key = data.get("key", "")
        if key:
            print(f"  ✅ VAPID 공개키: {key[:40]}...")
        else:
            print("  ⚠️  VAPID 키 없음 - 환경변수 확인 필요")
    except Exception as e:
        print(f"  ❌ 오류: {e}")


def test_simulate_emergency(shot_id: int = 9999, shot_code: str = "TEST_sh0010"):
    """ShotGrid AMI가 보내는 것과 동일한 형식으로 웹훅 테스트"""
    print(f"\n[테스트 3] 긴급 알림 시뮬레이션 (Shot ID: {shot_id})...")

    payload = {
        "entity": {
            "type": "Shot",
            "id": shot_id,
            "name": shot_code
        },
        "project": {
            "id": 1,
            "name": "TEST_PROJECT"
        },
        "user": {
            "type": "HumanUser",
            "id": 1,
            "name": "PM User"
        }
    }

    try:
        res = requests.post(
            f"{SERVER_URL}/api/webhook/shotgrid",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        data = res.json()
        if res.status_code == 200:
            print(f"  ✅ 긴급 알림 생성 성공!")
            print(f"     Emergency ID: {data.get('emergencyId')}")
            print(f"     샷 코드: {data.get('shotCode')}")
            print(f"     작업자 수: {data.get('assigneeCount', 0)}")
            return data.get("emergencyId")
        else:
            print(f"  ⚠️  응답 코드 {res.status_code}: {data}")
    except Exception as e:
        print(f"  ❌ 오류: {e}")
    return None


def test_emergency_list():
    print("\n[테스트 4] 긴급 알림 목록 확인...")
    try:
        res = requests.get(f"{SERVER_URL}/api/emergency")
        data = res.json()
        emergencies = data.get("data", [])
        print(f"  ✅ 총 {len(emergencies)}건")
        for e in emergencies[:3]:
            print(f"     [{e['status']}] {e['shotCode']} - {e['id'][:20]}...")
        return emergencies
    except Exception as e:
        print(f"  ❌ 오류: {e}")
    return []


def test_acknowledge(emergency_id: str, user_id: int = 1):
    print(f"\n[테스트 5] 긴급 알림 확인 처리...")
    try:
        res = requests.post(
            f"{SERVER_URL}/api/emergency/{emergency_id}/acknowledge",
            json={"userId": user_id},
            headers={"Content-Type": "application/json"}
        )
        data = res.json()
        if res.ok:
            print(f"  ✅ 확인 처리 완료: 상태 = {data['data']['status']}")
        else:
            print(f"  ❌ 실패: {data}")
    except Exception as e:
        print(f"  ❌ 오류: {e}")


def test_respond(emergency_id: str, response_type: str = "remote_within_10", user_id: int = 1):
    print(f"\n[테스트 6] 작업자 응답 처리 ({response_type})...")
    try:
        res = requests.post(
            f"{SERVER_URL}/api/emergency/{emergency_id}/respond",
            json={"userId": user_id, "responseType": response_type},
            headers={"Content-Type": "application/json"}
        )
        data = res.json()
        if res.ok:
            print(f"  ✅ 응답 처리 완료: {data.get('label')}")
        else:
            print(f"  ❌ 실패: {data}")
    except Exception as e:
        print(f"  ❌ 오류: {e}")


if __name__ == "__main__":
    print("=" * 55)
    print("  MAGO Emergency System - 기능 테스트")
    print("=" * 55)

    if not test_health():
        print("\n서버를 먼저 시작해주세요.")
        exit(1)

    test_vapid_key()
    emergency_id = test_simulate_emergency()
    test_emergency_list()

    if emergency_id:
        time.sleep(1)
        test_acknowledge(emergency_id)
        time.sleep(1)
        test_respond(emergency_id, "remote_within_10")

    print("\n" + "=" * 55)
    print("  테스트 완료!")
    print("=" * 55)
