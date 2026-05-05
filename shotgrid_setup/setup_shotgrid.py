"""
MAGO Emergency System - ShotGrid 초기 설정 스크립트
실행: python setup_shotgrid.py

필요한 패키지: pip install shotgun-api3
"""

import shotgun_api3

SERVER_PATH = "https://studiomago.shotgrid.autodesk.com"
SCRIPT_NAME = "comp_script"
SCRIPT_KEY  = "lslmtiosesnlsv1e(kbojetjH"

# 본인 서버의 외부 접근 가능한 URL로 변경하세요
# 예: ngrok 사용시 "https://xxxx.ngrok.io" 또는 실제 서버 IP
SERVER_WEBHOOK_URL = "http://YOUR_SERVER_IP:포트/api/webhook/shotgrid"

sg = shotgun_api3.Shotgun(SERVER_PATH, script_name=SCRIPT_NAME, api_key=SCRIPT_KEY)


def step1_add_custom_fields():
    """HumanUser 엔티티에 커스텀 필드 추가"""
    print("\n[1단계] HumanUser 커스텀 필드 확인/추가...")

    schema = sg.schema_field_read("HumanUser")

    if "sg_role" not in schema:
        sg.schema_field_create(
            "HumanUser",
            "text",
            "Role",
            {"name": {"value": "sg_role"}}
        )
        print("  ✅ sg_role 필드 생성됨")
    else:
        print("  ℹ️  sg_role 필드 이미 존재함")

    if "sg_push_token" not in schema:
        sg.schema_field_create(
            "HumanUser",
            "text",
            "Push Token",
            {"name": {"value": "sg_push_token"}}
        )
        print("  ✅ sg_push_token 필드 생성됨")
    else:
        print("  ℹ️  sg_push_token 필드 이미 존재함")

    if "sg_emergency" not in schema:
        sg.schema_field_create(
            "Shot",
            "checkbox",
            "Emergency",
            {"name": {"value": "sg_emergency"}}
        )
        print("  ✅ Shot.sg_emergency 체크박스 필드 생성됨")
    else:
        print("  ℹ️  Shot.sg_emergency 필드 이미 존재함")

    print("  [완료] 커스텀 필드 설정 완료")


def step2_list_users():
    """현재 사용자 목록 출력 (역할 설정 참고용)"""
    print("\n[2단계] 현재 사용자 목록 (역할을 sg_role에 설정해주세요)...")

    users = sg.find(
        "HumanUser",
        [["sg_status_list", "is", "act"]],
        ["name", "email", "sg_role", "login", "id"]
    )

    print(f"\n  {'ID':<8} {'이름':<20} {'로그인':<20} {'현재 역할':<15}")
    print("  " + "-" * 65)
    for u in users:
        role = u.get("sg_role") or "(미설정)"
        print(f"  {u['id']:<8} {u['name']:<20} {u.get('login',''):<20} {role:<15}")

    print(f"\n  총 {len(users)}명")
    print("\n  역할 설정 방법:")
    print("  - ShotGrid 웹에서 각 사용자의 sg_role 필드에 값 입력")
    print("  - 값 옵션: 'artist' / 'supervisor' / 'pm'")

    return users


def step3_set_user_roles_example(users):
    """사용자 역할 설정 예시 (직접 수정 필요)"""
    print("\n[3단계] 역할 설정 예시 (아래 코드를 참고해서 직접 수정하세요):")
    print("""
  # 예시: 특정 사용자 역할 설정
  # sg.update("HumanUser", USER_ID, {"sg_role": "supervisor"})
  # sg.update("HumanUser", USER_ID, {"sg_role": "pm"})
  # sg.update("HumanUser", USER_ID, {"sg_role": "artist"})
  """)


def step4_register_ami():
    """Action Menu Item 등록 - ShotGrid 관리자 패널에서 수행"""
    print("\n[4단계] Action Menu Item(AMI) 설정 방법:")
    print("""
  ShotGrid 웹사이트에서 수동으로 등록해야 합니다:

  1. ShotGrid 관리자 계정으로 로그인
  2. 우측 상단 아이콘 → Admin → Action Menu Items
  3. [+ New Action Menu Item] 클릭
  4. 아래 값으로 설정:

     Title:        mago_emergency
     Entity Type:  Shot
     URL:          {url}
     HTTP Method:  POST
     Selection:    Single entity or Multiple entities

  5. 저장 후 테스트:
     - ShotGrid에서 샷(Shot) 선택 → 우클릭 → mago_emergency 클릭
     - 서버 로그에 요청이 들어오는지 확인
  """.format(url=SERVER_WEBHOOK_URL))


def step5_test_connection():
    """ShotGrid API 연결 테스트"""
    print("\n[5단계] ShotGrid API 연결 테스트...")
    try:
        info = sg.info()
        print(f"  ✅ 연결 성공! ShotGrid 버전: {info.get('version', 'N/A')}")
    except Exception as e:
        print(f"  ❌ 연결 실패: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("  MAGO Emergency System - ShotGrid 초기 설정")
    print("=" * 60)

    step5_test_connection()
    step1_add_custom_fields()
    users = step2_list_users()
    step3_set_user_roles_example(users)
    step4_register_ami()

    print("\n" + "=" * 60)
    print("  설정 완료! 다음 단계:")
    print("  1. 사용자 sg_role 설정 (supervisor / pm / artist)")
    print("  2. AMI를 ShotGrid 관리자 패널에서 등록")
    print("  3. 각 작업자 폰에서 웹앱 접속 후 사용자 ID 등록")
    print(f"  웹앱 URL: https://YOUR_SERVER/api/app")
    print("=" * 60)
