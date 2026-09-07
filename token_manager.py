import os
import time
import requests
from dotenv import load_dotenv

# ==========================================
# 환경변수
# ==========================================

load_dotenv()

CLIENT_ID = os.getenv("TOSS_CLIENT_ID")
CLIENT_SECRET = os.getenv("TOSS_CLIENT_SECRET")

BASE_URL = "https://openapi.tossinvest.com"

# ==========================================
# Token Manager
# ==========================================

_access_token = None
_token_expire_time = 0


def get_access_token():

    global _access_token
    global _token_expire_time

    # 기존 Token이 아직 유효한 경우 재사용
    if _access_token is not None:

        if time.time() < _token_expire_time:
            print("♻️ 기존 Access Token 재사용")
            return _access_token

    # ======================================
    # 새로운 Token 발급
    # ======================================

    print("🔑 새로운 Access Token 발급")

    url = f"{BASE_URL}/oauth2/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    response = requests.post(url, data=data)

    if response.status_code != 200:
        print("❌ Access Token 발급 실패")
        print("상태 코드:", response.status_code)
        print(response.text)
        return None

    token_data = response.json()

    access_token = token_data.get("access_token")
    expires_in = token_data.get("expires_in")

    if not access_token:
        print("❌ Access Token이 없습니다.")
        return None

    # ======================================
    # Token 정보 저장
    # ======================================

    _access_token = access_token

    # 만료 직전의 문제를 방지하기 위해
    # 실제 만료시간보다 60초 먼저 갱신
    _token_expire_time = time.time() + expires_in - 60

    print("✅ Access Token 발급 성공")
    print(f"Token 유효시간: {expires_in}초")

    return _access_token

# ==========================================
# 직접 실행했을 때 테스트
# ==========================================

if __name__ == "__main__":

    token1 = get_access_token()

    if token1:
        print("첫 번째 Token 요청 완료")

    print()

    token2 = get_access_token()

    if token2:
        print("두 번째 Token 요청 완료")

    print()

    if token1 == token2:
        print("✅ 동일한 Token을 재사용했습니다.")
    else:
        print("⚠️ 새로운 Token이 발급되었습니다.")