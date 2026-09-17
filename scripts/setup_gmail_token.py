"""
[최초 1회만 로컬에서 실행] Gmail API 리프레시 토큰 발급 스크립트

이 스크립트는 사람이 브라우저로 한 번 로그인해서 "리프레시 토큰"을 받기 위한 용도입니다.
발급받은 리프레시 토큰은 만료되지 않으므로(직접 취소하지 않는 한),
이후 GitHub Actions 크론에서는 이 토큰만으로 계속 자동 접근합니다.

사전 준비:
  1. https://console.cloud.google.com 에서 프로젝트 생성
  2. "Gmail API" 사용 설정
  3. OAuth 동의화면 구성 (범위: gmail.readonly)
  4. OAuth 클라이언트 ID 생성 (유형: 데스크톱 앱) -> client_secret.json 다운로드

실행:
  pip install google-auth-oauthlib google-api-python-client
  python3 setup_gmail_token.py

실행하면 브라우저가 열리고 로그인 후, 터미널에 refresh_token이 출력됩니다.
이 값을 GitHub Secrets에 GMAIL_REFRESH_TOKEN 이름으로 등록하세요.
(client_id/client_secret도 각각 GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET 로 등록)
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CLIENT_SECRET_FILE = "client_secret.json"  # 구글 클라우드 콘솔에서 받은 파일


def main():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n===== GitHub Secrets에 등록할 값 =====")
    print(f"GMAIL_CLIENT_ID     = {creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET = {creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN = {creds.refresh_token}")
    print("=======================================\n")


if __name__ == "__main__":
    main()
