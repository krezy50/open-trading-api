import requests # <--- 이제 이 임포트는 필요 없을 수 있습니다. (auth.py와 함께 제거 고려)
import json
import logging # <--- 이 줄을 추가합니다!
import asyncio
import aiohttp
from typing import Dict, List, Optional
from .auth import KISAuth
from ..config import settings


class KISClient:
    def __init__(self):
        self.auth = KISAuth(
            settings.KIS_APP_KEY,
            settings.KIS_APP_SECRET,
            settings.KIS_IS_MOCK
        )
        # KISAuth 클래스에서도 settings.url_base를 사용할 수 있도록
        # auth 객체 초기화 시 필요한 정보가 모두 전달되도록 확인 필요
        # (현재 auth.base_url을 사용하고 있으므로 KISAuth 내부에서 처리될 것으로 보임)

    async def get_current_price(self, stock_code: str) -> Dict:
        """현재가 조회"""
        url = f"{self.auth.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = await self.auth.get_headers("FHKST01010100") # <-- await 추가

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["rt_cd"] == "0":
                        return data["output"]
                    else:
                        raise Exception(f"API 오류: {data['msg1']}")
                else:
                    raise Exception(f"HTTP 오류: {response.status}")

    async def get_daily_chart(self, stock_code: str, period: str = "D", count: int = 100) -> List[Dict]:
        """일봉 차트 조회"""
        url = f"{self.auth.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        headers = await self.auth.get_headers("FHKST03010100") # <-- await 추가

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_DATE_1": "",  # 시작일자 (공백시 최근)
            "FID_INPUT_DATE_2": "",  # 종료일자 (공백시 최근)
            "FID_PERIOD_DIV_CODE": period,  # D:일봉, W:주봉, M:월봉
            "FID_ORG_ADJ_PRC": "0"  # 0:수정주가, 1:원주가
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["rt_cd"] == "0":
                        return data["output2"][:count]
                    else:
                        raise Exception(f"API 오류: {data['msg1']}")
                else:
                    raise Exception(f"HTTP 오류: {response.status}")

    async def buy_order(self, stock_code: str, quantity: int, price: int = 0) -> Dict:
        """매수 주문"""
        url = f"{self.auth.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        headers = await self.auth.get_headers("TTTC0802U")  # <-- await 추가

        data = {
            "CANO": settings.KIS_ACCOUNT_NO,
            "ACNT_PRDT_CD": settings.acnt_prdt_cd,
            "PDNO": stock_code,
            "ORD_DVSN": "01" if price > 0 else "01",  # 01:지정가, 01:시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price) if price > 0 else "0"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    raise Exception(f"매수 주문 실패: {response.status}")

    async def sell_order(self, stock_code: str, quantity: int, price: int = 0) -> Dict:
        """매도 주문"""
        url = f"{self.auth.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        headers = await self.auth.get_headers("TTTC0801U")  # <-- await 추가

        data = {
            "CANO": settings.KIS_ACCOUNT_NO,
            "ACNT_PRDT_CD": settings.acnt_prdt_cd,
            "PDNO": stock_code,
            "ORD_DVSN": "01" if price > 0 else "01",
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price) if price > 0 else "0"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    raise Exception(f"매도 주문 실패: {response.status}")

    async def get_balance(self) -> tuple[Dict, List[Dict]]:
        """계좌 잔고 조회 (API 응답 구조에 맞춰 유연하게 처리)"""
        url = f"{self.auth.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        headers = await self.auth.get_headers("TTTC8434R")  # TR_ID는 모의/실전 설정에 따라 결정

        params = {
            "CANO": settings.KIS_ACCOUNT_NO,
            "ACNT_PRDT_CD": settings.acnt_prdt_cd,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["rt_cd"] == "0":
                        balance_info = {}
                        holdings = []

                        # Case 1: output1에 잔고 정보, output2에 보유 종목이 오는 일반적인 경우
                        if data.get("output1") and isinstance(data["output1"], dict):
                            balance_info = data["output1"]
                            holdings = data.get("output2", [])  # output2는 리스트일 것임

                        # Case 2: output1은 []이고, output2의 첫 번째 요소에 잔고 정보가 오는 경우 (현재 당신의 상황)
                        elif data.get("output2") and isinstance(data["output2"], list) and data["output2"]:
                            # output2의 첫 번째 요소에 'dnca_tot_amt' 같은 잔고 관련 키가 있는지 확인
                            first_item_in_output2 = data["output2"][0]
                            if 'dnca_tot_amt' in first_item_in_output2 and 'tot_evlu_amt' in first_item_in_output2:
                                balance_info = first_item_in_output2
                                # 이 경우 실제 보유 종목은 없으므로 holdings는 빈 리스트로 유지
                                holdings = []  # 또는 data["output2"][1:] 만약 이후 항목에 종목이 있다면
                            else:
                                # output2가 있지만 첫 항목이 잔고 정보가 아니고, 보유 종목일 가능성도 고려 (기존 로직 유지)
                                holdings = data["output2"]

                        # 로그에 API 원본 응답을 남겨서 디버깅에 도움
                        logging.debug(f"KIS API Raw Response: {json.dumps(data, indent=2)}")

                        return balance_info, holdings
                    else:
                        raise Exception(f"API 오류: {data['msg1']} ({data['rt_cd']}) - 상세: {data.get('msg2', 'N/A')}")
                else:
                    raise Exception(f"HTTP 오류: {response.status} - {await response.text()}")