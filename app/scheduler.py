from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import logging
from datetime import datetime, time
from typing import List, Dict

from .kis_api.client import KISClient
from .strategies.squeeze_momentum import SqueezeMomentumStrategy
from .strategies.macd_strategy import MACDStrategy
from .analyzers.theme_analyzer import ThemeAnalyzer
from .config import settings

logger = logging.getLogger(__name__)


class TradingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.kis_client = KISClient()
        self.theme_analyzer = ThemeAnalyzer()

        # 전략 초기화
        self.strategies = {
            'squeeze_momentum': SqueezeMomentumStrategy(),
            'macd': MACDStrategy()
        }

        self.target_stocks = []  # 분석 대상 종목
        self.is_trading_time = False

    def start(self):
        """스케줄러 시작"""
        # 장 시작 전 준비 (08:30)
        self.scheduler.add_job(
            self.prepare_trading_day,
            CronTrigger(hour=8, minute=30, second=0),
            id='prepare_trading'
        )

        # 테마 분석 (09:00)
        self.scheduler.add_job(
            self.analyze_themes,
            CronTrigger(hour=9, minute=0, second=0),
            id='analyze_themes'
        )

        # 매매 실행 (09:05-15:15, 5분마다)
        self.scheduler.add_job(
            self.execute_trading,
            CronTrigger(hour='9-15', minute='*/5', second=0),
            id='execute_trading'
        )

        # 포지션 관리 (매 시간)
        self.scheduler.add_job(
            self.manage_positions,
            CronTrigger(hour='9-15', minute=0, second=0),
            id='manage_positions'
        )

        # 장 마감 후 정리 (15:30)
        self.scheduler.add_job(
            self.end_trading_day,
            CronTrigger(hour=15, minute=30, second=0),
            id='end_trading_day'
        )

        self.scheduler.start()
        logger.info("자동매매 스케줄러 시작됨")

    async def prepare_trading_day(self):
        """장 시작 전 준비"""
        logger.info("=== 장 시작 전 준비 ===")
        try:
            # 계좌 잔고 확인
            balance_info, holdings = await self.kis_client.get_balance()
            logger.info(f"현재 잔고: {balance_info}")

            # 보유 종목 확인
            for holding in holdings:
                if int(holding['hldg_qty']) > 0:
                    logger.info(f"보유 종목: {holding['pdno']} - {holding['hldg_qty']}주")

            self.is_trading_time = True

        except Exception as e:
            logger.error(f"장 시작 전 준비 오류: {e}")

    async def analyze_themes(self):
        """테마 및 섹터 분석"""
        logger.info("=== 테마 분석 시작 ===")
        try:
            # 급등 테마 분석
            hot_themes = await self.theme_analyzer.get_hot_themes()
            logger.info(f"급등 테마: {[theme['name'] for theme in hot_themes[:5]]}")

            # 섹터 자금 흐름 분석
            sector_flow = await self.theme_analyzer.analyze_sector_flow()
            logger.info(f"상승 섹터: {[sector['name'] for sector in sector_flow['hot_sectors']]}")

            # 거래량 급증 종목
            volume_surge_stocks = await self.theme_analyzer.get_volume_surge_stocks()
            logger.info(f"거래량 급증 종목 수: {len(volume_surge_stocks)}")

            # 분석 대상 종목 업데이트
            self.target_stocks = []

            # 테마 종목 추가
            for theme in hot_themes[:3]:  # 상위 3개 테마
                if theme['url']:
                    theme_stocks = await self.theme_analyzer.get_theme_stocks(theme['url'])
                    self.target_stocks.extend(theme_stocks[:5])  # 테마당 5개 종목

            # 거래량 급증 종목 추가
            self.target_stocks.extend(volume_surge_stocks[:10])

            # 중복 제거
            self.target_stocks = list(set(self.target_stocks))
            logger.info(f"총 분석 대상 종목 수: {len(self.target_stocks)}")

        except Exception as e:
            logger.error(f"테마 분석 오류: {e}")

    async def execute_trading(self):
        """매매 실행"""
        if not self.is_trading_time or not self.target_stocks:
            return

        current_time = datetime.now().time()
        if current_time < time(9, 5) or current_time > time(15, 15):
            return

        logger.info("=== 매매 신호 분석 ===")

        try:
            for stock_code in self.target_stocks[:20]:  # 상위 20개 종목만 분석
                await self.analyze_and_trade(stock_code)
                await asyncio.sleep(0.2)  # API 호출 제한 고려

        except Exception as e:
            logger.error(f"매매 실행 오류: {e}")

    async def analyze_and_trade(self, stock_code: str):
        """개별 종목 분석 및 매매"""
        try:
            # 차트 데이터 조회
            chart_data = await self.kis_client.get_daily_chart(stock_code, count=50)
            if not chart_data:
                return

            df = pd.DataFrame(chart_data)

            # 각 전략별 분석
            all_signals = []

            for strategy_name, strategy in self.strategies.items():
                if strategy.is_active:
                    analysis = await strategy.analyze(stock_code, df)
                    signals = await strategy.generate_signals(stock_code, analysis)

                    for signal in signals:
                        signal['strategy'] = strategy_name
                        all_signals.append(signal)

                # 신호 통합 및 실행
                if all_signals:
                    await self.process_signals(all_signals)

        except Exception as e:
            logger.error(f"종목 {stock_code} 분석 오류: {e}")

    async def process_signals(self, signals: List[Dict]):
        """매매 신호 처리"""
        # 신호 강도별 정렬
        signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)

        for signal in signals:
            try:
                stock_code = signal['stock_code']
                action = signal['action']
                price = signal['price']
                confidence = signal.get('confidence', 0)

                # 신뢰도가 낮은 신호는 무시
                if confidence < 30:
                    continue

                # 현재가 확인
                current_price_data = await self.kis_client.get_current_price(stock_code)
                current_price = int(current_price_data['stck_prpr'])

                if action == 'BUY':
                    await self.execute_buy_order(stock_code, current_price, signal)
                elif action == 'SELL':
                    await self.execute_sell_order(stock_code, current_price, signal)

            except Exception as e:
                logger.error(f"신호 처리 오류: {e}")

    async def execute_buy_order(self, stock_code: str, price: int, signal: Dict):
        """매수 주문 실행"""
        try:
            # 포지션 크기 계산 (최대 투자금액의 5%)
            max_investment = settings.MAX_POSITION_SIZE * 0.05
            quantity = int(max_investment / price)

            if quantity < 1:
                return

            # 매수 주문
            result = await self.kis_client.buy_order(stock_code, quantity, price)

            if result.get('rt_cd') == '0':
                logger.info(f"매수 주문 성공: {stock_code} {quantity}주 @ {price}원")
                logger.info(f"매수 사유: {signal['reason']} (신뢰도: {signal.get('confidence', 0)}%)")

                # 전략별 포지션 업데이트
                strategy = self.strategies[signal['strategy']]
                strategy.update_position(stock_code, 'BUY', quantity, price)
            else:
                logger.error(f"매수 주문 실패: {result.get('msg1', 'Unknown error')}")

        except Exception as e:
            logger.error(f"매수 주문 오류: {e}")

    async def execute_sell_order(self, stock_code: str, price: int, signal: Dict):
        """매도 주문 실행"""
        try:
            # 보유 수량 확인
            balance_info, holdings = await self.kis_client.get_balance()

            holding_qty = 0
            for holding in holdings:
                if holding['pdno'] == stock_code:
                    holding_qty = int(holding['hldg_qty'])
                    break

            if holding_qty <= 0:
                return

            # 매도 주문 (보유 수량의 50% 또는 전량)
            sell_qty = holding_qty if signal.get('confidence', 0) > 70 else holding_qty // 2

            if sell_qty < 1:
                return

            result = await self.kis_client.sell_order(stock_code, sell_qty, price)

            if result.get('rt_cd') == '0':
                logger.info(f"매도 주문 성공: {stock_code} {sell_qty}주 @ {price}원")
                logger.info(f"매도 사유: {signal['reason']} (신뢰도: {signal.get('confidence', 0)}%)")

                # 전략별 포지션 업데이트
                strategy = self.strategies[signal['strategy']]
                strategy.update_position(stock_code, 'SELL', sell_qty, price)
            else:
                logger.error(f"매도 주문 실패: {result.get('msg1', 'Unknown error')}")

        except Exception as e:
            logger.error(f"매도 주문 오류: {e}")

    async def manage_positions(self):
        """포지션 관리 (손절/익절)"""
        logger.info("=== 포지션 관리 ===")
        try:
            balance_info, holdings = await self.kis_client.get_balance()

            for holding in holdings:
                if int(holding['hldg_qty']) > 0:
                    await self.check_stop_loss_take_profit(holding)

        except Exception as e:
            logger.error(f"포지션 관리 오류: {e}")

    async def check_stop_loss_take_profit(self, holding: Dict):
        """손절/익절 확인"""
        try:
            stock_code = holding['pdno']
            holding_qty = int(holding['hldg_qty'])
            avg_price = float(holding['pchs_avg_pric'])

            # 현재가 조회
            current_price_data = await self.kis_client.get_current_price(stock_code)
            current_price = int(current_price_data['stck_prpr'])

            # 수익률 계산
            profit_rate = (current_price - avg_price) / avg_price * 100

            # 손절 조건: -5% 이하
            if profit_rate <= -5:
                await self.execute_stop_loss(stock_code, holding_qty, current_price, profit_rate)

            # 익절 조건: +10% 이상
            elif profit_rate >= 10:
                await self.execute_take_profit(stock_code, holding_qty, current_price, profit_rate)

        except Exception as e:
            logger.error(f"손절/익절 확인 오류: {e}")

    async def execute_stop_loss(self, stock_code: str, quantity: int, price: int, profit_rate: float):
        """손절 실행"""
        try:
            result = await self.kis_client.sell_order(stock_code, quantity, price)

            if result.get('rt_cd') == '0':
                logger.info(f"손절 실행: {stock_code} {quantity}주 @ {price}원 (수익률: {profit_rate:.2f}%)")
            else:
                logger.error(f"손절 실패: {result.get('msg1', 'Unknown error')}")

        except Exception as e:
            logger.error(f"손절 실행 오류: {e}")

    async def execute_take_profit(self, stock_code: str, quantity: int, price: int, profit_rate: float):
        """익절 실행 (부분 매도)"""
        try:
            # 50% 부분 매도
            sell_qty = quantity // 2

            if sell_qty < 1:
                return

            result = await self.kis_client.sell_order(stock_code, sell_qty, price)

            if result.get('rt_cd') == '0':
                logger.info(f"익절 실행: {stock_code} {sell_qty}주 @ {price}원 (수익률: {profit_rate:.2f}%)")
            else:
                logger.error(f"익절 실패: {result.get('msg1', 'Unknown error')}")

        except Exception as e:
            logger.error(f"익절 실행 오류: {e}")

    async def end_trading_day(self):
        """장 마감 후 정리"""
        logger.info("=== 장 마감 후 정리 ===")
        try:
            self.is_trading_time = False

            # 최종 잔고 확인
            balance_info, holdings = await self.kis_client.get_balance()

            total_value = 0
            for holding in holdings:
                if int(holding['hldg_qty']) > 0:
                    stock_code = holding['pdno']
                    quantity = int(holding['hldg_qty'])
                    avg_price = float(holding['pchs_avg_pric'])

                    # 현재가 조회
                    current_price_data = await self.kis_client.get_current_price(stock_code)
                    current_price = int(current_price_data['stck_prpr'])

                    profit_rate = (current_price - avg_price) / avg_price * 100
                    position_value = current_price * quantity
                    total_value += position_value

                    logger.info(
                        f"보유 종목: {stock_code} {quantity}주, 수익률: {profit_rate:.2f}%, 평가금액: {position_value:,}원")

            logger.info(f"총 보유 자산 평가액: {total_value:,}원")

        except Exception as e:
            logger.error(f"장 마감 정리 오류: {e}")

    def stop(self):
        """스케줄러 중지"""
        self.scheduler.shutdown()
        logger.info("자동매매 스케줄러 중지됨")