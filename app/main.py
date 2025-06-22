from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
import asyncio
import logging
from datetime import datetime
from typing import Dict, List

from .scheduler import TradingScheduler
from .kis_api.client import KISClient
from .config import settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)

app = FastAPI(
    title="KIS Auto Trading System",
    description="한국투자증권 API를 활용한 자동매매 시스템",
    version="1.0.0"
)

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Jinja2 필터 추가 (통화 형식)
def format_currency_filter(value):
    try:
        # 값을 숫자로 변환 시도 (문자열일 경우 대비)
        numeric_value = float(value)
        # 소수점 이하가 없는 정수형 금액은 int로, 있는 경우 float으로 처리
        if numeric_value == int(numeric_value):
            return f"{int(numeric_value):,}"
        else:
            return f"{numeric_value:,.2f}" # 소수점 2자리까지 표시 (필요에 따라 조절)
    except (ValueError, TypeError):
        return str(value) # 변환 실패 시 문자열로 반환

templates.env.filters['format_currency'] = format_currency_filter


# 전역 변수
trading_scheduler = None
kis_client = KISClient()


@app.on_event("startup")
async def startup_event():
    """앱 시작시 실행"""
    global trading_scheduler
    trading_scheduler = TradingScheduler()

    # 개발 모드에서는 스케줄러 자동 시작 안함
    if not settings.KIS_IS_MOCK:
        trading_scheduler.start()
        logging.info("자동매매 시스템 시작됨")


