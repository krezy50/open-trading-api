import json
from datetime import datetime, timedelta
from typing import Optional
import aiohttp # <--- aiohttp 추가

class KISAuth:
    def __init__(self, app_key: str, app_secret: str, is_mock: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        # base_url 설정: is_mock이 True면 모의투자, False면 실전투자 URL 사용
        self.base_url = "https://openapivts.koreainvestment.com:29443" if is_mock else "https://openapi.koreainvestment.com:9443"
        self.access_token: Optional[str] = None
        self.token_expired: Optional[datetime] = None
        self.is_mock = is_mock # <--- 이 줄을 추가해야 합니다!

    async def get_access_token(self) -> str:
        """액세스 토큰 발급 (비동기)"""
        if self.access_token and self.token_expired and datetime.now() < self.token_expired:
            return self.access_token

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result["access_token"]
                    self.token_expired = datetime.now() + timedelta(hours=23)
                    return self.access_token
                else:
                    raise Exception(f"토큰 발급 실패: {response.status} - {await response.text()}")

    async def get_headers(self, tr_id: str, tr_cont: str = "") -> dict:
        """API 호출용 헤더 생성 (비동기)"""
        adjusted_tr_id = tr_id
        if self.is_mock: # <--- 여기서 self.is_mock을 사용합니다.
            if tr_id.startswith("TTTC"):
                adjusted_tr_id = "V" + tr_id

        token = await self.get_access_token()

        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": adjusted_tr_id,
            "tr_cont": tr_cont,
            "custtype": "P"
        }