@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료시 실행"""
    if trading_scheduler:
        trading_scheduler.stop()
        logging.info("자동매매 시스템 종료됨")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """메인 대시보드"""
    try:
        # 계좌 정보 조회
        balance_info, holdings = await kis_client.get_balance()

        # --- 디버깅을 위해 이 로그를 꼭 활용하세요! ---
        # 이 로그를 통해 balance_info와 holdings의 실제 내용을 확인하세요.
        logging.info(f"계좌 잔고 조회 결과 (balance_info): {balance_info}")
        logging.info(f"보유 종목 조회 결과 (holdings): {holdings}")
        # --- 디버깅 로그 끝 ---

        # 보유 종목 정보 가공
        portfolio = []
        total_value = 0

        # holdings가 리스트 형태이고 비어있지 않은지 먼저 확인
        # 그리고 실제 보유 종목 정보가 담긴 딕셔너리인지도 확인
        if isinstance(holdings, list) and holdings and \
           'hldg_qty' in holdings[0] and 'pdno' in holdings[0] and 'pchs_avg_pric' in holdings[0]:
            # holdings[0]에 이 키들이 있다는 것은 실제 보유 종목 데이터가 있다는 강력한 힌트
            for holding in holdings:
                # 각 holding 딕셔너리에 필요한 키들이 모두 존재하는지 확인 (더 안전하게)
                if 'hldg_qty' in holding and 'pdno' in holding and 'pchs_avg_pric' in holding:
                    try:
                        quantity = int(holding['hldg_qty'])
                    except ValueError:
                        logging.warning(f"유효하지 않은 보유수량 값: {holding.get('hldg_qty')} for {holding.get('pdno')}. 건너뜁니다.")
                        continue # 이 항목은 건너뛰고 다음으로 넘어감

                    if quantity > 0: # 보유 수량이 0보다 큰 경우만 처리
                        stock_code = holding['pdno']
                        avg_price = float(holding['pchs_avg_pric'])

                        # 현재가 조회
                        try:
                            current_price_data = await kis_client.get_current_price(stock_code)
                            current_price = int(current_price_data.get('stck_prpr', '0')) # '0'이 기본값. 이후 int로 변환
                            stock_name = current_price_data.get('hts_kor_isnm', stock_code)
                        except Exception as price_e:
                            logging.warning(f"현재가 조회 오류 for {stock_code}: {price_e}. 매입평균가 사용.")
                            current_price = avg_price # 현재가 조회 실패 시 매입 평균가 사용
                            stock_name = holding.get('prdt_name', stock_code) # 보유종목 데이터에 이름이 있다면 사용

                        profit_loss = (current_price - avg_price) * quantity
                        profit_rate = (profit_loss / avg_price * 100) if avg_price != 0 else 0 # 0으로 나누기 방지
                        position_value = current_price * quantity
                        total_value += position_value

                        portfolio.append({
                            'code': stock_code,
                            'name': stock_name,
                            'quantity': quantity,
                            'avg_price': avg_price,
                            'current_price': current_price,
                            'profit_loss': profit_loss,
                            'profit_rate': profit_rate,
                            'position_value': position_value
                        })
                    else:
                        logging.info(f"수량 0인 종목: {holding.get('pdno')} 건너뜁니다.")
                else:
                    logging.warning(f"보유 종목 항목에 필수 키(hldg_qty, pdno, pchs_avg_pric)가 누락되었습니다: {holding}")
        else:
            logging.info("보유 종목이 없거나, API 응답 형식이 예상과 다릅니다. holdings: %s", holdings)


        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "balance_info": balance_info, # 여기에는 이제 딕셔너리가 들어올 것으로 예상
            "portfolio": portfolio,
            "total_value": total_value,
            "is_trading_active": trading_scheduler.is_trading_time if trading_scheduler else False
        })

    except Exception as e:
        logging.error(f"대시보드 오류: {e}", exc_info=True)
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e)
        })


async def get_balance(self) -> tuple[Dict, List[Dict]]:  # 반환 타입을 명확히 지정
    """계좌 잔고 조회"""
    url = f"{self.auth.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = await self.auth.get_headers("TTTC8434R")  # 모의투자: VTTC8434R

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
                    # API 응답에서 output1 (잔고 정보)과 output2 (보유 종목)를 명확히 분리하여 반환
                    # output1은 딕셔너리, output2는 리스트(딕셔너리) 형태여야 함
                    balance_data = data.get("output1", {})  # output1이 없을 경우 빈 딕셔너리
                    holdings_data = data.get("output2", [])  # output2가 없을 경우 빈 리스트

                    # KIS API 문서에 따르면 output1은 딕셔너리, output2는 딕셔너리 리스트입니다.
                    # 만약 보유 종목이 없다면 holdings_data는 []가 될 것입니다.
                    # 로깅을 통해 실제 어떤 데이터가 오는지 다시 확인해볼 필요가 있습니다.
                    # print(f"Raw KIS API Response: {data}") # <-- 디버깅용으로 추가 가능

                    return balance_data, holdings_data
                else:
                    raise Exception(f"API 오류: {data['msg1']} ({data['rt_cd']})")
            else:
                raise Exception(f"HTTP 오류: {response.status} - {await response.text()}")


@app.get("/api/current-price/{stock_code}")
async def get_current_price(stock_code: str):
    """현재가 조회 API"""
    try:
        price_data = await kis_client.get_current_price(stock_code)
        return price_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/start")
async def start_trading():
    """자동매매 시작"""
    global trading_scheduler
    try:
        if not trading_scheduler:
            trading_scheduler = TradingScheduler()

        trading_scheduler.start()
        return {"message": "자동매매가 시작되었습니다.", "status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trading/stop")
async def stop_trading():
    """자동매매 중지"""
    global trading_scheduler
    try:
        if trading_scheduler:
            trading_scheduler.stop()
            trading_scheduler = None
        return {"message": "자동매매가 중지되었습니다.", "status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/status")
async def get_trading_status():
    """자동매매 상태 조회"""
    try:
        is_active = trading_scheduler.is_trading_time if trading_scheduler else False
        target_stocks_count = len(trading_scheduler.target_stocks) if trading_scheduler else 0

        return {
            "is_active": is_active,
            "target_stocks_count": target_stocks_count,
            "strategies": {
                name: {
                    "active": strategy.is_active,
                    "positions": len(strategy.positions)
                }
                for name, strategy in (trading_scheduler.strategies.items() if trading_scheduler else {})
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/themes")
async def get_hot_themes():
    """급등 테마 조회"""
    try:
        if trading_scheduler:
            themes = await trading_scheduler.theme_analyzer.get_hot_themes()
            return {"themes": themes, "timestamp": datetime.now().isoformat()}
        else:
            raise HTTPException(status_code=503, detail="Trading scheduler not initialized")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sectors")
async def get_sector_flow():
    """섹터 자금 흐름 조회"""
    try:
        if trading_scheduler:
            sector_data = await trading_scheduler.theme_analyzer.analyze_sector_flow()
            return {"sectors": sector_data, "timestamp": datetime.now().isoformat()}
        else:
            raise HTTPException(status_code=503, detail="Trading scheduler not initialized")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/order/buy")
async def manual_buy_order(stock_code: str, quantity: int, price: int = 0):
    """수동 매수 주문"""
    try:
        result = await kis_client.buy_order(stock_code, quantity, price)
        return {"result": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/order/sell")
async def manual_sell_order(stock_code: str, quantity: int, price: int = 0):
    """수동 매도 주문"""
    try:
        result = await kis_client.sell_order(stock_code, quantity, price)
        return {"result": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analysis/{stock_code}")
async def analyze_stock(stock_code: str):
    """개별 종목 분석"""
    try:
        if not trading_scheduler:
            raise HTTPException(status_code=503, detail="Trading scheduler not initialized")

        # 차트 데이터 조회
        chart_data = await kis_client.get_daily_chart(stock_code, count=50)
        if not chart_data:
            raise HTTPException(status_code=404, detail="Chart data not found")

        df = pd.DataFrame(chart_data)

        # 각 전략별 분석 결과
        analysis_results = {}

        for strategy_name, strategy in trading_scheduler.strategies.items():
            if strategy.is_active:
                analysis = await strategy.analyze(stock_code, df)
                signals = await strategy.generate_signals(stock_code, analysis)

                analysis_results[strategy_name] = {
                    "analysis": analysis,
                    "signals": signals
                }

        return {
            "stock_code": stock_code,
            "analysis": analysis_results,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)